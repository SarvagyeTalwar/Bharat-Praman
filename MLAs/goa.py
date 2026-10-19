import re, os
from bs4 import BeautifulSoup

d = "cache/goa2022"
for cid in [26, 30, 43]:
    page = open(f"{d}/_cons_{cid}.html", encoding="utf-8").read()
    soup = BeautifulSoup(page, "html.parser")
    print(f"\n=== constituency id {cid} | title: {soup.title.get_text(strip=True) if soup.title else None}")
    for k in dict.fromkeys(re.findall(r"candidate_id=(\d+)", page)):
        p = f"{d}/{k}.html"
        if not os.path.exists(p):
            print("  (not cached)", k); continue
        s = BeautifulSoup(open(p, encoding="utf-8").read(), "html.parser")
        h2 = next((h.get_text(" ", strip=True) for h in s.find_all("h2") if "(Winner)" in h.get_text() or "(Loser)" in h.get_text()), None)
        h5 = s.find("h5").get_text(" ", strip=True) if s.find("h5") else None
        print("  ", k, "|", h2, "|", h5)