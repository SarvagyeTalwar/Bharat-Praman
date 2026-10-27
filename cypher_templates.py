"""Deterministic Cypher templates for common politician-graph question shapes.

Each template returns a plan dict compatible with main.ask_graph:
    {result_type, cypher, parameters, explanation, template_id}

Templates are only used when the question shape is clear. Anything ambiguous
falls through to the Gemini planner.
"""
import re
from typing import Optional

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "NCT of Delhi",
    "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh", "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli and Daman and Diu", "Lakshadweep",
]

PARTY_ALIASES = {
    "bjp": "BJP", "bharatiya janata party": "BJP",
    "inc": "INC", "congress": "INC", "indian national congress": "INC",
    "aap": "AAP", "aam aadmi party": "AAP",
    "bsp": "BSP", "sp": "SP", "samajwadi party": "SP",
    "dmk": "DMK", "aiadmk": "AIADMK", "tmc": "TMC", "trinamool": "TMC",
    "tdp": "TDP", "ysrcp": "YSRCP", "jdu": "JDU", "rjd": "RJD",
    "ncp": "NCP", "shiv sena": "Shiv Sena", "ss": "Shiv Sena",
}

EMPTY_OK_TEMPLATES = {
    "case_section_overlap", "assets_and_cases_threshold",
    "mlas_in_state", "mlas_in_state_filtered",
    "top_constituencies_in_state", "party_highest_metric_in_state",
    "richest_mla", "most_cases_mla", "highest_liabilities_mla",
    "top_cases_mlas", "negative_net_worth", "mps_negative_net_worth",
    "entity_count", "constituency_counts", "party_mla_count",
    "case_threshold_count", "money_threshold_count", "party_most_with_cases",
    "party_most_zero_cases", "party_total_metric", "constituency_most_cases",
    "party_most_by_section", "count_mlas_by_section", "count_mlas_zero_cases",
    "ministers_with_cases", "minister_portfolios", "minister_of",
    "mp_party_most_cases", "mp_state_most_cases", "mp_count_with_cases",
    "mp_assets_above", "mp_highest_liabilities",
    "party_most_mlas", "state_most_mlas",
}

TEMPLATE_COLUMNS = {
    "mps_negative_net_worth": {"mp_name", "party", "total_assets", "liabilities", "shortfall"},
    "count_mlas_with_cases": {"mlas_with_cases"},
    "richest_mla": {"mla_name", "party", "total_assets", "liabilities"},
    "richest_politician": {"name", "party", "total_assets", "labels"},
    "highest_liabilities_mla": {"mla_name", "party", "liabilities", "total_assets"},
    "mlas_in_state_filtered": {"mla_name", "party", "constituency", "state", "cases", "total_assets", "liabilities"},
    "party_highest_metric_in_state": {"party_name", "mla_count"},
    "top_constituencies_in_state": {"constituency_name", "case_count", "mla_name"},
    "negative_net_worth": {"name", "party", "labels", "total_assets", "liabilities", "shortfall"},
    "top_cases_mlas": {"mla_name", "party", "case_count"},
    "most_cases_mla": {"mla_name", "party", "case_count"},
    "section_example": {"mla_name", "party", "section_code", "case_ref", "status"},
    "most_common_crime": {"section_code", "mla_count", "case_count"},
    "mlas_in_state": {"mla_name", "party", "constituency", "state"},
    "sample_politicians": {"mla_name", "party"},
    "asset_stats": {"mlas_with_assets", "average_assets", "median_assets", "max_assets"},
    "data_counts": {"label", "count"},
    "party_counts_by_section": {"party_name", "representative_count"},
    "state_party_counts_by_section": {"state_name", "party_name", "mla_count"},
    "state_case_percentage": {"state_name", "total_mlas", "mlas_with_cases", "percentage_with_cases"},
    "top_mlas_by_assets": {"mla_name", "party", "total_assets", "liabilities", "case_count", "sections"},
    "zero_cases_high_liabilities": {"party", "mla_count"},
    "case_section_overlap": {"mla_name", "party"},
    "top_constituencies_by_cases": {"constituency_name", "case_count", "mla_name"},
    "assets_and_cases_threshold": {"mla_name", "party", "total_assets", "criminal_case_count"},
    "mla_multi_constraint": {"mla_name", "party", "state", "constituency", "cases", "total_assets"},
    "top_sections_with_party": {"section_code", "total_mlas", "top_party"},
    "party_highest_average": {"party_name", "avg_cases", "mla_count"},
    "party_average_vs_mla": {"mla_name", "party_name", "mla_cases", "party_avg_cases", "excess_cases"},
    "elected_and_ministry": {"politician_name", "ministry_name", "portfolio_type", "total_assets"},
    "state_assets_summary": {"state_name", "average_total_assets", "median_total_assets", "top_3_mlas"},
    "combined_liabilities_union": {"scope", "name", "value"},
    "constituency_counts": {"parliamentary_constituencies", "assembly_constituencies"},
    "party_mla_count": {"mla_count"},
    "case_threshold_count": {"mla_count"},
    "money_threshold_count": {"mla_count"},
    "party_most_mlas": {"party_name", "mla_count"},
    "state_most_mlas": {"state_name", "mla_count"},
    "party_most_with_cases": {"party_name", "mla_count"},
    "party_most_zero_cases": {"party_name", "mla_count"},
    "constituency_most_cases": {"constituency_name", "case_count", "mla_name"},
    "party_most_by_section": {"party_name", "mla_count"},
    "count_mlas_by_section": {"mla_count"},
    "count_mlas_zero_cases": {"mlas_with_zero_cases"},
    "ministers_with_cases": {"name", "party", "ministries", "case_count"},
    "minister_portfolios": {"name", "party", "ministry", "portfolio_type"},
    "minister_of": {"name", "party", "ministry", "portfolio_type"},
    "mp_party_most_cases": {"party_name", "mp_count"},
    "mp_state_most_cases": {"state_name", "mp_count"},
    "mp_count_with_cases": {"mp_count"},
    "mp_assets_above": {"mp_count"},
    "mp_highest_liabilities": {"mp_name", "party", "liabilities", "total_assets"},
}


def _section_codes(q: str) -> list[str]:
    """Extract IPC/section codes, excluding years and small counts."""
    codes = []
    for raw in re.findall(r"\b(\d{1,4}[A-Z]?)\b", q):
        digits = re.sub(r"[A-Z]", "", raw)
        if not digits.isdigit():
            continue
        n = int(digits)
        if 1900 <= n <= 2099:  # years
            continue
        if n < 10:  # avoid "2 cases", "5 MLAs"
            continue
        codes.append(raw.upper())
    # de-duplicate preserving order
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _money(q: str) -> Optional[float]:
    patterns = [
        r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(crore|lakh|lakhs)?",
        r"(?:above|over|more than|exceeding|greater than)\s*([\d,]+(?:\.\d+)?)\s*(crore|lakh|lakhs)",
    ]
    for pat in patterns:
        m = re.search(pat, q, re.I)
        if not m:
            continue
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        if unit.startswith("crore"):
            value *= 10_000_000
        elif unit.startswith("lakh"):
            value *= 100_000
        return value
    return None


