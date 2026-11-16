import os, sys, re, json
sys.path.append(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman")
from scraper import fetch_url, parse_constituency_page, ELECTIONS
from bs4 import BeautifulSoup

# Specific constituencies to scrape for the 5 pilot MPs
# Amit Shah: Gandhinagar (2024: 117, 2019: 548, 2014: 271, 2009: 271)
# Rajnath Singh: Lucknow (2024: 490, 2019: 913, 2014: 347), Ghaziabad 2009
# Bansuri Swaraj: New Delhi (2024: 106, 2019: 537, 2014: 454, 2009: 454)
# Rahul Gandhi: Rae Bareli (2024: 491, 2019: 914), Wayanad (2024: 208, 2019: 634), Amethi (2024: 493, 2019: 915, 2014: 240, 2009: 240)
# Anand Kumar: Bahraich (2024: 488, 2019: 921, 2014: 356, 2009: 356)

PILOT_PAGES = {
    "ls2024": [117, 490, 106, 491, 208, 493, 488],
    "ls2019": [548, 913, 537, 914, 634, 915, 921],
    "ls2014": [271, 347, 454, 348, 45, 240, 356],
    "ls2009": [271, 347, 454, 348, 45, 240, 356]
}

# Also find Ghaziabad in 2009 for Rajnath Singh
def get_cid_for(elec, keyword):
    html = fetch_url(ELECTIONS[elec], elec, "index.html", delay=1.0)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        if "action=show_candidates&constituency_id=" in a.get("href", ""):
            if keyword.lower() in a.get_text().lower():
                return int(a.get("href").split("=")[-1])
    return None

gz_2009 = get_cid_for("ls2009", "ghaziabad")
if gz_2009:
    PILOT_PAGES["ls2009"].append(gz_2009)

# Fetch and parse all candidate rows
all_candidates_by_elec = {}
for elec, cids in PILOT_PAGES.items():
    all_candidates_by_elec[elec] = []
    base_url = ELECTIONS[elec]
    for cid in cids:
        url = f"{base_url}index.php?action=show_candidates&constituency_id={cid}"
        html = fetch_url(url, elec, f"cons_{cid}.html", delay=1.5)
        recs = parse_constituency_page(html, base_url)
        all_candidates_by_elec[elec].extend(recs)

# Normalization helper
def normalize_name(s):
    if not s:
        return ""
    # remove honorifics
    s = re.sub(r"\b(shri|smt|dr|prof|adv|advocate|mr|mrs|ms)\b\.?", "", s, flags=re.I)
    # remove punctuation
    s = re.sub(r"[^a-zA-Z0-9\s]", " ", s)
    # collapse whitespace
    return " ".join(s.lower().split())

def match_person(target_name, target_cons, elec_records):
    norm_target = normalize_name(target_name)
    target_parts = set(norm_target.split())
    
    matches = []
    for r in elec_records:
        norm_r = normalize_name(r["name"])
        r_parts = set(norm_r.split())
        
        # Check exact or strong token overlap
        if norm_target == norm_r or (target_parts and target_parts.issubset(r_parts)) or (r_parts and r_parts.issubset(target_parts)):
            same_cons = (target_cons.lower() in r["constituency"].lower() or r["constituency"].lower() in target_cons.lower())
            status = "exact" if norm_target == norm_r and same_cons else ("probable" if same_cons else "seat_change")
            matches.append((status, r))
    return matches

# Pilot 5 targets
targets = [
    {"name": "Amit Shah", "cons": "Gandhinagar", "state": "Gujarat", "role": "Home Minister (Sitting MP)"},
    {"name": "Rajnath Singh", "cons": "Lucknow", "state": "Uttar Pradesh", "role": "Cabinet Minister (Defence)"},
    {"name": "Bansuri Swaraj", "cons": "New Delhi", "state": "Delhi", "role": "Single-Term MP (First elected 2024)"},
    {"name": "Rahul Gandhi", "cons": "Rae Bareli", "state": "Uttar Pradesh", "role": "Seat / Constituency Switcher"},
    {"name": "Anand Kumar", "cons": "Bahraich", "state": "Uttar Pradesh", "role": "Common Name Target"}
]

print("=" * 110)
print("PILOT MATCH RESULTS: 5 SITTING MPs ACROSS PREVIOUS ELECTIONS (2024, 2019, 2014, 2009)")
print("=" * 110)

pilot_output = {}

for t in targets:
    tname = t["name"]
    tcons = t["cons"]
    print(f"\n>>> MP: {tname} [{t['role']}] | Base 2024 Seat: {tcons} ({t['state']})")
    print("-" * 110)
    print(f"{'Election':<8} | {'Match Type':<12} | {'Name on MyNeta':<22} | {'Party':<10} | {'Constituency':<16} | {'Assets (Rs)':<16} | {'Liab (Rs)':<14} | {'Cases':<5} | {'Profile URL'}")
    print("-" * 110)
    
    pilot_output[tname] = []
    
    for elec in ["ls2024", "ls2019", "ls2014", "ls2009"]:
        recs = all_candidates_by_elec[elec]
        matches = match_person(tname, tcons, recs)
        if matches:
            for mtype, mrec in matches:
                assets_fmt = f"Rs {mrec['total_assets']:,}"
                liab_fmt = f"Rs {mrec['liabilities']:,}"
                print(f"{elec.upper():<8} | {mtype:<12} | {mrec['name']:<22} | {mrec['party']:<10} | {mrec['constituency']:<16} | {assets_fmt:<16} | {liab_fmt:<14} | {mrec['criminal_cases']:<5} | {mrec['profile_url']}")
                pilot_output[tname].append({
                    "election": elec, "match_type": mtype, "data": mrec
                })
        else:
            print(f"{elec.upper():<8} | {'NO AFFIDAVIT':<12} | {'-':<22} | {'-':<10} | {'-':<16} | {'-':<16} | {'-':<14} | {'-':<5} | (missing / did not contest)")
            pilot_output[tname].append({"election": elec, "match_type": "none", "data": None})

os.makedirs("data", exist_ok=True)
with open("data/pilot_results.json", "w", encoding="utf-8") as f:
    json.dump(pilot_output, f, indent=2, ensure_ascii=False)
print("\nPilot results saved to data/pilot_results.json")
