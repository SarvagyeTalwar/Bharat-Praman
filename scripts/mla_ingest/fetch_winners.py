import requests, re, time
from pathlib import Path

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
OUT = Path("/tmp/opencode/winners_pages")
OUT.mkdir(exist_ok=True)

SLUGS = [
    "Haryana2024", "Haryana2019", "Haryana2014", "Haryana2009", "Haryana2004",
    "Odisha2024", "Odisha2019", "Odisha2014", "Orissa2009", "Orissa2004",
    "TamilNadu2026", "TamilNadu2021", "TamilNadu2016", "TamilNadu2011", "TamilNadu2006",
    "UttarPradesh2022", "UttarPradesh2017", "UttarPradesh2012", "UttarPradesh2007", "UttarPradesh2002",
]

def fetch(slug):
    p = OUT / f"{slug}.html"
    if p.exists() and p.stat().st_size > 20000:
        return "cache", p.read_text(encoding="utf-8")
    url = f"https://www.myneta.info/{slug}/index.php?action=show_winners&sort=default"
    for attempt in range(8):
        try:
            r = requests.get(url, headers=H, timeout=45)
            if r.status_code == 200 and "Page Not Found" not in r.text and len(r.text) > 20000:
                p.write_text(r.text, encoding="utf-8")
                return f"ok{attempt}", r.text
            return f"http{r.status_code}", r.text
        except Exception as e:
            print(f"  {slug} retry {attempt+1}: {type(e).__name__}", flush=True)
            time.sleep(15 * (attempt + 1))
    return "fail", ""

for slug in SLUGS:
    status, html = fetch(slug)
    rows = 0
    if html:
        tbls = re.findall(r"<table.*?</table>", html, re.S)
        best = max(tbls, key=lambda t: t.count("<tr")) if tbls else ""
        rows = max(0, best.count("<tr") - 1)
    print(f"{slug:18s} {status:8s} rows={rows}", flush=True)
    time.sleep(12)
print("FETCH DONE", flush=True)