def _int_after(q: str, words: str) -> Optional[int]:
    m = re.search(rf"(?:{words})\s+(\d+)", q, re.I)
    return int(m.group(1)) if m else None


def _top_n(q: str, default: int = 10) -> int:
    n = _int_after(q, r"top|first|richest")
    if n is None:
        n = _int_after(q, r"top")
    return max(1, min(50, n or default))


def _state(q: str) -> str:
    ql = q.lower()
    # The graph stores Delhi as "NCT of Delhi"; use the canonical name.
    if "delhi" in ql:
        return "NCT of Delhi"
    for state in sorted(INDIAN_STATES, key=len, reverse=True):
        if state.lower() in ql:
            return state
    return ""


def _states(q: str) -> list[str]:
    ql = q.lower()
    found = [s for s in INDIAN_STATES if s.lower() in ql]
    # Prefer "NCT of Delhi" over "Delhi" when both match, and de-duplicate.
    out = []
    for s in sorted(found, key=len, reverse=True):
        if not any(s.lower() in existing.lower() or existing.lower() in s.lower() for existing in out):
            out.append(s)
    return out


def _ipc_section(q: str) -> str:
    m = re.search(r"(?:ipc|section)\s*([0-9]{1,4}[A-Z]?)", q, re.I)
    return m.group(1).upper() if m else ""


def _party(q: str) -> str:
    ql = q.lower()
    for alias, canonical in sorted(PARTY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", ql):
            return canonical
    return ""


def _has(q: str, *words: str) -> bool:
    ql = q.lower()
    return all(w.lower() in ql for w in words)


def _any(q: str, *words: str) -> bool:
    ql = q.lower()
    return any(w.lower() in ql for w in words)


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------

def _mps_negative_net_worth(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MP:Person)
            WHERE m.total_assets IS NOT NULL AND m.liabilities IS NOT NULL
              AND m.liabilities > m.total_assets
            RETURN m.name AS mp_name, m.party_name AS party,
                   m.total_assets AS total_assets, m.liabilities AS liabilities,
                   (m.liabilities - m.total_assets) AS shortfall
            ORDER BY shortfall DESC
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "MPs whose declared liabilities exceed declared total assets, with the shortfall.",
        "template_id": "mps_negative_net_worth",
    }


def _count_mlas_with_cases(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE coalesce(m.criminal_case_count, 0) > 0
            RETURN count(DISTINCT m) AS mlas_with_cases
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "Total number of MLAs with at least one recorded criminal case.",
        "template_id": "count_mlas_with_cases",
    }


def _richest_mla(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA:Person)
            OPTIONAL MATCH (m)-[:REPRESENTS]->(:AssemblyConstituency)-[:IN_STATE]->(s:State)
            WITH m, collect(DISTINCT s.name) AS states
            WHERE m.total_assets IS NOT NULL
              AND ($state = '' OR $state IN states)
              AND ($party = '' OR m.party_name CONTAINS $party)
            RETURN m.name AS mla_name, m.party_name AS party,
                   m.total_assets AS total_assets, m.liabilities AS liabilities
            ORDER BY total_assets DESC
            LIMIT 1
        """,
        "parameters": {"state": _state(q), "party": _party(q)},
        "explanation": "The single MLA with the highest declared total assets, optionally filtered by state or party.",
        "template_id": "richest_mla",
    }


def _richest_politician(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)
            WHERE p.total_assets IS NOT NULL
            RETURN p.name AS name, p.party_name AS party,
                   p.total_assets AS total_assets, labels(p) AS labels
            ORDER BY total_assets DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "The single Person/MLA with the highest declared total assets.",
        "template_id": "richest_politician",
    }


def _most_cases_mla(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA:Person)
            OPTIONAL MATCH (m)-[:REPRESENTS]->(:AssemblyConstituency)-[:IN_STATE]->(s:State)
            WITH m, collect(DISTINCT s.name) AS states
            WHERE ($state = '' OR $state IN states)
              AND ($party = '' OR m.party_name CONTAINS $party)
            RETURN m.name AS mla_name, m.party_name AS party,
                   m.criminal_case_count AS case_count
            ORDER BY case_count DESC
            LIMIT 1
        """,
        "parameters": {"state": _state(q), "party": _party(q)},
        "explanation": "The MLA with the highest recorded criminal-case count, optionally filtered by state or party.",
        "template_id": "most_cases_mla",
    }


def _section_example(q):
    ql = q.lower()
    codes = []
    if "attempt to murder" in ql:
        codes = ["307"]
    elif "murder" in ql:
        codes = ["302"]
    else:
        section = _ipc_section(q)
        if section:
            codes = [section]
    if not codes:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:FACES]->(c:CriminalCase)-[:UNDER]->(s:Section)
            WHERE s.code IN $section_codes
            RETURN m.name AS mla_name, m.party_name AS party, s.code AS section_code,
                   coalesce(c.case_no, c.case_id, c.fir_no) AS case_ref,
                   c.status AS status
            ORDER BY m.criminal_case_count DESC
            LIMIT 5
        """,
        "parameters": {"section_codes": codes},
        "explanation": f"Examples of MLAs charged under section {', '.join(codes)}, with case reference and status.",
        "template_id": "section_example",
    }


def _most_common_crime(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (s:Section)<-[:UNDER]-(cc:CriminalCase)<-[:FACES]-(m:MLA)
            WHERE s.code <> 'IPC'
            RETURN s.code AS section_code, count(DISTINCT m) AS mla_count,
                   count(DISTINCT cc) AS case_count
            ORDER BY mla_count DESC
            LIMIT 10
        """,
        "parameters": {},
        "explanation": "The most common IPC sections among MLAs, ranked by distinct MLA count.",
        "template_id": "most_common_crime",
    }


def _mlas_in_state(q):
    state = _state(q)
    if not state:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(s:State)
            WHERE toLower(s.name) CONTAINS toLower($state)
            RETURN m.name AS mla_name, m.party_name AS party,
                   ac.name AS constituency, s.name AS state
            ORDER BY mla_name
            LIMIT 25
        """,
        "parameters": {"state": state},
        "explanation": f"MLAs representing constituencies in {state}, with their party and constituency.",
        "template_id": "mlas_in_state",
    }


def _sample_politicians(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA:Person)
            RETURN m.name AS mla_name, m.party_name AS party
            ORDER BY mla_name
            LIMIT 5
        """,
        "parameters": {},
        "explanation": "A small sample of MLA/Person nodes to show what the graph contains.",
        "template_id": "sample_politicians",
    }


def _asset_stats(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE m.total_assets IS NOT NULL
            RETURN count(m) AS mlas_with_assets,
                   round(avg(m.total_assets), 0) AS average_assets,
                   percentileCont(m.total_assets, 0.5) AS median_assets,
                   max(m.total_assets) AS max_assets
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "Summary asset statistics across MLAs: count, average, median, and maximum declared assets.",
        "template_id": "asset_stats",
    }


