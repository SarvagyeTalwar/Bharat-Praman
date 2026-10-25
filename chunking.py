"""
Ministry of Defence notifications -> chunks -> embeddings -> Neo4j (vector index).

Folder layout (next to this script):
    docs/MOD/*.pdf             the notifications (subfolders are fine)
    docs/MOD/metadata.json     optional: titles, dates and source links

Run:
    python defence_ingest.py                       # load every PDF in docs/MOD
    python defence_ingest.py "your question here"  # search what was loaded

Install once:
    pip install pypdf sentence-transformers neo4j python-dotenv truststore
"""
import os, re, sys, json, hashlib, textwrap
from pathlib import Path

import truststore
truststore.inject_into_ssl()
from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).resolve().parent
DOCS_DIR = HERE / "docs" / "MOD"
META_FILE = DOCS_DIR / "metadata.json"

MAX_CHARS = 1200        # about 300 tokens per chunk
OVERLAP_PARAS = 1       # repeat the last paragraph of a chunk at the start of the next one
BATCH = 50
INDEX = "chunk_embeddings"

load_dotenv(find_dotenv())
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    max_transaction_retry_time=120,
)

# 384-dimension model that handles English and Hindi. Downloads once (about 100 MB).
MODEL = SentenceTransformer("intfloat/multilingual-e5-small")


# ---------- finding the documents ----------
def load_docs():
    meta = json.load(open(META_FILE, encoding="utf-8")) if META_FILE.exists() else {}
    docs = []
    for f in sorted(DOCS_DIR.rglob("*.pdf")):
        m = meta.get(f.name, {})
        date = re.search(r"\d{4}-\d{2}-\d{2}", f.stem)
        docs.append({
            "file": f,
            "title": m.get("title") or re.sub(r"[_-]+", " ", f.stem).strip(),
            "date": m.get("date") or (date.group(0) if date else None),
            "url": m.get("url"),
            "category": f.parent.name,
        })
    return docs


# ---------- reading and chunking ----------
def looks_garbled(text):
    """Old Hindi fonts often extract as symbols. Flag text that is mostly not letters, digits or Devanagari."""
    if not text:
        return False
    ok = sum(1 for ch in text if ch.isalnum() or ch.isspace() or ch in ".,;:()-/&%'\"" or "\u0900" <= ch <= "\u097f")
    return ok / len(text) < 0.85


