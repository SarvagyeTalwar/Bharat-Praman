import os
import re
import time
import json
import logging
import urllib.request
import urllib.error
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
MYNETA_DIR = os.path.join(BASE_DIR, "data", "myneta")
LOG_FILE = os.path.join(BASE_DIR, "data", "scraper.log")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MYNETA_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

USER_AGENT = "BharatPraman-Research-Bot/1.0 (+academic-mp-affidavits; polite-research)"

ELECTIONS = {
    "ls2024": "https://myneta.info/LokSabha2024/",
    "ls2019": "https://myneta.info/LokSabha2019/",
    "ls2014": "https://myneta.info/ls2014/",
    "ls2009": "https://myneta.info/ls2009/"
}

def parse_money(text):
    if not text:
        return 0
    t = text.replace("\xa0", " ").strip()
    if "Nil" in t or t == "0" or t == "Rs 0 ~" or t == "Nil ~":
        return 0
    m = re.search(r"Rs\s*([\d,]+)", t)
    return int(m.group(1).replace(",", "")) if m else 0

def fetch_url(url, election_code, filename, delay=2.5):
    elec_cache = os.path.join(CACHE_DIR, election_code)
    os.makedirs(elec_cache, exist_ok=True)
    cache_path = os.path.join(elec_cache, filename)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            time.sleep(delay)
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.getcode()
                html = resp.read().decode("utf-8", errors="ignore")
                logging.info(f"FETCHED {url} -> {code}")
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html)
                return html
        except urllib.error.HTTPError as e:
            logging.error(f"HTTPError {e.code} for {url} attempt {attempt+1}")
            if e.code in [403, 429]:
                logging.critical(f"Rate limited or forbidden: {e.code} on {url}. Aborting.")
                raise RuntimeError(f"Immediate stop on {e.code}: {url}")
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            logging.error(f"Network error {e} for {url} attempt {attempt+1}")
            time.sleep(3 * (attempt + 1))

    raise RuntimeError(f"Failed to fetch {url} after retries")

def get_constituency_urls(election_code):
    base_url = ELECTIONS[election_code]
    html = fetch_url(base_url, election_code, "index.html")
    soup = BeautifulSoup(html, "html.parser")
    
    cons_map = {}
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if "action=show_candidates&constituency_id=" in href:
            full_url = urljoin(base_url, href)
            m = re.search(r"constituency_id=(\d+)", href)
            if m:
                cid = m.group(1)
                cons_map[cid] = full_url
    return cons_map

def parse_constituency_page(html, base_url, default_cons="", default_state=""):
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract constituency and state from header
    cons = default_cons
    state = default_state
    
    for h in soup.find_all(["h3", "h2", "title"]):
        t = h.get_text(" ", strip=True)
        m = re.search(r"List of Candidates\s*-\s*([^:]+)\s*:\s*([^(\n\r]+)", t)
        if m:
            cons = m.group(1).strip()
            state = m.group(2).strip()
            break
        m_title = re.search(r"List of Candidates in\s*([^:]+)\s*:\s*([^(\n\r]+?)(?:Lok Sabha|\(|$)", t)
        if m_title:
            cons = m_title.group(1).strip()
            state = m_title.group(2).strip()
            break

    # Find table
    t = None
    for table in soup.find_all("table"):
        th_texts = [th.get_text(" ", strip=True).lower() for th in table.find_all(["th", "td"])]
        if any("candidate" in x for x in th_texts) and any("asset" in x for x in th_texts):
            t = table
            break

    if not t:
        return []

    records = []
    rows = t.find_all("tr")
    for tr in rows[1:]:
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < 5:
            continue
        
        a = tr.find("a")
        cand_name = a.get_text(" ", strip=True) if a else tds[1]
        raw_cand_cell = tds[1]
        is_winner = "winner" in raw_cand_cell.lower()
        
        # Strip "(Winner)" or "Winner" from candidate name if present
        cand_name = re.sub(r"\(?\bWinner\b\)?", "", cand_name, flags=re.I).strip()
        
        href = a.get("href", "") if a else ""
        cid_m = re.search(r"candidate_id=(\d+)", href)
        cid = cid_m.group(1) if cid_m else ""
        profile_url = urljoin(base_url, href) if href else ""
        
        party = tds[2] if len(tds) > 2 else ""
        cases_m = re.search(r"\d+", tds[3]) if len(tds) > 3 else None
        cases = int(cases_m.group()) if cases_m else 0
        edu = tds[4] if len(tds) > 4 else ""
        age = int(tds[5]) if len(tds) > 5 and tds[5].isdigit() else None
        assets = parse_money(tds[6]) if len(tds) > 6 else 0
        liab = parse_money(tds[7]) if len(tds) > 7 else 0

        records.append({
            "name": cand_name,
            "party": party,
            "constituency": cons,
            "state": state,
            "candidate_id": cid,
            "profile_url": profile_url,
            "total_assets": assets,
            "liabilities": liab,
            "criminal_cases": cases,
            "education": edu,
            "age": age,
            "is_winner": is_winner
        })

    return records

if __name__ == "__main__":
    print("Scraper module loaded.")
