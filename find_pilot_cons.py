import os, sys, re
sys.path.append(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman")
from scraper import fetch_url, ELECTIONS
from bs4 import BeautifulSoup

target_names = ["gandhinagar", "lucknow", "new delhi", "rae bareli", "amethi", "wayanad", "bahraich"]

for elec, base in ELECTIONS.items():
    print(f"=== {elec} ===")
    html = fetch_url(base, elec, "index.html", delay=1.0)
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        if "show_candidates&constituency_id=" in href:
            text_clean = text.lower()
            for t in target_names:
                if t in text_clean and href not in found:
                    found.add(href)
                    cid = href.split("=")[-1]
                    print(f"  {text} -> cid={cid} ({href})")