def _data_counts(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person) RETURN 'Person' AS label, count(p) AS count
            UNION ALL
            MATCH (m:MLA) RETURN 'MLA' AS label, count(m) AS count
            UNION ALL
            MATCH (c:CriminalCase) RETURN 'CriminalCase' AS label, count(c) AS count
            UNION ALL
            MATCH (p:Party) RETURN 'Party' AS label, count(p) AS count
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "Node counts for Person, MLA, CriminalCase, and Party labels.",
        "template_id": "data_counts",
    }


def _party_counts_by_section(q):
    steps = _section_codes(q)
    if not steps:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Party)<-[:MEMBER_OF]-(m:MLA)-[:FACES]->(cc:CriminalCase)-[:UNDER]->(s:Section)
            WHERE s.code IN $section_codes
            RETURN p.name AS party_name, count(DISTINCT m) AS representative_count
            ORDER BY representative_count DESC
            LIMIT 50
        """,
        "parameters": {"section_codes": steps},
        "explanation": f"Counts distinct MLAs per party charged under sections {', '.join(steps)}.",
        "template_id": "party_counts_by_section",
    }


def _state_party_counts_by_section(q):
    steps = _section_codes(q)
    if not steps:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:MEMBER_OF]->(p:Party),
                  (m)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(s:State),
                  (m)-[:FACES]->(cc:CriminalCase)-[:UNDER]->(sec:Section)
            WHERE sec.code IN $section_codes
            RETURN s.name AS state_name, p.name AS party_name, count(DISTINCT m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 50
        """,
        "parameters": {"section_codes": steps},
        "explanation": f"Breaks down MLA counts by state and party for sections {', '.join(steps)}.",
        "template_id": "state_party_counts_by_section",
    }


def _state_case_percentage(q):
    ascending = _any(q.lower(), "lowest", "least", "smallest", "bottom")
    direction = "ASC" if ascending else "DESC"
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (s:State)<-[:IN_STATE]-(ac:AssemblyConstituency)<-[:REPRESENTS]-(m:MLA)
            WITH s.name AS state_name,
                 count(DISTINCT m) AS total_mlas,
                 count(DISTINCT CASE WHEN m.criminal_case_count > 0 THEN m END) AS mlas_with_cases
            RETURN state_name, total_mlas, mlas_with_cases,
                   round(mlas_with_cases * 100.0 / total_mlas, 2) AS percentage_with_cases
            ORDER BY percentage_with_cases {direction}
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "Percentage of MLAs with at least one recorded criminal case, by state"
                       + (" (lowest first)." if ascending else " (highest first)."),
        "template_id": "state_case_percentage",
    }


def _mla_multi_constraint(q):
    parties = [_party(q)] if _party(q) else []
    states = _states(q)
    ipc_section = _ipc_section(q)
    min_assets = _money(q) or 0
    min_cases = _int_after(q, r"more than|over|above") or 0
    if not parties or not states or not ipc_section:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA:Person)-[:MEMBER_OF]->(p:Party)
            MATCH (m)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(s:State)
            MATCH (m)-[:FACES]->(cc:CriminalCase)-[:UNDER]->(sec:Section)
            WHERE p.name IN $parties
              AND s.name IN $states
              AND m.criminal_case_count > $min_cases
              AND m.total_assets > $min_assets
              AND sec.code = $ipc_section
            RETURN DISTINCT m.name AS mla_name, p.name AS party, s.name AS state,
                   ac.name AS constituency, m.criminal_case_count AS cases,
                   m.total_assets AS total_assets
            ORDER BY total_assets DESC
            LIMIT 50
        """,
        "parameters": {
            "parties": parties, "states": states,
            "min_cases": min_cases, "min_assets": min_assets,
            "ipc_section": ipc_section,
        },
        "explanation": "MLAs matching all requested constraints: party, states, minimum cases, minimum assets, and a specific IPC section.",
        "template_id": "mla_multi_constraint",
    }


def _highest_liabilities_mla(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA:Person)
            OPTIONAL MATCH (m)-[:REPRESENTS]->(:AssemblyConstituency)-[:IN_STATE]->(s:State)
            WITH m, collect(DISTINCT s.name) AS states
            WHERE ($state = '' OR $state IN states)
              AND ($party = '' OR m.party_name CONTAINS $party)
            RETURN m.name AS mla_name, m.party_name AS party,
                   m.liabilities AS liabilities, m.total_assets AS total_assets
            ORDER BY liabilities DESC
            LIMIT 1
        """,
        "parameters": {"state": _state(q), "party": _party(q)},
        "explanation": "The MLA with the highest declared liabilities, optionally filtered by state or party.",
        "template_id": "highest_liabilities_mla",
    }


def _mlas_in_state_filtered(q):
    state = _state(q)
    if not state:
        return None
    ql = q.lower()
    party = _party(q)
    zero_cases = bool(re.search(r"zero\s+(?:criminal\s+)?cases", ql))
    # Any mention of cases/charges means the user wants only MLAs who have them,
    # unless they explicitly asked for zero cases.
    has_cases = bool(re.search(r"\bcases?\b|\bcharged\b|\bcharges?\b", ql)) and not zero_cases
    min_cases = _int_after(q, r"more than|over|above") if "criminal case" in ql else 0
    min_assets = _money(q) if "asset" in ql else 0
    min_liabilities = _money(q) if "liabilit" in ql else 0
    section = _ipc_section(q) or ("302" if "murder" in ql else "")
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:MEMBER_OF]->(p:Party)
            MATCH (m)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(s:State)
            OPTIONAL MATCH (m)-[:FACES]->(:CriminalCase)-[:UNDER]->(sec:Section)
            WITH m, p, ac, s, collect(DISTINCT sec.code) AS sections
            WHERE toLower(s.name) CONTAINS toLower($state)
              AND ($party = '' OR p.name CONTAINS $party)
              AND ($has_cases = false OR m.criminal_case_count > 0)
              AND ($min_cases = 0 OR m.criminal_case_count > $min_cases)
              AND ($min_assets = 0 OR m.total_assets > $min_assets)
              AND ($min_liabilities = 0 OR m.liabilities > $min_liabilities)
              AND ($zero_cases = false OR m.criminal_case_count = 0)
              AND ($section = '' OR $section IN sections)
            RETURN m.name AS mla_name, p.name AS party, ac.name AS constituency,
                   s.name AS state, m.criminal_case_count AS cases,
                   m.total_assets AS total_assets, m.liabilities AS liabilities
            ORDER BY cases DESC, total_assets DESC
            LIMIT 50
        """,
        "parameters": {
            "state": state, "party": party, "has_cases": has_cases,
            "min_cases": min_cases or 0, "min_assets": min_assets or 0,
            "min_liabilities": min_liabilities or 0, "zero_cases": zero_cases,
            "section": section,
        },
        "explanation": "MLAs in the requested state with optional party, case, asset, liability, or IPC filters.",
        "template_id": "mlas_in_state_filtered",
    }


def _party_highest_metric_in_state(q):
    state = _state(q)
    if not state:
        return None
    ql = q.lower()
    if "liabilit" in ql:
        prop, label = "liabilities", "average_liabilities"
    elif "asset" in ql:
        prop, label = "total_assets", "average_assets"
    else:
        prop, label = "criminal_case_count", "average_cases"
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (m:MLA)-[:MEMBER_OF]->(p:Party)
            MATCH (m)-[:REPRESENTS]->(:AssemblyConstituency)-[:IN_STATE]->(s:State)
            WHERE toLower(s.name) CONTAINS toLower($state)
            WITH p, avg(toFloat(m.{prop})) AS average_value, count(DISTINCT m) AS mla_count
            WHERE mla_count >= 5
            RETURN p.name AS party_name, round(average_value, 2) AS {label}, mla_count
            ORDER BY {label} DESC
            LIMIT 1
        """,
        "parameters": {"state": state},
        "explanation": f"Party with the highest average {prop.replace('_', ' ')} among MLAs in {state}.",
        "template_id": "party_highest_metric_in_state",
    }


