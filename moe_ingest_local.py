"""Local (dependency-free) vectorization of MoE PDFs -> TF-IDF vectors -> Neo4j.

Uses only stdlib + numpy + pymupdf + neo4j. No API keys or ML models required.
Produces fixed-dimension (<=2048) L2-normalized TF-IDF vectors.
"""
import os, re, sys, json, hashlib, textwrap, math
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
import fitz
import numpy as np

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

DEFAULT_PDF = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\moe24-25.pdf")
MAX_CHARS = 1200
MAX_FEATURES = 2048
INDEX = "moe_chunk_embeddings_local"
LABEL = "MoEChunkLocal"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), max_transaction_retry_time=120)


def read_pages(pdf):
    doc = fitz.open(str(pdf))
    for i in range(doc.page_count):
        t = (doc[i].get_text() or "").strip()
        if t:
            yield i + 1, t
    doc.close()


def make_chunks(pdf):
    out, buf, bp = [], [], None
    for page, text in read_pages(pdf):
        for para in re.split(r"\n\s*\n|\n(?=\d+\.\s)", text):
            para = re.sub(r"\s+", " ", para).strip()
            if not para:
                continue
            pieces = textwrap.wrap(para, MAX_CHARS) if len(para) > MAX_CHARS else [para]
            for piece in pieces:
                if buf and sum(map(len, buf)) + len(piece) > MAX_CHARS:
                    out.append((bp, " ".join(buf)))
                    buf, bp = buf[-1:], page
                if not buf:
                    bp = page
                buf.append(piece)
    if buf:
        out.append((bp, " ".join(buf)))
    return out


def tokenize(text):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", text.lower())


def build_vocab(texts):
    df = Counter()
    for t in texts:
        for tok in set(tokenize(t)):
            df[tok] += 1
    N = len(texts)
    terms = [tok for tok, c in df.items() if 2 <= c <= 0.9 * N]
    terms.sort(key=lambda x: df[x], reverse=True)
    terms = terms[:MAX_FEATURES]
    vocab = {tok: i for i, tok in enumerate(terms)}
    idf = [math.log((N + 1) / (df[terms[i]] + 1)) + 1.0 for i in range(len(terms))]
    return vocab, idf


def vectorize(text, vocab, idf):
    v = [0.0] * len(vocab)
    tf = Counter(tokenize(text))
    for tok, c in tf.items():
        if tok in vocab:
            v[vocab[tok]] = c * idf[vocab[tok]]
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def setup_schema(dim):
    with driver.session() as s:
        s.run(f"""CREATE VECTOR INDEX {INDEX} IF NOT EXISTS
                  FOR (c:{LABEL}) ON (c.embedding)
                  OPTIONS {{indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}}}}""").consume()
        s.run(f"CREATE CONSTRAINT moe_local_chunk_id IF NOT EXISTS FOR (c:{LABEL}) REQUIRE c.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT moe_local_doc_id IF NOT EXISTS FOR (d:MoELocalDoc) REQUIRE d.id IS UNIQUE").consume()


def main(pdf_path):
    pdf = Path(pdf_path)
    doc_id = hashlib.sha1(pdf.read_bytes()).hexdigest()[:12]
    chunks = make_chunks(pdf)
    print(f"{pdf.name}: {len(chunks)} chunks")
    texts = [t for _, t in chunks]
    vocab, idf = build_vocab(texts)
    dim = len(vocab)
    print(f"vocab size: {dim}")
    setup_schema(dim)

    # check already loaded
    with driver.session() as s:
        n = s.run(f"MATCH (d:MoELocalDoc {{id: $id}})-[:HAS_CHUNK]->(c:{LABEL}) RETURN count(c) AS n", id=doc_id).single()["n"]
    if n:
        print(f"  already loaded ({n} chunks). Re-running will skip write? Overwriting vectors anyway.")
    # We'll still overwrite to be safe.

    rows = []
    for i, (pg, t) in enumerate(chunks):
        rows.append({"id": f"{doc_id}_{i}", "i": i, "page": pg, "text": t, "vec": vectorize(t, vocab, idf)})

    with driver.session() as s:
        s.run("""MERGE (d:MoELocalDoc {id: $id})
                 SET d.title = $title, d.file = $file, d.category = $cat""",
              id=doc_id, title=re.sub(r"[_-]+", " ", pdf.stem).strip(), file=pdf.name, cat="MoE").consume()
        BATCH = 50
        for i in range(0, len(rows), BATCH):
            b = rows[i:i + BATCH]
            s.execute_write(lambda tx, b=b: tx.run(f"""
                UNWIND $rows AS r
                MATCH (d:MoELocalDoc {{id: $doc}})
                MERGE (c:{LABEL} {{id: r.id}})
                SET c.text = r.text, c.page = r.page, c.idx = r.i
                WITH c, r, d
                CALL db.create.setNodeVectorProperty(c, 'embedding', r.vec)
                MERGE (d)-[:HAS_CHUNK]->(c)
            """, rows=b, doc=doc_id).consume())
        s.run(f"""MATCH (d:MoELocalDoc {{id: $doc}})-[:HAS_CHUNK]->(a), (d)-[:HAS_CHUNK]->(b)
                 WHERE b.idx = a.idx + 1
                 MERGE (a)-[:NEXT]->(b)""", doc=doc_id).consume()

    # save artifacts
    out_dir = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = pdf.stem
    (out_dir / f"{base}_chunks_local.json").write_text(
        json.dumps([{"id": r["id"], "page": r["page"], "idx": r["i"], "text": r["text"]} for r in rows],
                   ensure_ascii=False, indent=1), encoding="utf-8")
    np.save(out_dir / f"{base}_embeddings_local.npy", np.array([r["vec"] for r in rows], dtype="float32"))
    with open(out_dir / f"{base}_vocab_local.json", "w", encoding="utf-8") as f:
        json.dump({"vocab": vocab, "idf": idf}, f, ensure_ascii=False)
    print(f"Saved artifacts to {out_dir}")
    print(f"Done: {len(rows)} chunks, dim {dim}.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_PDF)
    main(target)
