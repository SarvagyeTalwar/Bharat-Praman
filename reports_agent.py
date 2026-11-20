"""Semantic Multi-Ministry Annual Reports GraphRAG Engine (Instance02 — Part 2 Upgraded).

Implements all 5 Part-2 Checklist upgrades:
1. Stratified Quota Retrieval: Round-robin interleaving across (ministry, year) slices +
   per-document diversity cap so cross-ministry and multi-year comparisons are 100% balanced.
2. Model Option for Reasoning (`deepseek-reasoner` / R1 vs `deepseek-chat` / V3): Supports
   explicit `"reasoner"` (R1), `"chat"` (V3), or `"auto"` selection for complex audit/growth queries.
3. Strict Unit Normalization in Prompt: Preserves verbatim source units (`Rs. in Crore`,
   `Rs. in Lakh`, `BE`, `RE`, `Actuals`) and forbids silent mental conversions.
4. Mandatory "Not Disclosed / Data Limitations" Section: Explicitly lists what requested
   breakdowns or years are absent from the retrieved pages to prevent hallucinated fills.
5. Lexical + Vector RRF Re-tuning: Boosts exact scheme acronym matches (`PM-SHRI`, `HEFA`,
   `STARS`, `PMGSY`, `KVS`, `NVS`, `MGNREGA`, `CRPF`, `BSF`, `PM-KISAN`) and financial table
   chunks into the Top-3 hits before context assembly.
"""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
import logging
import math
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

from glossary import annotate_answer, expand_query

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

logger = logging.getLogger("uvicorn.error")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE1") or None

DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or "").split("DEEPSEEK_API_KEY=")[-1].strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_REASONER_MODEL = os.getenv("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner")
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

VECTOR_INDEX = os.getenv("VECTOR_INDEX", "bge_chunk_embeddings")
FULLTEXT_INDEX = "chunk_fulltext"

# Canonical 8 major ministries for the 3-year Annual Reports collection
MAJOR_MINISTRIES = [
    {"id": "education", "name": "Education", "label": "Ministry of Education", "short": "MoE"},
    {"id": "home", "name": "Home Affairs", "label": "Ministry of Home Affairs", "short": "MHA"},
    {"id": "finance", "name": "Finance", "label": "Ministry of Finance", "short": "MoF"},
    {"id": "health", "name": "Health & Family Welfare", "label": "Ministry of Health & Family Welfare", "short": "MoHFW"},
    {"id": "defence", "name": "Defence", "label": "Ministry of Defence", "short": "MoD"},
    {"id": "rural", "name": "Rural Development", "label": "Ministry of Rural Development", "short": "MoRD"},
    {"id": "road", "name": "Road Transport & Highways", "label": "Ministry of Road Transport & Highways", "short": "MoRTH"},
    {"id": "agriculture", "name": "Agriculture & Farmers Welfare", "label": "Ministry of Agriculture & Farmers Welfare", "short": "MoAFW"},
]

MINISTRY_LOOKUP = {}
for _m in MAJOR_MINISTRIES:
    MINISTRY_LOOKUP[_m["id"]] = _m["name"]
    MINISTRY_LOOKUP[_m["name"].lower()] = _m["name"]
    MINISTRY_LOOKUP[_m["label"].lower()] = _m["name"]
    MINISTRY_LOOKUP[_m["short"].lower()] = _m["name"]
MINISTRY_LOOKUP.update({
    "internal affairs": "Home Affairs",
    "defense": "Defence",
    "modef": "Defence",
    "highways": "Road Transport & Highways",
    "farmers welfare": "Agriculture & Farmers Welfare",
})

SUPPORTED_YEARS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

KNOWN_SCHEME_ACRONYMS = {
    "PM-SHRI", "PMSHRI", "PM SHRI", "SAMAGRA SHIKSHA", "STARS", "HEFA", "RISE",
    "KVS", "NVS", "NCERT", "UGC", "AICTE", "NEP", "NIRF", "UDISE", "PM-POSHAN",
    "PMPOSHAN", "NILP", "RUSA", "PM-USHA", "SWAYAM", "DIKSHA", "NISHTHA",
    "CRPF", "BSF", "CISF", "ITBP", "SSB", "NSG", "NDRF", "NIA", "CCTNS", "ICJS",
    "MGNREGA", "PMGSY", "PMAY", "PMAY-G", "DAY-NRLM", "NSAP",
    "PM-KISAN", "PMFBY", "ENAM", "ICAR", "RKVY",
    "AYUSHMAN BHARAT", "PM-JAY", "PMJAY", "NHM", "AIIMS",
    "BHARATMALA", "NHAI", "FASTAG", "PARIVAHAN",
    "DRDO", "BRO", "AGNIPATH",
}

FINANCIAL_QUERY_RE = re.compile(
    r"\b(?:budget|outlay|expenditure|allocated|allocation|spending|spent|fund|funds|grant|grants|crore|crores|lakh|lakhs|be|re|actuals?|sanctioned|released|disbursed|cost|financial|amount|rupees|rs\.?|₹)\b",
    re.I,
)
REASONING_QUERY_RE = re.compile(
    r"\b(?:compare|comparison|vs\.?|versus|difference|gap|shortfall|cut|growth|increase|decrease|percentage|percent|%|ratio|trend|audit|discrepancy|change\s+from|across\s+ministries|year-over-year|yoy)\b",
    re.I,
)

_driver = None
_EXECUTOR = ThreadPoolExecutor(max_workers=8)
_ANSWER_CACHE: dict[tuple, tuple[str, list[dict], str]] = {}
_CACHE_LOCK = threading.Lock()
_MAX_CACHE_ENTRIES = 128


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


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", (text or "").lower())


