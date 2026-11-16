"""Analytical Union Budget Table & Line-Item Ingester.

Ingests Union Budget PDFs (Demands for Grants, Expenditure Profile, Budget
Annexures) or CSV/XLSX spreadsheets into a dual Graph + Tabular schema:
  (:BudgetDoc)-[:HAS_TABLE]->(:BudgetTable)-[:HAS_ITEM]->(:BudgetLineItem)-[:FOR_SCHEME]->(:BudgetScheme)

Can also extract budget tables directly from already-ingested (:Chunk) nodes
in Instance02 via `--from-ingested-chunks`.

Usage:
  py -3.14 budget_ingest.py "C:\\path\\to\\budget.pdf" --ministry "Education" --fy 2023-24
  py -3.14 budget_ingest.py "C:\\path\\to\\demands.csv" --fy 2024-25
  py -3.14 budget_ingest.py --from-ingested-chunks
"""
import argparse
import csv
import hashlib
import os
import re
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

from embeddings import DIM, embed_texts

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

# Supports dedicated NEO4J_URI2 for Budgets, falling back cleanly to NEO4J_URI1
NEO4J_URI = (os.getenv("NEO4J_URI2") or os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME2") or os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD2") or os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE2") or os.getenv("NEO4J_DATABASE1") or None

TABLE_VEC_INDEX = "budget_table_embeddings"
TABLE_FT_INDEX = "budget_table_fulltext"

NUM_RE = re.compile(r"^-?\d+(?:,\d{2,3})*(?:\.\d+)?$")


def get_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
        max_transaction_retry_time=180,
        notifications_min_severity="OFF",
    )


def ensure_budget_schema(driver):
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run("CREATE CONSTRAINT budget_doc_id IF NOT EXISTS FOR (d:BudgetDoc) REQUIRE d.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT budget_table_id IF NOT EXISTS FOR (t:BudgetTable) REQUIRE t.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT budget_item_id IF NOT EXISTS FOR (i:BudgetLineItem) REQUIRE i.id IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT budget_scheme_name IF NOT EXISTS FOR (sc:BudgetScheme) REQUIRE sc.name IS UNIQUE").consume()
        s.run(
            f"""CREATE VECTOR INDEX {TABLE_VEC_INDEX} IF NOT EXISTS
                FOR (t:BudgetTable) ON (t.embedding)
                OPTIONS {{indexConfig: {{`vector.dimensions`: {DIM}, `vector.similarity_function`: 'cosine'}}}}"""
        ).consume()
        s.run(
            f"CREATE FULLTEXT INDEX {TABLE_FT_INDEX} IF NOT EXISTS FOR (t:BudgetTable) ON EACH [t.title, t.markdown, t.ministry]"
        ).consume()


def _parse_float(val) -> float | None:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    if not s or s in ("-", "—", "NA", "N/A", "nil", "Nil", ".."):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _compute_metrics(be_cr: float | None, re_cr: float | None) -> tuple[float | None, float | None]:
    if be_cr is not None and re_cr is not None:
        gap = round(re_cr - be_cr, 2)
        pct = round(((re_cr - be_cr) / be_cr) * 100.0, 2) if be_cr != 0 else None
        return gap, pct
    return None, None


