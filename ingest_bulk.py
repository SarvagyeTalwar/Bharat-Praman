"""Unified GraphRAG ingester for Ministry Annual Reports into Instance02.

Supports all 8 major ministries across multiple fiscal years (e.g. 2021-22,
2022-23, 2023-24, 2024-25). Parses with parser_lite, chunks with page- and
heading-aware chunking_utils, embeds with Qwen/Qwen3-Embedding-0.6B (1024-dim),
and links consecutive fiscal years via (:Document)-[:NEXT_YEAR]->(:Document).

Usage:
  py -3.14 ingest_bulk.py "C:\\path\\to\\report.pdf" --ministry "Home Affairs" --year 2023-24
  py -3.14 ingest_bulk.py "C:\\path\\to\\folder" --ministry "Education" --dry-run
"""
import argparse
import hashlib
import os
import re
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

from chunking_utils import chunk_pages
from embeddings import DIM, embed_texts
from parser_lite import Parser

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE1") or None

VECTOR_INDEX = "qwen_chunk_embeddings"
FULLTEXT_INDEX = "chunk_fulltext"
BATCH = 100
CHUNKER_VERSION = 3

MAJOR_MINISTRIES = {
    "education": "Education",
    "moe": "Education",
    "home": "Home Affairs",
    "home affairs": "Home Affairs",
    "mha": "Home Affairs",
    "finance": "Finance",
    "mof": "Finance",
    "health": "Health & Family Welfare",
    "health & family welfare": "Health & Family Welfare",
    "mohfw": "Health & Family Welfare",
    "defence": "Defence",
    "defense": "Defence",
    "mod": "Defence",
    "rural": "Rural Development",
    "rural development": "Rural Development",
    "mord": "Rural Development",
    "road": "Road Transport & Highways",
    "road transport": "Road Transport & Highways",
    "road transport & highways": "Road Transport & Highways",
    "morth": "Road Transport & Highways",
    "agriculture": "Agriculture & Farmers Welfare",
    "agriculture & farmers welfare": "Agriculture & Farmers Welfare",
    "moafw": "Agriculture & Farmers Welfare",
}

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    max_transaction_retry_time=300,
    notifications_min_severity="OFF",
)
parser = Parser()


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12]


def infer_fy(title: str, filename: str, explicit_year: str | None = None) -> str:
    if explicit_year and explicit_year.strip():
        return explicit_year.strip()
    combined = f"{title} {filename}"
    m = re.search(r"\b(20\d{2})\s*[-–/]\s*(\d{2,4})\b", combined)
    if m:
        y1, y2 = m.group(1), m.group(2)
        return f"{y1}-{y2[-2:]}"
    m2 = re.search(r"\b(20\d{2})\b", combined)
    if m2:
        y1 = int(m2.group(1))
        return f"{y1}-{str(y1 + 1)[-2:]}"
    return "2023-24"


def canonical_ministry(title: str, filename: str, hint: str | None = None) -> str:
    if hint:
        norm = hint.strip().lower()
        if norm in MAJOR_MINISTRIES:
            return MAJOR_MINISTRIES[norm]
        return hint.strip()
    t = f"{title} {filename}".lower()
    for key, canon in MAJOR_MINISTRIES.items():
        if len(key) >= 4 and key in t:
            return canon
    return "Education"


def classify(title, name):
    t = (title + " " + name).lower()
    if "annual report" in t:
        return "annual_report"
    if "press release" in t or t.startswith("pr-") or "pib" in t:
        return "press_release"
    if "budget" in t or "demand" in t:
        return "budget"
    if "notification" in t:
        return "notification"
    if "scheme" in t:
        return "scheme"
    return "annual_report"


def ensure_schema():
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run("CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE").consume()
        s.run(
            f"""CREATE VECTOR INDEX {VECTOR_INDEX} IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {{indexConfig: {{`vector.dimensions`: {DIM}, `vector.similarity_function`: 'cosine'}}}}"""
        ).consume()
        s.run(f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX} IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]").consume()


