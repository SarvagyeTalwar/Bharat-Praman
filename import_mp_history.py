"""Preview or import historical MP election data into Neo4j.

Run without arguments for a local count-only preview. Pass --apply to write nodes.
2024 affidavit rows are skipped because they already exist in the user's database.
"""

import argparse
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def node_id(kind, mp_id, *years):
    suffix = "_".join(str(year) for year in years)
    safe_mp_id = re.sub(r"[^a-zA-Z0-9_]+", "_", mp_id)
    return f"{kind}_{safe_mp_id}_{suffix}"


def flatten_fields(record):
    props = {}
    for key, value in record.items():
        if key == "fields" and isinstance(value, dict):
            for field, details in value.items():
                if isinstance(details, dict):
                    for detail_key, detail_value in details.items():
                        props[f"{field}_{detail_key}"] = detail_value
        elif value is None or isinstance(value, (str, int, float, bool)):
            props[key] = value
    return props


def load_payload():
    people = [row for row in read_jsonl(DATA_DIR / "all_mp_people.jsonl")
              if not row.get("is_current_mp")]
    events = [row for row in read_jsonl(DATA_DIR / "all_mp_elections.jsonl")
              if int(row.get("election_year", 0)) < 2024]
    party_changes = read_jsonl(DATA_DIR / "all_party_changes.jsonl")
    affidavit_changes = read_jsonl(DATA_DIR / "all_affidavit_changes.jsonl")
    return people, events, party_changes, affidavit_changes


def import_rows(tx, people, events, party_changes, affidavit_changes):
    people = [{"person_id": row["person_entity_id"], "name": row["name"],
               "candidate_key": row["candidate_key"]} for row in people]
    events = [{"person_id": row["person_entity_id"], "id": row["election_id"],
               "record_type": row["record_type"], "props": dict(flatten_fields(row), id=row["election_id"])}
              for row in events]
    party_changes = [{"person_id": row["person_entity_id"],
                      "id": node_id("party_change", row["person_entity_id"], row["from_year"], row["to_year"]),
                      "props": flatten_fields(row)} for row in party_changes]
    affidavit_changes = [{"person_id": row["person_entity_id"],
                          "id": node_id("affidavit_change", row["person_entity_id"], row["from_year"], row["to_year"]),
                          "from_id": row["from_election_id"], "to_id": row["to_election_id"],
                          "props": flatten_fields(row)} for row in affidavit_changes]

    tx.run("""
        UNWIND $rows AS row
        MERGE (p:Person:MP:HistoricalMP {entity_id: row.person_id})
        SET p.name = coalesce(p.name, row.name), p.canonical_name_key = row.candidate_key
    """, rows=people).consume()
    tx.run("""
        UNWIND $rows AS row
        MATCH (p:MP {entity_id: row.person_id})
        MERGE (r:ElectionRecord {id: row.id})
        SET r += row.props
        FOREACH (_ IN CASE WHEN row.record_type = 'affidavit_winner' THEN [1] ELSE [] END | SET r:Affidavit)
        FOREACH (_ IN CASE WHEN row.record_type = 'party_only_election_result' THEN [1] ELSE [] END | SET r:ElectionResult)
        MERGE (p)-[:HAS_ELECTION_RECORD]->(r)
        FOREACH (_ IN CASE WHEN row.record_type = 'affidavit_winner' THEN [1] ELSE [] END | MERGE (p)-[:FILED_AFFIDAVIT]->(r))
        FOREACH (_ IN CASE WHEN row.record_type = 'party_only_election_result' THEN [1] ELSE [] END | MERGE (p)-[:WON_ELECTION]->(r))
    """, rows=events).consume()
    tx.run("""
        UNWIND $rows AS row
        MATCH (p:MP {entity_id: row.person_id})
        MERGE (c:PartyChange {id: row.id})
        SET c += row.props
        MERGE (p)-[:HAS_PARTY_CHANGE]->(c)
    """, rows=party_changes).consume()
    tx.run("""
        UNWIND $rows AS row
        MATCH (p:MP {entity_id: row.person_id})
        MERGE (c:AffidavitChange {id: row.id})
        SET c += row.props
        MERGE (p)-[:HAS_AFFIDAVIT_CHANGE]->(c)
        WITH c, row
        OPTIONAL MATCH (a:Affidavit {id: row.from_id})
        FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (c)-[:FROM_AFFIDAVIT]->(a))
        WITH c, row
        OPTIONAL MATCH (b:Affidavit {id: row.to_id})
        FOREACH (_ IN CASE WHEN b IS NULL THEN [] ELSE [1] END | MERGE (c)-[:TO_AFFIDAVIT]->(b))
    """, rows=affidavit_changes).consume()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the historical rows into Neo4j")
    args = parser.parse_args()
    people, events, party_changes, affidavit_changes = load_payload()
    print("Full elected-MP import preview (2024 events excluded; existing current MPs reused):")
    print(f"  HistoricalMP nodes:    {len(people)}")
    print(f"  ElectionRecord nodes:  {len(events)}")
    print(f"  PartyChange nodes:     {len(party_changes)}")
    print(f"  AffidavitChange nodes: {len(affidavit_changes)}")
    print(f"  Potential new nodes:   {len(people) + len(events) + len(party_changes) + len(affidavit_changes)}")
    if not args.apply:
        print("Preview only. Pass --apply to write these idempotent MERGE records to Neo4j.")
        return

    load_dotenv(BASE_DIR / ".env")
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    missing = [name for name, value in {
        "NEO4J_URI": uri, "NEO4J_USERNAME": username, "NEO4J_PASSWORD": password
    }.items() if not value]
    if missing:
        raise ValueError(f"Missing Neo4j settings in .env: {', '.join(missing)}")

    from neo4j import GraphDatabase
    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        with driver.session() as session:
            session.execute_write(import_rows, people, events, party_changes, affidavit_changes)
    print("Historical MP records imported. Existing records were merged by stable IDs.")


if __name__ == "__main__":
    main()
