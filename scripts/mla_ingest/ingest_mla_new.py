"""Ingest winners-table MLAs for the new elections (dry-run unless --write)."""
import json, os, re, sys, time
from collections import Counter, defaultdict
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
URI = os.getenv("NEO4J_URI", "neo4j+ssc://c1bf4c50.databases.neo4j.io")
USER = os.getenv("NEO4J_USERNAME", "c1bf4c50")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
WRITE = "--write" in sys.argv

STATE = {"Haryana": ("Haryana", "state_haryana"), "Odisha": ("Odisha", "state_odisha"),
         "Orissa": ("Odisha", "state_odisha"), "TamilNadu": ("Tamil Nadu", "state_tamil_nadu"),
         "UttarPradesh": ("Uttar Pradesh", "state_uttar_pradesh")}

# elections that already exist with full data -> skip
EXISTING = {"Haryana2024", "Odisha2024", "UttarPradesh2022"}

ALIASES = {
    "IND": "Ind.", "CPM": "CPI(M)",
    "SUHELDEV BHARTIYA SAMAJ PARTY": "Suheldev Bharatiya Samaj Party",
    "DESIYA MURPOKKU DRAVIDA KAZHAGAM": "DMDK",
    "PATTALI MAKKAL KATCHI": "PMK",
    "INDIAN UNION MUSLIM LEAGUE": "IUML",
}

def norm(s):
    return re.sub(r"[^A-Z0-9]+", "", (s or "").upper())

def person_key_name(s):
    s = re.split(r"\bS/O\b", s or "", flags=re.I)[0]
    s = re.split(r"\bALIAS\b", s, flags=re.I)[0]
    return norm(s)

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")

