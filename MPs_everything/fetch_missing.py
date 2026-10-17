import re, json, os, time, requests
from MLAs_Scraper import fetch, parse, BASE, H, CACHE

CONS_CACHE = "myneta_cons_cache"   # separate folder so the scraper's cache stays clean
os.makedirs(CONS_CACHE, exist_ok=True)

def fetch_cons(cid):
    path = f"{CONS_CACHE}/{cid}.html"
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    url = BASE + f"index.php?action=show_candidates&constituency_id={cid}"
    html = requests.get(url, headers=H, timeout=30).text
    open(path, "w", encoding="utf-8").write(html)
    time.sleep(1.5)
    return html

# 1. constituency ids already covered by your 486 cached profiles
covered = set()
for f in os.listdir(CACHE):
    if f.endswith(".html"):
        html = open(f"{CACHE}/{f}", encoding="utf-8").read()
        m = re.search(r"show_candidates&constituency_id=(\d+)", html)
        if m:
            covered.add(int(m.group(1)))
print(len(covered), "constituencies covered, max id", max(covered))

# 2. try every other id up to a safe upper bound
todo = [c for c in range(1, max(covered) + 30) if c not in covered]
print(len(todo), "constituency ids to check")

parsed = json.load(open("myneta_parsed.json", encoding="utf-8"))
have = {d["myneta_id"] for d in parsed}
found = []

for cid in todo:
    page = fetch_cons(cid)
    cand_ids = list(dict.fromkeys(re.findall(r"candidate_id=(\d+)", page)))
    if not cand_ids:
        continue                      # not a real constituency id
    for k in cand_ids:
        html = fetch(k)               # cached in myneta_cache, same as before
        if "(Winner)" in html:
            if k not in have:
                rec = parse(k, html)
                parsed.append(rec); have.add(k); found.append(rec)
                print("WINNER", rec["name"], "|", rec["constituency"], "|", rec["state"])
            break

json.dump(parsed, open("myneta_parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(len(found), "new winners added; total", len(parsed))