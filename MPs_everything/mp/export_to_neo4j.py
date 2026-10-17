
import os
import json
import re
import time
from pathlib import Path
import truststore
truststore.inject_into_ssl()

from dotenv import load_dotenv
from neo4j import GraphDatabase


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "mp_entities.json"
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def validate_config():
    missing = [
        name
        for name, value in {
            "NEO4J_URI": NEO4J_URI,
            "NEO4J_USERNAME": NEO4J_USERNAME,
            "NEO4J_PASSWORD": NEO4J_PASSWORD,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(
            f"Missing .env variables: {', '.join(missing)}"
        )

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Cannot find input file: {INPUT_FILE}"
        )


# ==========================================
# HELPERS
# ==========================================

def make_id(prefix, value):
    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value).strip().casefold()
    ).strip("_")

    return f"{prefix}_{normalized}"


# ==========================================
# NEO4J QUERIES
# ==========================================

def create_constraints(session):
    queries = [
        """
        CREATE CONSTRAINT person_entity_id IF NOT EXISTS
        FOR (n:Person) REQUIRE n.entity_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT party_entity_id IF NOT EXISTS
        FOR (n:Party) REQUIRE n.entity_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT state_entity_id IF NOT EXISTS
        FOR (n:State) REQUIRE n.entity_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT constituency_entity_id IF NOT EXISTS
        FOR (n:Constituency) REQUIRE n.entity_id IS UNIQUE
        """,
    ]

    for query in queries:
        session.run(query).consume()


def import_person(tx, person_id, mp):
    name = mp.get("name") or {}
    family = mp.get("family_info") or {}
    constituency = mp.get("constituency") or {}

    # Create or update the MP node.
    tx.run("""
        MERGE (p:Person {entity_id: $entity_id})
        SET p.first_name = $first_name,
            p.last_name = $last_name,
            p.gender = $gender,
            p.age = $age,
            p.party_name = $party_name,
            p.profession = $profession,
            p.terms = $terms,
            p.nSons = $nSons,
            p.nDaughters = $nDaughters
    """,
        entity_id=person_id,
        first_name=name.get("first"),
        last_name=name.get("last"),
        gender=mp.get("gender"),
        age=mp.get("age"),
        party_name=mp.get("party"),
        profession=mp.get("profession") or [],
        terms=mp.get("terms"),
        nSons=family.get("nSons"),
        nDaughters=family.get("nDaughters"),
    ).consume()

    # Party node and relationship.
    party_name = mp.get("party")

    if party_name:
        party_id = make_id("party", party_name)

        tx.run("""
            MERGE (party:Party {entity_id: $party_id})
            ON CREATE SET party.name = $party_name

            WITH party
            MATCH (p:Person {entity_id: $person_id})
            MERGE (p)-[:MEMBER_OF]->(party)
        """,
            party_id=party_id,
            party_name=party_name,
            person_id=person_id,
        ).consume()

    # State node.
    state_name = constituency.get("state")

    if state_name:
        state_id = make_id("state", state_name)

        tx.run("""
            MERGE (s:State {entity_id: $state_id})
            ON CREATE SET s.name = $state_name
        """,
            state_id=state_id,
            state_name=state_name,
        ).consume()

    # Constituency node, connected to State and Person.
    constituency_name = constituency.get("name")

    if state_name and constituency_name:
        constituency_id = make_id(
            "constituency",
            f"{constituency_name}|{state_name}"
        )

        tx.run("""
            MERGE (c:Constituency {entity_id: $constituency_id})
            ON CREATE SET c.name = $constituency_name

            WITH c
            MATCH (s:State {entity_id: $state_id})
            MERGE (c)-[:IN_STATE]->(s)

            WITH c
            MATCH (p:Person {entity_id: $person_id})
            MERGE (p)-[:REPRESENTS]->(c)
        """,
            constituency_id=constituency_id,
            constituency_name=constituency_name,
            state_id=state_id,
            person_id=person_id,
        ).consume()


# ==========================================
# MAIN
# ==========================================

def main():
    validate_config()

    print("Connecting to Neo4j...")
    start = time.perf_counter()

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    ) as driver:

        driver.verify_connectivity()
        print("Connected successfully.")

        with driver.session() as session:
            create_constraints(session)

            with INPUT_FILE.open(
                "r", encoding="utf-8"
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError(
                    "Expected mp_entities.json to be an object "
                    "keyed by MP entity IDs."
                )

            imported = 0

            for person_id, mp in data.items():
                if not isinstance(mp, dict):
                    print(f"Skipping invalid record: {person_id}")
                    continue

                session.execute_write(
                    import_person,
                    person_id,
                    mp,
                )

                imported += 1

                if imported % 50 == 0:
                    print(f"Imported {imported} MPs...")

    elapsed = time.perf_counter() - start

    print("\nImport completed!")
    print(f"MP records processed: {imported}")
    print(f"Time taken: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