def _top_constituencies_in_state(q):
    state = _state(q)
    if not state:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(s:State)
            WHERE toLower(s.name) CONTAINS toLower($state)
            MATCH (m)-[:FACES]->(cc:CriminalCase)
            RETURN ac.name AS constituency_name, count(DISTINCT cc) AS case_count,
                   collect(DISTINCT m.name)[0] AS mla_name
            ORDER BY case_count DESC
            LIMIT 15
        """,
        "parameters": {"state": state},
        "explanation": f"Top constituencies in {state} by the number of distinct criminal cases linked to their MLA.",
        "template_id": "top_constituencies_in_state",
    }


def _negative_net_worth(q):
    ql = q.lower()
    label = "MP" if ("mp" in ql or "member of parliament" in ql) else ("MLA" if "mla" in ql else "Person")
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)
            WHERE p.total_assets IS NOT NULL AND p.liabilities IS NOT NULL
              AND p.liabilities > p.total_assets
              AND ($label = 'Person' OR $label IN labels(p))
            RETURN p.name AS name, p.party_name AS party, labels(p) AS labels,
                   p.total_assets AS total_assets, p.liabilities AS liabilities,
                   (p.liabilities - p.total_assets) AS shortfall
            ORDER BY shortfall DESC
            LIMIT 50
        """,
        "parameters": {"label": label},
        "explanation": "Politicians whose declared liabilities exceed declared total assets, with the shortfall.",
        "template_id": "negative_net_worth",
    }


def _top_cases_mlas(q):
    n = _top_n(q, 5)
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (m:MLA:Person)
            RETURN m.name AS mla_name, m.party_name AS party,
                   m.criminal_case_count AS case_count
            ORDER BY case_count DESC
            LIMIT {n}
        """,
        "parameters": {},
        "explanation": f"Top {n} MLAs by recorded criminal-case count.",
        "template_id": "top_cases_mlas",
    }


def _top_mlas_by_assets(q):
    state = _state(q)
    party = _party(q)
    limit = _top_n(q, 10)
    min_assets = _money(q) or 0
    min_cases = _int_after(q, r"more than|over|above") or 0
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (m:MLA:Person)
            OPTIONAL MATCH (m)-[:REPRESENTS]->(:AssemblyConstituency)-[:IN_STATE]->(s:State)
            OPTIONAL MATCH (m)-[:FACES]->(cc:CriminalCase)-[:UNDER]->(sec:Section)
            WITH m,
                 collect(DISTINCT s.name) AS states,
                 collect(DISTINCT sec.code) AS sections,
                 count(DISTINCT cc) AS case_count
            WHERE ($state = '' OR $state IN states)
              AND ($party = '' OR m.party_name CONTAINS $party)
              AND m.total_assets > $min_assets
              AND case_count > $min_cases
            RETURN m.name AS mla_name, m.party_name AS party,
                   m.total_assets AS total_assets, m.liabilities AS liabilities,
                   case_count, sections
            ORDER BY total_assets DESC
            LIMIT {limit}
        """,
        "parameters": {
            "state": state, "party": party,
            "min_assets": min_assets, "min_cases": min_cases,
        },
        "explanation": f"Top {limit} MLAs by total declared assets, with case count and charged sections.",
        "template_id": "top_mlas_by_assets",
    }


def _zero_cases_high_liabilities(q):
    threshold = _money(q) or 10_000_000
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE m.criminal_case_count = 0 AND m.liabilities > $min_liabilities
            RETURN m.party_name AS party, count(DISTINCT m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 50
        """,
        "parameters": {"min_liabilities": threshold},
        "explanation": "Counts MLAs with zero recorded criminal cases and liabilities above the threshold, grouped by party.",
        "template_id": "zero_cases_high_liabilities",
    }


def _case_section_overlap(q):
    # Query-specific extraction for the Arms Act / IPC 25 + hurt sections shape.
    a = []
    if re.search(r"arms act|ipc\s*25\b|\b25\b", q, re.I):
        a = ["25"]
    b = [c for c in _section_codes(q) if c in {"323", "324", "325", "326"}]
    if not a and not b:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:FACES]->(:CriminalCase)-[:UNDER]->(s1:Section)
            WHERE s1.code IN $sections_a
            WITH DISTINCT m
            MATCH (m)-[:FACES]->(:CriminalCase)-[:UNDER]->(s2:Section)
            WHERE s2.code IN $sections_b
            RETURN DISTINCT m.name AS mla_name, m.party_name AS party
            ORDER BY mla_name
            LIMIT 50
        """,
        "parameters": {"sections_a": a, "sections_b": b or ["323", "324", "325", "326"]},
        "explanation": "MLAs with both an Arms Act/IPC 25 case and a hurt case (IPC 323–326).",
        "template_id": "case_section_overlap",
    }


def _top_constituencies_by_cases(q):
    limit = _top_n(q, 15)
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (m:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency),
                  (m)-[:FACES]->(cc:CriminalCase)
            RETURN ac.name AS constituency_name,
                   count(DISTINCT cc) AS case_count,
                   collect(DISTINCT m.name)[0] AS mla_name
            ORDER BY case_count DESC
            LIMIT {limit}
        """,
        "parameters": {},
        "explanation": f"Top {limit} assembly constituencies by the number of distinct criminal cases linked to their MLA.",
        "template_id": "top_constituencies_by_cases",
    }


def _assets_and_cases_threshold(q):
    min_assets = _money(q)
    min_cases = _int_after(q, r"more than|over|above")
    if min_assets is None and min_cases is None:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA:Person)
            WHERE m.total_assets > $min_assets AND m.criminal_case_count > $min_cases
            RETURN m.name AS mla_name, m.party_name AS party,
                   m.total_assets AS total_assets, m.criminal_case_count AS criminal_case_count
            ORDER BY total_assets DESC
            LIMIT 50
        """,
        "parameters": {"min_assets": min_assets or 0, "min_cases": min_cases or 0},
        "explanation": "MLAs above the requested asset and criminal-case thresholds.",
        "template_id": "assets_and_cases_threshold",
    }