def _rows_to_markdown(headers: list[str], rows: list[list[str]], title: str = "") -> str:
    clean_headers = [str(h or "").replace("\n", " ").strip() for h in headers]
    if not any(clean_headers):
        clean_headers = [f"Col_{i+1}" for i in range(len(headers))]
    lines = []
    if title:
        lines.append(f"### {title}")
    lines.append("| " + " | ".join(clean_headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(clean_headers)) + " |")
    for r in rows:
        cells = [str(c or "").replace("\n", " ").strip() for c in r]
        if any(cells):
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _extract_line_items_from_grid(
    headers: list[str],
    rows: list[list[str]],
    table_id: str,
    fy: str,
    ministry: str,
    page: int,
) -> list[dict]:
    """Identify scheme/head column and BE / RE / Actual / Next BE numeric columns."""
    h_lower = [str(h or "").lower() for h in headers]

    be_col = next((i for i, h in enumerate(h_lower) if "be" in h or "budget estimate" in h), None)
    re_col = next((i for i, h in enumerate(h_lower) if "re" in h or "revised estimate" in h), None)
    act_col = next((i for i, h in enumerate(h_lower) if "actual" in h), None)
    next_be_col = None
    be_indices = [i for i, h in enumerate(h_lower) if "be" in h or "budget estimate" in h]
    if len(be_indices) >= 2:
        be_col, next_be_col = be_indices[0], be_indices[1]

    items = []
    for r_idx, row in enumerate(rows):
        cells = [str(c or "").replace("\n", " ").strip() for c in row]
        if not any(cells):
            continue
        # Find the descriptive text column (non-numeric, longest text in first 3 cols)
        text_candidates = [
            c for c in cells[:3]
            if c and not NUM_RE.match(c.replace(",", "")) and not re.match(r"^(?:[IVX]+|\d+[.)]?)$", c)
        ]
        if not text_candidates:
            continue
        scheme_name = max(text_candidates, key=len).strip()
        if len(scheme_name) < 3 or scheme_name.lower() in ("total", "grand total", "scheme", "particulars", "sl no."):
            continue

        nums = [_parse_float(c) for c in cells]
        numeric_vals = [n for n in nums if n is not None and n >= 0]
        if not numeric_vals:
            continue

        be_cr = nums[be_col] if be_col is not None and be_col < len(nums) else None
        re_cr = nums[re_col] if re_col is not None and re_col < len(nums) else None
        actual_cr = nums[act_col] if act_col is not None and act_col < len(nums) else None
        next_be_cr = nums[next_be_col] if next_be_col is not None and next_be_col < len(nums) else None

        # Fallback positional assignment when headers weren't explicitly labeled BE/RE
        if be_cr is None and re_cr is None and len(numeric_vals) >= 2:
            # Skip leading serial number if small integer
            tail_nums = [
                _parse_float(c) for idx_c, c in enumerate(cells)
                if idx_c > 0 and _parse_float(c) is not None
            ]
            if len(tail_nums) >= 3:
                be_cr, re_cr, next_be_cr = tail_nums[0], tail_nums[1], tail_nums[2]
            elif len(tail_nums) == 2:
                be_cr, re_cr = tail_nums[0], tail_nums[1]
            elif len(tail_nums) == 1:
                be_cr = tail_nums[0]

        if be_cr is None and re_cr is None and actual_cr is None:
            continue

        gap_cr, var_pct = _compute_metrics(be_cr, re_cr)
        items.append({
            "id": f"{table_id}_item_{r_idx}",
            "table_id": table_id,
            "fy": fy,
            "ministry": ministry,
            "scheme_name": scheme_name[:180],
            "actual_cr": actual_cr,
            "be_cr": be_cr,
            "re_cr": re_cr,
            "next_be_cr": next_be_cr,
            "be_re_gap_cr": gap_cr,
            "be_re_variance_pct": var_pct,
            "page": page,
        })
    return items


def parse_pdf_budget_tables(pdf_path: Path, ministry: str, fy: str) -> tuple[str, list[dict], list[dict]]:
    import pymupdf

    doc = pymupdf.open(str(pdf_path))
    doc_id = hashlib.sha1(pdf_path.read_bytes()).hexdigest()[:12]
    tables_out = []
    items_out = []

    for p_idx in range(doc.page_count):
        page = doc[p_idx]
        page_num = p_idx + 1
        try:
            finder = page.find_tables()
            found_tables = finder.tables if finder else []
        except Exception:
            found_tables = []

        for t_idx, tb in enumerate(found_tables):
            extracted = tb.extract()
            if not extracted or len(extracted) < 2:
                continue
            headers = [str(x or "").strip() for x in extracted[0]]
            body = [[str(x or "").strip() for x in r] for r in extracted[1:]]
            table_id = f"{doc_id}_p{page_num}_t{t_idx}"
            title = f"{ministry} Budget Table (FY {fy}, p.{page_num})"
            md = _rows_to_markdown(headers, body, title=title)
            line_items = _extract_line_items_from_grid(headers, body, table_id, fy, ministry, page_num)
            if not line_items and len(body) < 3:
                continue
            tables_out.append({
                "id": table_id,
                "doc_id": doc_id,
                "title": title,
                "fy": fy,
                "ministry": ministry,
                "page": page_num,
                "headers": headers,
                "row_count": len(body),
                "markdown": md,
            })
            items_out.extend(line_items)

    doc.close()
    return doc_id, tables_out, items_out


