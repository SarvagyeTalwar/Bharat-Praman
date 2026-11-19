"""Analytical Union Budget Engine for Journalists & Researchers.

Combines:
1. Structured Graph Line-Item Analytics over (:BudgetLineItem) — exact rankings,
   BE vs. RE variance %, largest budget cuts/increases, scheme trajectories.
2. Hybrid Table Search over (:BudgetTable) + fallback to budget-rich (:Chunk)
   nodes in Instance02 so thousands of tables can be queried analytically.
3. Journalist Briefing Synthesis via DeepSeek (`deepseek-chat`) or Gemini REST API.
"""
import json
import logging
import os
import re
import urllib.request
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

logger = logging.getLogger("uvicorn.error")

NEO4J_URI = (os.getenv("NEO4J_URI2") or os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME2") or os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD2") or os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE2") or os.getenv("NEO4J_DATABASE1") or None

DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

TABLE_VEC_INDEX = "budget_table_embeddings"
TABLE_FT_INDEX = "budget_table_fulltext"

_driver = None
_bootstrapped = False
_BUDGET_CACHE: dict = {}
_MAX_BUDGET_CACHE = 128


def get_driver():
    global _driver
    if _driver is None and NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_transaction_retry_time=60,
            notifications_min_severity="OFF",
        )
    return _driver


def _ensure_bootstrapped():
    """Auto-populate (:BudgetTable)/(:BudgetLineItem) from ingested chunks if empty."""
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True
    drv = get_driver()
    if drv is None:
        return
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            count = s.run("MATCH (li:BudgetLineItem) RETURN count(li) AS n").single()["n"]
        if count == 0:
            from budget_ingest import extract_budget_tables_from_ingested_chunks
            extract_budget_tables_from_ingested_chunks(drv)
    except Exception as exc:
        logger.warning("Budget bootstrap check skipped: %s", exc)


def get_budget_catalog() -> dict:
    _ensure_bootstrapped()
    drv = get_driver()
    if drv is None:
        return {"ministries": [], "years": [], "table_count": 0, "item_count": 0}
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            stats = s.run(
                """
                OPTIONAL MATCH (tb:BudgetTable)
                WITH count(DISTINCT tb) AS table_count
                OPTIONAL MATCH (li:BudgetLineItem)
                RETURN table_count,
                       count(li) AS item_count,
                       collect(DISTINCT li.ministry) AS ministries,
                       collect(DISTINCT li.fy) AS years,
                       round(sum(coalesce(li.be_cr, 0)), 2) AS total_be_cr,
                       round(sum(coalesce(li.re_cr, 0)), 2) AS total_re_cr
                """
            ).single()
            return {
                "table_count": stats["table_count"] or 0,
                "item_count": stats["item_count"] or 0,
                "ministries": sorted([m for m in (stats["ministries"] or []) if m]),
                "years": sorted([y for y in (stats["years"] or []) if y]),
                "total_be_cr": stats["total_be_cr"] or 0.0,
                "total_re_cr": stats["total_re_cr"] or 0.0,
            }
    except Exception as exc:
        logger.warning("Could not load budget catalog: %s", exc)
        return {"ministries": [], "years": [], "table_count": 0, "item_count": 0}


def query_budget_items(
    ministry: str | None = None,
    fy: str | None = None,
    search: str | None = None,
    sort_by: str = "be_cr",
    limit: int = 50,
) -> list[dict]:
    """Query structured (:BudgetLineItem) nodes for analytical sorting & filtering."""
    _ensure_bootstrapped()
    drv = get_driver()
    if drv is None:
        return []

    order_clause = {
        "be_cr": "coalesce(li.be_cr, 0) DESC",
        "re_cr": "coalesce(li.re_cr, 0) DESC",
        "biggest_cuts": "coalesce(li.be_re_gap_cr, 0) ASC",
        "biggest_increases": "coalesce(li.be_re_gap_cr, 0) DESC",
        "variance_pct": "abs(coalesce(li.be_re_variance_pct, 0)) DESC",
    }.get(sort_by, "coalesce(li.be_cr, 0) DESC")

    cypher = f"""
    MATCH (li:BudgetLineItem)
    WHERE ($ministry IS NULL OR $ministry = '' OR toLower(li.ministry) CONTAINS toLower($ministry))
      AND ($fy IS NULL OR $fy = '' OR li.fy = $fy)
      AND ($search IS NULL OR $search = '' OR toLower(li.scheme_name) CONTAINS toLower($search))
    RETURN li.id AS id,
           li.scheme_name AS scheme_name,
           li.ministry AS ministry,
           li.fy AS fy,
           li.actual_cr AS actual_cr,
           li.be_cr AS be_cr,
           li.re_cr AS re_cr,
           li.next_be_cr AS next_be_cr,
           li.be_re_gap_cr AS be_re_gap_cr,
           li.be_re_variance_pct AS be_re_variance_pct,
           li.page AS page
    ORDER BY {order_clause}
    LIMIT $limit
    """
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            return s.run(
                cypher,
                ministry=ministry,
                fy=fy,
                search=search,
                limit=min(max(1, limit), 200),
            ).data()
    except Exception as exc:
        logger.warning("Structured budget item query failed: %s", exc)
        return []


