import json, re
d = json.load(open("myneta_parsed.json", encoding="utf-8"))
for r in d:
    if r["state"] is None:
        m = re.match(r"^(.*?)\s*\((DELHI \(NCT\)|[^()]+)\)$", r["constituency"])
        if m:
            r["constituency"] = m.group(1).strip()
            r["state"] = "NCT of Delhi" if "DELHI" in m.group(2) else m.group(2).title()
json.dump(d, open("myneta_parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print([(r["name"], r["constituency"], r["state"]) for r in d if "DELHI" in (r["state"] or "").upper()])
print(sum(1 for r in d if r["state"] is None), "records still without a state")