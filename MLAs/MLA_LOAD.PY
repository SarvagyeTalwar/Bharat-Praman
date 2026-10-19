import os, re, sys, json
from pathlib import Path
from collections import Counter, defaultdict

import truststore
truststore.inject_into_ssl()
from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())          # walks up folders until it finds your .env
URI, USER, PWD = os.getenv("NEO4J_URI"), os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")
DRY = "--dry" in sys.argv            # python mla_load.py --dry  ->  show matching, write nothing
BATCH = 50

# MyNeta spelling -> your spelling. Add to this after the dry run shows what didn't match.
ALIASES = {
    "BJP": "Bharatiya Janata Party",
    "INC": "Indian National Congress",
    "IND": "Independent",
}
STATE_FIX = {"Chattisgarh": "Chhattisgarh", "Delhi": "NCT of Delhi"}


def find_file(name):
    for d in (HERE, Path.cwd(), HERE.parent):
        if (d / name).exists():
            return d / name
    raise FileNotFoundError(f"{name} not found in {HERE}, the current folder, or the parent folder")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("&", "and"))


def make_id(prefix, value):
    return f"{prefix}_" + re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")


def acronym(name):
    skip = {"of", "and", "the", "for"}
    return "".join(w[0].upper() for w in re.findall(r"[A-Za-z]+", name) if w.lower() not in skip)


# ---------- match MyNeta names to nodes that already exist ----------
def build_resolvers(session):
    parties = session.run("MATCH (p:Party) RETURN p.entity_id AS id, p.name AS name").data()
    states = session.run("MATCH (s:State) RETURN s.entity_id AS id, s.name AS name").data()
    p_by_norm = {norm(e["name"]): e for e in parties if e["name"]}
    p_by_acr = defaultdict(list)
    for e in parties:
        if e["name"]:
            p_by_acr[norm(acronym(e["name"]))].append(e)
    s_by_norm = {norm(e["name"]): e for e in states if e["name"]}

    def party(my_name):
        if not my_name:
            return None, None, "none"
        e = p_by_norm.get(norm(ALIASES.get(my_name, my_name)))
        if e:
            return e["id"], e["name"], "matched"
        c = p_by_acr.get(norm(my_name), [])
        if len(c) == 1:                                   # only if the initials are unambiguous
            return c[0]["id"], c[0]["name"], "initials"
        return make_id("party", my_name), my_name, "NEW"

    def state(my_name):
        name = STATE_FIX.get(my_name, my_name)
        e = s_by_norm.get(norm(name))
        return (e["id"], e["name"]) if e else (make_id("state", name), name)

    return party, state


LOAD = """
UNWIND $rows AS row
MERGE (p:Person {entity_id: row.entity_id})
SET p:MLA, p.name = row.name, p.myneta_id = row.myneta_id, p.election = row.slug,
    p.election_year = row.year, p.party_name = row.party_name, p.age = row.age,
    p.education = row.education, p.criminal_case_count = row.cases,
    p.total_assets = row.assets, p.liabilities = row.liab,
    p.movable_assets = row.movable, p.immovable_assets = row.immovable
MERGE (st:State {entity_id: row.state_id}) ON CREATE SET st.name = row.state
MERGE (c:AssemblyConstituency {entity_id: row.cons_id}) ON CREATE SET c.name = row.cons
MERGE (c)-[:IN_STATE]->(st)
MERGE (p)-[:REPRESENTS]->(c)
FOREACH (_ IN CASE WHEN row.party_id IS NULL THEN [] ELSE [1] END |
  MERGE (pa:Party {entity_id: row.party_id}) ON CREATE SET pa.name = row.party_name
  MERGE (p)-[:MEMBER_OF]->(pa))
"""

CASES = """
UNWIND $cases AS c
MATCH (p:Person {entity_id: c.entity_id})
MERGE (cc:CriminalCase {case_id: c.case_id})
  SET cc.status = c.status, cc.fir_no = c.fir_no, cc.case_no = c.case_no, cc.court = c.court,
      cc.charges_framed = c.charges_framed, cc.ipc_sections = c.ipc_sections
MERGE (p)-[:FACES]->(cc)
WITH cc, c UNWIND c.ipc_sections AS sec
MERGE (s:Section {code: sec})
MERGE (cc)-[:UNDER]->(s)
"""


