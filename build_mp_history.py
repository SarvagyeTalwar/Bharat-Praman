import os
import sys
import re
import json
import csv
import random
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_DIR = str(Path(__file__).resolve().parent)
BACKUP_PATH = os.environ.get("MP_BACKUP_PATH", os.path.join(BASE_DIR, "instance01_backup.json"))
DATA_DIR = os.path.join(BASE_DIR, "data")
REVIEW_DIR = os.path.join(BASE_DIR, "review")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REVIEW_DIR, exist_ok=True)

ELECTIONS = {
    "ls2024": {"year": 2024, "name": "Lok Sabha 2024", "base_url": "https://myneta.info/LokSabha2024/"},
    "ls2019": {"year": 2019, "name": "Lok Sabha 2019", "base_url": "https://myneta.info/LokSabha2019/"},
    "ls2014": {"year": 2014, "name": "Lok Sabha 2014", "base_url": "https://myneta.info/ls2014/"},
    "ls2009": {"year": 2009, "name": "Lok Sabha 2009", "base_url": "https://myneta.info/ls2009/"},
    "ls2004": {"year": 2004, "name": "Lok Sabha 2004", "base_url": "https://myneta.info/LokSabha2004/"}
}

ECI_WINNER_REPORTS = {
    1996: "https://www.eci.gov.in/eci-backend/public/api/download?url=LMAhAK6sOPBp%2FNFF0iRfXbEB1EVSLT41NNLRjYNJJP1KivrUxbfqkDatmHy12e%2FzVx8fLfn2ReU7TfrqYobgIuTuCk2PkeBIxFg6I0eU5VPBleY%2F6DYULm%2FuXGBfnzIL0Ossb%2FOZWQZAC46suNmXLGuKAvNGAd8XYdXG8yyL7DmzUC9jIpIidmbrBMwxOPlx",
    1998: "https://www.eci.gov.in/eci-backend/public/api/download?url=LMAhAK6sOPBp%2FNFF0iRfXbEB1EVSLT41NNLRjYNJJP1KivrUxbfqkDatmHy12e%2FzVx8fLfn2ReU7TfrqYobgIotDO5N8hbvBFq8kBOnZ7sAHisPYaglbcR%2Bvju5fSVaOXf9Vty0jaav%2F5MHa3IhIjhiXm886AoS1DyVcNFs9r4o2myzOL0Zc4rsnVkw9Ae1D",
    1999: "https://www.eci.gov.in/eci-backend/public/api/download?url=LMAhAK6sOPBp%2FNFF0iRfXbEB1EVSLT41NNLRjYNJJP1KivrUxbfqkDatmHy12e%2FzVx8fLfn2ReU7TfrqYobgIkUhbtp1jYSDOEh0putYIbkiZnCZWMJAWv5FOo8QaiJzbCrRQmR%2FvdHfl2oiLCgpBOFiQQw1DFUOpqPxvwifJXEZ%2FmEz%2F%2FSc%2FlW4LA3Se2g1",
    2004: "https://www.eci.gov.in/eci-backend/public/api/download?url=LMAhAK6sOPBp%2FNFF0iRfXbEB1EVSLT41NNLRjYNJJP1KivrUxbfqkDatmHy12e%2FzVx8fLfn2ReU7TfrqYobgIsoA%2BXCXZnG6uydEggnVRZmGUymXljx52Ks9I6%2FE0G%2Bvsy%2FPaobJQQ78Lxwa6Q%2FNsnhE64UeF0L0Zo5BluaLP%2BtUpyGVFqMTjZoK%2FJnG4EEj",
    2009: "https://www.eci.gov.in/eci-backend/public/api/download?url=LMAhAK6sOPBp%2FNFF0iRfXbEB1EVSLT41NNLRjYNJJP1KivrUxbfqkDatmHy12e%2FzVx8fLfn2ReU7TfrqYobgIk2SLw8dD74slOmpqOdCj8L5%2BlgG43fk1CaEWC4oENNIACIp8CPnUwR1vn%2B28XTPUaAgAFPNHoNkfDcKGuKQy9WHcdD6%2BVMpFfPrNVrogJNg27hgDXebA6RvZ%2BePPPTjPg%3D%3D",
    2014: "https://www.eci.gov.in/eci-backend/public/api/download?url=LMAhAK6sOPBp%2FNFF0iRfXbEB1EVSLT41NNLRjYNJJP1KivrUxbfqkDatmHy12e%2FzVx8fLfn2ReU7TfrqYobgIkrAJg6TGS7zQszzZhDDjIvYSZp4N37kshmQDV6%2FSqRvgmbaAc%2BHq5lwt28N%2FSOL0YL1ssN1JVJfMASbvZSp4V6cgK3pshjWkc%2FjvrcLC7KwQqBtaSiqCprZFXWF1lgNsQ%3D%3D"
}