def ingest_one(pdf_path, ministry_hint=None, year_hint=None, dry_run=False, rechunk=False):
    res = parser.parse(pdf_path)
    doc_id = sha1(pdf_path)
    dtype = classify(res["title"], res["file"])
    ministry_name = canonical_ministry(res["title"], res["file"], ministry_hint)
    fy = infer_fy(res["title"], res["file"], year_hint)

    print(f"\nFILE: {res['file']}")
    print(f"TITLE: {res['title']}")
    print(f"MINISTRY: {ministry_name} | FY: {fy} | TYPE: {dtype} | MODE: {res['mode']} | PAGES: {res['pages']}")

    chunks = chunk_pages(
        res.get("page_texts") or [(1, res["text"])],
        max_tokens=340,
        overlap_tokens=50,
        ministry=ministry_name,
        year=fy,
        doc_title=res["title"],
    )
    print(f"CHUNKS: {len(chunks)}")
    if dry_run:
        for c in chunks[:3]:
            print(f"  [{c['breadcrumb']}] ({c['token_count']} tokens)\n    {c['text'][:180]}")
        return

    ensure_schema()

    with driver.session(database=NEO4J_DATABASE) as s:
        existing = s.run(
            """
            MATCH (d:Document {id:$id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            RETURN count(DISTINCT d) AS docs, count(c) AS chunks
            """,
            id=doc_id,
        ).single()
        if existing["docs"] and existing["chunks"] and not rechunk:
            print(f"ALREADY INGESTED ({existing['chunks']} chunks), SKIPPING (use --rechunk to overwrite)")
            return

    texts = [c["text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks with Qwen3-Embedding-0.6B ({DIM}-dim)...")
    vecs = embed_texts(texts, batch=16, progress=True)

    rows = []
    for i, (c, vec) in enumerate(zip(chunks, vecs)):
        rows.append({
            "id": f"{doc_id}_{i}",
            "idx": i,
            "page": c["page_start"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "headings": c["headings"],
            "section": c.get("section"),
            "breadcrumb": c.get("breadcrumb"),
            "token_count": c["token_count"],
            "year": fy,
            "ministry": ministry_name,
            "text": c["text"],
            "embedding": vec,
        })

    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(
            """
            MERGE (d:Document {id:$id})
            SET d.file=$file, d.title=$title, d.path=$path, d.doc_type=$dtype,
                d.ministry=$ministry, d.year=$year, d.pages=$pages,
                d.chunker_version=$chunker_version
            MERGE (m:Ministry {name:$ministry})
            ON CREATE SET m.fullName = 'Ministry of ' + $ministry
            MERGE (d)-[:ABOUT_MINISTRY]->(m)
            MERGE (d)-[:PUBLISHED_BY]->(m)
            WITH d, m
            OPTIONAL MATCH (p:Person)-[:HOLDS]->(m)
            FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d)-[:CONCERNS_MINISTER]->(p)
            )
            """,
            id=doc_id,
            file=res["file"],
            title=res["title"],
            path=res["path"],
            dtype=dtype,
            ministry=ministry_name,
            year=fy,
            pages=res["pages"],
            chunker_version=CHUNKER_VERSION,
        ).consume()

        for i in range(0, len(rows), BATCH):
            b = rows[i:i + BATCH]
            s.execute_write(
                lambda tx, b=b: tx.run(
                    """
                    UNWIND $rows AS r
                    MATCH (d:Document {id:$doc})
                    MERGE (c:Chunk {id:r.id})
                    SET c.text=r.text, c.page=r.page, c.page_start=r.page_start,
                        c.page_end=r.page_end, c.headings=r.headings,
                        c.section=r.section, c.breadcrumb=r.breadcrumb,
                        c.token_count=r.token_count, c.year=r.year,
                        c.ministry=r.ministry, c.chunk_version=$version, c.idx=r.i
                    WITH c, r, d
                    CALL db.create.setNodeVectorProperty(c, 'embedding', r.embedding)
                    MERGE (d)-[:HAS_CHUNK]->(c)
                    """,
                    rows=b,
                    doc=doc_id,
                    version=CHUNKER_VERSION,
                ).consume()
            )

        s.run(
            """
            MATCH (d:Document {id:$doc})-[:HAS_CHUNK]->(a:Chunk),
                  (d)-[:HAS_CHUNK]->(b:Chunk)
            WHERE b.idx = a.idx + 1
            MERGE (a)-[:NEXT]->(b)
            """,
            doc=doc_id,
        ).consume()

        # Link consecutive fiscal years of the same ministry via [:NEXT_YEAR]
        s.run(
            """
            MATCH (d1:Document {ministry:$ministry}), (d2:Document {ministry:$ministry})
            WHERE d1.year < d2.year AND d1.id <> d2.id
            MERGE (d1)-[:NEXT_YEAR]->(d2)
            """,
            ministry=ministry_name,
        ).consume()

        if rechunk:
            s.run(
                """
                MATCH (d:Document {id:$doc})-[:HAS_CHUNK]->(c:Chunk)
                WHERE coalesce(c.chunk_version, 0) <> $version OR c.idx >= $new_count
                DETACH DELETE c
                """,
                doc=doc_id,
                version=CHUNKER_VERSION,
                new_count=len(rows),
            ).consume()

    print(f"INGESTED: {len(rows)} chunks for {ministry_name} ({fy})")


def main():
    ap = argparse.ArgumentParser(description="Ingest Ministry Annual Report PDFs into Neo4j Instance02.")
    ap.add_argument("target", help="PDF file or folder path")
    ap.add_argument("--ministry", default=None, help="Ministry name (e.g. 'Education', 'Home Affairs', 'Finance')")
    ap.add_argument("--year", default=None, help="Fiscal year (e.g. '2023-24')")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rechunk", action="store_true", help="Replace existing chunks for each PDF")
    args = ap.parse_args()

    p = Path(args.target)
    if p.is_dir():
        seen = set()
        for f in sorted(p.glob("*.pdf")):
            file_id = sha1(f)
            if file_id in seen:
                print(f"DUPLICATE CONTENT, SKIPPING: {f.name}")
                continue
            seen.add(file_id)
            ingest_one(f, args.ministry, args.year, args.dry_run, args.rechunk)
    elif p.is_file():
        ingest_one(p, args.ministry, args.year, args.dry_run, args.rechunk)
    else:
        print(f"Target not found: {p}")


if __name__ == "__main__":
    main()
