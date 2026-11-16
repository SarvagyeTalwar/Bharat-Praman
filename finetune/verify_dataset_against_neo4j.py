"""Verify generated fine-tuning Cypher queries against your live Neo4j (READ-ONLY).

Run locally using your .env / BACKEND/.env credentials.
Executes every query in READ_ACCESS mode with a 10s timeout, checks for Neo4j
syntax/schema errors, logs row counts, and outputs verified JSONL splits:
    data/finetune_train_verified.jsonl
    data/finetune_val_verified.jsonl

Usage:
    python finetune/verify_dataset_against_neo4j.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS, unit_of_work

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "BACKEND" / ".env")

SPLITS = [
    (BASE_DIR / "data" / "finetune_train.jsonl", BASE_DIR / "data" / "finetune_train_verified.jsonl"),
    (BASE_DIR / "data" / "finetune_val.jsonl", BASE_DIR / "data" / "finetune_val_verified.jsonl"),
]


def _connect():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    pw = os.getenv("NEO4J_PASSWORD")
    db = os.getenv("NEO4J_DATABASE") or None
    if not all([uri, user, pw]):
        raise RuntimeError("Missing NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD in .env")
    return GraphDatabase.driver(uri, auth=(user, pw)), db


def verify_split(driver, db, in_path: Path, out_path: Path):
    if not in_path.exists():
        print(f"Skipping missing file: {in_path}")
        return

    rows = [json.loads(line) for line in in_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    verified = []
    syntax_errors = []
    empty_queries = []

    with driver.session(database=db, default_access_mode=READ_ACCESS) as session:
        for idx, item in enumerate(rows, 1):
            user_q = item["messages"][1]["content"]
            plan = json.loads(item["messages"][2]["content"])

            if plan["result_type"] == "unsupported":
                verified.append(item)
                continue

            cypher = plan["cypher"]
            params = plan.get("parameters", {})

            @unit_of_work(timeout=10)
            def _run(tx):
                return list(tx.run(cypher, params))

            try:
                res = session.execute_read(_run)
                if len(res) == 0:
                    empty_queries.append((idx, user_q, cypher))
                else:
                    verified.append(item)
            except Exception as exc:
                syntax_errors.append((idx, user_q, str(exc)[:180], cypher))

    with out_path.open("w", encoding="utf-8") as f:
        for r in verified:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n=== {in_path.name} ===")
    print(f"Total: {len(rows)} | Verified (non-empty / unsupported): {len(verified)}")
    print(f"Empty result (dropped): {len(empty_queries)} | Neo4j errors (dropped): {len(syntax_errors)}")
    for idx, q, err, _ in syntax_errors[:5]:
        print(f"  [ERR #{idx}] {q[:60]} -> {err}")
    for idx, q, _ in empty_queries[:5]:
        print(f"  [EMPTY #{idx}] {q[:70]}")
    print(f"Saved: {out_path}")


def main():
    driver, db = _connect()
    try:
        for in_path, out_path in SPLITS:
            verify_split(driver, db, in_path, out_path)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