def read_pages(pdf):
    for i, page in enumerate(PdfReader(str(pdf)).pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            yield i, text


def make_chunks(pdf):
    """Split on paragraphs and numbered clauses, then pack them up to MAX_CHARS."""
    out, buf, buf_page = [], [], None
    for page, text in read_pages(pdf):
        for para in re.split(r"\n\s*\n|\n(?=\d+\.\s)", text):
            para = re.sub(r"\s+", " ", para).strip()
            if not para:
                continue
            pieces = textwrap.wrap(para, MAX_CHARS) if len(para) > MAX_CHARS else [para]
            for piece in pieces:
                if buf and sum(map(len, buf)) + len(piece) > MAX_CHARS:
                    out.append((buf_page, " ".join(buf)))
                    buf, buf_page = buf[-OVERLAP_PARAS:], page
                if not buf:
                    buf_page = page
                buf.append(piece)
    if buf:
        out.append((buf_page, " ".join(buf)))
    return out


# ---------- loading into Neo4j ----------
def setup_schema():
    with driver.session() as s:
        s.run(f"""CREATE VECTOR INDEX {INDEX} IF NOT EXISTS
                  FOR (c:Chunk) ON (c.embedding)
                  OPTIONS {{indexConfig: {{`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}}}""").consume()
        s.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE").consume()


def ingest(doc):
    pdf = doc["file"]
    doc_id = hashlib.sha1(pdf.read_bytes()).hexdigest()[:12]     # same file content = same id

    with driver.session() as s:
        n = s.run("MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c) RETURN count(c) AS n", id=doc_id).single()["n"]
    if n:
        print(f"  already loaded: {pdf.name} ({n} chunks)")
        return

    chunks = make_chunks(pdf)
    if not chunks:
        print(f"  NO TEXT FOUND in {pdf.name} (scanned PDF? it needs OCR), skipped")
        return
    garbled = sum(looks_garbled(t) for _, t in chunks)
    if garbled > len(chunks) / 2:
        print(f"  WARNING {pdf.name}: text looks garbled (old Hindi font?). Skipped. Check it with pypdf by hand.")
        return

    vecs = MODEL.encode([f"passage: {t}" for _, t in chunks],       # the e5 model expects this prefix
                        normalize_embeddings=True, batch_size=32)
    rows = [{"id": f"{doc_id}_{i}", "i": i, "page": pg, "text": t, "vec": v.tolist()}
            for i, ((pg, t), v) in enumerate(zip(chunks, vecs))]

    with driver.session() as s:
        s.run("""MERGE (d:Document {id: $id})
                 SET d.title = $title, d.date = $date, d.url = $url, d.file = $file, d.category = $cat""",
              id=doc_id, title=doc["title"], date=doc["date"], url=doc["url"],
              file=pdf.name, cat=doc["category"]).consume()
        for i in range(0, len(rows), BATCH):
            b = rows[i:i + BATCH]
            s.execute_write(lambda tx, b=b: tx.run("""
                UNWIND $rows AS r
                MATCH (d:Document {id: $doc})
                MERGE (c:Chunk {id: r.id})
                SET c.text = r.text, c.page = r.page, c.idx = r.i
                WITH c, r, d
                CALL db.create.setNodeVectorProperty(c, 'embedding', r.vec)
                MERGE (d)-[:HAS_CHUNK]->(c)
            """, rows=b, doc=doc_id).consume())
        s.run("""MATCH (d:Document {id: $doc})-[:HAS_CHUNK]->(a), (d)-[:HAS_CHUNK]->(b)
                 WHERE b.idx = a.idx + 1
                 MERGE (a)-[:NEXT]->(b)""", doc=doc_id).consume()
    print(f"  loaded: {pdf.name} -> {len(rows)} chunks")


def ingest_all():
    docs = load_docs()
    print(f"{len(docs)} PDFs found in {DOCS_DIR}")
    if not docs:
        print("Put the notification PDFs in that folder and run again.")
        return
    setup_schema()
    for d in docs:
        ingest(d)
    with driver.session() as s:
        try:
            s.run(f"CALL db.awaitIndex('{INDEX}', 300)").consume()     # wait until the vector index is ready
        except Exception:
            pass
        r = s.run("MATCH (d:Document) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c) "
                  "RETURN count(DISTINCT d) AS docs, count(c) AS chunks").single()
    print(f"\nDone. The graph now holds {r['docs']} documents and {r['chunks']} chunks.")


# ---------- searching ----------
def search(question, k=5):
    vec = MODEL.encode([f"query: {question}"], normalize_embeddings=True)[0].tolist()
    with driver.session() as s:
        return s.execute_read(lambda tx: tx.run(f"""
            CALL db.index.vector.queryNodes('{INDEX}', $k, $v) YIELD node, score
            MATCH (d:Document)-[:HAS_CHUNK]->(node)
            OPTIONAL MATCH (prev)-[:NEXT]->(node)
            OPTIONAL MATCH (node)-[:NEXT]->(nxt)
            RETURN d.title AS title, d.date AS date, d.url AS url, d.category AS category,
                   node.page AS page, node.text AS text,
                   prev.text AS before, nxt.text AS after, score
            ORDER BY score DESC
        """, k=k, v=vec).data())


def ask(question):
    hits = search(question)
    if not hits:
        print("No results. Has anything been loaded yet?")
        return
    for h in hits:
        print(f"\n[{h['score']:.3f}] {h['title']} ({h['date'] or 'no date'}), page {h['page']}")
        print("   ", h["text"][:400].replace("\n", " "))
        if h["url"]:
            print("    source:", h["url"])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
    else:
        ingest_all()
    driver.close()