rows = [r for r in json.load(open("/tmp/opencode/mla_winners_parsed.json")) if r["slug"] not in EXISTING]
print("rows to ingest", len(rows))

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session() as s:
    def one(q, p=None):
        r = s.run(q, p or {}).single()
        return None if r is None else {k: (v.data() if hasattr(v, "data") else v) for k, v in r.items()}

    # party resolver
    parties = [(r["name"], r["eid"]) for r in s.run("MATCH (p:Party) RETURN p.name AS name, p.entity_id AS eid")]
    by_norm = {norm(n): (n, eid) for n, eid in parties}
    def resolve_party(name):
        canonical = ALIASES.get(name.upper(), name)
        key = norm(canonical)
        if key in by_norm:
            n, eid = by_norm[key]
            return n, eid
        return canonical, "party_" + slugify(canonical)

    # state ids
    states = {r["name"]: r["eid"] for r in s.run("MATCH (st:State) RETURN st.name AS name, st.entity_id AS eid")}
    print("states", states)

    # existing entity id collisions
    existing_ids = {r["eid"] for r in s.run("MATCH (p:Person:MLA) RETURN p.entity_id AS eid")}
    new_ids = [f"mla_{r['slug']}_{r['cid']}" for r in rows]
    coll = [x for x in new_ids if x in existing_ids]
    print("entity_id collisions:", len(coll))

    # build payload
    payload = []
    for r, eid in zip(rows, new_ids):
        m = re.match(r"([A-Za-z]+)(\d{4})$", r["slug"])
        state_name, state_id = STATE[m.group(1)]
        year = int(m.group(2))
        pname, pid = resolve_party(r["party"])
        payload.append({
            "entity_id": eid, "name": r["name"], "myneta_name": r["myneta_name"], "myneta_id": r["cid"],
            "slug": r["slug"], "year": year, "state": state_name, "state_id": state_id,
            "party_name": pname, "party_id": pid, "cons": r["cons"],
            "cons_id": f"asmcons_{slugify(r['cons'])}|{slugify(state_name)}|{slugify(r['slug'])}",
            "cases": r["cases"], "edu": r["edu"], "assets": r["assets"],
            "person_key": f"{state_name}|{person_key_name(r['name'])}",
            "source_url": f"https://www.myneta.info/{r['slug']}/candidate.php?candidate_id={r['cid']}",
        })

    print("per election:", Counter(p["slug"] for p in payload))
    new_party = {p["party_name"] for p in payload} - {n for n, _ in parties}
    print("parties to create", len(new_party), sorted(new_party))
    print("constituencies", len({p["cons_id"] for p in payload}))
    print("sample", json.dumps(payload[0], default=str))

    if not WRITE:
        print("DRY RUN - nothing written")
        driver.close()
        raise SystemExit(0)

    # ---- write ----
    elections = {}
    for p in payload:
        elections[p["slug"]] = {"election_id": p["slug"], "type": "State Assembly", "year": p["year"], "state": p["state"]}
    s.run("""
        UNWIND $rows AS r
        MERGE (e:Election {election_id: r.election_id})
        ON CREATE SET e.type = r.type, e.year = r.year, e.state = r.state
    """, {"rows": list(elections.values())}).consume()
    print("elections now", one("MATCH (e:Election) RETURN count(e) AS n")["n"], flush=True)

    PERSONS = """
    UNWIND $rows AS r
    MATCH (st:State {entity_id: r.state_id})
    MERGE (p:Person {entity_id: r.entity_id})
    SET p:MLA
    SET p.name = r.name, p.myneta_name = r.myneta_name, p.myneta_id = r.myneta_id,
        p.election = r.slug, p.election_year = r.year, p.party_name = r.party_name,
        p.education = r.edu, p.criminal_case_count = r.cases, p.total_assets = r.assets,
        p.person_id = r.entity_id, p.person_key = r.person_key, p.source = 'myneta:winners-index'
    MERGE (pa:Party {entity_id: r.party_id}) ON CREATE SET pa.name = r.party_name
    MERGE (p)-[:MEMBER_OF]->(pa)
    MERGE (c:AssemblyConstituency {entity_id: r.cons_id}) ON CREATE SET c.name = r.cons
    MERGE (c)-[:IN_STATE]->(st)
    MERGE (p)-[:REPRESENTS]->(c)
    """
    AFFS = """
    UNWIND $rows AS r
    MATCH (p:Person {entity_id: r.entity_id})
    MATCH (e:Election {election_id: r.slug})
    MERGE (a:Affidavit {affidavit_id: r.entity_id})
    SET a.person_entity_id = r.entity_id, a.name = r.name, a.party_name = r.party_name,
        a.election_id = r.slug, a.election_year = r.year, a.total_assets = r.assets,
        a.criminal_case_count = r.cases, a.myneta_id = r.myneta_id, a.source_url = r.source_url,
        a.election_source = 'myneta: ' + r.slug, a.election_verified = true,
        a.source = 'myneta:winners-index'
    MERGE (p)-[:FILED]->(a)
    MERGE (a)-[fe:FOR_ELECTION]->(e)
    SET fe.election_source = 'myneta: ' + r.slug, fe.election_verified = true
    MERGE (p)-[co:CONTESTED]->(e)
    SET co.election_source = 'myneta: ' + r.slug, co.election_verified = true
    """
    B = 300
    for i in range(0, len(payload), B):
        b = payload[i:i + B]
        s.execute_write(lambda tx, b=b: tx.run(PERSONS, rows=b).consume())
        print("  persons", min(i + B, len(payload)), "/", len(payload), flush=True)
    for i in range(0, len(payload), B):
        b = payload[i:i + B]
        s.execute_write(lambda tx, b=b: tx.run(AFFS, rows=b).consume())
        print("  affidavits", min(i + B, len(payload)), "/", len(payload), flush=True)

    print("persons", one("MATCH (p:Person) RETURN count(p) AS n")["n"])
    print("affidavits", one("MATCH (a:Affidavit) RETURN count(a) AS n")["n"])
    print("elections", one("MATCH (e:Election) RETURN count(e) AS n")["n"])
    print("nodes", one("MATCH (n) RETURN count(n) AS n")["n"])
    print("rels", one("MATCH ()-[r]->() RETURN count(r) AS n")["n"])
    print("DONE")
driver.close()