def extract_query_acronyms(question: str) -> list[str]:
    """Extract uppercase scheme acronyms and known scheme names from a user question."""
    if not question:
        return []
    found = []
    q_upper = question.upper()
    # 1. Known multi-word or hyphenated scheme identifiers
    for known in sorted(KNOWN_SCHEME_ACRONYMS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(known)}\b", q_upper):
            found.append(known)
    # 2. Explicit uppercase tokens (2..10 chars) or hyphenated codes in user input
    for m in re.finditer(r"\b([A-Z]{2,10}(?:-[A-Z0-9]{1,8})?)\b", question):
        tok = m.group(1).upper()
        if tok not in {"WHAT", "WHEN", "WHERE", "WHICH", "HOW", "MUCH", "MANY", "TOTAL", "THE", "AND", "FOR", "FROM", "WITH", "YEAR", "IN", "OF", "TO"}:
            if tok not in found:
                found.append(tok)
    return found


def is_financial_query(question: str) -> bool:
    return bool(FINANCIAL_QUERY_RE.search(question or ""))


def should_use_reasoner(question: str, reasoning_mode: str | bool = "auto") -> bool:
    """Route synthesis to `deepseek-reasoner` (R1) only when explicitly requested; `"auto"` uses fast V3."""
    if isinstance(reasoning_mode, bool):
        return reasoning_mode
    mode = str(reasoning_mode or "auto").strip().lower()
    return mode in ("reasoner", "r1", "true", "1", "yes", "deep")


def resolve_ministries(ministry_arg: str | list[str] | None, question: str = "") -> list[str]:
    """Resolve user ministry selection + question keywords into canonical ministry names."""
    if isinstance(ministry_arg, list):
        raw_items = [str(x).strip().lower() for x in ministry_arg if str(x).strip()]
    elif isinstance(ministry_arg, str) and ministry_arg.strip():
        raw_items = [x.strip().lower() for x in ministry_arg.split(",") if x.strip()]
    else:
        raw_items = []

    if any(x in ("all", "both", "annual_reports", "annual reports", "compare") for x in raw_items):
        detected = detect_ministries_in_text(question)
        if raw_items == ["both"] and not detected:
            return ["Education", "Home Affairs"]
        return detected

    resolved = []
    for item in raw_items:
        canon = MINISTRY_LOOKUP.get(item)
        if canon and canon not in resolved:
            resolved.append(canon)
        elif item and item not in resolved:
            resolved.append(item.title())
    return resolved


def detect_ministries_in_text(question: str) -> list[str]:
    ql = (question or "").lower()
    found = []
    keyword_map = [
        ("Education", ["education", "school", "samagra shiksha", "pm shri", "pm-shri", "university", "ugc", "ncert", "kvs", "nvs", "higher education", "hefa", "stars project"]),
        ("Home Affairs", ["home affairs", "mha", "police", "capf", "crpf", "bsf", "cisf", "itbp", "border", "internal security", "cyber crime", "ndrf"]),
        ("Finance", ["finance ministry", "department of economic affairs", "department of expenditure", "direct tax", "cbdt", "cbic", "gst collection", "fiscal deficit"]),
        ("Health & Family Welfare", ["health ministry", "mohfw", "ayushman bharat", "pm-jay", "aiims", "nhm", "national health mission", "immunization", "hospital"]),
        ("Defence", ["defence", "defense", "armed forces", "army", "navy", "air force", "drdo", "border roads organisation", "agnipath"]),
        ("Rural Development", ["rural development", "mgnrega", "pmgsy", "pmay-g", "livelihoods mission", "day-nrlm", "panchayat"]),
        ("Road Transport & Highways", ["road transport", "morth", "nhai", "bharatmala", "national highway", "expressway", "fastag", "toll"]),
        ("Agriculture & Farmers Welfare", ["agriculture", "farmers welfare", "pm-kisan", "crop insurance", "pmfby", "msp", "icar", "foodgrain"]),
    ]
    for canon, keywords in keyword_map:
        if any(kw in ql for kw in keywords):
            found.append(canon)
    return found


def detect_years_in_text(question: str, explicit_years: list[str] | None = None) -> list[str]:
    q_text = question or ""
    found = []
    for m in re.finditer(r"\b(20\d{2})\s*[-–/]\s*(\d{2,4})\b", q_text):
        fy = f"{m.group(1)}-{m.group(2)[-2:]}"
        if fy not in found:
            found.append(fy)
    if len(found) == 2 and re.search(r"\b(?:from|between)\b.*\b(?:to|and)\b", q_text, re.I):
        start_y, end_y = int(found[0][:4]), int(found[1][:4])
        if 0 < (end_y - start_y) <= 6:
            found = [f"{y}-{str(y + 1)[-2:]}" for y in range(start_y, end_y + 1)]
    if found:
        return found
    if explicit_years:
        cleaned = [y.strip() for y in explicit_years if y and y.strip()]
        if len(cleaned) >= 5 and not re.search(
            r"\b(?:compare|growth|trend|across\s+years|year\s+by\s+year)\b",
            q_text,
            re.I,
        ):
            return []
        return cleaned
    return []