REQUEST_HEADERS = {"User-Agent": "BharatPraman/1.0 (historical election research; polite cache-first scraper)"}
ECI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
    "Referer": "https://www.eci.gov.in/"
}

def load_eci_winners():
    """Read successful candidates from official ECI statistical reports."""
    import pymupdf

    winners = {year: [] for year in ECI_WINNER_REPORTS}
    for year, url in ECI_WINNER_REPORTS.items():
        path = os.path.join(CACHE_DIR, f"eci_ls{year}.pdf")
        if not os.path.exists(path) or not os.path.getsize(path):
            response = requests.get(url, headers=ECI_HEADERS, timeout=60)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise ValueError(f"ECI returned a non-PDF response for {year}")
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(response.content)
        doc = pymupdf.open(path)
        for page in doc:
            if "LIST OF SUCCESSFUL CANDIDATE" not in page.get_text().upper():
                continue
            lines = {}
            for word in page.get_text("words"):
                x, y, _, _, token, *_ = word
                if year == 2009:
                    column = 0 if 130 <= x < 240 else 1 if 240 <= x < 400 else 2 if 400 <= x < 465 else None
                elif year == 2014:
                    column = 0 if 50 <= x < 140 else 1 if 200 <= x < 390 else 2 if 390 <= x < 440 else None
                else:
                    column = 0 if x < 255 else 1 if x < 465 else 2
                if column is None:
                    continue
                # Round to whole points so slightly offset table columns still join on a row.
                key = round(y)
                lines.setdefault(key, [[], [], []])[column].append(token)
            for cols in lines.values():
                name = " ".join(token for token in cols[1] if token.upper() not in {"GEN", "SC", "ST", "OBC"}).strip()
                party = " ".join(cols[2]).strip()
                constituency = re.sub(r"^\d+\.\s*", "", " ".join(cols[0])).strip()
                if not name or not constituency or not party or name.upper() == "LIST" or party.upper().startswith("OF SUCCESSFUL") or any(label in name.upper() for label in (
                    "WINNER", "PARTY", "PAGE", "LIST OF SUCCESSFUL", "ELECTION COMMISSION", "CONSTITUENCY"
                )):
                    continue
                if constituency.upper() == "SUBJECT" or party.upper() in {"NO.", "NO"}:
                    continue
                # Ignore headers and page furniture; party abbreviations appear in the right column.
                if len(party) > 14 or not re.fullmatch(r"[A-Za-z0-9()./& -]+", party):
                    continue
                if not re.search(r"[A-Za-z]", name) or not re.search(r"[A-Za-z]", party):
                    continue
                winners[year].append({
                    "name": name,
                    "constituency": constituency,
                    "party": party,
                    "source_url": url
                })
        doc.close()
        print(f"Loaded {len(winners[year])} successful candidate rows from ECI {year} report.")
    return winners