def main():
    recs = json.load(open(find_file("mla_parsed.json"), encoding="utf-8"))
    print(len(recs), "records in mla_parsed.json")

    # one record per seat; a by-election winner replaces the original winner
    best = {}
    for r in recs:
        k = (r["state"], norm(r["constituency"]), r["slug"])
        if k not in best or r.get("by_election"):
            best[k] = r
    recs = list(best.values())
    print(len(recs), "after keeping one record per seat")

    with GraphDatabase.driver(URI, auth=(USER, PWD), max_transaction_retry_time=120) as driver:
        driver.verify_connectivity()
        with driver.session() as s:
            resolve_party, resolve_state = build_resolvers(s)

            rows, cases, party_log = [], [], Counter()
            for r in recs:
                pid, pname, how = resolve_party(r["party"])
                sid, sname = resolve_state(r["state"])
                party_log[(r["party"], pname, how)] += 1
                eid = f'mla_{r["slug"]}_{r["myneta_id"]}'
                rows.append({
                    "entity_id": eid, "name": r["name"].title(), "myneta_id": r["myneta_id"],
                    "slug": r["slug"], "year": r["year"], "age": r["age"], "education": r["education"],
                    "cases": r["criminal_case_count"], "assets": r["total_assets"], "liab": r["liabilities"],
                    "movable": r["movable_assets"], "immovable": r["immovable_assets"],
                    "party_id": pid, "party_name": pname, "state_id": sid, "state": sname,
                    "cons": r["constituency"].title(),
                    "cons_id": make_id("asmcons", f'{r["constituency"]}|{sname}|{r["slug"]}'),
                })
                for i, c in enumerate(r["cases"], 1):
                    cases.append({**c, "entity_id": eid, "case_id": f"{eid}_{i}"})

            print("\nPARTY MATCHING (MyNeta name -> your node):")
            for (mine, theirs, how), n in sorted(party_log.items(), key=lambda x: (x[0][2] != "NEW", -x[1])):
                print(f"  {how:8} {n:4}  {mine}  ->  {theirs}")
            new_parties = sum(1 for (_, _, how) in party_log if how == "NEW")
            print(f"\n{new_parties} party names have no existing node and will be created as NEW.")

            if DRY:
                print("\nDry run, nothing written. Add rows to ALIASES for NEW parties that exist under another spelling, then run without --dry.")
                return

            s.run("CREATE CONSTRAINT asmcons_id IF NOT EXISTS FOR (n:AssemblyConstituency) REQUIRE n.entity_id IS UNIQUE").consume()
            s.run("CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:CriminalCase) REQUIRE n.case_id IS UNIQUE").consume()
            s.run("CREATE CONSTRAINT section_code IF NOT EXISTS FOR (n:Section) REQUIRE n.code IS UNIQUE").consume()

            for i in range(0, len(rows), BATCH):
                b = rows[i:i + BATCH]
                s.execute_write(lambda tx, b=b: tx.run(LOAD, rows=b).consume())
                print(f"  MLAs {min(i + BATCH, len(rows))}/{len(rows)}")
            for i in range(0, len(cases), BATCH):
                b = cases[i:i + BATCH]
                s.execute_write(lambda tx, b=b: tx.run(CASES, cases=b).consume())
                print(f"  cases {min(i + BATCH, len(cases))}/{len(cases)}")

            # full-name property for MPs too, so every Person has .name
            s.run("MATCH (p:Person) WHERE p.name IS NULL "
                  "SET p.name = trim(coalesce(p.first_name,'') + ' ' + coalesce(p.last_name,''))").consume()

            print("\nDone.", s.run("MATCH (p:MLA) RETURN count(p) AS n").single()["n"], "MLAs in the graph.")


if __name__ == "__main__":
    main()