def get_reports_catalog() -> dict:
    """Return ingested ministries, fiscal years, and document counts from Instance02."""
    drv = get_driver()
    ingested = []
    if drv is not None:
        try:
            with drv.session(database=NEO4J_DATABASE) as s:
                rows = s.run(
                    """
                    MATCH (d:Document)
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                    RETURN coalesce(d.ministry, d.ministry_hint, 'Education') AS ministry,
                           coalesce(d.year, '2023-24') AS year,
                           d.title AS title,
                           d.file AS file,
                           count(c) AS chunk_count
                    ORDER BY ministry, year DESC
                    """
                ).data()
                ingested = rows
        except Exception as exc:
            logger.warning("Could not query Instance02 catalog: %s", exc)

    ingested_by_ministry = {}
    years_present = set()
    for r in ingested:
        m = r.get("ministry") or "Education"
        y = r.get("year") or "2023-24"
        years_present.add(y)
        ingested_by_ministry.setdefault(m, []).append({
            "year": y,
            "title": r.get("title"),
            "file": r.get("file"),
            "chunk_count": r.get("chunk_count", 0),
        })

    ministries_out = []
    for m in MAJOR_MINISTRIES:
        docs = ingested_by_ministry.get(m["name"], [])
        ministries_out.append({
            **m,
            "ingested_docs": len(docs),
            "ingested_chunks": sum(d["chunk_count"] for d in docs),
            "years": sorted({d["year"] for d in docs}),
        })

    return {
        "ministries": ministries_out,
        "supported_years": SUPPORTED_YEARS,
        "ingested_years": sorted(years_present),
        "documents": ingested,
    }


def _vector_search_slice(query_vec: list[float], k: int, ministry: str | None = None, year: str | None = None) -> list[dict]:
    drv = get_driver()
    if drv is None or not query_vec:
        return []
    pool = max(k * 8, 32)
    cypher = f"""
    CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $pool, $v) YIELD node, score
    MATCH (d:Document)-[:HAS_CHUNK]->(node)
    WHERE ($ministry IS NULL OR toLower(coalesce(node.ministry, d.ministry, '')) CONTAINS toLower($ministry))
      AND ($year IS NULL OR coalesce(node.year, d.year, '') = $year)
    OPTIONAL MATCH (node)-[:NEXT]->(nxt:Chunk)
    RETURN node.id AS id,
           coalesce(d.title, d.file, 'Annual Report') AS title,
           d.file AS file,
           coalesce(node.ministry, d.ministry, $ministry, 'Ministry') AS ministry,
           coalesce(node.year, d.year, '2023-24') AS year,
           coalesce(node.page_start, node.page, 1) AS page,
           node.page_end AS page_end,
           node.section AS section,
           node.breadcrumb AS breadcrumb,
           node.text AS text,
           nxt.text AS next_text,
           score
    ORDER BY score DESC
    LIMIT $k
    """
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            return s.run(cypher, pool=pool, k=k, v=query_vec, ministry=ministry, year=year).data()
    except Exception as exc:
        logger.warning("Vector search on %s failed: %s", VECTOR_INDEX, exc)
        return []


def _fulltext_search_slice(question: str, k: int, ministry: str | None = None, year: str | None = None) -> list[dict]:
    drv = get_driver()
    tokens = tokenize(question)
    if drv is None or not tokens:
        return []
    # Boost acronym terms in Lucene fulltext query with ^2 caret
    acronyms = {a.lower() for a in extract_query_acronyms(question)}
    q_parts = []
    for t in tokens[:16]:
        if t in acronyms or len(t) >= 6:
            q_parts.append(f"{t}^2")
        else:
            q_parts.append(t)
    q_str = " OR ".join(q_parts)
    cypher = f"""
    CALL db.index.fulltext.queryNodes('{FULLTEXT_INDEX}', $q) YIELD node, score
    MATCH (d:Document)-[:HAS_CHUNK]->(node)
    WHERE ($ministry IS NULL OR toLower(coalesce(node.ministry, d.ministry, '')) CONTAINS toLower($ministry))
      AND ($year IS NULL OR coalesce(node.year, d.year, '') = $year)
    OPTIONAL MATCH (node)-[:NEXT]->(nxt:Chunk)
    RETURN node.id AS id,
           coalesce(d.title, d.file, 'Annual Report') AS title,
           d.file AS file,
           coalesce(node.ministry, d.ministry, $ministry, 'Ministry') AS ministry,
           coalesce(node.year, d.year, '2023-24') AS year,
           coalesce(node.page_start, node.page, 1) AS page,
           node.page_end AS page_end,
           node.section AS section,
           node.breadcrumb AS breadcrumb,
           node.text AS text,
           nxt.text AS next_text,
           score
    ORDER BY score DESC
    LIMIT $k
    """
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            return s.run(cypher, q=q_str, k=k, ministry=ministry, year=year).data()
    except Exception as exc:
        logger.warning("Fulltext search on %s failed: %s", FULLTEXT_INDEX, exc)
        return []


