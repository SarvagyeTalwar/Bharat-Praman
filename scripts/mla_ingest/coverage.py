import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

load_dotenv()
URI = os.getenv("NEO4J_URI", "neo4j+ssc://c1bf4c50.databases.neo4j.io")
USER = os.getenv("NEO4J_USERNAME", "c1bf4c50")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
SEATS = {"Haryana": 90, "Odisha": 147, "Tamil Nadu": 234, "Uttar Pradesh": 403}
TARGETS = ["Haryana2014", "Haryana2019", "Haryana2024",
           "Odisha2014", "Odisha2019", "Odisha2024", "Orissa2004", "Orissa2009",
           "TamilNadu2011", "TamilNadu2016", "TamilNadu2021", "TamilNadu2026",
           "UttarPradesh2017", "uttarpradesh2022"]

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session(default_access_mode=READ_ACCESS) as s:
    print(f"{'election':18s} {'state':15s} {'ingested':>8s} {'seats':>6s} {'missing':>8s}")
    for el in TARGETS:
        r = s.run("""
            MATCH (p:Person:MLA)-[:FILED]->(:Affidavit)-[:FOR_ELECTION]->(e:Election {election_id:$el})
            RETURN e.state AS state, count(DISTINCT p) AS n
        """, {"el": el}).single()
        if not r:
            print(el, "NO DATA"); continue
        state, n = r["state"], r["n"]
        seats = SEATS.get(state, 0)
        print(f"{el:18s} {state:15s} {n:8d} {seats:6d} {seats-n:8d}")
driver.close()