def parse_csv_budget_tables(csv_path: Path, ministry: str, fy: str) -> tuple[str, list[dict], list[dict]]:
    doc_id = hashlib.sha1(csv_path.read_bytes()).hexdigest()[:12]
    with csv_path.open("r", encoding="utf-8-sig", errors="replace") as f:
        reader = list(csv.reader(f))
    if len(reader) < 2:
        return doc_id, [], []
    headers = reader[0]
    body = reader[1:]
    table_id = f"{doc_id}_csv_0"
    title = f"{ministry} — {csv_path.stem} ({fy})"
    md = _rows_to_markdown(headers, body[:120], title=title)
    items = _extract_line_items_from_grid(headers, body, table_id, fy, ministry, page=1)
    table = {
        "id": table_id,
        "doc_id": doc_id,
        "title": title,
        "fy": fy,
        "ministry": ministry,
        "page": 1,
        "headers": headers,
        "row_count": len(body),
        "markdown": md,
    }
    return doc_id, [table], items


def extract_budget_tables_from_ingested_chunks(driver) -> tuple[int, int]:
    """Scan existing (:Chunk) nodes in Instance02 for budget/scheme tables and index them as (:BudgetTable)/(:BudgetLineItem)."""
    ensure_budget_schema(driver)
    with driver.session(database=NEO4J_DATABASE) as s:
        rows = s.run(
            """
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
            WHERE toLower(c.text) CONTAINS 'crore'
               OR toLower(c.text) CONTAINS 'be 20'
               OR toLower(c.text) CONTAINS 're 20'
               OR toLower(c.text) CONTAINS 'budget'
               OR toLower(c.text) CONTAINS 'outlay'
            RETURN d.id AS doc_id,
                   coalesce(d.title, d.file, 'Annual Report') AS doc_title,
                   coalesce(c.ministry, d.ministry, 'Education') AS ministry,
                   coalesce(c.year, d.year, '2023-24') AS fy,
                   c.id AS chunk_id,
                   coalesce(c.page, 1) AS page,
                   c.text AS text,
                   c.embedding AS embedding
            """
        ).data()

    line_pattern = re.compile(
        r"(?:\b\d+\s+)?([A-Za-z][A-Za-z0-9\s\-()&,/.]{3,75}?)\s+"
        r"(\d{1,6}(?:,\d{2,3})*\.\d{2})\s+"
        r"(\d{1,6}(?:,\d{2,3})*\.\d{2})"
        r"(?:\s+(\d{1,6}(?:,\d{2,3})*\.\d{2}))?"
    )

    tables_to_write = []
    items_to_write = []

    for r in rows:
        text = r.get("text") or ""
        matches = list(line_pattern.finditer(text))
        if not matches:
            continue

        table_id = f"btable_{r['chunk_id']}"
        fy = r["fy"]
        ministry = r["ministry"]
        page = int(r["page"] or 1)
        md_rows = []

        for m_idx, m in enumerate(matches):
            raw_name = re.sub(r"^(?:Schemes|Centrally Sponsored Schemes|Central Sector Schemes|Sl No\.?)\s*", "", m.group(1), flags=re.I).strip()
            raw_name = re.sub(r"^\d+\s+", "", raw_name).strip(" -–:.")
            if len(raw_name) < 3 or raw_name.lower() in ("total", "grand total", "year", "crore"):
                continue
            be_val = _parse_float(m.group(2))
            re_val = _parse_float(m.group(3))
            next_be_val = _parse_float(m.group(4)) if m.group(4) else None
            if be_val is None and re_val is None:
                continue
            gap_cr, var_pct = _compute_metrics(be_val, re_val)
            item_id = f"{table_id}_i{m_idx}"
            items_to_write.append({
                "id": item_id,
                "table_id": table_id,
                "doc_id": r["doc_id"],
                "fy": fy,
                "ministry": ministry,
                "scheme_name": raw_name[:160],
                "actual_cr": None,
                "be_cr": be_val,
                "re_cr": re_val,
                "next_be_cr": next_be_val,
                "be_re_gap_cr": gap_cr,
                "be_re_variance_pct": var_pct,
                "page": page,
            })
            md_rows.append([
                raw_name,
                f"{be_val:,.2f}" if be_val is not None else "—",
                f"{re_val:,.2f}" if re_val is not None else "—",
                f"{next_be_val:,.2f}" if next_be_val is not None else "—",
            ])

        if md_rows:
            title = f"{r['doc_title']} — Budget & Outlay Table (p.{page})"
            md = _rows_to_markdown(["Scheme / Head", f"BE {fy} (₹ Cr)", f"RE {fy} (₹ Cr)", "Next FY BE (₹ Cr)"], md_rows, title=title)
            tables_to_write.append({
                "id": table_id,
                "doc_id": r["doc_id"],
                "doc_title": r["doc_title"],
                "title": title,
                "fy": fy,
                "ministry": ministry,
                "page": page,
                "row_count": len(md_rows),
                "markdown": md + "\n\nRaw Source Excerpt:\n" + text,
                "embedding": r.get("embedding"),
            })

    if not tables_to_write:
        return 0, 0

    # Compute embeddings only for tables whose source chunk didn't already carry a 1024-dim vector
    missing_idx = [i for i, t in enumerate(tables_to_write) if not t.get("embedding") or len(t["embedding"]) != DIM]
    if missing_idx:
        vecs = embed_texts([tables_to_write[i]["markdown"] for i in missing_idx], batch=16)
        for i, v in zip(missing_idx, vecs):
            tables_to_write[i]["embedding"] = v

    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(
            """
            UNWIND $tables AS t
            MERGE (d:BudgetDoc {id: t.doc_id})
            SET d.title = t.doc_title, d.fy = t.fy, d.ministry = t.ministry
            MERGE (tb:BudgetTable {id: t.id})
            SET tb.doc_id = t.doc_id, tb.title = t.title, tb.fy = t.fy,
                tb.ministry = t.ministry, tb.page = t.page,
                tb.row_count = t.row_count, tb.markdown = t.markdown
            WITH d, tb, t
            CALL db.create.setNodeVectorProperty(tb, 'embedding', t.embedding)
            MERGE (d)-[:HAS_TABLE]->(tb)
            """,
            tables=tables_to_write,
        ).consume()

        s.run(
            """
            UNWIND $items AS item
            MATCH (tb:BudgetTable {id: item.table_id})
            MERGE (li:BudgetLineItem {id: item.id})
            SET li.table_id = item.table_id, li.fy = item.fy,
                li.ministry = item.ministry, li.scheme_name = item.scheme_name,
                li.actual_cr = item.actual_cr, li.be_cr = item.be_cr,
                li.re_cr = item.re_cr, li.next_be_cr = item.next_be_cr,
                li.be_re_gap_cr = item.be_re_gap_cr,
                li.be_re_variance_pct = item.be_re_variance_pct,
                li.page = item.page
            MERGE (tb)-[:HAS_ITEM]->(li)
            MERGE (sc:BudgetScheme {name: item.scheme_name})
            MERGE (li)-[:FOR_SCHEME]->(sc)
            """,
            items=items_to_write,
        ).consume()

    return len(tables_to_write), len(items_to_write)


