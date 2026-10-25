"""Ministry of Education (MoE) PDF -> chunks -> Gemini embeddings -> Neo4j (vector index).

Usage:
    python moe_ingest.py "C:\\path\\to\\file.pdf"
    python moe_ingest.py   # defaults to the attached MoE 2024-25 PDF

Install once (already available here):
    pymupdf, google-genai, neo4j, python-dotenv
"""
import os, re, sys, json, hashlib, textwrap, time
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
import fitz  # pymupdf

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")

from google import genai

GEMINI_EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072

DEFAULT_PDF = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\moe24-25.pdf")

MAX_CHARS = 1200
OVERLAP_PARAS = 1
BATCH = 50
EMBED_BATCH = 64
INDEX = "moe_chunk_embeddings"
LABEL = "MoEChunk"

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    max_transaction_retry_time=120,
)
gemini = genai.Client(api_key=GEMINI_API_KEY)
MODEL_READY = True


def load_docs(pdf_path):
    p = Path(pdf_path)
    docs = []
    if p.is_dir():
        for f in sorted(p.rglob("*.pdf")):
            docs.append(make_doc(f))
    else:
        docs.append(make_doc(p))
    return docs


def make_doc(f):
    date = re.search(r"\d{4}-\d{2}-\d{2}", f.stem)
    return {
        "file": f,
        "title": re.sub(r"[_-]+", " ", f.stem).strip(),
        "date": date.group(0) if date else None,
        "url": None,
        "category": "MoE",
    }


def read_pages(pdf):
    doc = fitz.open(str(pdf))
    for i in range(doc.page_count):
        page = doc[i]
        text = (page.get_text() or "").strip()
        if text:
            yield i + 1, text
    doc.close()


def make_chunks(pdf):
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


def looks_garbled(text):
    if not text:
        return False
    ok = sum(1 for ch in text if ch.isalnum() or ch.isspace() or ch in ".,;:()-/&%'\"" or "\u0900" <= ch <= "\u097f")
    return ok / len(text) < 0.85


def embed_texts(texts):
    vecs = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        for attempt in range(6):
            try:
                r = gemini.models.embed_content(model=GEMINI_EMBED_MODEL, contents=batch)
                for e in r.embeddings:
                    vecs.append(e.values)
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait = 65
                    m = re.search(r"retry in ([0-9.]+)s", msg)
                    if m:
                        wait = float(m.group(1)) + 2
                    print(f"  rate limited; sleeping {wait:.0f}s (attempt {attempt+1})")
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError("embedding failed after retries")
        time.sleep(1.5)
    return vecs


def setup_schema():
    with driver.session() as s:
        s.run(f"""CREATE VECTOR INDEX {INDEX} IF NOT EXISTS
                  FOR (c:{LABEL}) ON (c.embedding)
                  OPTIONS {{indexConfig: {{`vector.dimensions`: {EMBED_DIM}, `vector.similarity_function`: 'cosine'}}}}""").consume()
        s.run(f"CREATE CONSTRAINT moe_chunk_id IF NOT EXISTS FOR (c:{LABEL}) REQUIRE c.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT moe_doc_id IF NOT EXISTS FOR (d:MoEDocument) REQUIRE d.id IS UNIQUE").consume()


