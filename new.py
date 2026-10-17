import os, re, json, time
from pathlib import Path
from difflib import SequenceMatcher

import truststore
truststore.inject_into_ssl()

from dotenv import load_dotenv
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).resolve().parent
PARSED_FILE = BASE_DIR / "myneta_parsed.json"
OVERRIDES_FILE = BASE_DIR / "overrides.json"
load_dotenv(BASE_DIR / ".env")

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PWD = os.getenv("NEO4J_PASSWORD")
BATCH = 50
MIN_SCORE = 0.6   # CHANGED: was 0.5, which let "Rahul Gandhi" pass for "Priyanka Gandhi Vadra"

# ---------- normalisation ----------
def norm_cons(s):
    s = re.sub(r"\((sc|st)\)", "", (s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)

def norm_state(s):
    s = (s or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", s)

def name_tokens(s):
    s = re.sub(r"\b(dr|shri|smt|prof|adv|mr|mrs|ms)\b\.?", " ", (s or "").lower())
    return sorted(re.sub(r"[^a-z ]", " ", s).split())

def name_score(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    overlap = len(set(ta) & set(tb)) / min(len(set(ta)), len(set(tb)))
    seq = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    return max(overlap, seq)


# ---------- cypher ----------
PROPS = """
UNWIND $rows AS row
MATCH (p:Person {entity_id: row.entity_id})
SET p.myneta_id = row.myneta_id,
    p.myneta_name = row.name,
    p.criminal_case_count = row.criminal_case_count,
    p.total_assets = row.total_assets,
    p.liabilities = row.liabilities,
    p.movable_assets = row.movable_assets,
    p.immovable_assets = row.immovable_assets,
    p.education = row.education
"""

CASES = """
UNWIND $cases AS c
MATCH (p:Person {entity_id: c.entity_id})
MERGE (cc:CriminalCase {case_id: c.case_id})
  SET cc.status = c.status, cc.fir_no = c.fir_no, cc.case_no = c.case_no,
      cc.court = c.court, cc.charges_framed = c.charges_framed,
      cc.ipc_sections = c.ipc_sections
MERGE (p)-[:FACES]->(cc)
WITH cc, c
UNWIND c.ipc_sections AS sec
MERGE (s:Section {code: sec})
MERGE (cc)-[:UNDER]->(s)
"""

MINE = """
MATCH (p:Person)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(st:State)
RETURN p.entity_id AS id,
       coalesce(p.first_name, '') + ' ' + coalesce(p.last_name, '') AS name,
       c.name AS cons, st.name AS state
"""


def main():
    myneta = json.load(open(PARSED_FILE, encoding="utf-8"))
    print(len(myneta), "MyNeta records loaded")

    # CHANGED: manual pairs (spelling variants like Burdwan/Bardhaman) from triage.py
    overrides = {}
    if OVERRIDES_FILE.exists():
        overrides = json.load(open(OVERRIDES_FILE, encoding="utf-8"))
    print(len(overrides), "manual overrides loaded")
    by_id = {m["myneta_id"]: m for m in myneta}

    with GraphDatabase.driver(URI, auth=(USER, PWD),
                              max_transaction_retry_time=120) as driver:
        driver.verify_connectivity()
        print("Connected.")

        with driver.session() as s:
            mine = s.run(MINE).data()
            print(len(mine), "MPs in Neo4j with a constituency")

            # index MyNeta by (constituency, state) and by constituency alone
            by_key, by_cons = {}, {}
            for m in myneta:
                by_key.setdefault((norm_cons(m["constituency"]), norm_state(m["state"])), []).append(m)
                by_cons.setdefault(norm_cons(m["constituency"]), []).append(m)

            matched, review, used = [], [], set()
            for p in mine:
                # CHANGED: overrides win over automatic matching
                if p["id"] in overrides and overrides[p["id"]] in by_id:
                    rec = by_id[overrides[p["id"]]]
                    matched.append({**rec, "entity_id": p["id"], "score": 1.0})
                    used.add(rec["myneta_id"])
                    continue

                cands = by_key.get((norm_cons(p["cons"]), norm_state(p["state"])), [])
                if not cands:   # state spelled differently: fall back to constituency alone
                    cands = by_cons.get(norm_cons(p["cons"]), [])
                best = max(cands, key=lambda c: name_score(p["name"], c["name"]), default=None)
                score = name_score(p["name"], best["name"]) if best else 0.0

                if best and score >= MIN_SCORE:   # CHANGED: uses the stricter threshold
                    matched.append({**best, "entity_id": p["id"], "score": round(score, 2)})
                    used.add(best["myneta_id"])
                else:
                    review.append({"mine": p, "best_guess": best["name"] if best else None,
                                   "score": round(score, 2),
                                   "options": [c["name"] for c in cands]})

            print(f"matched: {len(matched)} | need review: {len(review)}")

            case_rows = []
            for m in matched:
                for i, c in enumerate(m["cases"], 1):
                    case_rows.append({**c, "entity_id": m["entity_id"],
                                      "case_id": f'{m["entity_id"]}_{m["myneta_id"]}_{i}'})

            s.run("CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:CriminalCase) REQUIRE n.case_id IS UNIQUE").consume()
            s.run("CREATE CONSTRAINT section_code IF NOT EXISTS FOR (n:Section) REQUIRE n.code IS UNIQUE").consume()

            for i in range(0, len(matched), BATCH):
                batch = matched[i:i + BATCH]
                s.execute_write(lambda tx, b=batch: tx.run(PROPS, rows=b).consume())
                print(f"  properties: {min(i + BATCH, len(matched))}/{len(matched)}")

            for i in range(0, len(case_rows), BATCH):
                batch = case_rows[i:i + BATCH]
                s.execute_write(lambda tx, b=batch: tx.run(CASES, cases=b).consume())
                print(f"  cases: {min(i + BATCH, len(case_rows))}/{len(case_rows)}")

    unused = [m for m in myneta if m["myneta_id"] not in used]
    out = {"unmatched_mps_in_my_db": review,
           "myneta_records_not_matched_to_anyone": [
               {"myneta_id": m["myneta_id"], "name": m["name"],
                "constituency": m["constituency"], "state": m["state"]} for m in unused]}
    json.dump(out, open(BASE_DIR / "review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nDone. {len(matched)} MPs updated, {len(case_rows)} criminal cases added.")
    print(f"{len(review)} of my MPs unmatched, {len(unused)} MyNeta records unused -> review.json")


if __name__ == "__main__":
    main()