def retrieve_budget_tables(question: str, ministry: str | None = None, fy: str | None = None, top_k: int = 6) -> list[dict]:
    """Retrieve relevant (:BudgetTable) nodes + budget-heavy (:Chunk) passages."""
    _ensure_bootstrapped()
    drv = get_driver()
    if drv is None:
        return []

    tokens = [
        t for t in re.findall(r"[A-Za-z0-9]+", (question or "").lower())
        if len(t) >= 3 and t not in {"how", "much", "what", "was", "were", "the", "for", "and", "between", "budget", "spent", "allocation"}
    ]
    tables = []
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            if tokens:
                q_ft = " OR ".join(tokens[:12])
                rows = s.run(
                    f"""
                    CALL db.index.fulltext.queryNodes('{TABLE_FT_INDEX}', $q) YIELD node, score
                    WHERE ($ministry IS NULL OR $ministry = '' OR toLower(node.ministry) CONTAINS toLower($ministry))
                      AND ($fy IS NULL OR $fy = '' OR node.fy = $fy)
                    RETURN node.id AS id, node.title AS title, node.ministry AS ministry,
                           node.fy AS fy, node.page AS page, node.markdown AS markdown, score
                    ORDER BY score DESC
                    LIMIT $k
                    """,
                    q=q_ft,
                    ministry=ministry,
                    fy=fy,
                    k=top_k,
                ).data()
                tables.extend(rows)

            if len(tables) < top_k:
                extra = s.run(
                    """
                    MATCH (node:BudgetTable)
                    WHERE ($ministry IS NULL OR $ministry = '' OR toLower(node.ministry) CONTAINS toLower($ministry))
                      AND ($fy IS NULL OR $fy = '' OR node.fy = $fy)
                    RETURN node.id AS id, node.title AS title, node.ministry AS ministry,
                           node.fy AS fy, node.page AS page, node.markdown AS markdown, 1.0 AS score
                    ORDER BY node.row_count DESC
                    LIMIT $k
                    """,
                    ministry=ministry,
                    fy=fy,
                    k=top_k,
                ).data()
                seen = {t["id"] for t in tables}
                for r in extra:
                    if r["id"] not in seen:
                        tables.append(r)
                        seen.add(r["id"])
    except Exception as exc:
        logger.warning("BudgetTable retrieval fallback: %s", exc)

    # Also pull top semantic chunks with numeric/budget evidence from reports_agent
    try:
        from reports_agent import stratified_hybrid_search
        chunk_hits = stratified_hybrid_search(
            question + " budget allocation outlay BE RE crore table",
            ministries=[ministry] if ministry else None,
            years=[fy] if fy else None,
            top_k=top_k,
        )
        for ch in chunk_hits:
            tables.append({
                "id": ch["id"],
                "title": f"{ch.get('title')} (p.{ch.get('page')})",
                "ministry": ch.get("ministry"),
                "fy": ch.get("year"),
                "page": ch.get("page"),
                "markdown": (ch.get("text") or "") + ("\n" + ch["next_text"] if ch.get("next_text") else ""),
                "score": ch.get("score", 0.5),
            })
    except Exception:
        pass

    return tables[: top_k * 2]


