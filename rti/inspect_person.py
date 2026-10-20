"""Prints what a Person node looks like in Neo4j. Run from the repo root:  python3 rti/inspect_person.py"""
import os
from pathlib import Path

import truststore
truststore.inject_into_ssl()
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))
with driver.session(default_access_mode=READ_ACCESS) as s:
    rec = s.run("MATCH (p:Person) WHERE p.entity_id IS NOT NULL RETURN properties(p) AS p LIMIT 1").single()
    print("--- one Person node ---")
    for k, v in rec["p"].items():
        print(k, "=", str(v)[:60])
    print("--- relationships from Person ---")
    for r in s.run("MATCH (:Person)-[r]->(n) RETURN type(r) AS rel, labels(n) AS lab, count(*) AS c ORDER BY c DESC LIMIT 25"):
        print(r["rel"], r["lab"], r["c"])
