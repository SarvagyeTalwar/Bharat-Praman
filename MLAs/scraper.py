import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))   # finds ../MLAs_Scraper.py

import re, os, json, time, requests
from MLAs_Scraper import parse
import re, os, json, time, requests
from MLAs_Scraper import parse

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
ONLY = None             # e.g. ["Goa"] to test one state; None = all states
SKIP = {"Tamil Nadu"}   # MyNeta's newest Tamil Nadu site is still 2021
sites = json.load(open("mla_sites.json"))

def get(url, path):
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    for attempt in range(6):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200:
                break
            print(f"  HTTP {r.status_code}, retrying: {url}")
        except requests.exceptions.RequestException as e:
            print(f"  network error ({type(e).__name__}), retry {attempt + 1}/6")
        time.sleep(2 * 2 ** attempt)        # waits 2, 4, 8, 16, 32, 64 seconds
    else:
        raise RuntimeError(f"gave up on {url}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(r.text)
    time.sleep(1.5)
    return r.text

def clean(rec, state, slug, year):
    rec["state"] = state
    c = rec["constituency"]
    rec["by_election"] = "BYE" in c.upper()
    rec["constituency"] = re.sub(r"\s*(:|\().*$", "", c).strip()
    rec["slug"], rec["year"] = slug, year
    return rec

out, gaps = [], []
for state, info in sites.items():
    if (ONLY and state not in ONLY) or state in SKIP:
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

    # second pass: constituencies the winners list skipped
    covered = set()
    for k in have:
        m = re.search(r"show_candidates&(?:amp;)?constituency_id=(\d+)",
                      open(f"{d}/{k}.html", encoding="utf-8").read())
        if m: covered.add(int(m.group(1)))
    for c in range(1, (max(covered) if covered else 0) + 15):
        if c in covered:
            continue
        page = get(base + f"index.php?action=show_candidates&constituency_id={c}", f"{d}/_cons_{c}.html")
        cand_ids = list(dict.fromkeys(re.findall(r"candidate_id=(\d+)", page)))
        if not cand_ids:
            continue
        for k in cand_ids:
            html = get(base + f"candidate.php?candidate_id={k}", f"{d}/{k}.html")
            if "(Winner)" in html:
                if k not in have:
                    try:
                        out.append(clean(parse(k, html), state, slug, year)); have.add(k)
                        print("  extra winner", out[-1]["name"], "|", out[-1]["constituency"])
                    except Exception as e:
                        print("  FAILED", k, repr(e))
                break
        else:   # candidates exist but none is tagged Winner
            t = re.search(r"<title>(.*?)</title>", page, re.S)
            gaps.append({"state": state, "slug": slug, "constituency_id": c,
                         "page": t.group(1).strip() if t else None})

    json.dump(out, open("mla_parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(gaps, open("mla_gaps.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(state, "done, total so far", len(out), "| seats without a winner so far", len(gaps))