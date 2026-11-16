import os, sys, json
sys.path.append(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman")
from scraper import fetch_url, parse_constituency_page, ELECTIONS

elec = "ls2024"
url = "https://myneta.info/LokSabha2024/index.php?action=show_candidates&constituency_id=5"
html = fetch_url(url, elec, "cons_5.html", delay=1.0)
recs = parse_constituency_page(html, ELECTIONS[elec])

print(f"LIVE URL: {url}")
print(f"Constituency: {recs[0]['constituency']}, State: {recs[0]['state']}")
print("-" * 120)
print(f"{'#':<3} | {'Status':<7} | {'Candidate Name':<30} | {'Party':<24} | {'Age':<4} | {'Cases':<5} | {'Assets':<18} | {'Liabilities':<18} | {'Education'}")
print("-" * 120)
for i, r in enumerate(recs[:10], 1):
    status = "WINNER" if r["is_winner"] else ""
    assets_str = f"Rs {r['total_assets']:,}"
    liab_str = f"Rs {r['liabilities']:,}"
    print(f"{i:<3} | {status:<7} | {r['name']:<30} | {r['party']:<24} | {str(r['age']):<4} | {r['criminal_cases']:<5} | {assets_str:<18} | {liab_str:<18} | {r['education']}")