def _top_sections_with_party(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (s:Section)<-[:UNDER]-(cc:CriminalCase)<-[:FACES]-(m:MLA)-[:MEMBER_OF]->(p:Party)
            WHERE s.code <> 'IPC'
            WITH s.code AS section_code, p.name AS party_name, count(DISTINCT m) AS mla_count
            ORDER BY section_code, mla_count DESC
            WITH section_code, collect(party_name) AS parties, sum(mla_count) AS total_mlas
            RETURN section_code, total_mlas, parties[0] AS top_party
            ORDER BY total_mlas DESC
            LIMIT 10
        """,
        "parameters": {},
        "explanation": "Top 10 IPC sections by distinct MLA count, with the party with the most MLAs in each section.",
        "template_id": "top_sections_with_party",
    }


def _party_highest_average(q):
    min_mlas = _int_after(q, r"with|having|at least") or 10
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:MEMBER_OF]->(p:Party)
            WITH p, avg(toFloat(m.criminal_case_count)) AS avg_cases, count(DISTINCT m) AS mla_count
            WHERE mla_count >= $min_mlas
            RETURN p.name AS party_name, round(avg_cases, 2) AS avg_cases, mla_count
            ORDER BY avg_cases DESC
            LIMIT 1
        """,
        "parameters": {"min_mlas": max(1, min(50, min_mlas))},
        "explanation": "Party with the highest average criminal cases per MLA, among parties with at least the requested number of MLAs.",
        "template_id": "party_highest_average",
    }


def _party_average_vs_mla(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:MEMBER_OF]->(p:Party)
            WITH p, avg(toFloat(m.criminal_case_count)) AS party_avg_cases
            MATCH (m2:MLA)-[:MEMBER_OF]->(p)
            WHERE toFloat(m2.criminal_case_count) > party_avg_cases
            RETURN m2.name AS mla_name, p.name AS party_name,
                   m2.criminal_case_count AS mla_cases,
                   round(party_avg_cases, 2) AS party_avg_cases,
                   round(toFloat(m2.criminal_case_count) - party_avg_cases, 2) AS excess_cases
            ORDER BY excess_cases DESC
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "For each party, lists MLAs whose criminal-case count exceeds their party average.",
        "template_id": "party_average_vs_mla",
    }


def _elected_and_ministry(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[:REPRESENTS]->(ac:AssemblyConstituency),
                  (p)-[:HOLDS_PORTFOLIO]->(m:Ministry)
            RETURN p.name AS politician_name, m.name AS ministry_name,
                   m.portfolio_type AS portfolio_type, p.total_assets AS total_assets
            ORDER BY total_assets DESC
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "Elected representatives who also hold a Ministry portfolio, with assets.",
        "template_id": "elected_and_ministry",
    }


def _state_assets_summary(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (s:State)<-[:IN_STATE]-(ac:AssemblyConstituency)<-[:REPRESENTS]-(m:MLA)
            WHERE m.total_assets IS NOT NULL
            WITH s, m ORDER BY m.total_assets DESC
            WITH s,
                 avg(m.total_assets) AS average_total_assets,
                 percentileCont(m.total_assets, 0.5) AS median_total_assets,
                 collect({name: m.name, assets: m.total_assets})[0..3] AS top_3_mlas
            RETURN s.name AS state_name, average_total_assets, median_total_assets, top_3_mlas
            ORDER BY average_total_assets DESC
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "States ranked by average MLA assets, with median and the three richest MLAs per state.",
        "template_id": "state_assets_summary",
    }


def _combined_liabilities_union(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:MEMBER_OF]->(p:Party)
            WITH p, sum(toFloat(m.liabilities)) AS total_liabilities
            RETURN 'party' AS scope, p.name AS name, total_liabilities AS value
            ORDER BY value DESC LIMIT 1
            UNION
            MATCH (m:MLA)
            RETURN 'mla' AS scope, m.name AS name, toFloat(m.liabilities) AS value
            ORDER BY value DESC LIMIT 1
        """,
        "parameters": {},
        "explanation": "Highest combined party liabilities and the single MLA with the highest liabilities.",
        "template_id": "combined_liabilities_union",
    }


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------

def _count_mlas_zero_cases(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE coalesce(m.criminal_case_count, 0) = 0
            RETURN count(m) AS mlas_with_zero_cases
        """,
        "parameters": {},
        "explanation": "Number of MLAs with zero recorded criminal cases.",
        "template_id": "count_mlas_zero_cases",
    }


def _entity_count(q):
    ql = q.lower()
    if re.search(r"\bmps?\b|\bmembers? of parliament\b", ql):
        label, alias, cypher = "MP", "mp_count", "MATCH (p:Person:MP) RETURN count(p) AS mp_count"
    elif re.search(r"\bmlas?\b|\bmembers? of (?:the )?legislative assembly\b", ql):
        label, alias, cypher = "MLA", "mla_count", "MATCH (m:MLA) RETURN count(m) AS mla_count"
    elif "criminal case" in ql:
        label, alias, cypher = "CriminalCase", "case_count", "MATCH (c:CriminalCase) RETURN count(c) AS case_count"
    elif "part" in ql:
        label, alias, cypher = "Party", "party_count", "MATCH (p:Party) RETURN count(p) AS party_count"
    elif "state" in ql:
        label, alias, cypher = "State", "state_count", "MATCH (s:State) RETURN count(s) AS state_count"
    elif "ministr" in ql:
        label, alias, cypher = "Ministry", "ministry_count", "MATCH (m:Ministry) RETURN count(m) AS ministry_count"
    elif "constituenc" in ql:
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (c:Constituency) WITH count(c) AS parliamentary_constituencies
                MATCH (ac:AssemblyConstituency)
                RETURN parliamentary_constituencies, count(ac) AS assembly_constituencies
            """,
            "parameters": {},
            "explanation": "Counts of parliamentary constituencies and assembly constituencies stored in the graph.",
            "template_id": "constituency_counts",
        }
    else:
        return None
    return {
        "result_type": "aggregate",
        "cypher": cypher,
        "parameters": {},
        "explanation": f"Total number of {label} nodes in the graph.",
        "template_id": "entity_count",
    }


def _party_mla_count(q):
    party = _party(q)
    if not party or "mla" not in q.lower():
        return None
    has_cases = _any(q.lower(), "criminal", "case", "charged")
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE (m.party_name = $party OR m.party_name CONTAINS $party)
              AND ($has_cases = false OR coalesce(m.criminal_case_count, 0) > 0)
            RETURN count(m) AS mla_count
        """,
        "parameters": {"party": party, "has_cases": has_cases},
        "explanation": f"Number of MLAs from {party}" + (" with at least one criminal case." if has_cases else "."),
        "template_id": "party_mla_count",
    }