def fetch_page(url, path):
    """Return a cached page, fetching it once when absent."""
    if os.path.exists(path) and os.path.getsize(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    time.sleep(0.3)
    return html

def ensure_election_cache(election, info):
    """Cache winners by default; fetch every constituency only in full-download mode."""
    folder = os.path.join(CACHE_DIR, election)
    os.makedirs(folder, exist_ok=True)
    base_url = info["base_url"]
    index_path = os.path.join(folder, "index.html")
    try:
        index_html = fetch_page(base_url, index_path)
    except requests.RequestException as exc:
        print(f"Could not fetch index for {info['year']}: {exc}")
        index_html = ""
    # MyNeta uses this endpoint for the winner listing across its LS archives.
    winners_url = urljoin(base_url, "index.php?action=show_winners")
    winners_path = os.path.join(folder, "show_winners.html")
    if not (os.path.exists(winners_path) and os.path.getsize(winners_path)):
        try:
            fetch_page(winners_url, winners_path)
        except requests.RequestException as exc:
            print(f"Could not fetch winners page for {info['year']}: {exc}")

    if os.environ.get("MP_FETCH_ALL_CANDIDATES") != "1":
        return

    soup = BeautifulSoup(index_html, "html.parser")
    cons_urls = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "show_candidates" not in href or "constituency_id=" not in href:
            continue
        cid = re.search(r"constituency_id=(\d+)", href)
        if cid:
            cons_urls[cid.group(1)] = urljoin(base_url, href)
    def fetch_constituency(cid, url):
        path = os.path.join(folder, f"cons_{cid}.html")
        if os.path.exists(path) and os.path.getsize(path):
            return cid, None
        try:
            fetch_page(url, path)
            return cid, None
        except requests.RequestException as exc:
            return cid, exc

    # A small bounded pool avoids spending many minutes on sequential page requests.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_constituency, cid, url) for cid, url in cons_urls.items()]
        for future in as_completed(futures):
            cid, error = future.result()
            if error:
                print(f"Could not fetch {info['year']} constituency {cid}: {error}")

# --- Normalization Helpers ---
def compact(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def clean_tokens(s):
    if not s:
        return set()
    s = re.sub(r"\b(shri|smt|dr|prof|adv|advocate|mr|mrs|ms|winner|loser)\b\.?", "", s, flags=re.I)
    s = re.sub(r"[^a-zA-Z0-9\s]", " ", s)
    return set(s.lower().split())

def parse_money(text):
    if not text:
        return None
    t = text.replace("\xa0", " ").strip()
    if "Nil" in t or t == "0" or t == "Rs 0 ~" or t == "Nil ~":
        return 0
    m = re.search(r"Rs\s*([\d,]+)", t)
    return int(m.group(1).replace(",", "")) if m else None

# --- Load Sitting MPs from Backup ---
def load_sitting_mps():
    if not os.path.exists(BACKUP_PATH):
        # The generated 2024 history file is a portable fallback when the local graph export
        # is unavailable. It contains one baseline row for each sitting MP.
        history_path = os.path.join(DATA_DIR, "mp_history.jsonl")
        if not os.path.exists(history_path):
            raise FileNotFoundError(
                f"MP backup not found at {BACKUP_PATH}, and {history_path} is unavailable. "
                "Set MP_BACKUP_PATH to your graph backup JSON."
            )
        by_id = {}
        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("election_year") != 2024:
                    continue
                by_id[rec["mp_entity_id"]] = {
                    "entity_id": rec["mp_entity_id"], "name": rec.get("candidate_name", ""),
                    "myneta_name": rec.get("candidate_name", ""), "constituency": rec.get("constituency", ""),
                    "state": rec.get("state", ""), "party_name": rec.get("party", ""),
                    "age": rec.get("age"), "education": rec.get("education"),
                    "total_assets": rec.get("total_assets"), "movable_assets": rec.get("movable_assets"),
                    "immovable_assets": rec.get("immovable_assets"), "liabilities": rec.get("liabilities"),
                    "criminal_case_count": rec.get("criminal_cases_count", 0),
                    "myneta_id": (re.search(r"candidate_id=(\d+)", rec.get("source_url", "")) or [None, ""])[1]
                }
        if not by_id:
            raise ValueError(f"No 2024 MP baseline records found in {history_path}")
        print(f"Using {history_path} as the MP baseline (set MP_BACKUP_PATH to use a graph export).")
        return list(by_id.values())

    with open(BACKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cons_to_state = {}
    for r in data.get("relationships", []):
        if r.get("rel_type") == "IN_STATE":
            cons_to_state[r["source_properties"].get("entity_id")] = r["target_properties"].get("name")

    mp_map = {}
    for n in data["nodes"]:
        if "MP" in n.get("labels", []):
            eid = n["properties"].get("entity_id")
            mp_map[eid] = dict(n["properties"])

    for r in data.get("relationships", []):
        if r.get("rel_type") == "REPRESENTS":
            eid = r["source_properties"].get("entity_id")
            if eid in mp_map:
                target_eid = r["target_properties"].get("entity_id")
                mp_map[eid]["constituency"] = r["target_properties"].get("name")
                mp_map[eid]["state"] = cons_to_state.get(target_eid, "")

    return list(mp_map.values())

# --- Parse All Cached Candidates & Winners ---
def load_all_election_candidates():
    election_candidates = {e: [] for e in ELECTIONS}

    for e, info in ELECTIONS.items():
        # 2024 records are taken directly from the sitting-MP baseline below.
        if e == "ls2024":
            continue
        ensure_election_cache(e, info)
    
    # 1. From winners pages
    for e, info in ELECTIONS.items():
        base_url = info["base_url"]
        win_path = os.path.join(CACHE_DIR, e, "show_winners.html")
        if os.path.exists(win_path):
            html = open(win_path, "r", encoding="utf-8").read()
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")
            if len(tables) > 4:
                t = tables[4]
                for tr in t.find_all("tr")[1:]:
                    tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if len(tds) < 8:
                        continue
                    a = tr.find("a")
                    name = a.get_text(" ", strip=True) if a else tds[1]
                    href = a.get("href", "") if a else ""
                    cid = href.split("candidate_id=")[-1] if "candidate_id=" in href else ""
                    profile_url = urljoin(base_url, href) if href else ""
                    
                    election_candidates[e].append({
                        "name": re.sub(r"\(?\bWinner\b\)?", "", name, flags=re.I).strip(),
                        "constituency": tds[2],
                        "state": "", # inferred or enriched
                        "party": tds[3],
                        "criminal_cases": int(tds[4]) if tds[4].isdigit() else 0,
                        "education": tds[5],
                        "age": None,
                        "total_assets": parse_money(tds[6]),
                        "liabilities": parse_money(tds[7]),
                        "is_winner": True,
                        "candidate_id": cid,
                        "profile_url": profile_url
                    })

    # 2. From constituency cache files
    for e, info in ELECTIONS.items():
        base_url = info["base_url"]
        elec_cache = os.path.join(CACHE_DIR, e)
        if not os.path.exists(elec_cache):
            continue
        for f in os.listdir(elec_cache):
            if f.startswith("cons_") and f.endswith(".html"):
                path = os.path.join(elec_cache, f)
                html = open(path, "r", encoding="utf-8").read()
                soup = BeautifulSoup(html, "html.parser")
                
                # Cons and state from header
                cons, state = "", ""
                for h in soup.find_all(["h3", "h2", "title"]):
                    t = h.get_text(" ", strip=True)
                    m = re.search(r"List of Candidates\s*-\s*([^:]+)\s*:\s*([^(\n\r]+)", t)
                    if m:
                        cons, state = m.group(1).strip(), m.group(2).strip()
                        break
                    m_title = re.search(r"List of Candidates in\s*([^:]+)\s*:\s*([^(\n\r]+?)(?:Lok Sabha|\(|$)", t)
                    if m_title:
                        cons, state = m_title.group(1).strip(), m_title.group(2).strip()
                        break
                
                t = None
                for table in soup.find_all("table"):
                    th_texts = [th.get_text(" ", strip=True).lower() for th in table.find_all(["th", "td"])]
                    if any("candidate" in x for x in th_texts) and any("asset" in x for x in th_texts):
                        t = table
                        break
                if not t:
                    continue
                
                for tr in t.find_all("tr")[1:]:
                    tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if len(tds) < 5:
                        continue
                    a = tr.find("a")
                    name = a.get_text(" ", strip=True) if a else tds[1]
                    is_winner = "winner" in tds[1].lower()
                    href = a.get("href", "") if a else ""
                    cid = href.split("candidate_id=")[-1] if "candidate_id=" in href else ""
                    profile_url = urljoin(base_url, href) if href else ""
                    
                    party = tds[2] if len(tds) > 2 else ""
                    cases_m = re.search(r"\d+", tds[3]) if len(tds) > 3 else None
                    cases = int(cases_m.group()) if cases_m else 0
                    edu = tds[4] if len(tds) > 4 else ""
                    age = int(tds[5]) if len(tds) > 5 and tds[5].isdigit() else None
                    assets = parse_money(tds[6]) if len(tds) > 6 else None
                    liab = parse_money(tds[7]) if len(tds) > 7 else None
                    
                    clean_n = re.sub(r"\(?\bWinner\b\)?", "", name, flags=re.I).strip()
                    election_candidates[e].append({
                        "name": clean_n,
                        "constituency": cons,
                        "state": state,
                        "party": party,
                        "criminal_cases": cases,
                        "education": edu,
                        "age": age,
                        "total_assets": assets,
                        "liabilities": liab,
                        "is_winner": is_winner,
                        "candidate_id": cid,
                        "profile_url": profile_url
                    })

    # Deduplicate candidates per election by candidate_id or (name + cons)
    deduped = {}
    for e in ELECTIONS:
        seen = {}
        for c in election_candidates[e]:
            key = c["candidate_id"] if c["candidate_id"] else (compact(c["name"]), compact(c["constituency"]))
            if key not in seen or (c["total_assets"] is not None and seen[key]["total_assets"] is None):
                seen[key] = c
        deduped[e] = list(seen.values())
        print(f"Loaded {len(deduped[e])} total unique candidate records for {e}.")
    return deduped

def main():
    mps = load_sitting_mps()
    print(f"Loaded {len(mps)} sitting MPs from local backup.")

    eci_winners_by_year = load_eci_winners()
    eci_history_by_mp = {m["entity_id"]: [] for m in mps}
    for year, candidates in eci_winners_by_year.items():
        for mp in mps:
            mp_id = mp["entity_id"]
            known_names = [clean_tokens(mp.get(key, "")) for key in ("name", "myneta_name")]
            known_names = [tokens for tokens in known_names if len(tokens) >= 2]
            scored = []
            for candidate in candidates:
                cand_tokens = clean_tokens(candidate["name"])
                if len(cand_tokens) < 2:
                    continue
                score = max((len(tokens & cand_tokens) / len(tokens | cand_tokens) for tokens in known_names), default=0)
                if score >= 0.8:
                    same_seat = compact(mp.get("constituency", "")) == compact(candidate.get("constituency", ""))
                    scored.append((score, same_seat, candidate))
            if not scored:
                continue
            best_score = max(row[0] for row in scored)
            best = [row for row in scored if row[0] == best_score]
            same_seat = [row for row in best if row[1]]
            selected = same_seat if len(same_seat) == 1 else best
            if len(selected) != 1:
                continue
            candidate = selected[0][2]
            eci_history_by_mp[mp_id].append({
                "mp_entity_id": mp_id,
                "candidate_name": candidate["name"],
                "election": f"Lok Sabha {year}",
                "election_year": year,
                "constituency": candidate["constituency"],
                "party": candidate["party"],
                "is_winner": True,
                "record_type": "party_only_election_result",
                "match_method": "eci_name_match",
                "source_url": candidate["source_url"]
            })
    print("Matched ECI winner records by year: " + ", ".join(
        f"{year}: {sum(any(r['election_year'] == year for r in rows) for rows in eci_history_by_mp.values())} MPs"
        for year in sorted(eci_winners_by_year)
    ))
    
    candidates_by_elec = load_all_election_candidates()
    
    # Store outputs
    affidavit_nodes = []
    ambiguous_records = []
    seat_change_records = []
    
    mp_history_summary = {m["entity_id"]: {"mp": m, "affidavits": {}} for m in mps}
    
    for m in mps:
        m_eid = m["entity_id"]
        m_name = m.get("name", "")
        m_myneta_name = m.get("myneta_name", "")
        m_cons = m.get("constituency", "")
        m_state = m.get("state", "")
        m_party = m.get("party_name", "")
        
        m_comp = compact(m_name)
        m_my_comp = compact(m_myneta_name)
        m_tokens = clean_tokens(m_name) | clean_tokens(m_myneta_name)
        cons_comp = compact(m_cons)
        
        for e, einfo in ELECTIONS.items():
            eyear = einfo["year"]
            ename = einfo["name"]
            
            # 2024 Base Match directly from MP node properties
            if e == "ls2024":
                aff_id = f"affidavit_{m_eid}_{eyear}"
                rec = {
                    "affidavit_id": aff_id,
                    "mp_entity_id": m_eid,
                    "election": ename,
                    "election_year": eyear,
                    "candidate_name": m_myneta_name or m_name,
                    "constituency": m_cons,
                    "state": m_state,
                    "party": m_party,
                    "age": m.get("age"),
                    "education": m.get("education"),
                    "total_assets": m.get("total_assets"),
                    "movable_assets": m.get("movable_assets"),
                    "immovable_assets": m.get("immovable_assets"),
                    "liabilities": m.get("liabilities"),
                    "criminal_cases_count": m.get("criminal_case_count", 0),
                    "is_winner": True,
                    "source_url": f"https://myneta.info/LokSabha2024/candidate.php?candidate_id={m.get('myneta_id')}" if m.get("myneta_id") else "",
                    "match_method": "sitting_mp_exact",
                    "match_confidence": 1.0,
                    "status": "accepted",
                    "extracted_at": datetime.datetime.now().isoformat()
                }
                affidavit_nodes.append(rec)
                mp_history_summary[m_eid]["affidavits"][eyear] = rec
                continue
            
            # Older Elections (2019, 2014, 2009)
            cands = candidates_by_elec[e]
            matches = []
            
            for c in cands:
                c_name = c["name"]
                c_comp = compact(c_name)
                c_tokens = clean_tokens(c_name)
                c_cons_comp = compact(c["constituency"])
                
                # Exclude homonyms / distinct persons with extra paternal names
                if "valsamma" in c_name.lower() or "s/o" in c_name.lower():
                    continue
                
                # Check Name Match
                is_exact_name = (m_comp == c_comp) or (m_my_comp and m_my_comp == c_comp)
                is_token_match = len(m_tokens) >= 2 and (m_tokens == c_tokens or (m_tokens.issubset(c_tokens) and len(c_tokens - m_tokens) <= 1))
                is_name_match = is_exact_name or is_token_match
                
                if not is_name_match:
                    continue
                
                # Check Constituency
                is_same_seat = (cons_comp and (cons_comp in c_cons_comp or c_cons_comp in cons_comp))
                
                if is_same_seat:
                    mtype = "exact" if is_exact_name else "probable"
                    conf = 1.0 if is_exact_name else 0.85
                    matches.append((mtype, conf, c))
                else:
                    # Same person in different constituency
                    matches.append(("possible_seat_change", 0.75, c))

            if len(matches) == 1:
                mtype, conf, matched_cand = matches[0]
                if mtype in ["exact", "probable"]:
                    aff_id = f"affidavit_{m_eid}_{eyear}"
                    rec = {
                        "affidavit_id": aff_id,
                        "mp_entity_id": m_eid,
                        "election": ename,
                        "election_year": eyear,
                        "candidate_name": matched_cand["name"],
                        "constituency": matched_cand["constituency"] or m_cons,
                        "state": matched_cand["state"] or m_state,
                        "party": matched_cand["party"] or m_party,
                        "age": matched_cand["age"],
                        "education": matched_cand["education"],
                        "total_assets": matched_cand["total_assets"],
                        "movable_assets": None,
                        "immovable_assets": None,
                        "liabilities": matched_cand["liabilities"],
                        "criminal_cases_count": matched_cand["criminal_cases"],
                        "is_winner": matched_cand["is_winner"],
                        "source_url": matched_cand["profile_url"],
                        "match_method": mtype,
                        "match_confidence": conf,
                        "status": "accepted",
                        "extracted_at": datetime.datetime.now().isoformat()
                    }
                    affidavit_nodes.append(rec)
                    mp_history_summary[m_eid]["affidavits"][eyear] = rec
                elif mtype == "possible_seat_change":
                    seat_change_records.append({
                        "mp_name": m_name,
                        "mp_entity_id": m_eid,
                        "sitting_constituency": m_cons,
                        "sitting_state": m_state,
                        "election_year": eyear,
                        "candidate_name": matched_cand["name"],
                        "other_constituency": matched_cand["constituency"],
                        "other_state": matched_cand["state"],
                        "party": matched_cand["party"],
                        "source_url": matched_cand["profile_url"]
                    })
            elif len(matches) > 1:
                # Disambiguate: check if exactly one is in same seat
                seat_matches = [m_item for m_item in matches if m_item[0] in ["exact", "probable"]]
                if len(seat_matches) == 1:
                    mtype, conf, matched_cand = seat_matches[0]
                    aff_id = f"affidavit_{m_eid}_{eyear}"
                    rec = {
                        "affidavit_id": aff_id,
                        "mp_entity_id": m_eid,
                        "election": ename,
                        "election_year": eyear,
                        "candidate_name": matched_cand["name"],
                        "constituency": matched_cand["constituency"] or m_cons,
                        "state": matched_cand["state"] or m_state,
                        "party": matched_cand["party"] or m_party,
                        "age": matched_cand["age"],
                        "education": matched_cand["education"],
                        "total_assets": matched_cand["total_assets"],
                        "movable_assets": None,
                        "immovable_assets": None,
                        "liabilities": matched_cand["liabilities"],
                        "criminal_cases_count": matched_cand["criminal_cases"],
                        "is_winner": matched_cand["is_winner"],
                        "source_url": matched_cand["profile_url"],
                        "match_method": mtype,
                        "match_confidence": conf,
                        "status": "accepted",
                        "extracted_at": datetime.datetime.now().isoformat()
                    }
                    affidavit_nodes.append(rec)
                    mp_history_summary[m_eid]["affidavits"][eyear] = rec
                else:
                    for mtype, conf, cand_match in matches:
                        ambiguous_records.append({
                            "mp_name": m_name,
                            "mp_entity_id": m_eid,
                            "sitting_constituency": m_cons,
                            "election_year": eyear,
                            "candidate_name": cand_match["name"],
                            "matched_constituency": cand_match["constituency"],
                            "party": cand_match["party"],
                            "match_type": mtype,
                            "source_url": cand_match["profile_url"]
                        })

    # --- Derive party and affidavit changes from each MP's accepted election rows ---
    party_changes = []
    affidavit_changes = []
    for mp_eid, item in mp_history_summary.items():
        history = sorted(
            list(item["affidavits"].values()) + eci_history_by_mp.get(mp_eid, []),
            key=lambda row: row["election_year"]
        )
        for previous, current in zip(history, history[1:]):
            old_party = (previous.get("party") or "").strip()
            new_party = (current.get("party") or "").strip()
            if old_party and new_party and compact(old_party) != compact(new_party):
                party_changes.append({
                    "mp_entity_id": mp_eid,
                    "mp_name": item["mp"].get("name", ""),
                    "from_year": previous["election_year"],
                    "to_year": current["election_year"],
                    "from_party": old_party,
                    "to_party": new_party,
                    "from_constituency": previous.get("constituency", ""),
                    "to_constituency": current.get("constituency", ""),
                    "source_from": previous.get("source_url", ""),
                    "source_to": current.get("source_url", "")
                })

        affidavit_history = sorted(item["affidavits"].values(), key=lambda row: row["election_year"])
        for previous, current in zip(affidavit_history, affidavit_history[1:]):
            old_party = (previous.get("party") or "").strip()
            new_party = (current.get("party") or "").strip()
            change = {
                "mp_entity_id": mp_eid,
                "mp_name": item["mp"].get("name", ""),
                "from_year": previous["election_year"],
                "to_year": current["election_year"],
                "years_between": current["election_year"] - previous["election_year"],
                "from_party": old_party,
                "to_party": new_party,
                "from_constituency": previous.get("constituency", ""),
                "to_constituency": current.get("constituency", ""),
                "fields": {}
            }
            for field in ("total_assets", "liabilities", "criminal_cases_count"):
                before, after = previous.get(field), current.get(field)
                if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                    change["fields"][field] = {"from": before, "to": after, "change": after - before}
                    if field in ("total_assets", "liabilities"):
                        change["fields"][field]["percent_change"] = (
                            round((after - before) / before * 100, 2) if before else None
                        )
            if previous.get("education") != current.get("education"):
                change["fields"]["education"] = {
                    "from": previous.get("education"), "to": current.get("education")
                }
            change["source_from"] = previous.get("source_url", "")
            change["source_to"] = current.get("source_url", "")
            affidavit_changes.append(change)

    def write_jsonl(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    party_changes_path = os.path.join(DATA_DIR, "party_changes.jsonl")
    affidavit_changes_path = os.path.join(DATA_DIR, "affidavit_changes.jsonl")
    election_history_path = os.path.join(DATA_DIR, "mp_election_history.jsonl")
    write_jsonl(party_changes_path, party_changes)
    write_jsonl(affidavit_changes_path, affidavit_changes)
    write_jsonl(election_history_path, [
        *affidavit_nodes,
        *(record for rows in eci_history_by_mp.values() for record in rows)
    ])
    print(f"Wrote {len(party_changes)} party changes to {party_changes_path}")
    print(f"Wrote {len(affidavit_changes)} affidavit comparisons to {affidavit_changes_path}")
    print(f"Wrote current-MP election timeline to {election_history_path}")

    # --- Write Output JSONL ---
    jsonl_path = os.path.join(DATA_DIR, "mp_history.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for node in affidavit_nodes:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(affidavit_nodes)} total affidavit records to {jsonl_path}")

    # --- Write Review CSVs ---
    ambig_csv = os.path.join(REVIEW_DIR, "mp_ambiguous.csv")
    with open(ambig_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mp_name", "mp_entity_id", "sitting_constituency", "election_year", "candidate_name", "matched_constituency", "party", "match_type", "source_url"])
        writer.writeheader()
        writer.writerows(ambiguous_records)
    print(f"Wrote {len(ambiguous_records)} ambiguous records to {ambig_csv}")

    seat_csv = os.path.join(REVIEW_DIR, "possible_seat_changes.csv")
    with open(seat_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mp_name", "mp_entity_id", "sitting_constituency", "sitting_state", "election_year", "candidate_name", "other_constituency", "other_state", "party", "source_url"])
        writer.writeheader()
        writer.writerows(seat_change_records)
    print(f"Wrote {len(seat_change_records)} seat change suggestions to {seat_csv}")

    # --- Coverage Statistics ---
    counts = {i: 0 for i in range(len(ELECTIONS))}
    for m_eid, item in mp_history_summary.items():
        # count older affidavits (2004, 2009, 2014, 2019)
        older_affs = len([y for y in item["affidavits"] if y != 2024])
        counts[older_affs] += 1

    print("\n" + "=" * 60)
    print("AFFIDAVIT COVERAGE REPORT (AVAILABLE MYNETA YEARS: 2004, 2009, 2014, 2019, 2024)")
    print("=" * 60)
    for k in range(len(ELECTIONS)):
        pct = (counts[k] / len(mps)) * 100
        print(f"  MPs with {k} older affidavits: {counts[k]:3d} ({pct:5.1f}%)")
    total_with_history = len(mps) - counts[0]
    print(f"  Total MPs with prior electoral history: {total_with_history}/{len(mps)} ({(total_with_history/len(mps))*100:.1f}%)")

    # --- Random Spot Verification (30 Matches) ---
    accepted_matches = [a for a in affidavit_nodes if a["match_method"] in ["exact", "probable"] and a["election_year"] != 2024 and a["source_url"]]
    random.seed(42)
    sample_size = min(30, len(accepted_matches))
    sampled = random.sample(accepted_matches, sample_size)

    print("\n" + "=" * 110)
    print(f"RANDOM VERIFICATION OF {sample_size} OLDER ELECTION MATCHES")
    print("=" * 110)
    print(f"{'#':<3} | {'Election':<8} | {'MP Name':<24} | {'Constituency':<18} | {'Declared Assets (Rs)':<20} | {'Cases':<5} | {'Profile URL'}")
    print("-" * 110)
    for i, a in enumerate(sampled, 1):
        ass = f"Rs {a['total_assets']:,}" if a['total_assets'] is not None else "No Data"
        cases = str(a['criminal_cases_count']) if a['criminal_cases_count'] is not None else "-"
        print(f"{i:<3} | {a['election_year']:<8} | {a['candidate_name']:<24} | {a['constituency']:<18} | {ass:<20} | {cases:<5} | {a['source_url']}")

if __name__ == "__main__":
    main()
