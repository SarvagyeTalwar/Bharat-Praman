import re, json, time, os, requests
from bs4 import BeautifulSoup

BASE = "https://www.myneta.info/LokSabha2024/"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CACHE = "myneta_cache"
os.makedirs(CACHE, exist_ok=True)


def get_ids():
    html = requests.get(BASE + "index.php?action=show_winners&sort=default", headers=H, timeout=30).text
    return sorted(set(re.findall(r"candidate_id=(\d+)", html)), key=int)


def fetch(cid):
    path = f"{CACHE}/{cid}.html"
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    html = requests.get(BASE + f"candidate.php?candidate_id={cid}", headers=H, timeout=30).text
    open(path, "w", encoding="utf-8").write(html)
    time.sleep(1.5)
    return html


def rs(text):
    m = re.search(r"Rs\s*([\d,]+)", (text or "").replace("\xa0", " "))
    return int(m.group(1).replace(",", "")) if m else 0


def parse(cid, html):
    soup = BeautifulSoup(html, "html.parser")

    # --- header ---
    h2 = next(h for h in soup.find_all("h2")
              if "(Winner)" in h.get_text() or "(Loser)" in h.get_text())
    name = re.sub(r"\((Winner|Loser)\)", "", h2.get_text(" ")).strip()
    h5 = re.sub(r"\s+", " ", h2.find_next("h5").get_text(" ", strip=True))
    m = re.match(r"^(.*?)\s*(?:\((?:SC|ST)\))?\s*\(([^()]+)\)$", h5)
    constituency, state = (m.group(1).strip(), m.group(2).strip()) if m else (h5, None)

    def label(lbl):
        b = soup.find("b", string=re.compile(rf"^\s*{lbl}\s*$"))
        sib = b.next_sibling if b else None
        return sib.strip() if sib and isinstance(sib, str) else None

    party = label("Party:")
    age_s = label("Age:")
    age = int(re.search(r"\d+", age_s).group()) if age_s and re.search(r"\d+", age_s) else None

    text = soup.get_text(" ", strip=True).replace("\xa0", " ")

    m = re.search(r"Number of Criminal Cases:\s*(\d+)", text)
    cases_n = int(m.group(1)) if m else 0

    m = re.search(r"Assets:\s*Rs\s*([\d,]+)", text)
    assets = int(m.group(1).replace(",", "")) if m else None
    m = re.search(r"Liabilities:\s*Rs\s*([\d,]+)", text)
    liab = int(m.group(1).replace(",", "")) if m else 0   # "Nil" -> 0

    node = soup.find(string=re.compile(r"Category:"))
    edu = node.strip().split(":", 1)[1].strip() if node else None

    # --- immovable total (movable is script-generated, so derive it) ---
    immovable = 0
    t = soup.find("table", id="immovable_assets")
    if t:
        for tr in t.find_all("tr"):
            if "Total Current Market Value" in tr.get_text():
                immovable = rs(tr.find_all("td")[-1].get_text(" "))
                break
    movable = (assets - immovable) if assets is not None else None

    # --- criminal cases: 1st table = pending, 2nd = convicted ---
    cases = []
    tables = soup.find_all("table", id="cases")
    for status, t in zip(["Pending", "Convicted"], tables):
        for tr in t.find_all("tr")[1:]:
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(tds) < 5 or not tds[0].isdigit():
                continue
            if status == "Pending":
                fir, case_no, court, ipc = tds[1], tds[2], tds[3], tds[4]
                charges = tds[6] if len(tds) > 6 else ""
            else:
                fir, case_no, court, ipc = "", tds[1], tds[2], tds[3]
                charges = ""
            cases.append({
                "status": status, "fir_no": fir, "case_no": case_no, "court": court,
                "ipc_sections": [s.strip() for s in ipc.split(",") if s.strip()],
                "charges_framed": charges,
            })

    return {
        "myneta_id": cid, "name": name, "constituency": constituency, "state": state,
        "party": party, "age": age, "criminal_case_count": cases_n,
        "total_assets": assets, "liabilities": liab,
        "movable_assets": movable, "immovable_assets": immovable,
        "education": edu, "cases": cases,
    }


if __name__ == "__main__":
    # Use the pages already on disk, no network needed
    ids = sorted((f[:-5] for f in os.listdir(CACHE) if f.endswith(".html")), key=int)
    print(len(ids), "cached pages")

    out = []
    for n, cid in enumerate(ids, 1):
        try:
            out.append(parse(cid, fetch(cid)))
        except Exception as e:
            print("FAILED", cid, repr(e))
        if n % 100 == 0:
            print(n, "done")

    json.dump(out, open("myneta_parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(len(out), "parsed ->", "myneta_parsed.json")