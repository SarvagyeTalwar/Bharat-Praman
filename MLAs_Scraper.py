import re, json, time, os, requests
from bs4 import BeautifulSoup

BASE = "https://www.myneta.info/LokSabha2024/"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CACHE = "myneta_cache"


# ---------- fetching ----------
def get_ids():
    html = requests.get(BASE + "index.php?action=show_winners&sort=default", headers=H, timeout=30).text
    return sorted(set(re.findall(r"candidate_id=(\d+)", html)), key=int)


def fetch(cid):
    path = f"{CACHE}/{cid}.html"
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    for attempt in range(6):
        try:
            r = requests.get(BASE + f"candidate.php?candidate_id={cid}", headers=H, timeout=30)
            if r.status_code == 200:
                break
            print(f"  HTTP {r.status_code}, retrying {cid}")
        except requests.exceptions.RequestException as e:
            print(f"  network error ({type(e).__name__}), retry {attempt + 1}/6")
        time.sleep(2 * 2 ** attempt)
    else:
        raise RuntimeError(f"gave up on candidate {cid}")
    os.makedirs(CACHE, exist_ok=True)
    open(path, "w", encoding="utf-8").write(r.text)
    time.sleep(1.5)
    return r.text


# ---------- helpers ----------
def rs(text):
    m = re.search(r"Rs\s*([\d,]+)", (text or "").replace("\xa0", " "))
    return int(m.group(1).replace(",", "")) if m else 0


def split_header(h5):
    """'NEW DELHI (DELHI (NCT))' -> ('NEW DELHI', 'DELHI (NCT)'). Takes the LAST balanced bracket group."""
    h5 = re.sub(r"\s+", " ", h5).strip()
    if not h5.endswith(")"):
        return h5, None
    depth = 0
    for i in range(len(h5) - 1, -1, -1):
        if h5[i] == ")":
            depth += 1
        elif h5[i] == "(":
            depth -= 1
            if depth == 0:
                return h5[:i].strip(), h5[i + 1:-1].strip()
    return h5, None


def money_after(label, text):
    """'Assets: Rs 22,65,797 ~2 Crore+' -> 2265797 ; 'Liabilities: Nil' -> 0 ; not found -> None"""
    m = re.search(rf"{label}\s*(?:Rs\s*([\d,]+)|(Nil))", text)
    if not m:
        return None
    return int(m.group(1).replace(",", "")) if m.group(1) else 0


# ---------- main parser ----------
def parse(cid, html):
    soup = BeautifulSoup(html, "html.parser")

    # header: name, constituency, state
    h2 = next(h for h in soup.find_all("h2")
              if "(Winner)" in h.get_text() or "(Loser)" in h.get_text())
    name = re.sub(r"\((Winner|Loser)\)", "", h2.get_text(" ")).strip()
    h5 = h2.find_next("h5").get_text(" ", strip=True)
    constituency, state = split_header(h5)

    reservation = None
    m = re.search(r"\((SC|ST)\)\s*$", constituency)
    if m:
        reservation = m.group(1)
        constituency = constituency[:m.start()].strip()
    if state and re.search(r"DELHI\s*\(NCT\)", state, re.I):
        state = "NCT of Delhi"

    # labelled fields
    def label(lbl):
        b = soup.find("b", string=re.compile(rf"^\s*{lbl}\s*$"))
        sib = b.next_sibling if b else None
        return sib.strip() if sib and isinstance(sib, str) else None

    party = label("Party:")
    age_s = label("Age:")
    m = re.search(r"\d+", age_s or "")
    age = int(m.group()) if m else None

    text = soup.get_text(" ", strip=True).replace("\xa0", " ")

    m = re.search(r"Number of Criminal Cases:\s*(\d+)", text)
    cases_n = int(m.group(1)) if m else 0
    assets = money_after("Assets:", text)
    liab = money_after("Liabilities:", text)
    liab = 0 if liab is None else liab

    node = soup.find(string=re.compile(r"Category:"))
    edu = node.strip().split(":", 1)[1].strip() if node else None

    # immovable total from HTML; movable is script-generated, so derive it
    immovable = 0
    t = soup.find("table", id="immovable_assets")
    if t:
        for tr in t.find_all("tr"):
            if "Total Current Market Value" in tr.get_text():
                immovable = rs(tr.find_all("td")[-1].get_text(" "))
                break
    movable = (assets - immovable) if assets is not None else None   # derived value

    # criminal cases: 1st table = pending, 2nd = convicted
    cases = []
    for status, t in zip(["Pending", "Convicted"], soup.find_all("table", id="cases")):
        for tr in t.find_all("tr")[1:]:
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(tds) < 5 or not tds[0].isdigit():
                continue                       # header row or "No Cases" row
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
        "reservation": reservation, "party": party, "age": age,
        "criminal_case_count": cases_n, "total_assets": assets, "liabilities": liab,
        "movable_assets": movable, "immovable_assets": immovable,
        "education": edu, "cases": cases,
    }


# ---------- run directly: re-parse every cached MP page ----------
if __name__ == "__main__":
    # quick self-test of the header splitter
    assert split_header("KOKRAJHAR (ST)  (ASSAM)") == ("KOKRAJHAR (ST)", "ASSAM")
    assert split_header("NEW DELHI (DELHI (NCT))") == ("NEW DELHI", "DELHI (NCT)")
    assert split_header("PONDA : BYE ELECTION ON 9-04-2026  (SOUTH GOA)")[1] == "SOUTH GOA"
    print("header tests passed")

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
    print(len(out), "parsed -> myneta_parsed.json")