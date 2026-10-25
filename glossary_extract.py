"""Extract acronyms/short forms from MHA and MoE chunks into JSON glossaries.

Pattern-based (free, local): finds 'Full Name (ABC)' and normalizes.
Outputs glossary_mha.json, glossary_moe.json, glossary_global.json.
"""
import os, re, json
from collections import Counter, defaultdict
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv('BACKEND/.env')
URI = (os.getenv('NEO4J_URI1') or '').strip()
d = GraphDatabase.driver(URI, auth=(os.getenv('NEO4J_USERNAME1'), os.getenv('NEO4J_PASSWORD1')),
                         notifications_min_severity='OFF')
DB = os.getenv('NEO4J_DATABASE1')
OUT = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")

# Full Name (ABC) — allow 1-8 word expansions
PAT = re.compile(r"([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Za-z0-9&.\-]+){0,7})\s*\(([A-Z][A-Z0-9&.\-]{1,9})\)")

def clean(s):
    return re.sub(r"\s+", " ", s).strip(" .,;:-")

def extract(chunks):
    seen = Counter()          # acronym -> count
    expansions = defaultdict(Counter)  # acronym -> expansion -> count
    for text in chunks:
        for m in PAT.finditer(text):
            exp, acr = clean(m.group(1)), m.group(2)
            if len(exp) < 4 or len(exp.split()) > 8:
                continue
            # avoid junk like 'Page (A)'
            if exp.lower() in {"page", "figure", "table", "source", "annexure", "chapter"}:
                continue
            seen[acr] += 1
            expansions[acr][exp] += 1
    out = {}
    for acr, cnt in seen.items():
        best = expansions[acr].most_common(1)[0][0]
        out[acr] = {"expansion": best, "count": cnt,
                    "variants": [e for e, _ in expansions[acr].most_common(3)]}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["count"]))

with d.session(database=DB) as s:
    mha = [r["t"] for r in s.run("MATCH (c:MHAChunk) RETURN c.text AS t")]
    # Education chunks are :Chunk but exclude MHA (MHAChunk is a different label)
    moe = [r["t"] for r in s.run("MATCH (c:Chunk) RETURN c.text AS t")]
d.close()

print("MHA chunks:", len(mha), "| MoE chunks:", len(moe))
g_mha = extract(mha)
g_moe = extract(moe)
combined = {}
for g in (g_mha, g_moe):
    for k, v in g.items():
        combined.setdefault(k, {"expansion": v["expansion"], "count": 0, "variants": []})
        combined[k]["count"] += v["count"]
combined = dict(sorted(combined.items(), key=lambda kv: -kv[1]["count"]))

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "glossary_mha.json").write_text(json.dumps(g_mha, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "glossary_moe.json").write_text(json.dumps(g_moe, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "glossary_global.json").write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\nMHA unique acronyms: {len(g_mha)} | MoE: {len(g_moe)} | combined: {len(combined)}")
print("\nTop MHA:")
for k, v in list(g_mha.items())[:20]:
    print(f"  {k}: {v['expansion']} ({v['count']})")
print("\nTop MoE:")
for k, v in list(g_moe.items())[:20]:
    print(f"  {k}: {v['expansion']} ({v['count']})")
print("\nAmbiguous (same acronym, different top expansion across ministries):")
for k in combined:
    if k in g_mha and k in g_moe and g_mha[k]["expansion"] != g_moe[k]["expansion"]:
        print(f"  {k}: MHA='{g_mha[k]['expansion']}' vs MoE='{g_moe[k]['expansion']}'")
print("\nSaved glossaries to", OUT)
