"""Re-embed MoE (Chunk) + MHA (MHAChunk) with multilingual-e5-small (384-dim).

One-time local migration from TF-IDF (2048-dim) to semantic e5 embeddings.
Writes to a NEW property `embedding_e5` + new vector indexes, leaving the
old TF-IDF index intact until you verify the switch.

Runs fully offline (no API, no quota). Resumable: re-running skips chunks
that already have `embedding_e5`.
"""
import os
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
import torch
torch.set_num_threads(max(4, min(8, os.cpu_count() or 4)))

from embeddings import embed_texts, DIM

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

URI = os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
PW = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USER, PW))

# (chunk label, new vector index name)
TARGETS = [
    ("MHAChunk", "mha_chunk_embeddings_e5"),
    ("Chunk", "chunk_embeddings_e5"),
]
BATCH = 512


def create_index(label, index_name):
    with driver.session() as s:
        s.run(
            f"""CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (c:{label}) ON (c.embedding_e5)
                OPTIONS {{indexConfig: {{`vector.dimensions`: {DIM}, `vector.similarity_function`: 'cosine'}}}}"""
        ).consume()
        print(f"[{label}] index {index_name} ready ({DIM}-dim)")


def reembed(label, index_name):
    with driver.session() as s:
        rows = s.run(
            f"MATCH (c:{label}) WHERE c.text IS NOT NULL AND c.embedding_e5 IS NULL "
            f"RETURN c.id AS id, c.text AS text"
        ).data()
    total = len(rows)
    print(f"[{label}] {total} chunks to embed")
    if not total:
        return
    for i in range(0, total, BATCH):
        chunk = rows[i:i + BATCH]
        ids = [r["id"] for r in chunk]
        texts = [r["text"] for r in chunk]
        vecs = embed_texts(texts, batch=128)
        params = [{"id": rid, "vec": v} for rid, v in zip(ids, vecs)]
        with driver.session() as s:
            s.execute_write(
                lambda tx, p=params: tx.run(
                    f"""UNWIND $rows AS r
                        MATCH (c:{label} {{id: r.id}})
                        CALL db.create.setNodeVectorProperty(c, 'embedding_e5', r.vec)
                        RETURN count(c) AS n""",
                    rows=p,
                ).consume()
            )
        print(f"[{label}] {min(i + BATCH, total)}/{total}")


for label, idx in TARGETS:
    create_index(label, idx)

for label, idx in TARGETS:
    reembed(label, idx)

with driver.session() as s:
    for label, idx in TARGETS:
        try:
            s.run(f"CALL db.awaitIndex('{idx}', 300)").consume()
            print(f"[{label}] index {idx} ONLINE")
        except Exception:
            pass

print("\nMigration complete. New e5 semantic indexes ready.")
driver.close()