def _rrf(
    ft_hits: list[dict],
    vec_hits: list[dict],
    k: int,
    question: str = "",
) -> list[dict]:
    """Re-tuned Lexical + Vector Reciprocal Rank Fusion with Acronym & Financial Table Boosting."""
    scores = {}
    by_id = {}
    in_vec = set()
    in_ft = set()

    for rank, r in enumerate(vec_hits):
        cid = r["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.25 / (50 + rank)
        by_id[cid] = r
        in_vec.add(cid)

    for rank, r in enumerate(ft_hits):
        cid = r["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.00 / (55 + rank)
        if cid not in by_id:
            by_id[cid] = r
        in_ft.add(cid)

    acronyms = extract_query_acronyms(question)
    fin_intent = is_financial_query(question)

    for cid, hit in by_id.items():
        haystack = " ".join([
            str(hit.get("section") or ""),
            str(hit.get("breadcrumb") or ""),
            str(hit.get("text") or ""),
        ]).upper()

        # 1. Dual-hit consensus bonus (matched both semantically and lexically)
        if cid in in_vec and cid in in_ft:
            scores[cid] += 0.012

        # 2. Exact Scheme / Acronym Boost (surfaces exact scheme line-items into Top-3)
        if acronyms:
            matched_acronyms = sum(1 for acr in acronyms if acr in haystack)
            if matched_acronyms > 0:
                scores[cid] += min(0.055, 0.022 * matched_acronyms)

        # 3. Financial Table & Unit Boost when question asks about budget/outlay/spending
        if fin_intent:
            txt = str(hit.get("text") or "")
            if "| --- |" in txt or "Unit:" in txt or re.search(r"\b(?:BE|RE)\s+20\d{2}\b", txt, re.I):
                scores[cid] += 0.015
            elif re.search(r"\b(?:crore|lakh|outlay|allocated|released)\b", txt, re.I):
                scores[cid] += 0.006

            # Penalize Table-of-Contents / front-matter pages so data tables outrank TOC hits
            has_toc_markers = bool(
                re.search(r"\btable\s+of\s+contents\b", txt, re.I)
                or (re.search(r"\bcontents\b", txt, re.I) and re.search(r"\.{4,}", txt))
            )
            page_num = hit.get("page")
            low_page_no_digits = isinstance(page_num, int) and page_num <= 3 and (
                not re.search(r"\d", txt) or bool(re.search(r"\bcontents\b", txt, re.I))
            )
            if has_toc_markers or low_page_no_digits:
                scores[cid] -= 0.018

        hit["rrf_score"] = round(scores[cid], 5)

    ranked = sorted(by_id.values(), key=lambda x: scores[x["id"]], reverse=True)
    return ranked[:k]


def _safe_embed_query(text: str) -> list[float] | None:
    try:
        from embeddings import embed_query
        return embed_query((text or "").strip())
    except Exception as exc:
        logger.warning("Qwen embedding unavailable locally, falling back to full-text search: %s", exc)
        return None


def stratified_hybrid_search(
    question: str,
    ministries: list[str] | None = None,
    years: list[str] | None = None,
    top_k: int = 8,
    raw_question: str | None = None,
) -> list[dict]:
    """Run parallel balanced hybrid search with round-robin quota allocation across ministries and fiscal years."""
    q_for_boost = raw_question or question
    m_slices = ministries if ministries else [None]
    y_slices = years if years else [None]
    num_buckets = len(m_slices) * len(y_slices)
    per_bucket_k = max(3, math.ceil(top_k / num_buckets) + 1)

    slices = [(m, y) for m in m_slices for y in y_slices]

    # Overlap local CPU query embedding with Neo4j fulltext network calls
    embed_fut = _EXECUTOR.submit(_safe_embed_query, q_for_boost)
    ft_futs = {
        (m, y): _EXECUTOR.submit(_fulltext_search_slice, question, per_bucket_k * 2, m, y)
        for m, y in slices
    }

    q_vec = embed_fut.result()
    vec_futs = (
        {
            (m, y): _EXECUTOR.submit(_vector_search_slice, q_vec, per_bucket_k * 2, m, y)
            for m, y in slices
        }
        if q_vec
        else {}
    )

    bucket_lists = []
    for m, y in slices:
        ft_hits = ft_futs[(m, y)].result()
        vec_hits = vec_futs[(m, y)].result() if (m, y) in vec_futs else []
        bucket_top = _rrf(ft_hits, vec_hits, per_bucket_k, question=q_for_boost)
        if bucket_top:
            bucket_lists.append(bucket_top)

    # Round-Robin Interleaving across all (ministry, year) buckets for strict quota balance
    combined = []
    seen_ids = set()
    max_depth = max((len(b) for b in bucket_lists), default=0)
    for depth in range(max_depth):
        for b in bucket_lists:
            if depth < len(b):
                hit = b[depth]
                if hit["id"] not in seen_ids:
                    seen_ids.add(hit["id"])
                    combined.append(hit)
                    if len(combined) >= top_k:
                        break
        if len(combined) >= top_k:
            break

    # Only run global fallback in parallel when stratified slices returned sparse hits
    if len(combined) < max(3, top_k // 2):
        ft_global_fut = _EXECUTOR.submit(_fulltext_search_slice, question, top_k * 3, None, None)
        vec_global_fut = _EXECUTOR.submit(_vector_search_slice, q_vec, top_k * 3, None, None) if q_vec else None
        ft_global = ft_global_fut.result()
        vec_global = vec_global_fut.result() if vec_global_fut else []
        global_ranked = _rrf(ft_global, vec_global, top_k * 2, question=q_for_boost)

        # Diversity pass 1: cap any single (ministry, year) document at ceil(top_k / 2) if multiple docs exist
        doc_counts = {}
        for h in combined:
            key = (h.get("ministry"), h.get("year"), h.get("title"))
            doc_counts[key] = doc_counts.get(key, 0) + 1
        max_per_doc = max(3, math.ceil(top_k / 2))

        overflow = []
        for hit in global_ranked:
            if hit["id"] in seen_ids:
                continue
            key = (hit.get("ministry"), hit.get("year"), hit.get("title"))
            if doc_counts.get(key, 0) < max_per_doc:
                seen_ids.add(hit["id"])
                doc_counts[key] = doc_counts.get(key, 0) + 1
                combined.append(hit)
                if len(combined) >= top_k:
                    break
            else:
                overflow.append(hit)

        # Diversity pass 2: if only 1 document exists in the DB, fill remaining slots from overflow
        for hit in overflow:
            if len(combined) >= top_k:
                break
            if hit["id"] not in seen_ids:
                seen_ids.add(hit["id"])
                combined.append(hit)

    return combined[:top_k]


def fetch_graph_context(hits: list[dict]) -> str:
    """Fetch Ministry, Minister governance, and multi-year graph traversal trace for retrieved documents."""
    drv = get_driver()
    if not hits:
        return ""
    titles = list({h.get("title") for h in hits if h.get("title")})
    ministries_hit = sorted({str(h.get("ministry") or "Ministry") for h in hits})
    years_hit = sorted({str(h.get("year") or "2023-24") for h in hits})
    trace_header = (
        f"Neo4j Hybrid Graph Trace: VectorIndex({VECTOR_INDEX}) + FulltextIndex({FULLTEXT_INDEX}) "
        f"-> (:Ministry)-[:PUBLISHED]->(:Document)-[:HAS_CHUNK]->(:Chunk)-[:NEXT]->(:Chunk) "
        f"| Ministries: {', '.join(ministries_hit)} | Fiscal Years: {', '.join(years_hit)}"
    )
    if drv is None or not titles:
        return trace_header
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            rows = s.run(
                """
                MATCH (d:Document)
                WHERE d.title IN $titles OR d.file IN $titles
                OPTIONAL MATCH (d)-[:ABOUT_MINISTRY|PUBLISHED]-(m:Ministry)
                OPTIONAL MATCH (p:Person)-[:HOLDS]->(m)
                OPTIONAL MATCH (p)-[:HAS_RANK]->(r:Rank)
                RETURN coalesce(d.title, d.file) AS title,
                       d.year AS year,
                       coalesce(m.fullName, m.name, d.ministry) AS ministry,
                       collect(DISTINCT {name: p.name, rank: r.name}) AS ministers
                """,
                titles=titles,
            ).data()
    except Exception:
        return trace_header

    lines = [trace_header]
    for r in rows:
        mins = ", ".join(
            f"{x['name']} ({x['rank']})" if x.get("rank") else x["name"]
            for x in (r.get("ministers") or [])
            if x.get("name")
        )
        lines.append(
            f"- Report: {r.get('title')} ({r.get('year') or 'n/a'}) | "
            f"Ministry: {r.get('ministry') or 'Government of India'}"
            + (f" | Accountable Ministers: {mins}" if mins else "")
        )
    return "\n".join(lines)


def _build_report_prompts(
    question: str,
    hits: list[dict],
    gctx: str,
    glossary_note: str = "",
    detail_level: str = "long",
    reasoning_mode: str | bool = "auto",
) -> tuple:
    """Build (system_prompt, user_prompt, max_tokens, short_mode, use_r1) for report synthesis."""
    ctx_blocks = []
    for i, h in enumerate(hits, 1):
        p_start = h.get("page")
        p_end = h.get("page_end")
        page_label = f"p.{p_start}-{p_end}" if p_end and p_end != p_start else f"p.{p_start}"
        header = f"[Source {i} | {h.get('title')} | Ministry: {h.get('ministry')} | FY: {h.get('year')} | {page_label}]"
        if h.get("breadcrumb"):
            header += f"\nBreadcrumb: {h['breadcrumb']}"
        passage = h.get("text") or ""
        if i <= 4 and h.get("next_text"):
            passage += "\n" + h["next_text"][:400]
        ctx_blocks.append(f"{header}\n{passage}")

    context = "\n\n---\n\n".join(ctx_blocks)
    short_mode = str(detail_level or "long").strip().lower() == "short"
    use_r1 = should_use_reasoner(question, reasoning_mode)

    if short_mode:
        max_tokens = 480
        system_prompt = """You are a Senior Civic Intelligence Analyst answering questions from Indian Government Annual Reports.

Give a CRISP, DIRECT, SHORT answer using ONLY the provided CONTEXT:
1. Start with a 2–3 sentence direct summary answering the question.
2. Follow with 3–5 concise bullet points for key figures, BE vs. RE comparisons, or scheme highlights.
3. **Strict Unit Normalization:** Always state the exact reporting unit from the source (`Rs. in Crore`, `Rs. in Lakh`, `BE`, `RE`, `Actuals`). Never silently convert Lakhs to Crores without writing the verbatim source number + unit first.
4. End with a single line `**Not Disclosed in Retrieved Pages:**` noting any requested detail not present in the passages.
5. Cite every figure with `[Report Title, p.XX]`. Never invent or extrapolate numbers outside the CONTEXT."""
    else:
        max_tokens = 1350
        system_prompt = """You are a Senior Policy & Civic Intelligence Analyst specializing in Indian Government Annual Reports across Ministries and Fiscal Years.

Provide a rigorous, comprehensive, and audit-grade briefing using ONLY the facts and figures in the provided CONTEXT.

Format your response using these exact 4 sections:
# 1. Executive Summary
High-level synthesis answering the question across all relevant ministries and fiscal years present in the evidence, explicitly calling out major Budget Estimate (BE) vs. Revised Estimate (RE) or release gaps.

# 2. Financial Allocation & Metric Breakdown
Present all relevant figures, schemes, or year-over-year / cross-ministry comparisons in a Markdown Table:
| Ministry / Scheme / Body | Fiscal Year | Budget / Outlay / Target (with Unit) | Revised / Released / Achievement (with Unit) | Variance / Audit Note | Citation |
|---|---|---|---|---|---|

# 3. Key Initiatives & Comparative Findings
Detailed breakdown of programs, physical assets, reforms, or cross-ministry / cross-year trends cited in the passages.

# 4. Information Not Disclosed & Data Limitations
MANDATORY SECTION: Explicitly list what specific breakdowns, fiscal years, state-wise splits, or metrics asked for (or implied) by the question are NOT disclosed in the retrieved source passages, and note any BE vs. RE or recurring vs. capital distinctions.

Strict Rules:
- **Strict Unit Normalization:** Always preserve and display the exact unit reported in the source passage (`Rs. in Crore`, `Rs. in Lakh`, `Actuals`, `BE`, `RE`). Never perform silent mental unit conversions; if you provide an approximate Crore conversion for a Lakh figure, always write the verbatim source figure and unit first (e.g. `Rs. 4,80,839.66 Lakh (approx. Rs. 4,808.40 Cr)`).
- Never invent, guess, or extrapolate numbers outside the CONTEXT.
- Every figure and claim MUST carry its source citation like `[Report Title, p.XX]`."""

    user_prompt = (
        f"GRAPH CONTEXT:\n{gctx or '(none)'}\n\n"
        f"GLOSSARY:\n{glossary_note or '(none)'}\n\n"
        f"CONTEXT PASSAGES:\n{context}\n\n"
        f"QUESTION: {question}\n\nREPORT:"
    )
    return system_prompt, user_prompt, max_tokens, short_mode, use_r1


def synthesize_report(
    question: str,
    hits: list[dict],
    gctx: str,
    glossary_note: str = "",
    detail_level: str = "long",
    reasoning_mode: str | bool = "auto",
    skip_deepseek: bool = False,
) -> str:
    """Generate a short or long cited briefing via DeepSeek (V3 or R1 Reasoner) or Gemini REST API."""
    system_prompt, user_prompt, max_tokens, short_mode, use_r1 = _build_report_prompts(
        question, hits, gctx, glossary_note, detail_level, reasoning_mode
    )

    # 1. Prefer DeepSeek (R1 reasoner or V3 chat) if DEEPSEEK_API_KEY is configured
    if DEEPSEEK_API_KEY and not skip_deepseek:
        models_to_try = (
            [DEEPSEEK_REASONER_MODEL, DEEPSEEK_MODEL]
            if use_r1
            else [DEEPSEEK_MODEL]
        )
        for ds_model in dict.fromkeys(models_to_try):
            try:
                body_dict = {
                    "model": ds_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                }
                if "reasoner" not in ds_model:
                    body_dict["temperature"] = 0.12

                req = urllib.request.Request(
                    "https://api.deepseek.com/chat/completions",
                    data=json.dumps(body_dict).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                timeout_s = 75 if "reasoner" in ds_model else 45
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    msg = payload["choices"][0]["message"]
                    content = msg.get("content") or ""
                    reasoning = (msg.get("reasoning_content") or "").strip()
                    if reasoning and not short_mode:
                        return (
                            f"<details><summary>DeepSeek R1 Audit Reasoning Trace</summary>\n\n"
                            f"{reasoning}\n\n</details>\n\n{content}"
                        )
                    return content
            except Exception as exc:
                logger.warning("DeepSeek model %s failed, trying fallback: %s", ds_model, exc)

    # 2. Gemini REST API
    if GEMINI_API_KEY:
        for model_name in dict.fromkeys([GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-3.8-flash"]):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                req = urllib.request.Request(
                    url,
                    data=json.dumps({
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": 0.15, "maxOutputTokens": max_tokens},
                    }).encode("utf-8"),
                    headers={
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=35) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    return payload["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", model_name, exc)

    # 3. Deterministic evidence fallback if no LLM key is reachable
    bullet_lines = [
        f"- **[{h.get('title')} | {h.get('year')} | p.{h.get('page')}]**: {(h.get('text') or '')[:350]}..."
        for h in hits[:6]
    ]
    return "# Retrieved Evidence Passages\n\n" + "\n".join(bullet_lines)


_MINISTRY_PORTAL_URLS = {
    "education": "https://www.education.gov.in/documents_reports",
    "home affairs": "https://www.mha.gov.in/en/documents/annual-reports",
    "defence": "https://mod.gov.in/documents/annual-report",
    "defense": "https://mod.gov.in/documents/annual-report",
    "finance": "https://dea.gov.in/",
    "health": "https://mohfw.gov.in/",
    "rural development": "https://rural.nic.in/",
    "road transport": "https://morth.nic.in/",
    "agriculture": "https://agriwelfare.gov.in/",
    "railways": "https://indianrailways.gov.in/",
    "external affairs": "https://www.mea.gov.in/annual-reports.htm",
}


def _source_portal_url(ministry: str = "", title: str = "", file_name: str = "") -> str:
    """Return the canonical official government portal URL for a report or Demand for Grants."""
    combined = f"{title or ''} {file_name or ''}".lower()
    if any(k in combined for k in ("dfg", "demand", "outcome", "budget", "eb")):
        return "https://www.indiabudget.gov.in/"
    m_low = (ministry or "").lower()
    for key, url in _MINISTRY_PORTAL_URLS.items():
        if key in m_low:
            return url
    return "https://www.indiabudget.gov.in/"


def search_reports(
    question: str,
    ministry: str | list[str] | None = "all",
    years: list[str] | None = None,
    top_k: int = 8,
    detail_level: str = "long",
) -> dict:
    """Fast retrieval-only search across Ministry & Budget reports (no LLM synthesis)."""
    target_ministries = resolve_ministries(ministry, question)
    target_years = detect_years_in_text(question, years)

    scope_label = target_ministries[0] if len(target_ministries) == 1 else "Education"
    expanded_q, gmatches = expand_query(question, scope_label)
    glossary_note = "; ".join(f"{m['acronym']} = {m['expansion']}" for m in gmatches)

    effective_k = 10 if str(detail_level or "long").strip().lower() == "short" else min(max(top_k, 10), 14)
    hits = stratified_hybrid_search(
        expanded_q,
        ministries=target_ministries or None,
        years=target_years or None,
        top_k=effective_k,
        raw_question=question,
    )
    gctx = fetch_graph_context(hits) if hits else ""

    ministers_by_ministry = {}
    drv = get_driver()
    hit_ministries = sorted({str(h.get("ministry") or "") for h in hits if h.get("ministry")})
    if drv is not None and hit_ministries:
        try:
            with drv.session(database=NEO4J_DATABASE) as s:
                m_rows = s.run(
                    """
                    UNWIND $mins AS min_name
                    MATCH (d:Document)-[:ISSUED_BY]->(m:Ministry {name: min_name})
                    OPTIONAL MATCH (mp:MP)-[hp:HOLDS_PORTFOLIO]->(m)
                    WITH min_name, mp, hp
                    ORDER BY coalesce(hp.rank_order, 2) ASC, mp.name ASC
                    RETURN min_name,
                           collect(DISTINCT CASE WHEN mp IS NOT NULL THEN {
                               entity_id: mp.entity_id,
                               name: mp.name,
                               party: coalesce(mp.party_name, 'BJP'),
                               constituency: coalesce(mp.constituency, '—'),
                               rank: coalesce(hp.rank, 'Cabinet Minister')
                           } END)[0..3] AS ministers
                    """,
                    mins=hit_ministries,
                ).data()
                for mr in m_rows:
                    ministers_by_ministry[mr["min_name"]] = mr.get("ministers") or []
        except Exception as exc:
            logger.warning("GraphRAG minister join failed: %s", exc)

    enriched_hits = []
    for h in hits:
        raw_text = " ".join((h.get("text") or "").split())
        excerpt = (raw_text[:480] + "...") if len(raw_text) > 480 else raw_text
        cid = h.get("id", "")
        h_min = h.get("ministry", "")
        enriched_hits.append(
            {
                "id": cid,
                "title": h.get("title", ""),
                "file": h.get("file", ""),
                "ministry": h_min,
                "year": h.get("year", ""),
                "page": h.get("page"),
                "page_end": h.get("page_end"),
                "section": h.get("section", ""),
                "breadcrumb": h.get("breadcrumb", ""),
                "excerpt": excerpt,
                "score": h.get("rrf_score", h.get("score", 0.0)),
                "ministers": ministers_by_ministry.get(h_min, []),
                "graph_path": "(:MP)-[:HOLDS_PORTFOLIO]->(:Ministry)<-[:ISSUED_BY]-(:Document)<-[:FROM]-(:Chunk)",
                "source_url": _source_portal_url(
                    h_min,
                    h.get("title", ""),
                    h.get("file", ""),
                ),
            }
        )

    return {
        "hits": enriched_hits,
        "glossary_note": glossary_note,
        "graph_context": gctx,
        "ministries": target_ministries,
        "years": target_years,
    }


def answer_reports(
    question: str,
    ministry: str | list[str] | None = "all",
    years: list[str] | None = None,
    top_k: int = 8,
    detail_level: str = "long",
    reasoning_mode: str | bool = "auto",
) -> tuple[str, list[dict], str]:
    """End-to-end multi-ministry, multi-year GraphRAG answer."""
    target_ministries = resolve_ministries(ministry, question)
    target_years = detect_years_in_text(question, years)
    use_r1 = should_use_reasoner(question, reasoning_mode)

    cache_key = (
        (question or "").strip().lower(),
        tuple(target_ministries),
        tuple(target_years),
        str(detail_level or "long").strip().lower(),
        use_r1,
    )
    with _CACHE_LOCK:
        cached = _ANSWER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    scope_label = target_ministries[0] if len(target_ministries) == 1 else "Education"
    expanded_q, gmatches = expand_query(question, scope_label)
    glossary_note = "; ".join(f"{m['acronym']} = {m['expansion']}" for m in gmatches)

    effective_k = 10 if str(detail_level or "long").strip().lower() == "short" else min(max(top_k, 10), 14)
    hits = stratified_hybrid_search(
        expanded_q,
        ministries=target_ministries or None,
        years=target_years or None,
        top_k=effective_k,
        raw_question=question,
    )
    if not hits:
        return (
            "No matching annual-report passages were found in Instance02 for the selected ministry/year filter. "
            f"Verify that the reports are ingested into `{VECTOR_INDEX}`.",
            [],
            "",
        )

    gctx = fetch_graph_context(hits)
    raw_ans = synthesize_report(
        question,
        hits,
        gctx,
        glossary_note,
        detail_level=detail_level,
        reasoning_mode=reasoning_mode,
    )
    annotated_ans, _ = annotate_answer(raw_ans, scope_label)
    result = (annotated_ans, hits, gctx)
    with _CACHE_LOCK:
        if len(_ANSWER_CACHE) >= _MAX_CACHE_ENTRIES:
            _ANSWER_CACHE.pop(next(iter(_ANSWER_CACHE)))
        _ANSWER_CACHE[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SSE streaming (token-by-token) variants
# ---------------------------------------------------------------------------
def synthesize_report_stream(
    question: str,
    hits: list[dict],
    gctx: str,
    glossary_note: str = "",
    detail_level: str = "long",
    reasoning_mode: str | bool = "auto",
):
    """Yield (kind, text) tuples where kind is 'reasoning' or 'content'.

    Streams DeepSeek tokens as they arrive. If streaming fails before any token is
    emitted, falls back to the non-streaming Gemini / evidence path in one chunk.
    """
    system_prompt, user_prompt, max_tokens, short_mode, use_r1 = _build_report_prompts(
        question, hits, gctx, glossary_note, detail_level, reasoning_mode
    )

    if DEEPSEEK_API_KEY:
        models_to_try = [DEEPSEEK_REASONER_MODEL, DEEPSEEK_MODEL] if use_r1 else [DEEPSEEK_MODEL]
        for ds_model in dict.fromkeys(models_to_try):
            emitted = False
            try:
                body_dict = {
                    "model": ds_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if "reasoner" not in ds_model:
                    body_dict["temperature"] = 0.12
                req = urllib.request.Request(
                    "https://api.deepseek.com/chat/completions",
                    data=json.dumps(body_dict).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                    method="POST",
                )
                timeout_s = 75 if "reasoner" in ds_model else 45
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    for raw in resp:
                        line = raw.decode("utf-8", "ignore").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        r_txt = delta.get("reasoning_content")
                        if r_txt and not short_mode:
                            emitted = True
                            yield ("reasoning", r_txt)
                        c_txt = delta.get("content")
                        if c_txt:
                            emitted = True
                            yield ("content", c_txt)
                if emitted:
                    return
            except Exception as exc:
                logger.warning("DeepSeek stream %s failed: %s", ds_model, exc)
                if emitted:
                    yield ("content", "\n\n_[Stream interrupted. Partial answer shown.]_")
                    return

    yield (
        "content",
        synthesize_report(
            question, hits, gctx, glossary_note,
            detail_level=detail_level, reasoning_mode=reasoning_mode, skip_deepseek=True,
        ),
    )


def answer_reports_stream(
    question: str,
    ministry: str | list[str] | None = "all",
    years: list[str] | None = None,
    top_k: int = 8,
    detail_level: str = "long",
    reasoning_mode: str | bool = "auto",
):
    """Streaming twin of answer_reports(). Yields dict events:

    {"type": "meta", "hits": [...], "graph_context": str, "cached": bool, "reasoning_mode": str}
    {"type": "reasoning" | "content", "delta": str}
    {"type": "done", "answer": str}   # final glossary-annotated answer (same as answer_reports)
    """
    target_ministries = resolve_ministries(ministry, question)
    target_years = detect_years_in_text(question, years)
    use_r1 = should_use_reasoner(question, reasoning_mode)
    short_mode = str(detail_level or "long").strip().lower() == "short"
    mode_label = "reasoner" if use_r1 else "chat"

    cache_key = (
        (question or "").strip().lower(),
        tuple(target_ministries),
        tuple(target_years),
        str(detail_level or "long").strip().lower(),
        use_r1,
    )
    with _CACHE_LOCK:
        cached = _ANSWER_CACHE.get(cache_key)
    if cached is not None:
        yield {"type": "meta", "hits": cached[1], "graph_context": cached[2], "cached": True, "reasoning_mode": mode_label}
        yield {"type": "done", "answer": cached[0]}
        return

    scope_label = target_ministries[0] if len(target_ministries) == 1 else "Education"
    expanded_q, gmatches = expand_query(question, scope_label)
    glossary_note = "; ".join(f"{m['acronym']} = {m['expansion']}" for m in gmatches)

    effective_k = 10 if short_mode else min(max(top_k, 10), 14)
    hits = stratified_hybrid_search(
        expanded_q,
        ministries=target_ministries or None,
        years=target_years or None,
        top_k=effective_k,
        raw_question=question,
    )
    if not hits:
        yield {"type": "meta", "hits": [], "graph_context": "", "cached": False, "reasoning_mode": mode_label}
        yield {
            "type": "done",
            "answer": "No matching annual-report passages were found for the selected ministry/year filter.",
        }
        return

    gctx = fetch_graph_context(hits)
    yield {"type": "meta", "hits": hits, "graph_context": gctx, "cached": False, "reasoning_mode": mode_label}

    reasoning_parts: list[str] = []
    content_parts: list[str] = []
    for kind, txt in synthesize_report_stream(
        question, hits, gctx, glossary_note,
        detail_level=detail_level, reasoning_mode=reasoning_mode,
    ):
        (reasoning_parts if kind == "reasoning" else content_parts).append(txt)
        yield {"type": kind, "delta": txt}

    content = "".join(content_parts)
    reasoning = "".join(reasoning_parts).strip()
    if reasoning and not short_mode:
        raw_ans = (
            f"<details><summary>DeepSeek R1 Audit Reasoning Trace</summary>\n\n"
            f"{reasoning}\n\n</details>\n\n{content}"
        )
    else:
        raw_ans = content

    annotated_ans, _ = annotate_answer(raw_ans, scope_label)
    if "_[Stream interrupted" not in content:
        with _CACHE_LOCK:
            if len(_ANSWER_CACHE) >= _MAX_CACHE_ENTRIES:
                _ANSWER_CACHE.pop(next(iter(_ANSWER_CACHE)))
            _ANSWER_CACHE[cache_key] = (annotated_ans, hits, gctx)
    yield {"type": "done", "answer": annotated_ans}
