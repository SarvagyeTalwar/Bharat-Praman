"""Enrich the 1,829 index-ingested MLAs from their candidate pages (dry-run unless --write)."""
import sys, re, json, time
from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.path.append(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman")
from MLAs_Scraper import parse

load_dotenv()
URI = os.getenv("NEO4J_URI", "neo4j+ssc://c1bf4c50.databases.neo4j.io")
USER = os.getenv("NEO4J_USERNAME", "c1bf4c50")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
CACHE = Path("/tmp/opencode/mla_pages")
WRITE = "--write" in sys.argv
LIMIT = None
for a in sys.argv:
    if a.startswith("--limit="):
        LIMIT = int(a.split("=")[1])

def gender_of(soup):
    b = soup.find("b", string=re.compile(r"^\s*S/o\|D/o\|W/o:\s*$"))
    if not b:
        return None
    # the label itself tells relationship? It is the literal "S/o|D/o|W/o", not filled.
    return None  # pages show the generic label; skip unless a specific prefix found

def parse_cases(soup):
    out = []
    for t in soup.find_all("table", id="cases"):
        prev = t.find_previous(["h3", "h4", "h5"])
        heading = prev.get_text(" ", strip=True).lower() if prev else ""
        if "pending" in heading: status = "Pending"
        elif "convicted" in heading: status = "Convicted"
        elif "charges framed" in heading: status = "Charges Framed"
        elif "cognizance" in heading: status = "Cognizance"
        elif "accused" in heading: status = "Pending"
        else: status = heading or "Unknown"
        rows = t.find_all("tr")
        if not rows: continue
        header = [td.get_text(" ", strip=True) for td in rows[0].find_all(["td", "th"])]
        hm = {}
        for i, h in enumerate(header):
            hl = h.lower()
            if "serial" in hl: continue
            if "fir" in hl: hm["fir_no"] = i
            elif "case no" in hl: hm["case_no"] = i
            elif "court" in hl and "cognizance" not in hl: hm["court"] = i
            elif "other details" in hl: hm["other"] = i
            elif "ipc" in hl: hm["ipc"] = i
            elif "charges framed" in hl: hm["charges"] = i
            elif "punishment" in hl: hm["punishment"] = i
        for tr in rows[1:]:
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not tds or not tds[0].strip().isdigit():
                continue
            rec = {"status": status, "fir_no": None, "case_no": None, "court": None,
                   "charges_framed": ("Yes" if status == "Charges Framed" else None),
                   "ipc_sections": [], "other_details": None}
            for k, i in hm.items():
                if i < len(tds):
                    if k == "ipc":
                        rec["ipc_sections"] = [x.strip() for x in re.split(r"[,;]", tds[i]) if x.strip()]
                    elif k == "other":
                        rec["other_details"] = tds[i]
                    else:
                        rec[k] = tds[i] or None
            out.append(rec)
    return out

def parse_profession(soup):
    b = soup.find("b", string=re.compile(r"^\s*Self Profession:\s*$"))
    if not b:
        return None
    sib = b.next_sibling
    if isinstance(sib, str) and sib.strip():
        return [x.strip() for x in sib.strip().split(",") if x.strip()]
    return None

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session() as s:
    db = [{k: (v.data() if hasattr(v, "data") else v) for k, v in r.items()} for r in s.run("""
        MATCH (p:Person {source:'myneta:winners-index'})
        WHERE ($pending = false OR p.source_detail IS NULL)
        RETURN p.entity_id AS eid, p.election AS slug, p.myneta_id AS cid,
               p.total_assets AS assets, p.criminal_case_count AS cases, p.name AS name
        ORDER BY slug, cid
    """, {"pending": "--pending" in sys.argv})]
    print("targets", len(db), flush=True)
    if LIMIT:
        db = db[:LIMIT]

    records, missing = [], 0
    for r in db:
        p = CACHE / r["slug"] / f"{r['cid']}.html"
        if not p.exists() or p.stat().st_size < 20000:
            missing += 1
            continue
        html = p.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        try:
            d = parse(r["cid"], html)
        except Exception as e:
            print("parse fail", r["eid"], repr(e)[:80], flush=True)
            continue
        records.append({
            "eid": r["eid"], "slug": r["slug"], "cid": r["cid"],
            "age": d.get("age"), "liab": d.get("liabilities"),
            "movable": d.get("movable_assets"), "immovable": d.get("immovable_assets"),
            "assets": d.get("total_assets"), "cases": parse_cases(soup),
            "profession": parse_profession(soup),
            "db_assets": r["assets"], "db_cases": r["cases"],
        })
    print("parsed", len(records), "missing pages", missing, flush=True)

    print("age null", sum(1 for x in records if x["age"] is None))
    print("liab null", sum(1 for x in records if x["liab"] is None))
    print("movable null", sum(1 for x in records if x["movable"] is None))
    print("profession parsed", sum(1 for x in records if x["profession"]))
    mism = [x for x in records if x["db_assets"] is not None and x["assets"] is not None and x["assets"] != x["db_assets"]]
    print("asset mismatches vs index", len(mism), flush=True)
    for x in mism[:5]:
        print("  ", x["eid"], x["db_assets"], x["assets"])
    case_pages = sum(1 for x in records if x["cases"])
    case_rows = sum(len(x["cases"]) for x in records)
    count_mismatch = [x for x in records if (x["db_cases"] or 0) != len(x["cases"])]
    print("pages with parsed cases", case_pages, "case rows", case_rows, flush=True)
    print("case-count mismatches", len(count_mismatch), flush=True)
    for x in count_mismatch[:8]:
        print("  ", x["eid"], "db", x["db_cases"], "parsed", len(x["cases"]), flush=True)
    print("sample", json.dumps(records[0], default=str)[:600] if records else None, flush=True)

    if not WRITE:
        print("DRY RUN - nothing written", flush=True)
        driver.close()
        raise SystemExit(0)

    # ---- write ----
    batch = 200
    for i in range(0, len(records), batch):
        b = records[i:i + batch]
        s.execute_write(lambda tx, b=b: tx.run("""
            UNWIND $rows AS r
            MATCH (p:Person {entity_id: r.eid})
            SET p.age = coalesce(p.age, r.age),
                p.liabilities = coalesce(p.liabilities, r.liab),
                p.movable_assets = coalesce(p.movable_assets, r.movable),
                p.immovable_assets = coalesce(p.immovable_assets, r.immovable),
                p.profession = coalesce(p.profession, r.profession)
            SET p.source_detail = 'myneta:candidate-page'
            WITH r
            MATCH (a:Affidavit {affidavit_id: r.eid})
            SET a.liabilities = coalesce(a.liabilities, r.liab),
                a.movable_assets = coalesce(a.movable_assets, r.movable),
                a.immovable_assets = coalesce(a.immovable_assets, r.immovable),
                a.total_assets = coalesce(a.total_assets, r.assets)
            SET a.source_detail = 'myneta:candidate-page'
        """, {"rows": b}).consume())
        print("  people", min(i + batch, len(records)), "/", len(records), flush=True)

    case_rows = []
    for x in records:
        for j, c in enumerate(x["cases"], 1):
            case_rows.append({**c, "eid": x["eid"], "case_id": f'{x["eid"]}_{j}'})
    for i in range(0, len(case_rows), batch):
        b = case_rows[i:i + batch]
        s.execute_write(lambda tx, b=b: tx.run("""
            UNWIND $rows AS r
            MATCH (p:Person {entity_id: r.eid})
            MATCH (a:Affidavit {affidavit_id: r.eid})
            MERGE (cc:CriminalCase {case_id: r.case_id})
            SET cc.status = r.status, cc.fir_no = r.fir_no, cc.case_no = r.case_no,
                cc.court = r.court, cc.charges_framed = r.charges_framed,
                cc.ipc_sections = r.ipc_sections, cc.other_details = r.other_details
            MERGE (p)-[:FACES]->(cc)
            MERGE (a)-[:DISCLOSES]->(cc)
            WITH cc, r
            UNWIND r.ipc_sections AS sec
            MERGE (s:Section {code: sec})
            MERGE (cc)-[:UNDER]->(s)
        """, {"rows": b}).consume())
        print("  cases", min(i + batch, len(case_rows)), "/", len(case_rows), flush=True)

    print("persons with age", s.run("MATCH (p:Person:MLA) WHERE p.age IS NOT NULL RETURN count(p) AS n").single()["n"], flush=True)
    print("persons with liabilities", s.run("MATCH (p:Person:MLA) WHERE p.liabilities IS NOT NULL RETURN count(p) AS n").single()["n"], flush=True)
    print("criminal cases", s.run("MATCH (c:CriminalCase) RETURN count(c) AS n").single()["n"], flush=True)
    print("DONE", flush=True)
driver.close()