def ingest_budget_file(path: Path, ministry: str, fy: str, dry_run: bool = False):
    if path.suffix.lower() == ".csv":
        doc_id, tables, items = parse_csv_budget_tables(path, ministry, fy)
    else:
        doc_id, tables, items = parse_pdf_budget_tables(path, ministry, fy)

    print(f"Parsed {path.name}: {len(tables)} budget tables, {len(items)} structured line items")
    if dry_run or not tables:
        for li in items[:8]:
            print(f"  - {li['scheme_name']}: BE={li['be_cr']} Cr | RE={li['re_cr']} Cr | Var={li['be_re_variance_pct']}% (p.{li['page']})")
        return

    drv = get_driver()
    try:
        ensure_budget_schema(drv)
        vecs = embed_texts([t["markdown"] for t in tables], batch=16, progress=True)
        for t, v in zip(tables, vecs):
            t["embedding"] = v
            t["doc_title"] = path.stem

        with drv.session(database=NEO4J_DATABASE) as s:
            for i in range(0, len(tables), 50):
                s.run(
                    """
                    UNWIND $tables AS t
                    MERGE (d:BudgetDoc {id: t.doc_id})
                    SET d.title = t.doc_title, d.fy = t.fy, d.ministry = t.ministry
                    MERGE (tb:BudgetTable {id: t.id})
                    SET tb.doc_id = t.doc_id, tb.title = t.title, tb.fy = t.fy,
                        tb.ministry = t.ministry, tb.page = t.page,
                        tb.row_count = t.row_count, tb.markdown = t.markdown
                    WITH d, tb, t
                    CALL db.create.setNodeVectorProperty(tb, 'embedding', t.embedding)
                    MERGE (d)-[:HAS_TABLE]->(tb)
                    """,
                    tables=tables[i:i + 50],
                ).consume()

            for i in range(0, len(items), 200):
                s.run(
                    """
                    UNWIND $items AS item
                    MATCH (tb:BudgetTable {id: item.table_id})
                    MERGE (li:BudgetLineItem {id: item.id})
                    SET li.table_id = item.table_id, li.fy = item.fy,
                        li.ministry = item.ministry, li.scheme_name = item.scheme_name,
                        li.actual_cr = item.actual_cr, li.be_cr = item.be_cr,
                        li.re_cr = item.re_cr, li.next_be_cr = item.next_be_cr,
                        li.be_re_gap_cr = item.be_re_gap_cr,
                        li.be_re_variance_pct = item.be_re_variance_pct,
                        li.page = item.page
                    MERGE (tb)-[:HAS_ITEM]->(li)
                    MERGE (sc:BudgetScheme {name: item.scheme_name})
                    MERGE (li)-[:FOR_SCHEME]->(sc)
                    """,
                    items=items[i:i + 200],
                ).consume()
        print(f"Successfully ingested {len(tables)} tables and {len(items)} line items into Neo4j!")
    finally:
        drv.close()


