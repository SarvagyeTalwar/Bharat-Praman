import re, json, time, os, requests, pandas as pd
from io import StringIO
from bs4 import BeautifulSoup   # pip install lxml too (read_html needs it)

BASE = "https://www.myneta.info/LokSabha2024/"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
os.makedirs("myneta_cache", exist_ok=True)

def get_ids():
    html = requests.get(BASE + "index.php?action=show_winners&sort=default", headers=H, timeout=30).text
    return sorted(set(re.findall(r"candidate_id=(\d+)", html)), key=int)

def fetch(cid):
    path = f"myneta_cache/{cid}.html"
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    html = requests.get(BASE + f"candidate.php?candidate_id={cid}", headers=H, timeout=30).text
    open(path, "w", encoding="utf-8").write(html)
    time.sleep(1.5)
    return html

def rs(text):
    m = re.search(r"Rs\s*([\d,]+)", text or "")
    return int(m.group(1).replace(",", "")) if m else 0

def parse(cid, html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Header: NAME (Winner) / CONSTITUENCY (ST) (STATE) / Party:XXX
    i = next(k for k, l in enumerate(lines) if "(Winner)" in l or "(Loser)" in l)
    name = re.sub(r"\((Winner|Loser)\)", "", lines[i]).strip()
    m = re.match(r"(.+?)(?:\s*\((?:SC|ST)\))?\s*\(([^()]+)\)$", lines[i + 1])
    constituency, state = (m.group(1).strip(), m.group(2).strip()) if m else (lines[i + 1], None)
    party = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Party:")), None)
    age = next((int(re.search(r"\d+", l).group()) for l in lines if l.startswith("Age:")), None)

    cases_n = int(re.search(r"Number of Criminal Cases:\s*(\d+)", text).group(1)) if "Number of Criminal Cases" in text else 0
    assets = rs(re.search(r"Assets:\s*(Rs[^\n]*)", text).group(1)) if re.search(r"Assets:\s*Rs", text) else None
    liab = rs(re.search(r"Liabilities:\s*(Rs[^\n]*)", text).group(1)) if re.search(r"Liabilities:\s*Rs", text) else None
    edu = re.search(r"Category:\s*([^\n]+)", text)

    def gross(section_start, section_end):
        seg = text.split(section_start, 1)[-1].split(section_end, 1)[0]
        g = re.search(r"Gross Total Value[^\n]*|Total Current Market Value[^\n]*", seg)
        # last Rs amount in the row = combined total
        nums = re.findall(r"Rs\s*([\d,]+)", seg[g.start():]) if g else []
        return int(nums[0].replace(",", "")) if nums else 0

    movable = gross("Details of Movable Assets", "Data Readability Report of Movable")
    immovable = gross("Details of Immovable Assets", "Data Readability Report of Immovable")

    # Criminal cases tables
    cases = []
    try:
        for t in pd.read_html(StringIO(html)):
            cols = [str(c).lower() for c in t.columns]
            if not any("ipc sections" in c for c in cols):
                continue
            status = "Convicted" if any("punishment" in c for c in cols) else "Pending"
            for _, row in t.iterrows():
                d = {str(k).lower(): ("" if pd.isna(v) else str(v)) for k, v in row.items()}
                if not d.get(next(k for k in d if "serial" in k), "").strip().isdigit():
                    continue
                get = lambda key: next((v for k, v in d.items() if key in k), "")
                cases.append({
                    "status": status,
                    "fir_no": get("fir no"),
                    "case_no": get("case no"),
                    "court": get("court"),
                    "ipc_sections": [s.strip() for s in get("ipc sections").split(",") if s.strip()],
                    "charges_framed": get("charges framed").split()[0] if get("charges framed") else "",
                })
    except ValueError:
        pass  # no tables

    return {
        "myneta_id": cid, "name": name, "constituency": constituency, "state": state,
        "party": party, "age": age, "criminal_case_count": cases_n,
        "total_assets": assets, "liabilities": liab,
        "movable_assets": movable, "immovable_assets": immovable,
        "education": edu.group(1).strip() if edu else None,
        "cases": cases,
    }

if __name__ == "__main__":
    ids = get_ids()
    print(len(ids), "winner ids")
    out = []
    for n, cid in enumerate(ids, 1):
        try:
            out.append(parse(cid, fetch(cid)))
        except Exception as e:
            print("FAILED", cid, repr(e))
        if n % 25 == 0:
            print(n, "done")
    json.dump(out, open("myneta_parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)