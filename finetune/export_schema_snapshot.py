"""Read-only Neo4j schema and categorical-value exporter for fine-tuning.

Run locally with your existing .env / BACKEND/.env credentials.
Never prints or writes credentials. Saves sanitized metadata to:
    data/schema_snapshot.json

Usage:
    python finetune/export_schema_snapshot.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "BACKEND" / ".env")

OUT_PATH = BASE_DIR / "data" / "schema_snapshot.json"


def _connect():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    pw = os.getenv("NEO4J_PASSWORD")
    db = os.getenv("NEO4J_DATABASE") or None
    if not all([uri, user, pw]):
        raise RuntimeError("Missing NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD in .env")
    return GraphDatabase.driver(uri, auth=(user, pw)), db


def _run_read(driver, db, query, params=None):
    with driver.session(database=db, default_access_mode=READ_ACCESS) as s:
        return [dict(r) for r in s.run(query, params or {})]


def main():
    driver, db = _connect()
    try:
        labels = [r["label"] for r in _run_read(driver, db, "CALL db.labels() YIELD label RETURN label ORDER BY label")]
        rel_types = [r["relationshipType"] for r in _run_read(driver, db, "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")]

        label_counts = {}
        label_props = {}
        for lbl in labels:
            safe_lbl = lbl.replace("`", "")
            cnt = _run_read(driver, db, f"MATCH (n:`{safe_lbl}`) RETURN count(n) AS c")
            label_counts[lbl] = cnt[0]["c"] if cnt else 0
            props = _run_read(
                driver,
                db,
                f"MATCH (n:`{safe_lbl}`) WITH n LIMIT 500 UNWIND keys(n) AS k RETURN collect(DISTINCT k) AS props",
            )
            label_props[lbl] = sorted(props[0]["props"]) if props and props[0]["props"] else []

        rel_patterns = _run_read(
            driver,
            db,
            """
            MATCH (a)-[r]->(b)
            RETURN labels(a) AS src_labels, type(r) AS rel_type, labels(b) AS dst_labels, count(*) AS count
            ORDER BY count DESC
            LIMIT 100
            """,
        )

        # Categorical values that small LLMs most commonly get wrong (exact spelling/casing)
        parties = [
            r["name"]
            for r in _run_read(driver, db, "MATCH (p:Party) WHERE p.name IS NOT NULL RETURN p.name AS name ORDER BY name LIMIT 100")
        ]
        states = [
            r["name"]
            for r in _run_read(driver, db, "MATCH (s:State) WHERE s.name IS NOT NULL RETURN s.name AS name ORDER BY name LIMIT 100")
        ]
        elections = _run_read(
            driver,
            db,
            "MATCH (e:Election) RETURN e.election_id AS election_id, e.type AS type, e.year AS year, e.state AS state ORDER BY e.year DESC LIMIT 100",
        )
        case_statuses = [
            r["status"]
            for r in _run_read(
                driver,
                db,
                "MATCH (c:CriminalCase) WHERE c.status IS NOT NULL RETURN DISTINCT c.status AS status LIMIT 50",
            )
        ]
        top_sections = _run_read(
            driver,
            db,
            "MATCH (s:Section)<-[:UNDER]-(c:CriminalCase) RETURN s.code AS code, count(DISTINCT c) AS cases ORDER BY cases DESC LIMIT 40",
        )
        ministries = _run_read(
            driver,
            db,
            "MATCH (m:Ministry) RETURN DISTINCT m.name AS name, m.portfolio_type AS portfolio_type ORDER BY name LIMIT 100",
        )
        sample_people = [
            r["name"]
            for r in _run_read(
                driver,
                db,
                "MATCH (p:Person) WHERE p.name IS NOT NULL RETURN p.name AS name ORDER BY coalesce(p.criminal_case_count, 0) DESC LIMIT 25",
            )
        ]
        sample_constituencies = {
            "Parliamentary": [
                r["name"]
                for r in _run_read(driver, db, "MATCH (c:Constituency) WHERE c.name IS NOT NULL RETURN c.name AS name LIMIT 25")
            ],
            "Assembly": [
                r["name"]
                for r in _run_read(driver, db, "MATCH (c:AssemblyConstituency) WHERE c.name IS NOT NULL RETURN c.name AS name LIMIT 25")
            ],
        }

        snapshot = {
            "labels": labels,
            "relationship_types": rel_types,
            "label_counts": label_counts,
            "label_properties": label_props,
            "relationship_patterns": rel_patterns,
            "categorical_values": {
                "parties": parties,
                "states": states,
                "elections": elections,
                "criminal_case_statuses": case_statuses,
                "top_sections": top_sections,
                "ministries": ministries,
                "sample_people": sample_people,
                "sample_constituencies": sample_constituencies,
            },
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote schema snapshot to {OUT_PATH}")
        print(f"Labels ({len(labels)}): {', '.join(labels)}")
        print(f"Relationships ({len(rel_types)}): {', '.join(rel_types)}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