def _case_threshold_count(q):
    n = _int_after(q.lower(), r"more than|over|above|at least")
    if n is None:
        return None
    return {
        "result_type": "aggregate",
        "cypher": "MATCH (m:MLA) WHERE coalesce(m.criminal_case_count, 0) > $n RETURN count(m) AS mla_count",
        "parameters": {"n": n},
        "explanation": f"Number of MLAs with more than {n} recorded criminal cases.",
        "template_id": "case_threshold_count",
    }


def _money_threshold_count(q):
    amount = _money(q)
    if amount is None:
        return None
    metric = "liabilities" if "liabilit" in q.lower() else "total_assets"
    alias = "mla_count"
    return {
        "result_type": "aggregate",
        "cypher": f"MATCH (m:MLA) WHERE m.{metric} > $amount RETURN count(m) AS {alias}",
        "parameters": {"amount": amount},
        "explanation": f"Number of MLAs whose declared {metric.replace('_', ' ')} exceed the requested amount.",
        "template_id": "money_threshold_count",
    }


def _party_most_mlas(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            RETURN m.party_name AS party_name, count(m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "The party with the largest number of MLA nodes in the graph.",
        "template_id": "party_most_mlas",
    }


def _state_most_mlas(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:REPRESENTS]->(:AssemblyConstituency)-[:IN_STATE]->(s:State)
            RETURN s.name AS state_name, count(DISTINCT m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "The state with the largest number of MLAs in the graph.",
        "template_id": "state_most_mlas",
    }


def _party_most_with_cases(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE coalesce(m.criminal_case_count, 0) > 0
            RETURN m.party_name AS party_name, count(m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "The party with the largest number of MLAs who have at least one criminal case.",
        "template_id": "party_most_with_cases",
    }


def _top_parties_by_cases(q):
    n = _top_n(q, default=5)
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE m.party_name IS NOT NULL
            RETURN m.party_name AS party_name, sum(coalesce(m.criminal_case_count, 0)) AS total_cases
            ORDER BY total_cases DESC
            LIMIT $n
        """,
        "parameters": {"n": n},
        "explanation": f"The top {n} parties ranked by total criminal cases across their MLAs.",
        "template_id": "top_parties_by_cases",
    }


def _mlas_over_liabilities(q):
    amount = _money(q)
    if amount is None:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE m.liabilities IS NOT NULL AND m.liabilities > $amount
            RETURN m.name AS mla_name, m.party_name AS party, m.liabilities AS liabilities
            ORDER BY liabilities DESC
            LIMIT 50
        """,
        "parameters": {"amount": amount},
        "explanation": "MLAs whose declared liabilities exceed the requested amount, ordered highest first.",
        "template_id": "mlas_over_liabilities",
    }


def _party_most_zero_cases(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)
            WHERE coalesce(m.criminal_case_count, 0) = 0
            RETURN m.party_name AS party_name, count(m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "The party with the largest number of MLAs who have zero recorded criminal cases.",
        "template_id": "party_most_zero_cases",
    }


def _party_total_metric(q):
    ql = q.lower()
    metric = "liabilities" if "liabilit" in ql else "total_assets"
    alias = "total_liabilities" if metric == "liabilities" else "total_assets"
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (p:Person)
            WHERE p.{metric} IS NOT NULL AND p.party_name IS NOT NULL
            RETURN p.party_name AS party_name, sum(p.{metric}) AS {alias}
            ORDER BY {alias} DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": f"The party whose politicians have the highest combined declared {metric.replace('_', ' ')}.",
        "template_id": "party_total_metric",
    }


def _constituency_most_cases(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)
            OPTIONAL MATCH (m)-[:FACES]->(c:CriminalCase)
            WITH ac, count(DISTINCT c) AS case_count, head(collect(DISTINCT m.name)) AS mla_name
            RETURN ac.name AS constituency_name, case_count, mla_name
            ORDER BY case_count DESC
            LIMIT 1
        """,
        "parameters": {},
        "explanation": "The assembly constituency whose MLA has the largest number of recorded criminal cases.",
        "template_id": "constituency_most_cases",
    }


def _party_most_by_section(q):
    codes = _section_codes(q)
    ql = q.lower()
    if "murder" in ql and not codes:
        codes = ["302"]
    if not codes:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:FACES]->(:CriminalCase)-[:UNDER]->(s:Section)
            WHERE s.code IN $section_codes
            RETURN m.party_name AS party_name, count(DISTINCT m) AS mla_count
            ORDER BY mla_count DESC
            LIMIT 1
        """,
        "parameters": {"section_codes": codes},
        "explanation": f"The party with the most MLAs charged under section(s) {', '.join(codes)}.",
        "template_id": "party_most_by_section",
    }


def _count_mlas_by_section(q):
    codes = _section_codes(q)
    if not codes:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (m:MLA)-[:FACES]->(:CriminalCase)-[:UNDER]->(s:Section)
            WHERE s.code IN $section_codes
            RETURN count(DISTINCT m) AS mla_count
        """,
        "parameters": {"section_codes": codes},
        "explanation": f"Number of distinct MLAs with a recorded case under section(s) {', '.join(codes)}.",
        "template_id": "count_mlas_by_section",
    }


def _ministers_with_cases(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[:HOLDS_PORTFOLIO]->(m:Ministry)
            OPTIONAL MATCH (p)-[:FACES]->(c:CriminalCase)
            WITH p, collect(DISTINCT m.name) AS ministries, count(DISTINCT c) AS case_count
            WHERE case_count > 0
            RETURN p.name AS name, p.party_name AS party, ministries, case_count
            ORDER BY case_count DESC
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "One row per person holding a ministry portfolio who also has at least one recorded criminal case, with their portfolios grouped.",
        "template_id": "ministers_with_cases",
    }


def _minister_portfolios(q):
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[r:HOLDS_PORTFOLIO]->(m:Ministry)
            RETURN p.name AS name, p.party_name AS party, m.name AS ministry,
                   r.portfolio_type AS portfolio_type
            ORDER BY name
            LIMIT 50
        """,
        "parameters": {},
        "explanation": "Every person in the graph who holds a ministry or department portfolio, with the portfolio name.",
        "template_id": "minister_portfolios",
    }