def main():
    ap = argparse.ArgumentParser(description="Ingest Union Budget tables & line items into Neo4j.")
    ap.add_argument("target", nargs="?", default=None, help="Budget PDF or CSV file/folder")
    ap.add_argument("--ministry", default="Union Budget", help="Ministry or Demand name")
    ap.add_argument("--fy", default="2023-24", help="Fiscal year (e.g. 2023-24)")
    ap.add_argument("--from-ingested-chunks", action="store_true", help="Extract structured budget tables from already ingested (:Chunk) nodes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.from_ingested_chunks:
        drv = get_driver()
        try:
            t_count, i_count = extract_budget_tables_from_ingested_chunks(drv)
            print(f"Extracted {t_count} BudgetTables and {i_count} BudgetLineItems from existing chunks!")
        finally:
            drv.close()
        return

    if not args.target:
        ap.error("Provide a target file/folder or pass --from-ingested-chunks")

    p = Path(args.target)
    if p.is_dir():
        for f in sorted(list(p.glob("*.pdf")) + list(p.glob("*.csv"))):
            ingest_budget_file(f, args.ministry, args.fy, args.dry_run)
    elif p.is_file():
        ingest_budget_file(p, args.ministry, args.fy, args.dry_run)
    else:
        print(f"File not found: {p}")


if __name__ == "__main__":
    main()
