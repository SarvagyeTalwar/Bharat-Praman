"""Ingest MHA annual reports into Instance02 with structure-aware chunks.

Creates :MHADocument / :MHAChunk, links to the Home Affairs ministry and
its ministers, builds vector + full-text indexes, and saves local artifacts.
"""
import os, re, json, math, time, hashlib
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase

from mha_parse import parse_doc, ROOT

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
USER = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
PW = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
DB = os.getenv("NEO4J_DATABASE1") or None

MAX_FEATURES = 2048
BATCH = 40
THROTTLE = 0.4
OUT = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")

driver = GraphDatabase.driver(URI, auth=(USER, PW), max_transaction_retry_time=300)


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
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def setup_schema():
    with driver.session(database=DB) as s:
        s.run("CREATE CONSTRAINT mha_document_id IF NOT EXISTS FOR (d:MHADocument) REQUIRE d.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT mha_chunk_id IF NOT EXISTS FOR (c:MHAChunk) REQUIRE c.id IS UNIQUE").consume()
        s.run("""CREATE VECTOR INDEX mha_chunk_embeddings_local IF NOT EXISTS
                 FOR (c:MHAChunk) ON (c.embedding)
                 OPTIONS {indexConfig: {`vector.dimensions`: 2048, `vector.similarity_function`: 'cosine'}}""").consume()
        s.run("CREATE FULLTEXT INDEX mha_chunk_text_fulltext IF NOT EXISTS FOR (c:MHAChunk) ON EACH [c.text]").consume()


def infer_title(fname, text):
    m = re.search(r"Annual Report\s*(\d{4}-\d{2})", text, re.I)
    year = m.group(1) if m else None
    if not year:
        m = re.search(r"(20\d{2})[_-]?(\d{2})", fname)
        year = f"{m.group(1)}-{m.group(2)}" if m else "n.d."
    return f"Ministry of Home Affairs Annual Report {year}", year


def main():
    files = sorted(ROOT.glob("*.pdf"))
    parsed = []
    print(f"STEP 1: Parsing {len(files)} MHA annual reports...")
    for f in files:
        r = parse_doc(f)
        print(f"  {f.name}: pages={r['pages']} chapters={len(r['chapters'])} chunks={len(r['chunks'])}")
        parsed.append(r)

    all_texts = [c["text"] for r in parsed for c in r["chunks"]]
    print(f"\nSTEP 2: Building TF-IDF vocab from {len(all_texts)} chunks...")
    vocab, idf = build_vocab(all_texts)
    print(f"  vocab size: {len(vocab)}")

    print("\nSTEP 3: Preparing vectors...")
    rows_by_doc = {}
    for r in parsed:
        rows = []
        for i, c in enumerate(r["chunks"]):
            rows.append({
                "id": f"{r['id']}_{i}", "i": i, "page": c["page"], "text": c["text"],
                "breadcrumb": c["breadcrumb"], "chapter": c["chapter"], "chapter_num": c["chapter_num"],
                "section_num": c["section_num"], "section": c["section"],
                "vec": vectorize(c["text"], vocab, idf),
            })
        rows_by_doc[r["file"]] = (r, rows)

    print("\nSTEP 4: Writing to Neo4j (Instance02 / Home Affairs)...")
    setup_schema()
    for fname, (r, rows) in rows_by_doc.items():
        title, year = infer_title(fname, "\n".join(c["text"][:500] for c in r["chunks"][:3]))
        with driver.session(database=DB) as s:
            existing = s.run("MATCH (d:MHADocument {id:$id}) RETURN count(d) AS c", id=r["id"]).single()["c"]
            if existing:
                print(f"  {fname}: already ingested, skipping write")
                continue
            s.run("""
                MERGE (d:MHADocument {id:$id})
                SET d.file=$file, d.title=$title, d.doc_type='annual_report', d.year=$year,
                    d.ministry='Home Affairs', d.ministry_name='Ministry of Home Affairs',
                    d.pages=$pages
                WITH d
                MATCH (m:Ministry {name:'Home Affairs'})
                SET m.fullName = coalesce(m.fullName, 'Ministry of Home Affairs')
                MERGE (d)-[:ABOUT_MINISTRY]->(m)
                MERGE (d)-[:PUBLISHED_BY]->(m)
                WITH d, m
                MATCH (p:Person)-[:HOLDS]->(m)
                MERGE (d)-[:CONCERNS_MINISTER]->(p)
            """, id=r["id"], file=fname, title=title, year=year, pages=r["pages"]).consume()
            for i in range(0, len(rows), BATCH):
                b = rows[i:i + BATCH]
                s.execute_write(lambda tx, b=b: tx.run("""
                    UNWIND $rows AS r
                    MATCH (d:MHADocument {id:$doc})
                    MERGE (c:MHAChunk {id:r.id})
                    SET c.text=r.text, c.page=r.page, c.idx=r.i,
                        c.breadcrumb=r.breadcrumb, c.chapter=r.chapter, c.chapter_num=r.chapter_num,
                        c.section_num=r.section_num, c.section=r.section
                    WITH c,r,d
                    CALL db.create.setNodeVectorProperty(c, 'embedding', r.vec)
                    MERGE (d)-[:HAS_CHUNK]->(c)
                """, rows=b, doc=r["id"]).consume())
                time.sleep(THROTTLE)
                if (i // BATCH) % 5 == 0:
                    print(f"    {fname}: {min(i+BATCH, len(rows))}/{len(rows)} chunks")
            s.run("""MATCH (d:MHADocument {id:$doc})-[:HAS_CHUNK]->(a), (d)-[:HAS_CHUNK]->(b)
                     WHERE b.idx = a.idx + 1
                     MERGE (a)-[:NEXT]->(b)""", doc=r["id"]).consume()
        print(f"  {fname}: ingested {len(rows)} chunks")

    print("\nSTEP 5: Saving local artifacts...")
    OUT.mkdir(parents=True, exist_ok=True)
    chunks_out, vecs_out = [], []
    for r in parsed:
        for i, c in enumerate(r["chunks"]):
            chunks_out.append({"id": f"{r['id']}_{i}", "file": r["file"], **c})
            vecs_out.append(vectorize(c["text"], vocab, idf))
    (OUT / "mha_chunks.json").write_text(json.dumps(chunks_out, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "mha_vocab.json").write_text(json.dumps({"vocab": vocab, "idf": idf}, ensure_ascii=False), encoding="utf-8")
    import numpy as np
    np.save(OUT / "mha_embeddings.npy", np.array(vecs_out, dtype="float32"))
    print(f"  saved mha_chunks.json, mha_vocab.json, mha_embeddings.npy")

    with driver.session(database=DB) as s:
        print("\nVERIFY:")
        print("  MHA documents:", s.run("MATCH (d:MHADocument) RETURN count(d) AS c").single()["c"])
        print("  MHA chunks:", s.run("MATCH (c:MHAChunk) RETURN count(c) AS c").single()["c"])
        print("  linked to ministry:", s.run("MATCH (d:MHADocument)-[:ABOUT_MINISTRY]->(m:Ministry {name:'Home Affairs'}) RETURN count(d) AS c").single()["c"])
        print("  ministers linked:", s.run("MATCH (d:MHADocument)-[:CONCERNS_MINISTER]->(p:Person) RETURN collect(distinct p.name) AS names").single()["names"])
    print("\nDONE.")


if __name__ == "__main__":
    main()