def ask_budget(
    question: str,
    ministry: str | None = None,
    fy: str | None = None,
    sort_by: str = "be_cr",
    top_k: int = 8,
) -> dict:
    """Run analytical line-item query + table RAG + journalist synthesis."""
    cache_key = ((question or "").strip().lower(), ministry, fy, sort_by, top_k)
    if cache_key in _BUDGET_CACHE:
        return _BUDGET_CACHE[cache_key]

    ql = (question or "").lower()
    if "cut" in ql or "drop" in ql or "reduc" in ql or "under" in ql or "unspent" in ql:
        effective_sort = "biggest_cuts"
    elif "increas" in ql or "jump" in ql or "higher" in ql or "grew" in ql:
        effective_sort = "biggest_increases"
    else:
        effective_sort = sort_by

    line_items = query_budget_items(ministry=ministry, fy=fy, search=None, sort_by=effective_sort, limit=30)
    tables = retrieve_budget_tables(question, ministry=ministry, fy=fy, top_k=top_k)

    items_md_rows = [
        f"| {li['scheme_name']} | {li['ministry']} | {li['fy']} | "
        f"{li['be_cr'] if li['be_cr'] is not None else '—'} | "
        f"{li['re_cr'] if li['re_cr'] is not None else '—'} | "
        f"{li['be_re_gap_cr'] if li['be_re_gap_cr'] is not None else '—'} "
        f"({str(li['be_re_variance_pct']) + '%' if li['be_re_variance_pct'] is not None else '—'}) | "
        f"{li['next_be_cr'] if li['next_be_cr'] is not None else '—'} | p.{li['page']} |"
        for li in line_items[:25]
    ]
    structured_items_block = (
        "| Scheme / Line Item | Ministry | FY | BE (₹ Cr) | RE (₹ Cr) | BE→RE Gap (₹ Cr / %) | Next FY BE (₹ Cr) | Page |\n"
        "|---|---|---|---|---|---|---|---|\n"
        + ("\n".join(items_md_rows) if items_md_rows else "| (No pre-extracted line items matched) | — | — | — | — | — | — | — |")
    )

    tables_block = "\n\n---\n\n".join(
        f"[{t.get('title')} | Ministry: {t.get('ministry')} | FY: {t.get('fy')} | p.{t.get('page')}]\n{t.get('markdown')}"
        for t in tables[:top_k]
    )

    system_prompt = """You are an Investigative Data Journalist & Public Finance Analyst examining Indian Union Budget tables and Ministry Demands for Grants.

Answer the user's question using ONLY the provided STRUCTURED LINE-ITEM TABLE and SOURCE BUDGET TABLES.

Format your analysis into:
# 1. Headline Finding & Key Numbers
Direct analytical takeaway with exact ₹ Crore / Lakh figures and percentage variances between Budget Estimates (BE), Revised Estimates (RE), and next-year projections.

# 2. Structured Budget Comparison Table
A clean Markdown table showing:
| Scheme / Budget Head | Ministry | FY | Budget Estimate (BE) | Revised Estimate (RE) | BE→RE Variance (₹ Cr & %) | Next FY BE / Outlay | Citation |
|---|---|---|---|---|---|---|---|

# 3. Utilisation, Cuts & Capital vs. Revenue Analysis
Highlight schemes where RE fell short of BE (under-utilisation / budget cuts), schemes where allocations increased, and any capital vs. recurring splits.

Rules:
- Never invent numbers.
- Cite every row with its exact source report and page number [Report, p.XX]."""

    user_prompt = (
        f"STRUCTURED LINE-ITEM ROWS FROM NEO4J:\n{structured_items_block}\n\n"
        f"SOURCE BUDGET TABLES & PASSAGES:\n{tables_block}\n\n"
        f"JOURNALIST QUESTION: {question}\n\nANALYSIS:"
    )

    answer_text = None
    if DEEPSEEK_API_KEY:
        try:
            req = urllib.request.Request(
                "https://api.deepseek.com/chat/completions",
                data=json.dumps({
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2200,
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                answer_text = payload["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("DeepSeek budget synthesis failed, trying Gemini: %s", exc)

    if not answer_text and GEMINI_API_KEY:
        for model_name in dict.fromkeys([GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.5-flash-lite"]):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                req = urllib.request.Request(
                    url,
                    data=json.dumps({
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2200},
                    }).encode("utf-8"),
                    headers={
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=35) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    answer_text = payload["candidates"][0]["content"]["parts"][0]["text"]
                    break
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", model_name, exc)

    if not answer_text:
        answer_text = f"# Structured Budget Line Items\n\n{structured_items_block}"

    res = {
        "question": question,
        "answer": answer_text,
        "line_items": line_items,
        "sources": [
            {"title": t.get("title"), "ministry": t.get("ministry"), "fy": t.get("fy"), "page": t.get("page")}
            for t in tables[:8]
        ],
    }
    if len(_BUDGET_CACHE) >= _MAX_BUDGET_CACHE:
        _BUDGET_CACHE.pop(next(iter(_BUDGET_CACHE)))
    _BUDGET_CACHE[cache_key] = res
    return res