def _minister_of(q):
    ql = q.lower()
    if _any(ql, "prime minister", "chief minister", "deputy chief minister"):
        return None
    m = re.search(r"minister\s+of\s+([a-z&,\- ]+)", ql)
    portfolio = (m.group(1).strip() if m else "").rstrip("?. ")
    if not portfolio:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[r:HOLDS_PORTFOLIO]->(m:Ministry)
            WHERE toLower(m.name) CONTAINS toLower($portfolio)
            RETURN p.name AS name, p.party_name AS party, m.name AS ministry,
                   r.portfolio_type AS portfolio_type
            ORDER BY name
            LIMIT 20
        """,
        "parameters": {"portfolio": portfolio},
        "explanation": f"People holding a portfolio matching '{portfolio}', from stored ministry links.",
        "template_id": "minister_of",
    }


def _mp_metric(q):
    ql = q.lower()
    if "party" in ql and _any(ql, "most", "highest"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)
                WHERE coalesce(p.criminal_case_count, 0) > 0
                RETURN p.party_name AS party_name, count(p) AS mp_count
                ORDER BY mp_count DESC LIMIT 1
            """,
            "parameters": {},
            "explanation": "The party with the most MPs who have at least one recorded criminal case.",
            "template_id": "mp_party_most_cases",
        }
    if "state" in ql and _any(ql, "most", "highest"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)-[:REPRESENTS]->(:Constituency)-[:IN_STATE]->(s:State)
                WHERE coalesce(p.criminal_case_count, 0) > 0
                RETURN s.name AS state_name, count(p) AS mp_count
                ORDER BY mp_count DESC LIMIT 1
            """,
            "parameters": {},
            "explanation": "The state with the most MPs who have at least one recorded criminal case.",
            "template_id": "mp_state_most_cases",
        }
    if "how many" in ql and "criminal" in ql:
        return {
            "result_type": "aggregate",
            "cypher": "MATCH (p:Person:MP) WHERE coalesce(p.criminal_case_count, 0) > 0 RETURN count(p) AS mp_count",
            "parameters": {},
            "explanation": "Number of MPs with at least one recorded criminal case.",
            "template_id": "mp_count_with_cases",
        }
    if _money(q) is not None:
        return {
            "result_type": "aggregate",
            "cypher": "MATCH (p:Person:MP) WHERE p.total_assets > $amount RETURN count(p) AS mp_count",
            "parameters": {"amount": _money(q)},
            "explanation": "Number of MPs whose declared total assets exceed the requested amount.",
            "template_id": "mp_assets_above",
        }
    if "liabilit" in ql and _any(ql, "highest", "most"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)
                WHERE p.liabilities IS NOT NULL
                RETURN p.name AS mp_name, p.party_name AS party, p.liabilities AS liabilities,
                       p.total_assets AS total_assets
                ORDER BY liabilities DESC LIMIT 1
            """,
            "parameters": {},
            "explanation": "The MP with the highest declared liabilities.",
            "template_id": "mp_highest_liabilities",
        }
    return None


