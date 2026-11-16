import os, sys, re, json
sys.path.append(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman")
from scraper import fetch_url, parse_constituency_page, parse_money, ELECTIONS
from bs4 import BeautifulSoup

def compact(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def normalize_name(s):
    if not s:
        return ""
    s = re.sub(r"\b(shri|smt|dr|prof|adv|advocate|mr|mrs|ms)\b\.?", "", s, flags=re.I)
    s = re.sub(r"[^a-zA-Z0-9\s]", " ", s)
    return " ".join(s.lower().split())

def enrich_from_profile(profile_url, elec_code, cid):
    if not profile_url or not cid:
        return None, None
    html = fetch_url(profile_url, elec_code, f"cand_{cid}.html", delay=1.0)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).replace("\xa0", " ")
    m_ass = re.search(r"Assets:\s*Rs\s*([\d,]+)", text)
    m_lia = re.search(r"Liabilities:\s*(?:Rs\s*([\d,]+)|(Nil))", text)
    ass = int(m_ass.group(1).replace(",", "")) if m_ass else None
    if m_lia:
        lia = int(m_lia.group(1).replace(",", "")) if m_lia.group(1) else 0
    else:
        lia = None
    return ass, lia

# Pre-cached constituency pages for the 5 pilot targets
PILOT_PAGES = {
    "ls2024": [117, 490, 106, 491, 208, 493, 488],
    "ls2019": [548, 913, 537, 914, 634, 915, 921],
    "ls2014": [271, 347, 454, 348, 45, 240, 356],
    "ls2009": [271, 347, 454, 348, 45, 240, 356, 328] # 328 is Ghaziabad 2009
}

all_candidates = {}
for elec, cids in PILOT_PAGES.items():
    all_candidates[elec] = []
    base_url = ELECTIONS[elec]
    for cid in cids:
        url = f"{base_url}index.php?action=show_candidates&constituency_id={cid}"
        html = fetch_url(url, elec, f"cons_{cid}.html", delay=1.0)
        recs = parse_constituency_page(html, base_url)
        all_candidates[elec].extend(recs)

targets = [
    {"name": "Amit Shah", "cons": "Gandhinagar", "state": "Gujarat", "role": "Home Minister (Sitting MP)"},
    {"name": "Rajnath Singh", "cons": "Lucknow", "state": "Uttar Pradesh", "role": "Cabinet Minister (Defence)"},
    {"name": "Bansuri Swaraj", "cons": "New Delhi", "state": "Delhi", "role": "Single-Term MP (First elected 2024)"},
    {"name": "Rahul Gandhi", "cons": "Rae Bareli", "state": "Uttar Pradesh", "role": "Seat / Constituency Switcher"},
    {"name": "Anand Kumar", "cons": "Bahraich", "state": "Uttar Pradesh", "role": "Common Name Target"}
]

pilot_results = []

for t in targets:
    tname = t["name"]
    tcons = t["cons"]
    tstate = t["state"]
    t_comp = compact(tname)
    
    mp_block = {"mp": tname, "role": t["role"], "base_constituency": tcons, "affidavits": []}
    
    for elec in ["ls2024", "ls2019", "ls2014", "ls2009"]:
        recs = all_candidates[elec]
        found_matches = []
        for r in recs:
            r_comp = compact(r["name"])
            r_norm = normalize_name(r["name"])
            
            # Exact or compact match
            is_same_person = (t_comp == r_comp) or (t_comp in r_comp and len(t_comp) > 7)
            
            # Disambiguate common/partial matches like "Rahul Gandhi K E S/O Valsamma"
            if is_same_person and "valsamma" in r["name"].lower():
                found_matches.append(("ambiguous_homonym", r))
                continue
            if tname == "Anand Kumar" and "raaj kumar" in r["name"].lower():
                found_matches.append(("ambiguous_homonym", r))
                continue

            if is_same_person:
                same_cons = (tcons.lower() in r["constituency"].lower() or r["constituency"].lower() in tcons.lower())
                status = "exact" if same_cons else "seat_change"
                
                # Check if values need enrichment from profile
                if r["total_assets"] == 0 and r["profile_url"]:
                    ass, lia = enrich_from_profile(r["profile_url"], elec, r["candidate_id"])
                    if ass is not None:
                        r["total_assets"] = ass
                    if lia is not None:
                        r["liabilities"] = lia
                
                found_matches.append((status, r))
                
        if found_matches:
            for status, r in found_matches:
                mp_block["affidavits"].append({
                    "election": elec.upper(),
                    "match_type": status,
                    "candidate_name": r["name"],
                    "party": r["party"],
                    "constituency": r["constituency"],
                    "state": r["state"],
                    "total_assets": r["total_assets"],
                    "liabilities": r["liabilities"],
                    "criminal_cases": r["criminal_cases"],
                    "education": r["education"],
                    "profile_url": r["profile_url"]
                })
        else:
            mp_block["affidavits"].append({
                "election": elec.upper(),
                "match_type": "none",
                "candidate_name": "None",
                "party": "-",
                "constituency": "-",
                "state": "-",
                "total_assets": None,
                "liabilities": None,
                "criminal_cases": None,
                "education": "-",
                "profile_url": None
            })
    pilot_results.append(mp_block)

with open(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman\data\pilot_output_refined.json", "w", encoding="utf-8") as f:
    json.dump(pilot_results, f, indent=2, ensure_ascii=False)

print("Refined Pilot Execution Complete.")
