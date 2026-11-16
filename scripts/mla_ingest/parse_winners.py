import re, json
from pathlib import Path

OUT = Path("/tmp/opencode/winners_pages")
SLUGS = ["Haryana2024", "Haryana2019", "Haryana2014",
         "Odisha2024", "Odisha2019", "Odisha2014", "Orissa2009", "Orissa2004",
         "TamilNadu2026", "TamilNadu2021", "TamilNadu2016", "TamilNadu2011",
         "UttarPradesh2022", "UttarPradesh2017"]
STATE = {"Haryana": "Haryana", "Odisha": "Odisha", "Orissa": "Odisha",
         "TamilNadu": "Tamil Nadu", "UttarPradesh": "Uttar Pradesh"}

def amt(s):
    m = re.search(r"Rs[\s\xa0&nbsp;]*([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None

def clean_cons(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*\((SC|ST)\)\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*:.*$", "", s)
    return s

def party_name_from_slug(slug):
    m = re.match(r"([A-Za-z]+)(\d{4})$", slug)
    return STATE[m.group(1)]

allrows = []
issues = []
for slug in SLUGS:
    p = OUT / f"{slug}.html"
    html = p.read_text(encoding="utf-8")
    tables = re.findall(r"<table.*?</table>", html, re.S)
    tbl = None
    for t in tables:
        if "Constituency" in t and "Party" in t and "Candidate" in t:
            tbl = t
            break
    if tbl is None:
        issues.append((slug, "no winners table"))
        continue
    rows = re.findall(r"<tr.*?</tr>", tbl, re.S)
    header = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip().lower()
              for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0], re.S)]
    # map columns
    def idx(*keys):
        for i, h in enumerate(header):
            if all(k in h for k in keys):
                return i
        return None
    ci = {"cid": idx("candidate"), "cons": idx("constituency"), "party": idx("party"),
          "cases": idx("criminal"), "edu": idx("education"), "assets": idx("total"),
          "liab": idx("liabilit")}
    if any(v is None for v in ci.values()):
        issues.append((slug, f"missing column {ci} header={header}"))
        continue
    n = 0
    for row in rows[1:]:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        if len(cells) <= max(ci.values()):
            continue
        cid = re.search(r"candidate_id=(\d+)", cells[ci["cid"]])
        if not cid:
            continue
        txt = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
        raw_name = re.sub(r"\s+", " ", txt[ci["cid"]]).strip()
        name = raw_name
        cons = clean_cons(txt[ci["cons"]])
        allrows.append({
            "slug": slug, "cid": cid.group(1), "name": name, "myneta_name": raw_name,
            "cons": cons, "party": txt[ci["party"]], "cases": int(txt[ci["cases"]]) if txt[ci["cases"]].isdigit() else None,
            "edu": txt[ci["edu"]], "assets": amt(txt[ci["assets"]]), "liab_table": amt(txt[ci["liab"]]),
        })
        n += 1
    print(f"{slug:18s} rows={n:4d}", flush=True)
    if n == 0:
        issues.append((slug, "0 rows parsed"))

print("TOTAL", len(allrows), flush=True)
# duplicates within election (same constituency)
from collections import Counter
for slug in SLUGS:
    rs = [r for r in allrows if r["slug"] == slug]
    c = Counter(re.sub(r"[^A-Z0-9]", "", r["cons"].upper()) for r in rs)
    dup = {k: v for k, v in c.items() if v > 1}
    if dup:
        print("DUP", slug, dup, flush=True)
# sanity
print("party names:", sorted({r["party"] for r in allrows}))
print("null assets:", sum(1 for r in allrows if r["assets"] is None), flush=True)
print("null cases:", sum(1 for r in allrows if r["cases"] is None), flush=True)
print("issues:", issues, flush=True)
json.dump(allrows, open("/tmp/opencode/mla_winners_parsed.json", "w"), indent=1)
print("DONE", flush=True)
