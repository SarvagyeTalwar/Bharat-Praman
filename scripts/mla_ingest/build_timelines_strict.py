import json, os, re
from collections import defaultdict, Counter
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

load_dotenv()
URI = os.getenv("NEO4J_URI", "neo4j+ssc://c1bf4c50.databases.neo4j.io")
USER = os.getenv("NEO4J_USERNAME", "c1bf4c50")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")

def ck(s):
    s = re.sub(r"\((SC|ST)\)", "", (s or ""), flags=re.I)
    s = re.sub(r":.*$", "", s)
    return re.sub(r"[^A-Z0-9]+", "", s.upper())

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session(default_access_mode=READ_ACCESS) as s:
    data = [{k: (v.data() if hasattr(v, "data") else v) for k, v in r.items()} for r in s.run("""
        MATCH (p:Person:MLA)-[:REPRESENTS]->(c:AssemblyConstituency)
        MATCH (p)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election {type:'State Assembly'})
        RETURN p.person_key AS key, p.entity_id AS eid, p.name AS name, e.election_id AS election,
               e.year AS year, e.state AS state, c.name AS cons, a.party_name AS party,
               a.total_assets AS assets, a.criminal_case_count AS cases, p.myneta_id AS cid
        ORDER BY key, year
    """)]
driver.close()
print("rows", len(data), flush=True)

bykey = defaultdict(list)
for r in data:
    bykey[r["key"]].append(r)

def components(nodes):
    parent = list(range(len(nodes)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i, j):
        parent[find(i)] = find(j)
    bycons = defaultdict(list)
    for i, n in enumerate(nodes):
        bycons[ck(n["cons"])].append(i)
    for idxs in bycons.values():
        for j in idxs[1:]:
            union(idxs[0], j)
    comps = defaultdict(list)
    for i in range(len(nodes)):
        comps[find(i)].append(nodes[i])
    return list(comps.values())

strict = []
ambiguous = 0
for key, nodes in bykey.items():
    for comp in components(nodes):
        if len({n["election"] for n in comp}) < 2:
            continue
        comp = sorted(comp, key=lambda x: (x["year"] or 0))
        extra = [n for n in nodes if n["election"] in {c["election"] for c in comp} and n["eid"] not in {c["eid"] for c in comp}]
        strict.append({
            "person_key": key,
            "name": comp[0]["name"],
            "state": comp[0]["state"],
            "n_elections": len({n["election"] for n in comp}),
            "constituencies": sorted({n["cons"] for n in comp}),
            "parties": sorted({n["party"] for n in comp if n["party"]}),
            "elections": [{
                "election": n["election"], "year": n["year"], "constituency": n["cons"],
                "party": n["party"], "assets": n["assets"], "cases": n["cases"],
                "entity_id": n["eid"],
            } for n in comp],
            "other_same_name_same_election": [{
                "election": n["election"], "constituency": n["cons"], "party": n["party"], "entity_id": n["eid"]
            } for n in extra],
        })

strict.sort(key=lambda t: (-t["n_elections"], t["person_key"]))
json.dump(strict, open("/tmp/opencode/mla_timelines_strict.json", "w"), indent=1)
print("strict timelines", len(strict), flush=True)
print("by election count", Counter(t["n_elections"] for t in strict), flush=True)

lines = ["# MLA career timelines — winning elections (strict, same-constituency linked)", ""]
lines.append(f"- Source: myneta winners indexes (name, party, constituency, total assets, criminal cases).")
lines.append(f"- Method: within same state + normalised name, nodes are linked only when they share a constituency across elections; different people with the same name are therefore not merged.")
lines.append(f"- Timelines (2+ winning elections): **{len(strict)}**; 4+ elections: {sum(1 for t in strict if t['n_elections']>=4)}; 3: {sum(1 for t in strict if t['n_elections']==3)}; 2: {sum(1 for t in strict if t['n_elections']==2)}.")
lines.append("- Coverage caveat: winners indexes list ~85–90% of seats per election; seats with no winner entry are absent.")
lines.append("")
lines.append("## Top 50")
for t in strict[:50]:
    lines.append("")
    lines.append(f"### {t['name']} ({t['state']}) — {t['n_elections']} elections")
    lines.append(f"Constituencies: {', '.join(t['constituencies'])} · Parties: {', '.join(t['parties'])}")
    for e in t["elections"]:
        lines.append(f"- {e['year']} · {e['election']} · {e['constituency']} · {e['party']} · assets {e['assets']} · cases {e['cases']}")
    if t["other_same_name_same_election"]:
        lines.append(f"- ⚠ same name in same election: " + "; ".join(f"{o['election']} {o['constituency']} ({o['party']})" for o in t["other_same_name_same_election"]))
open(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman\DOCS\MLA_TIMELINES.md", "w", encoding="utf-8").write("\n".join(lines))
print("wrote DOCS/MLA_TIMELINES.md", flush=True)
print("top:", [(t["name"], t["n_elections"]) for t in strict[:12]], flush=True)
print("DONE", flush=True)