def plan_from_template(question: str) -> dict | None:
    q = question.strip()
    ql = q.lower()

    # MP net-worth-negative question.
    if (("mp" in ql or "member of parliament" in ql) and "liabilit" in ql and "assets" in ql
            and _any(ql, "exceed", "negative", "shortfall", "net-worth", "net worth")):
        return _mps_negative_net_worth(q)

    # Generic negative net worth (MP/MLA/Person).
    if _any(ql, "negative net worth", "net worth negative"):
        return _negative_net_worth(q)

    # Top N parties by total criminal cases (party aggregation, checked before the MLA ranking).
    if (_any(ql, "top 5", "top five", "top 10", "top ten", "rank the top", "top parties")
            and _any(ql, "party", "parties") and _any(ql, "criminal", "case", "tainted", "charges")):
        return _top_parties_by_cases(q)

    # Top N by criminal cases ("tainted" is common Indian political shorthand).
    if (_any(ql, "top 5", "top five", "top 10", "top ten")
            and "mla" in ql and _any(ql, "criminal", "tainted", "cases")):
        return _top_cases_mlas(q)

    # The "normal judge" questions: instant, deterministic answers.
    if _any(ql, "how much data", "how many politicians", "how many nodes"):
        return _data_counts(q)

    if ("how many mla" in ql and "criminal case" in ql
            and not _any(ql, "average", "per mla", "more than", "zero", "without", "no criminal")):
        return _count_mlas_with_cases(q)

    # Paraphrase with "elected" between "how many" and "MLAs", or "charges" instead of "cases".
    if (re.search(r"how many", ql) and re.search(r"\bmlas?\b", ql)
            and _any(ql, "criminal charge", "face charge", "criminal record", "criminal case", "with case", "tainted")
            and not _section_codes(q)
            and not _any(ql, "more than", "over", "above", "at least", "zero", "without", "no criminal", "average", "per mla")):
        return _count_mlas_with_cases(q)

    # How many MLAs with zero / without cases ("clean" is common shorthand).
    if "how many mla" in ql and _any(ql, "zero", "without criminal", "no criminal cases", "clean"):
        return _count_mlas_zero_cases(q)

    # Threshold counts: more than N cases, assets/liabilities above X.
    if "how many mla" in ql and "criminal case" in ql and _any(ql, "more than", "over", "above", "at least"):
        plan = _case_threshold_count(q)
        if plan:
            return plan
    if "how many mla" in ql and _any(ql, "asset", "liabilit") and _any(ql, "above", "over", "more than", "at least"):
        plan = _money_threshold_count(q)
        if plan:
            return plan

    # "Which MLAs have liabilities above X" — a list, not a count.
    if ("mla" in ql and "liabilit" in ql and _any(ql, "above", "over", "more than", "exceed", "exceeding")
            and not _any(ql, "how many", "highest", "most", "single", "combined")):
        plan = _mlas_over_liabilities(q)
        if plan:
            return plan

    # How many MLAs from a named party, optionally with cases.
    if "how many" in ql and "mla" in ql and _party(q) and not _section_codes(q):
        plan = _party_mla_count(q)
        if plan:
            return plan

    # Which party has the most MLAs charged under a section / with murder.
    if "party" in ql and "how many" not in ql and _any(
            ql, "charged", "murder", "ipc", "section", "302", "307", "420", "120b",
            "376", "354", "153a", "295a", "147", "148", "149"):
        plan = _party_most_by_section(q)
        if plan:
            return plan

    # How many MLAs are charged under a named section.
    if "how many mla" in ql and _section_codes(q):
        plan = _count_mlas_by_section(q)
        if plan:
            return plan

    # MP-specific (Member of Parliament) metrics.
    if re.search(r"\bmps?\b|\bmembers? of parliament\b", ql) and _any(
            ql, "criminal", "liabilit", "asset", "party", "state"):
        plan = _mp_metric(q)
        if plan:
            return plan

    # Ministers and portfolios.
    if "minister" in ql and _any(ql, "criminal", "case"):
        return _ministers_with_cases(q)
    if "minister" in ql and _any(ql, "portfolio", "ministry", "hold"):
        plan = _minister_portfolios(q)
        if plan:
            return plan
    if "minister" in ql and " of " in ql:
        plan = _minister_of(q)
        if plan:
            return plan

    # Plain entity counts: how many MLAs/MPs/states/parties/ministries/constituencies.
    if "how many" in ql:
        plan = _entity_count(q)
        if plan:
            return plan

    # Party-level comparisons.
    if ("party" in ql and _any(ql, "most seats", "controls the most", "largest party")
            and not re.search(r"\bmps?\b|\bmembers? of parliament\b", ql)):
        plan = _party_most_mlas(q)
        if plan:
            return plan
    if ("party" in ql and "mla" in ql and _any(ql, "most", "largest")
            and not _any(ql, "criminal", "case", "asset", "liabilit", "average", "charged")):
        plan = _party_most_mlas(q)
        if plan:
            return plan
    if ("state" in ql and "mla" in ql and _any(ql, "most", "largest") and not _state(q)
            and not _any(ql, "criminal", "case", "asset", "liabilit", "percentage", "average")):
        plan = _state_most_mlas(q)
        if plan:
            return plan
    if ("party" in ql and "mla" in ql and _any(ql, "most", "highest")
            and _any(ql, "criminal case", "criminal cases", "charged")
            and not _any(ql, "average", "avg", "per mla")):
        plan = _party_most_with_cases(q)
        if plan:
            return plan
    if "party" in ql and "mla" in ql and "zero" in ql and _any(ql, "most", "highest"):
        plan = _party_most_zero_cases(q)
        if plan:
            return plan
    if "party" in ql and _any(ql, "highest total", "total assets", "total liabilities"):
        plan = _party_total_metric(q)
        if plan:
            return plan

    # Plain constituency-level comparison.
    if "constituenc" in ql and _any(ql, "most", "highest") and "criminal" in ql and not _state(q):
        return _constituency_most_cases(q)

    if (_any(ql, "richest", "wealthiest", "most wealthy", "highest assets", "highest total assets",
             "largest assets", "largest total assets", "most assets", "highest declared assets", "highest net worth")
            and not _any(ql, "top 10", "top 5", "top 3", "top ten", "top five")):
        if "mla" in ql or "legislat" in ql or "assembly member" in ql:
            return _richest_mla(q)
        return _richest_politician(q)

    if _any(ql, "most dangerous", "most cases", "highest number of cases", "most criminal cases", "most tainted") and "mla" in ql:
        return _most_cases_mla(q)

    if (_any(ql, "murder", "302", "307", "376", "354")
            and _any(ql, "show me one", "show me", "is there one", "one with")
            and not _any(ql, "how many", "list every", "still holding")):
        plan = _section_example(q)
        if plan:
            return plan

    if _any(ql, "most common crime", "common crime", "most common criminal"):
        return _most_common_crime(q)

    if _any(ql, "richer than me", "sense of the numbers", "average assets", "median assets") and "my mla" not in ql and not _state(q) and not _party(q):
        return _asset_stats(q)

    if _any(ql, "show me any politician", "any politician", "show me a politician"):
        return _sample_politicians(q)

    # More specific shapes first.
    if _any(ql, "combined total liabilities", "combined liabilities") and _any(ql, "single mla", "highest liabilities"):
        return _combined_liabilities_union(q)

    if _any(ql, "highest liabilit", "biggest liabilit", "most liabilities") and "mla" in ql:
        return _highest_liabilities_mla(q)

    if _state(q) and "party" in ql and _any(ql, "highest average", "highest avg") and _any(ql, "asset", "case", "liabilit"):
        return _party_highest_metric_in_state(q)

    if _state(q) and "constituenc" in ql and "criminal case" in ql and _any(ql, "most", "top"):
        return _top_constituencies_in_state(q)

    if _any(ql, "zero criminal cases", "zero cases") and "liabilit" in ql and "party" in ql:
        return _zero_cases_high_liabilities(q)

    if "overlap" in ql and _any(ql, "arms act", "ipc 25") and _any(ql, "323", "324", "325", "326", "hurt"):
        return _case_section_overlap(q)

    if _any(ql, "elected representative", "elected representatives") and _any(ql, "ministry", "portfolio"):
        return _elected_and_ministry(q)

    if "state" in ql and _any(ql, "average", "avg") and "assets" in ql and _any(ql, "median", "top 3", "top three"):
        return _state_assets_summary(q)

    if "percentage" in ql and "state" in ql and "criminal case" in ql:
        return _state_case_percentage(q)

    if _any(ql, "highest average", "most average", "highest avg", "most avg") and "cases per mla" in ql:
        return _party_highest_average(q)

    if _any(ql, "average", "avg") and "cases per mla" in ql and _any(ql, "exceeds", "above", "higher than"):
        return _party_average_vs_mla(q)

    if "constituenc" in ql and "criminal case" in ql and _any(ql, "rank", "top"):
        return _top_constituencies_by_cases(q)

    # Party + state(s) + IPC section + asset/case thresholds: a multi-constraint list.
    if _party(q) and _states(q) and _ipc_section(q) and "criminal case" in ql and "assets" in ql:
        plan = _mla_multi_constraint(q)
        if plan:
            return plan

    # State + party/case/asset/section filters: filtered list.
    if (_state(q) and "mla" in ql and "constituenc" not in ql
            and (_party(q) or _any(ql, "criminal", "case", "asset", "liabilit", "section", "ipc", "murder", "zero"))):
        plan = _mlas_in_state_filtered(q)
        if plan:
            return plan

    # "I'm from Delhi. Show me my MLA." / "I type Delhi — what comes up?"
    if _state(q) and (
        ("mla" in ql and _any(ql, "show", "my", "from", "type", "delhi"))
        or _any(ql, "i type", "what comes up", "search for")
    ) and not _party(q) and not _any(
        ql, "weather", "temperature", "capital", "prime minister", "president",
        "criminal", "case", "asset", "liabilit", "section", "ipc", "murder", "zero",
        "richest", "highest", "most", "top", "constituency", "minister",
    ):
        plan = _mlas_in_state(q)
        if plan:
            return plan

    # "assets above X and more than Y criminal cases" — only for a simple two-threshold
    # question. Multi-constraint questions (party, state, IPC, contested) must go to Gemini.
    if ("assets" in ql and _any(ql, "more than", "above", "over") and "criminal case" in ql and "mla" in ql
            and not _party(q) and not _state(q)
            and not _any(ql, "contested", "ipc", "section", "constituency")):
        plan = _assets_and_cases_threshold(q)
        if plan:
            return plan

    # "top N / richest MLAs by assets"
    if _any(ql, "top", "richest") and "assets" in ql and "mla" in ql:
        return _top_mlas_by_assets(q)

    # "break it down state by state" with party + section
    if _any(ql, "state by state", "break it down", "breakdown") and "party" in ql and _any(ql, "ipc", "section", "charged"):
        return _state_party_counts_by_section(q)

    if "ipc section" in ql and "party" in ql and _any(ql, "most associated", "top party", "party most"):
        return _top_sections_with_party(q)

    # "rank every party by count charged under IPC X" — must be an explicit
    # party-ranking question, not a per-MLA list that happens to mention party.
    party_rank_phrases = ("rank every party", "rank all parties", "count per party",
                          "party by the number", "parties by the number",
                          "number of its elected representatives")
    if _any(ql, *party_rank_phrases) and _any(ql, "charged", "cases", "ipc"):
        return _party_counts_by_section(q)

    return None

    return None