def ingest(doc):
    pdf = doc["file"]
    doc_id = hashlib.sha1(pdf.read_bytes()).hexdigest()[:12]

    with driver.session() as s:
        n = s.run(f"MATCH (d:MoEDocument {{id: $id}})-[:HAS_CHUNK]->(c:{LABEL}) RETURN count(c) AS n", id=doc_id).single()["n"]
    if n:
        print(f"  already loaded: {pdf.name} ({n} chunks)")
        return doc_id, n

    chunks = make_chunks(pdf)
    if not chunks:
        print(f"  NO TEXT FOUND in {pdf.name}")
        return doc_id, 0
    garbled = sum(looks_garbled(t) for _, t in chunks)
    if garbled > len(chunks) / 2:
        print(f"  WARNING {pdf.name}: text looks garbled. Continuing anyway.")

    texts = [f"passage: {t}" for _, t in chunks]
    print(f"  embedding {len(texts)} chunks ...")
    vecs = embed_texts(texts)

    rows = [{"id": f"{doc_id}_{i}", "i": i, "page": pg, "text": t, "vec": v}
            for i, ((pg, t), v) in enumerate(zip(chunks, vecs))]

    # save local artifacts (text + vectors) for verification / offline use
    try:
        import numpy as np
        out_dir = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")
        out_dir.mkdir(parents=True, exist_ok=True)
        base = pdf.stem
        (out_dir / f"{base}_chunks.json").write_text(
            json.dumps([{"id": r["id"], "page": r["page"], "idx": r["i"], "text": r["text"]} for r in rows],
                       ensure_ascii=False, indent=1), encoding="utf-8")
        np.save(out_dir / f"{base}_embeddings.npy", np.array([r["vec"] for r in rows], dtype="float32"))
        print(f"  saved artifacts: {base}_chunks.json, {base}_embeddings.npy")
    except Exception as e:
        print("  artifact save failed:", e)

    with driver.session() as s:
        s.run("""MERGE (d:MoEDocument {id: $id})
                 SET d.title = $title, d.date = $date, d.url = $url, d.file = $file, d.category = $cat""",
              id=doc_id, title=doc["title"], date=doc["date"], url=doc["url"],
              file=pdf.name, cat=doc["category"]).consume()
        for i in range(0, len(rows), BATCH):
            b = rows[i:i + BATCH]
            s.execute_write(lambda tx, b=b: tx.run(f"""
                UNWIND $rows AS r
                MATCH (d:MoEDocument {{id: $doc}})
                MERGE (c:{LABEL} {{id: r.id}})
                SET c.text = r.text, c.page = r.page, c.idx = r.i
                WITH c, r, d
                CALL db.create.setNodeVectorProperty(c, 'embedding', r.vec)
                MERGE (d)-[:HAS_CHUNK]->(c)
            """, rows=b, doc=doc_id).consume())
        s.run(f"""MATCH (d:MoEDocument {{id: $doc}})-[:HAS_CHUNK]->(a), (d)-[:HAS_CHUNK]->(b)
                 WHERE b.idx = a.idx + 1
                 MERGE (a)-[:NEXT]->(b)""", doc=doc_id).consume()
    print(f"  loaded: {pdf.name} -> {len(rows)} chunks")
    return doc_id, len(rows)


def ingest_all(paths):
    docs = load_docs(paths)
    print(f"{len(docs)} PDFs found")
    setup_schema()
    total = 0
    for d in docs:
        _, n = ingest(d)
        total += n
    with driver.session() as s:
        try:
            s.run(f"CALL db.awaitIndex('{INDEX}', 300)").consume()
        except Exception as e:
            print("awaitIndex:", e)
        r = s.run(f"MATCH (d:MoEDocument) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:{LABEL}) "
                  "RETURN count(DISTINCT d) AS docs, count(c) AS chunks").single()
    print(f"\nDone. MoE graph now holds {r['docs']} documents and {r['chunks']} chunks.")

    # save local artifact
    return total


def search(question, k=5):
    vec = embed_texts([f"query: {question}"])[0]
    with driver.session() as s:
        return s.execute_read(lambda tx: tx.run(f"""
            CALL db.index.vector.queryNodes('{INDEX}', $k, $v) YIELD node, score
            MATCH (d:MoEDocument)-[:HAS_CHUNK]->(node)
            OPTIONAL MATCH (prev)-[:NEXT]->(node)
            OPTIONAL MATCH (node)-[:NEXT]->(nxt)
            RETURN d.title AS title, d.date AS date, d.url AS url, d.category AS category,
                   node.page AS page, node.text AS text,
                   prev.text AS before, nxt.text AS after, score
            ORDER BY score DESC
        """, k=k, v=vec).data())


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_PDF)
    ingest_all(target)
    # demo search
    print("\n--- demo search ---")
    hits = search("What subjects are allocated to the Ministry of Education?")
    for h in hits[:3]:
        print(f"\n[{h['score']:.3f}] {h['title']}, page {h['page']}")
        print("   ", h["text"][:300].replace("\n", " "))
