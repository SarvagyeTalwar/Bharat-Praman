import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))   # lets it find ../MLAs_Scraper.py
import re, os, json, time, requests
from MLAs_Scraper import parse

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
ONLY = ["Goa"]          # test one small state first; set to None for all
sites = json.load(open("mla_sites.json"))

def get(url, path):
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    html = requests.get(url, headers=H, timeout=30).text
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(html)
    time.sleep(1.5)
    return html

def clean(rec, state, slug, year):
    rec["state"] = state                      # trust our own state name, not the page header
    rec["constituency"] = re.sub(r"\s*\(.*$", "", rec["constituency"]).strip()   # drop (SC)/(ST)
    rec["slug"], rec["year"] = slug, year
    return rec

out = []
for state, info in sites.items():
    if ONLY and state not in ONLY:
        continue
    slug, year = info["slug"], info["year"]
    base, d = f"https://www.myneta.info/{slug}/", f"cache/{slug}"

    wl = get(base + "index.php?action=show_winners&sort=default", f"{d}/_winners.html")
    ids = list(dict.fromkeys(re.findall(r"candidate_id=(\d+)", wl)))
    print(state, slug, len(ids), "winners listed")

    have = set()
    for k in ids:
        try:
            html = get(base + f"candidate.php?candidate_id={k}", f"{d}/{k}.html")
            out.append(clean(parse(k, html), state, slug, year)); have.add(k)
        except Exception as e:
            print("  FAILED", k, repr(e))

    # second pass: constituencies the winners list skipped (same trick as fetch_missing.py)
    covered = set()
    for k in have:
        m = re.search(r"show_candidates&(?:amp;)?constituency_id=(\d+)",
                      open(f"{d}/{k}.html", encoding="utf-8").read())
        if m: covered.add(int(m.group(1)))
    for c in range(1, (max(covered) if covered else 0) + 15):
        if c in covered:
            continue
        page = get(base + f"index.php?action=show_candidates&constituency_id={c}", f"{d}/_cons_{c}.html")
        for k in dict.fromkeys(re.findall(r"candidate_id=(\d+)", page)):
            html = get(base + f"candidate.php?candidate_id={k}", f"{d}/{k}.html")
            if "(Winner)" in html:
                if k not in have:
                    out.append(clean(parse(k, html), state, slug, year)); have.add(k)
                    print("  extra winner", out[-1]["name"], "|", out[-1]["constituency"])
                break

    json.dump(out, open("mla_parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(state, "done, total so far", len(out))