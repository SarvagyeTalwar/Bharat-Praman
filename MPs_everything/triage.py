import json, re
from difflib import SequenceMatcher

r = json.load(open("review.json", encoding="utf-8"))
mps = r["unmatched_mps_in_my_db"]
unused = r["myneta_records_not_matched_to_anyone"]

def n(s): return re.sub(r"[^a-z0-9]", "", re.sub(r"\((sc|st)\)", "", (s or "").lower()))
def sim(a, b): return SequenceMatcher(None, n(a), n(b)).ratio()

suggest, nomatch = {}, []
for m in mps:
    p = m["mine"]
    best, bs = None, 0
    for u in unused:
        s = sim(p["cons"], u["constituency"]) * 0.7 + sim(p["state"], u["state"]) * 0.3
        if s > bs: best, bs = u, s
    if best and bs >= 0.8:
        suggest[p["id"]] = best["myneta_id"]
        print(f'CHECK  {p["name"]} ({p["cons"]}, {p["state"]})  <->  {best["name"]} ({best["constituency"]}, {best["state"]})  [{bs:.2f}]')
    else:
        nomatch.append(p)

print(f"\n{len(suggest)} suggested pairs, {len(nomatch)} MPs with no MyNeta page in the 486")
for p in nomatch:
    print("MISSING", p["name"], "|", p["cons"], "|", p["state"])

json.dump(suggest, open("overrides.json", "w"), indent=2)