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

_STATE_ABBR = {
    "up": "Uttar Pradesh", "tn": "Tamil Nadu", "hr": "Haryana", "od": "Odisha",
    "mh": "Maharashtra", "wb": "West Bengal", "ka": "Karnataka", "kl": "Kerala",
    "tg": "Telangana", "ap": "Andhra Pradesh", "br": "Bihar", "gj": "Gujarat",
    "rj": "Rajasthan", "pb": "Punjab", "hp": "Himachal Pradesh",
    "jk": "Jammu and Kashmir", "uk": "Uttarakhand", "cg": "Chhattisgarh",
    "jh": "Jharkhand", "ga": "Goa", "py": "Puducherry", "dl": "NCT of Delhi",
}

PARTY_ALIASES = {
    "bjp": "BJP", "bharatiya janata party": "BJP",
    "inc": "INC", "congress": "INC", "indian national congress": "INC",
    "aap": "AAP", "aam aadmi party": "AAP",
    "bsp": "BSP", "sp": "SP", "samajwadi party": "SP",
    "dmk": "DMK", "aiadmk": "AIADMK", "tmc": "TMC", "trinamool": "TMC",
    "tdp": "TDP", "ysrcp": "YSRCP", "jdu": "JDU", "rjd": "RJD",
    "ncp": "NCP", "shiv sena": "Shiv Sena", "ss": "Shiv Sena", "bjd": "BJD",
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
    "mla_timeline", "mla_case_change", "mla_party_switchers",
    "mla_election_roster", "politician_profile", "constituency_winner",
    "party_seats_in_state", "party_section_in_state", "state_most_cases",
    "mp_mla_counts_by_state", "state_avg_assets", "states_ranked_by_avg_assets",
    "party_sections", "largest_party_section",
    "richest_mps", "multiple_sections", "politicians_by_year_filter",
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
    "mp_highest_liabilities": {"mp_name", "constituency", "party", "liabilities", "total_assets"},
    "mla_timeline": {"name", "year", "election", "party", "total_assets", "liabilities", "cases"},
    "mla_case_change": {"year", "election", "cases"},
    "mla_party_switchers": {"person_key", "parties", "elections", "n"},
    "mla_election_roster": {"mla_name", "constituency", "party", "total_assets", "cases"},
    "politician_profile": {"name", "election", "year", "party", "age", "total_assets", "liabilities", "cases", "education"},
    "constituency_winner": {"mla_name", "constituency", "year", "election", "party", "total_assets", "cases"},
    "party_seats_in_state": {"party", "seats"},
    "party_section_in_state": {"party", "mlas", "cases"},
    "state_most_cases": {"state", "mlas_with_cases"},
    "mp_mla_counts_by_state": {"state", "mps", "mlas"},
    "state_avg_assets": {"state", "mlas", "avg_assets", "max_assets"},
    "states_ranked_by_avg_assets": {"state", "avg_assets", "mlas"},
    "party_sections": {"section", "cases"},
    "largest_party_section": {"party", "seats", "section", "cases"},
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
    # Common two-letter state abbreviations, matched as whole words only.
    for abbr, state in _STATE_ABBR.items():
        if re.search(rf"\b{abbr}\b", ql):
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
            RETURN m.entity_id AS entity_id, m.name AS mp_name, m.party_name AS party,
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
            RETURN m.entity_id AS entity_id, m.name AS mla_name, m.party_name AS party,
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
            WHERE case_count > 0 OR coalesce(p.criminal_case_count, 0) > 0
            RETURN p.entity_id AS entity_id, p.name AS name, p.party_name AS party,
                   ministries,
                   CASE WHEN case_count > 0 THEN case_count ELSE coalesce(p.criminal_case_count, 0) END AS case_count
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
    portfolio = None
    # Direct ministry acronym & keyword matching
    if re.search(r"\b(?:mod|defence|defense)\b", ql):
        portfolio = "defence"
    elif re.search(r"\b(?:mha|home\s+affairs?)\b", ql):
        portfolio = "home affairs"
    elif re.search(r"\b(?:mof|finance)\b", ql):
        portfolio = "finance"
    elif re.search(r"\b(?:morth|road\s+transport|highways?)\b", ql):
        portfolio = "road transport"
    elif re.search(r"\b(?:moe|mhrd|education)\b", ql):
        portfolio = "education"
    elif re.search(r"\b(?:railways?|mor)\b", ql):
        portfolio = "railways"
    elif re.search(r"\b(?:health)\b", ql):
        portfolio = "health"
    elif re.search(r"\b(?:agriculture)\b", ql):
        portfolio = "agriculture"
    elif re.search(r"\b(?:external\s+affairs?|foreign)\b", ql):
        portfolio = "external affairs"
    elif re.search(r"\b(?:civil\s+aviation|aviation)\b", ql):
        portfolio = "civil aviation"
    elif re.search(r"\b(?:power)\b", ql):
        portfolio = "power"
    elif re.search(r"\b(?:coal)\b", ql):
        portfolio = "coal"
    elif re.search(r"\b(?:mines)\b", ql):
        portfolio = "mines"
    elif re.search(r"\b(?:steel)\b", ql):
        portfolio = "steel"
    elif re.search(r"\b(?:textiles)\b", ql):
        portfolio = "textiles"
    elif re.search(r"\b(?:commerce)\b", ql):
        portfolio = "commerce"
    elif re.search(r"\b(?:law)\b", ql):
        portfolio = "law"

    if not portfolio:
        m = re.search(r"(?:minister|ministry)\s+of\s+([a-z&,\- ]+)", ql)
        if m:
            portfolio = m.group(1).strip().rstrip("?. ")
        else:
            m2 = re.search(r"([a-z&,\- ]+)\s+(?:minister|ministry)", ql)
            if m2:
                cand = m2.group(1).strip().rstrip("?. ")
                if cand not in ("chief", "prime", "deputy", "cabinet", "union", "state"):
                    portfolio = cand

    if not portfolio:
        return None

    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[r:HOLDS_PORTFOLIO]->(m:Ministry)
            WHERE toLower(m.name) CONTAINS toLower($portfolio)
            OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)
            OPTIONAL MATCH (p)-[:MEMBER_OF]->(pty:Party)
            RETURN p.name AS name,
                   coalesce(p.party_name, pty.name, 'BJP') AS party,
                   m.name AS ministry,
                   coalesce(r.rank, r.role, 'Cabinet Minister') AS portfolio_rank,
                   coalesce(r.rank, r.role, 'Cabinet Minister') AS portfolio_type,
                   coalesce(c.name, '—') AS constituency,
                   coalesce(p.criminal_case_count, 0) AS criminal_cases,
                   coalesce(p.total_assets, 0) AS total_assets,
                   coalesce(p.entity_id, '') AS entity_id
            ORDER BY coalesce(r.rank_order, 1) ASC, p.total_assets DESC, name ASC
            LIMIT 20
        """,
        "parameters": {"portfolio": portfolio},
        "explanation": f"Ministers holding a portfolio matching '{portfolio}', ordered by Cabinet rank.",
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
                MATCH (p:Person:MP)-[:REPRESENTS]->(c:Constituency)
                WHERE p.entity_id STARTS WITH 'sansad_mp_' AND p.liabilities IS NOT NULL
                RETURN p.name AS mp_name, c.name AS constituency, p.party_name AS party,
                       p.liabilities AS liabilities, p.total_assets AS total_assets
                ORDER BY liabilities DESC LIMIT 1
            """,
            "parameters": {},
            "explanation": "The MP with the highest declared liabilities, with their constituency.",
            "template_id": "mp_highest_liabilities",
        }
    return None


def _politicians_with_criminal_cases(q):
    limit = _top_n(q, 50)
    ql = q.lower()
    has_mp = bool(re.search(r"\bmps?\b", ql))
    has_mla = bool(re.search(r"\bmlas?\b", ql))
    if has_mp and not has_mla:
        label_expr = "p:MP"
        who = "MPs"
    elif has_mla and not has_mp:
        label_expr = "p:MLA"
        who = "MLAs"
    else:
        label_expr = "(p:MP OR p:MLA)"
        who = "MPs and MLAs"
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (p:Person)
            WHERE {label_expr} AND coalesce(p.criminal_case_count, 0) > 0
            RETURN p.entity_id AS entity_id,
                   p.name AS name,
                   [l IN labels(p) WHERE l IN ['MP', 'MLA']][0] AS house_role,
                   p.party_name AS party,
                   p.criminal_case_count AS criminal_case_count,
                   p.total_assets AS total_assets
            ORDER BY criminal_case_count DESC, total_assets DESC
            LIMIT {limit}
        """,
        "parameters": {},
        "explanation": f"Top {limit} {who} with declared criminal cases, ordered by case count.",
        "template_id": "politicians_with_criminal_cases",
    }


def _mps_in_state(q):
    state = _state(q)
    if not state:
        return None
    party = _party(q)
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MP)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
            WHERE toLower(s.name) = toLower($state)
              AND ($party = '' OR p.party_name CONTAINS $party)
            RETURN p.entity_id AS entity_id,
                   p.name AS mp_name,
                   p.party_name AS party,
                   c.name AS constituency,
                   coalesce(p.criminal_case_count, 0) AS criminal_cases,
                   p.total_assets AS total_assets
            ORDER BY mp_name
            LIMIT 100
        """,
        "parameters": {"state": state, "party": party},
        "explanation": f"MPs representing constituencies in {state}" + (f" ({party})" if party else "") + ".",
        "template_id": "mps_in_state",
    }


_MP_PARTY_MAP = {
    "TMC": ["AITC", "TMC"],
    "Shiv Sena": ["SS", "SHSUBT", "Shiv Sena"],
    "JDU": ["JD(U)", "JDU"],
    "YSRCP": ["YSR Congress Party", "YSRCP"],
    "NCP": ["NCPSP", "NCP"],
}


def _mp_party_variants(q: str) -> list[str]:
    p = _party(q)
    if not p:
        return []
    return _MP_PARTY_MAP.get(p, [p])


def _mp_party_switchers(q):
    party = _party(q)
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MP)-[:HAS_PARTY_CHANGE]->(pc:PartyChange)
            WHERE ($party = '' OR toLower(coalesce(pc.from_party, '')) CONTAINS toLower($party)
                   OR toLower(coalesce(pc.to_party, '')) CONTAINS toLower($party))
            RETURN p.entity_id AS entity_id,
                   p.name AS mp_name,
                   pc.from_party AS from_party,
                   pc.to_party AS to_party,
                   pc.from_year AS from_year,
                   pc.to_year AS to_year,
                   coalesce(pc.to_constituency, pc.from_constituency) AS constituency
            ORDER BY pc.to_year DESC, mp_name ASC
            LIMIT 50
        """,
        "parameters": {"party": party},
        "explanation": "MPs with recorded party switches across Lok Sabha elections.",
        "template_id": "mp_party_switchers",
    }


def _mp_affidavit_changes(q):
    ql = q.lower()
    party = _party(q)
    if _any(ql, "criminal", "case", "cases", "charge"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)-[:HAS_AFFIDAVIT_CHANGE]->(ac:AffidavitChange)
                WHERE coalesce(ac.criminal_cases_count_change, 0) > 0
                  AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                RETURN p.entity_id AS entity_id,
                       p.name AS mp_name,
                       coalesce(p.party_name, ac.to_party, '—') AS party,
                       ac.from_year AS from_year,
                       ac.to_year AS to_year,
                       ac.criminal_cases_count_from AS cases_from,
                       ac.criminal_cases_count_to AS cases_to,
                       ac.criminal_cases_count_change AS cases_increase
                ORDER BY ac.criminal_cases_count_change DESC, ac.to_year DESC
                LIMIT 50
            """,
            "parameters": {"party": party},
            "explanation": "MPs whose declared criminal case count increased between elections.",
            "template_id": "mp_affidavit_case_changes",
        }
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MP)-[:HAS_AFFIDAVIT_CHANGE]->(ac:AffidavitChange)
            WHERE ac.total_assets_change IS NOT NULL
              AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
            RETURN p.entity_id AS entity_id,
                   p.name AS mp_name,
                   coalesce(p.party_name, ac.to_party, '—') AS party,
                   ac.from_year AS from_year,
                   ac.to_year AS to_year,
                   ac.total_assets_from AS assets_from,
                   ac.total_assets_to AS assets_to,
                   ac.total_assets_change AS assets_change,
                   ac.total_assets_percent_change AS pct_change
            ORDER BY ac.total_assets_change DESC
            LIMIT 50
        """,
        "parameters": {"party": party},
        "explanation": "MPs ranked by declared asset growth across elections.",
        "template_id": "mp_affidavit_changes",
    }


def _mp_case_status(q):
    ql = q.lower()
    state = _state(q)
    parties = _mp_party_variants(q)
    if "serious" in ql and _any(ql, "by party", "party wise", "party-wise", "per party"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)
                WHERE coalesce(p.serious_criminal_cases, p.criminal_case_count, 0) > 0
                RETURN coalesce(p.party_name, 'Independent/Other') AS party,
                       count(DISTINCT p) AS mps_with_serious_cases,
                       sum(coalesce(p.serious_criminal_cases, p.criminal_case_count, 0)) AS total_cases
                ORDER BY mps_with_serious_cases DESC, total_cases DESC
                LIMIT 30
            """,
            "parameters": {},
            "explanation": "Party-wise count of MPs with declared serious/criminal charges.",
            "template_id": "mp_serious_by_party",
        }
    if "serious" in ql:
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE coalesce(p.serious_criminal_cases, p.criminal_case_count, 0) > 0
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
                RETURN p.entity_id AS entity_id,
                       p.name AS mp_name,
                       coalesce(p.party_name, '—') AS party,
                       coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state,
                       coalesce(p.serious_criminal_cases, p.criminal_case_count, 0) AS criminal_cases,
                       p.total_assets AS total_assets
                ORDER BY criminal_cases DESC, mp_name ASC
                LIMIT 50
            """,
            "parameters": {"state": state, "parties": parties},
            "explanation": "MPs with declared serious/criminal cases in their affidavits.",
            "template_id": "mp_serious_cases",
        }
    if "convict" in ql:
        mode = "convicted"
    elif "cognizance" in ql:
        mode = "cognizance"
    elif _any(ql, "charges framed", "charge framed", "framed"):
        mode = "framed"
    else:
        mode = "pending"
    if mode == "pending":
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE coalesce(p.criminal_case_count, 0) > 0
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
                RETURN p.entity_id AS entity_id,
                       p.name AS mp_name,
                       coalesce(p.party_name, '—') AS party,
                       coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state,
                       p.criminal_case_count AS pending_cases,
                       p.total_assets AS total_assets
                ORDER BY pending_cases DESC, mp_name ASC
                LIMIT 50
            """,
            "parameters": {"state": state, "parties": parties},
            "explanation": "MPs with pending criminal cases declared in their election affidavits.",
            "template_id": "mp_case_status",
        }
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MP)-[:FACES]->(cc:CriminalCase)
            OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
            WITH p, cc, c, s
            WHERE ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
              AND (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
              AND (
                ($mode = 'convicted' AND (toLower(coalesce(cc.case_type, '')) CONTAINS 'convict' OR toLower(coalesce(cc.status, '')) CONTAINS 'convict' OR coalesce(p.convicted_cases, 0) > 0))
                OR ($mode = 'cognizance' AND (toLower(coalesce(cc.case_type, '')) CONTAINS 'cognizance' OR toLower(coalesce(cc.status, '')) CONTAINS 'cognizance' OR cc.status IS NOT NULL))
                OR ($mode = 'framed' AND ((cc.charges_framed IS NOT NULL AND NOT toLower(toString(cc.charges_framed)) IN ['false', 'no', '0', 'none', '']) OR toLower(coalesce(cc.case_type, '')) CONTAINS 'framed'))
              )
            RETURN p.entity_id AS entity_id,
                   p.name AS mp_name,
                   coalesce(p.party_name, '—') AS party,
                   coalesce(c.name, '—') AS constituency,
                   coalesce(s.name, '—') AS state,
                   count(DISTINCT cc) AS matched_cases
            ORDER BY matched_cases DESC, mp_name ASC
            LIMIT 50
        """,
        "parameters": {"state": state, "parties": parties, "mode": mode},
        "explanation": f"MPs with criminal cases matching status '{mode}'.",
        "template_id": "mp_case_status",
    }


def _mp_constituency_or_person(q):
    ql = q.strip().lower()
    if re.search(r"\bminister\s+of\b|\bministry\s+of\b", ql):
        return None
    # 1. Constituency lookup: "Who is the MP of Varanasi?", "MP representing Wayanad", "MP from Guntur"
    m_const = re.search(
        r"(?:\bmp\s+(?:of|from|for|representing)|who\s+is\s+the\s+mp\s+(?:of|from|for)|member\s+of\s+parliament\s+(?:of|from|for|representing)|who\s+represents)\s+([a-z][a-z\s\-]{2,30}?)(?:\s+constituency|\s+seat|\s+in\s+lok\s+sabha|[?.!]|$)",
        ql,
    )
    if m_const:
        cand = m_const.group(1).strip()
        cands = [c.strip() for c in re.split(r"\s+or\s+|\s+and\s+", cand) if c.strip()]
        if cands and not any(_state(c) or _party(c) or c in {"lok sabha", "parliament", "india"} for c in cands):
            return {
                "result_type": "aggregate",
                "cypher": """
                    MATCH (p:Person:MP)-[:REPRESENTS]->(c:Constituency)
                    OPTIONAL MATCH (c)-[:IN_STATE]->(s:State)
                    WITH p, c, s
                    WHERE any(target IN $constituencies WHERE toLower(c.name) CONTAINS toLower(target))
                    RETURN p.entity_id AS entity_id,
                           p.name AS mp_name,
                           coalesce(p.party_name, '—') AS party,
                           c.name AS constituency,
                           coalesce(s.name, '—') AS state,
                           p.terms AS terms,
                           coalesce(p.criminal_case_count, 0) AS criminal_cases,
                           p.total_assets AS total_assets
                    ORDER BY mp_name ASC
                    LIMIT 20
                """,
                "parameters": {"constituencies": cands},
                "explanation": f"MP(s) representing constituency matching '{cand}'.",
                "template_id": "mp_by_constituency",
            }

    # 2. Named MP lookup: "Criminal cases of Rahul Gandhi", "What are the declared assets of Jyotiraditya Scindia?", "Show details of Supriya Sule or Akhilesh Yadav"
    m_person = re.search(
        r"(?:(?:declared\s+|total\s+|pending\s+)?(?:criminal\s+cases?|assets?\s+and\s+criminal\s+cases?|assets?|liabilities|net\s+worth|profile|details)\s+of|tell\s+me\s+about|how\s+many\s+(?:terms|criminal\s+cases?)\s+(?:has|does)|terms\s+of)\s+(?:mp\s+)?([a-z][a-z\s\.]{2,45}?)(?:\s+from\s+[a-z\s]+|\s+have|\s+served|\s+in\s+our\s+mp\s+database|\s+in\s+the\s+mp\s+database|\s+in\s+lok\s+sabha|\s+declared|[?.!]|$)",
        ql,
    )
    if m_person:
        pname = m_person.group(1).strip()
        raw_names = [n.strip() for n in re.split(r"\s+or\s+|\s+and\s+", pname) if len(n.strip()) >= 3]
        if raw_names and not any(_state(n) or _party(n) or re.search(r"\b(mp|mps|mla|mlas|minister|ministers|party|parties|state|states)\b", n) for n in raw_names):
            t1 = [w for w in raw_names[0].split() if len(w) >= 2]
            t2 = [w for w in raw_names[1].split() if len(w) >= 2] if len(raw_names) > 1 else []
            return {
                "result_type": "aggregate",
                "cypher": """
                    MATCH (p:Person:MP)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                    WITH p, c, s
                    WHERE (size($t1) > 0 AND all(tok IN $t1 WHERE toLower(p.name) CONTAINS tok OR toLower(coalesce(p.myneta_name, '')) CONTAINS tok))
                       OR (size($t2) > 0 AND all(tok IN $t2 WHERE toLower(p.name) CONTAINS tok OR toLower(coalesce(p.myneta_name, '')) CONTAINS tok))
                    RETURN p.entity_id AS entity_id,
                           p.name AS mp_name,
                           coalesce(p.party_name, '—') AS party,
                           coalesce(c.name, '—') AS constituency,
                           coalesce(s.name, '—') AS state,
                           p.terms AS terms,
                           coalesce(p.criminal_case_count, 0) AS criminal_cases,
                           p.total_assets AS total_assets,
                           p.liabilities AS liabilities,
                           coalesce(p.education, '—') AS education
                    ORDER BY CASE WHEN p.total_assets IS NULL THEN 1 ELSE 0 END, mp_name ASC
                    LIMIT 15
                """,
                "parameters": {"t1": t1, "t2": t2},
                "explanation": f"MP affidavit and parliamentary record for '{pname}'.",
                "template_id": "mp_by_name",
            }
    return None


_WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _mp_demographics_and_terms(q):
    ql = q.lower()
    state = _state(q)
    party = _party(q)
    limit = _top_n(q, 50)

    # 1. Age: youngest / oldest MP
    if _any(ql, "youngest", "oldest", "age above", "older than", "younger than"):
        is_young = "young" in ql
        order_dir = "ASC" if is_young else "DESC"
        lim = _top_n(q, 10 if _any(ql, "top", "mps") else 5)
        return {
            "result_type": "aggregate",
            "cypher": f"""
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE p.age IS NOT NULL AND p.age > 0
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                RETURN p.entity_id AS entity_id,
                       p.name AS mp_name,
                       p.age AS age,
                       coalesce(p.party_name, '—') AS party,
                       coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state,
                       p.total_assets AS total_assets
                ORDER BY p.age {order_dir}, mp_name ASC
                LIMIT {lim}
            """,
            "parameters": {"state": state, "party": party},
            "explanation": f"{'Youngest' if is_young else 'Oldest'} MPs with recorded age.",
            "template_id": "mp_by_age",
        }

    # 2. Terms: first-time, N+ terms, most terms
    if _any(ql, "term", "terms", "first-time", "first time", "longest serving", "most experienced"):
        if _any(ql, "first-time", "first time", "1 term", "one term", "single term") and not _any(ql, "more than", "over", "above"):
            return {
                "result_type": "aggregate",
                "cypher": f"""
                    MATCH (p:Person:MP)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                    WITH p, c, s
                    WHERE p.terms = 1
                      AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                      AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                    RETURN p.entity_id AS entity_id, p.name AS mp_name, coalesce(p.party_name, '—') AS party,
                           coalesce(c.name, '—') AS constituency, coalesce(s.name, '—') AS state,
                           p.terms AS terms, p.total_assets AS total_assets
                    ORDER BY CASE WHEN p.total_assets IS NULL THEN 1 ELSE 0 END, mp_name ASC
                    LIMIT {limit}
                """,
                "parameters": {"state": state, "party": party},
                "explanation": "First-time MPs (1 recorded Lok Sabha term).",
                "template_id": "mp_by_terms",
            }
        m_t = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+|or\s+more|plus|and\s+more)?\s*terms?", ql)
        min_terms = 2
        if m_t:
            raw_t = m_t.group(1)
            min_terms = int(raw_t) if raw_t.isdigit() else _WORD_NUMS.get(raw_t, 2)
        elif _any(ql, "most terms", "highest terms", "longest serving", "most experienced"):
            min_terms = 2
        return {
            "result_type": "aggregate",
            "cypher": f"""
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE p.terms IS NOT NULL AND p.terms >= $min_terms
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                RETURN p.entity_id AS entity_id, p.name AS mp_name, coalesce(p.party_name, '—') AS party,
                       coalesce(c.name, '—') AS constituency, coalesce(s.name, '—') AS state,
                       p.terms AS terms, coalesce(p.criminal_case_count, 0) AS criminal_cases,
                       p.total_assets AS total_assets
                ORDER BY p.terms DESC, mp_name ASC
                LIMIT {limit}
            """,
            "parameters": {"min_terms": min_terms, "state": state, "party": party},
            "explanation": f"MPs with at least {min_terms} recorded Lok Sabha terms, ordered by terms.",
            "template_id": "mp_by_terms",
        }

    # 3. Gender: women / female / male MPs
    if _any(ql, "women", "woman", "female", "male", "men"):
        is_female = _any(ql, "women", "woman", "female")
        g_vals = ["F", "FEMALE"] if is_female else ["M", "MALE"]
        if "how many" in ql or "count" in ql:
            return {
                "result_type": "aggregate",
                "cypher": """
                    MATCH (p:Person:MP)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(:Constituency)-[:IN_STATE]->(s:State)
                    WITH p, s
                    WHERE toUpper(coalesce(p.gender, '')) IN $g_vals
                      AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                      AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                    RETURN count(DISTINCT p) AS mp_count
                    LIMIT 1
                """,
                "parameters": {"g_vals": g_vals, "state": state, "party": party},
                "explanation": f"Count of {'female' if is_female else 'male'} MPs matching the criteria.",
                "template_id": "mp_gender_count",
            }
        return {
            "result_type": "aggregate",
            "cypher": f"""
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE toUpper(coalesce(p.gender, '')) IN $g_vals
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                RETURN p.entity_id AS entity_id, p.name AS mp_name, p.gender AS gender,
                       coalesce(p.party_name, '—') AS party, coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state, coalesce(p.criminal_case_count, 0) AS criminal_cases,
                       p.total_assets AS total_assets
                ORDER BY CASE WHEN p.total_assets IS NULL THEN 1 ELSE 0 END, mp_name ASC
                LIMIT {limit}
            """,
            "parameters": {"g_vals": g_vals, "state": state, "party": party},
            "explanation": f"{'Female' if is_female else 'Male'} MPs recorded in the graph.",
            "template_id": "mp_by_gender",
        }

    # 4. Education & Profession
    edu_kw = ""
    for kw, pat in [("doctorate", r"\b(phd|ph\.d|doctorate)\b"), ("post graduate", r"\b(post\s*graduate|master)\b"), ("graduate", r"\bgraduate\b")]:
        if re.search(pat, ql):
            edu_kw = kw
            break
    if edu_kw:
        return {
            "result_type": "aggregate",
            "cypher": f"""
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE toLower(coalesce(p.education, '')) CONTAINS $edu
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                RETURN p.entity_id AS entity_id, p.name AS mp_name, p.education AS education,
                       coalesce(p.party_name, '—') AS party, coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state, p.total_assets AS total_assets
                ORDER BY mp_name ASC
                LIMIT {limit}
            """,
            "parameters": {"edu": edu_kw, "state": state, "party": party},
            "explanation": f"MPs with education matching '{edu_kw}'.",
            "template_id": "mp_by_education",
        }

    prof_kw = ""
    for kw, pat in [
        ("advocate", r"\b(lawyer|lawyers|advocate|advocates|legal)\b"),
        ("medical", r"\b(doctor|doctors|medical|physician)\b"),
        ("agriculturist", r"\b(farmer|farmers|agriculturist|agriculture)\b"),
        ("social worker", r"\bsocial\s+worker\b"),
        ("business", r"\b(business|businessman|industrialist|trader)\b"),
    ]:
        if re.search(pat, ql):
            prof_kw = kw
            break
    if prof_kw:
        return {
            "result_type": "aggregate",
            "cypher": f"""
                MATCH (p:Person:MP)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, c, s
                WHERE toLower(toString(coalesce(p.profession, ''))) CONTAINS $prof
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND ($party = '' OR toLower(coalesce(p.party_name, '')) CONTAINS toLower($party))
                RETURN p.entity_id AS entity_id, p.name AS mp_name, p.profession AS profession,
                       coalesce(p.party_name, '—') AS party, coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state, p.total_assets AS total_assets
                ORDER BY mp_name ASC
                LIMIT {limit}
            """,
            "parameters": {"prof": prof_kw, "state": state, "party": party},
            "explanation": f"MPs with profession matching '{prof_kw}'.",
            "template_id": "mp_by_profession",
        }
    return None


def _mp_ipc_sections(q):
    state = _state(q)
    parties = _mp_party_variants(q)
    code = _ipc_section(q)
    if not code:
        sc = _section_codes(q)
        code = sc[0] if sc else ""
    if code:
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)-[:FACES]->(cc:CriminalCase)-[:UNDER]->(sec:Section)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, cc, sec, c, s
                WHERE sec.code <> 'IPC' AND sec.code <> 'BNS'
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
                  AND toUpper(sec.code) CONTAINS toUpper($code)
                RETURN p.entity_id AS entity_id,
                       p.name AS mp_name,
                       coalesce(p.party_name, '—') AS party,
                       coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state,
                       sec.code AS ipc_section,
                       count(DISTINCT cc) AS case_count
                ORDER BY case_count DESC, mp_name ASC
                LIMIT 50
            """,
            "parameters": {"state": state, "parties": parties, "code": code},
            "explanation": f"MPs facing criminal cases under IPC section {code}.",
            "template_id": "mp_ipc_sections",
        }
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MP)-[:FACES]->(cc:CriminalCase)-[:UNDER]->(sec:Section)
            OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
            WITH p, cc, sec, s
            WHERE sec.code <> 'IPC' AND sec.code <> 'BNS'
              AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
              AND (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
            RETURN sec.code AS ipc_section,
                   count(DISTINCT p) AS mp_count,
                   collect(DISTINCT p.name)[0..5] AS sample_mps
            ORDER BY mp_count DESC
            LIMIT 30
        """,
        "parameters": {"state": state, "parties": parties},
        "explanation": "IPC sections cited in criminal cases against MPs, with MP counts and sample names.",
        "template_id": "mp_ipc_sections",
    }


def _mp_unified_query(q):
    ql = q.lower()
    state = _state(q)
    party = _party(q)
    parties = _mp_party_variants(q)
    has_ministry = _any(ql, "ministry", "ministries", "portfolio", "portfolios", "minister", "mod", "mha", "mof", "morth", "defence", "defense")
    zero_cases = _any(
        ql,
        "zero criminal", "zero case", "0 criminal", "0 case",
        "no criminal", "no case", "no declared case", "without criminal",
        "without case", "clean mp", "clean mps", "clean record",
    )
    has_criminal = (not zero_cases) and _any(ql, "criminal", "case", "cases", "charge", "accused", "tainted")
    is_richest = _any(ql, "richest", "wealthiest", "highest asset", "most asset", "top", "assets", "worth")
    money_val = _money(q)
    is_liab_thresh = money_val is not None and "liabilit" in ql
    min_assets = money_val if (money_val is not None and not is_liab_thresh) else 0.0
    min_liab = money_val if is_liab_thresh else 0.0
    case_mode = "zero" if zero_cases else ("positive" if has_criminal else "any")
    limit = _top_n(q, 50)

    if has_ministry and "state" in ql and not state and not has_criminal:
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)-[:HOLDS_PORTFOLIO]->(m:Ministry)
                MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WHERE (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
                RETURN s.name AS state,
                       count(DISTINCT p) AS minister_mps,
                       collect(DISTINCT p.name)[0..5] AS sample_mps,
                       collect(DISTINCT m.name)[0..5] AS ministries
                ORDER BY minister_mps DESC
                LIMIT 50
            """,
            "parameters": {"parties": parties},
            "explanation": "States represented by MPs who hold Union Ministry portfolios.",
            "template_id": "mp_ministry_states",
        }

    if has_ministry:
        min_kw = ""
        if re.search(r"\b(?:mod|defence|defense)\b", ql):
            min_kw = "defence"
        elif re.search(r"\b(?:mha|home(?:\s+affairs)?)\b", ql):
            min_kw = "home affairs"
        elif re.search(r"\b(?:mof|finance)\b", ql):
            min_kw = "finance"
        elif re.search(r"\b(?:morth|road\s+transport|highways?)\b", ql):
            min_kw = "road transport"
        elif re.search(r"\b(?:moe|mhrd|education)\b", ql):
            min_kw = "education"
        elif re.search(r"\b(?:railways?|mor)\b", ql):
            min_kw = "railways"
        else:
            for kw in (
                "home affairs", "finance", "defence", "road transport", "agriculture",
                "railways", "external affairs", "education", "health", "commerce",
                "law", "rural development", "panchayati raj", "civil aviation",
                "housing", "power", "coal", "mines", "steel", "textiles",
                "telecom", "communications", "environment", "labour", "jal shakti",
            ):
                if kw in ql:
                    min_kw = kw
                    break
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (p:Person:MP)-[hp:HOLDS_PORTFOLIO]->(m:Ministry)
                OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                WITH p, hp, m, c, s
                WHERE (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
                  AND ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
                  AND ($min_kw = '' OR toLower(m.name) CONTAINS $min_kw)
                  AND ($min_assets <= 0 OR (p.total_assets IS NOT NULL AND toFloat(p.total_assets) >= $min_assets))
                  AND ($case_mode = 'any' OR ($case_mode = 'positive' AND coalesce(p.criminal_case_count, 0) > 0))
                RETURN p.entity_id AS entity_id,
                       p.name AS mp_name,
                       coalesce(hp.rank, 'Cabinet Minister') AS portfolio_rank,
                       coalesce(p.party_name, '—') AS party,
                       m.name AS ministry,
                       coalesce(c.name, '—') AS constituency,
                       coalesce(s.name, '—') AS state,
                       coalesce(p.criminal_case_count, 0) AS criminal_cases,
                       p.total_assets AS total_assets
                ORDER BY coalesce(hp.rank_order, 2) ASC, CASE WHEN p.total_assets IS NULL THEN 1 ELSE 0 END, toFloat(p.total_assets) DESC, mp_name ASC
                LIMIT 50
            """,
            "parameters": {
                "parties": parties,
                "state": state,
                "min_kw": min_kw,
                "min_assets": float(min_assets),
                "case_mode": case_mode,
            },
            "explanation": "MPs holding Union Ministry portfolios" + (f" ({min_kw.title()})" if min_kw else "") + ", ordered by Cabinet rank.",
            "template_id": "mp_ministries",
        }

    if not (state or parties or has_criminal or zero_cases or is_richest or money_val is not None):
        return None

    order_clause = (
        "CASE WHEN p.liabilities IS NULL THEN 1 ELSE 0 END, toFloat(p.liabilities) DESC, mp_name ASC"
        if is_liab_thresh
        else "CASE WHEN p.total_assets IS NULL THEN 1 ELSE 0 END, toFloat(p.total_assets) DESC, criminal_cases DESC, mp_name ASC"
        if (is_richest or min_assets > 0) and not has_criminal
        else "criminal_cases DESC, CASE WHEN p.total_assets IS NULL THEN 1 ELSE 0 END, toFloat(p.total_assets) DESC, mp_name ASC"
        if has_criminal
        else "mp_name ASC"
    )
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (p:Person:MP)
            OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
            WITH p, c, s
            WHERE ($state = '' OR toLower(coalesce(s.name, '')) = toLower($state))
              AND (size($parties) = 0 OR any(pt IN $parties WHERE toLower(coalesce(p.party_name, '')) = toLower(pt) OR toLower(coalesce(p.party_name, '')) CONTAINS toLower(pt)))
              AND (
                $case_mode = 'any'
                OR ($case_mode = 'positive' AND coalesce(p.criminal_case_count, 0) > 0)
                OR ($case_mode = 'zero' AND p.criminal_case_count IS NOT NULL AND p.criminal_case_count = 0)
              )
              AND ($min_assets <= 0 OR (p.total_assets IS NOT NULL AND toFloat(p.total_assets) >= $min_assets))
              AND ($min_liab <= 0 OR (p.liabilities IS NOT NULL AND toFloat(p.liabilities) >= $min_liab))
            RETURN p.entity_id AS entity_id,
                   p.name AS mp_name,
                   coalesce(p.party_name, '—') AS party,
                   coalesce(c.name, '—') AS constituency,
                   coalesce(s.name, '—') AS state,
                   coalesce(p.criminal_case_count, 0) AS criminal_cases,
                   p.total_assets AS total_assets,
                   p.liabilities AS liabilities
            ORDER BY {order_clause}
            LIMIT {limit}
        """,
        "parameters": {
            "state": state,
            "parties": parties,
            "case_mode": case_mode,
            "min_assets": float(min_assets),
            "min_liab": float(min_liab),
        },
        "explanation": "MPs matching the requested state, party, criminal-case, or financial threshold criteria.",
        "template_id": "mp_unified_query",
    }


# ---------------------------------------------------------------------------
# Phase 2: cross-election and profile templates
# ---------------------------------------------------------------------------

_GENERIC_NAME_WORDS = {
    "mla", "mlas", "mp", "mps", "politician", "politicians", "minister", "ministers",
    "party", "parties", "constituency", "state", "district", "assembly", "election",
}

_NAME_STOP = {
    "show", "tell", "give", "list", "did", "does", "what", "how", "who", "is", "was",
    "find", "get", "display", "explain", "compare", "about", "of", "for", "me", "the",
    "please", "can", "you", "has", "had", "were", "are", "do",
}


def _year(q: str) -> Optional[int]:
    m = re.search(r"\b(?:19|20)\d{2}\b", q)
    return int(m.group(0)) if m else None


def _person_name(q: str) -> str:
    """Best-effort proper-noun extraction for a named politician."""
    patterns = [
        r"([A-Z][\w.\-]*(?:\s+[A-Z][\w.\-]*){0,4})(?:['’]s)?\s+"
        r"(?i:assets?|liabilit\w*|net worth|criminal|cases?|party|affidavits?|profile|details)\b",
        r"(?i:about|of|for|did|does|has|had|is|was)\s+"
        r"([A-Z][\w.\-]*(?:\s+[A-Z][\w.\-]*){0,4})",
    ]
    for pat in patterns:
        m = re.search(pat, q)
        if not m:
            continue
        words = m.group(1).strip(" .,'’").split()
        while words and words[0].lower() in _NAME_STOP:
            words.pop(0)
        name = " ".join(words)
        if name and not any(w.lower() in _GENERIC_NAME_WORDS for w in words):
            return name
    return ""


def _constituency(q: str) -> str:
    """Best-effort assembly-constituency extraction for winner questions."""
    patterns = [
        r"(?i:who won|winner of|mla of|mla from|mla is|represents|represented|representing|"
        r"constituency of|seat of)\s+(?:from\s+)?([A-Z][\w .\-&']+?)"
        r"(?:\s+in\s+\d{4}|\?|$)",
        r"(?i:for)\s+([A-Z][\w .\-&']+?),\s*(?:who|which)",
    ]
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            name = m.group(1).strip(" .,'")
            name = re.sub(r"\s+(?:back|there|please|roughly|around|again|now)$", "", name, flags=re.I)
            return name
    return ""


def _constituency_winner(q):
    """Who won an assembly constituency (optionally in a given year)."""
    cons = _constituency(q)
    if not cons:
        return None
    # "MLA from Delhi" is a state question, not a constituency.
    if any(cons.lower() == s.lower() for s in INDIAN_STATES):
        return None
    year = _year(q) or 0
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:REPRESENTS]->(c:AssemblyConstituency)
            MATCH (p)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election {type:'State Assembly'})
            WHERE toLower(c.name) CONTAINS toLower($constituency)
              AND ($year = 0 OR e.year = $year)
            RETURN p.name AS mla_name, c.name AS constituency, e.year AS year,
                   e.election_id AS election, a.party_name AS party,
                   a.total_assets AS total_assets, a.criminal_case_count AS cases
            ORDER BY year DESC
        """,
        "parameters": {"constituency": cons, "year": year},
        "explanation": (
            f"MLA recorded as representing {cons}"
            + (f" in {year}" if year else " across recorded elections")
            + ", with party, declared total assets and the number of criminal cases declared."
        ),
        "template_id": "constituency_winner",
    }


def _mla_timeline(q):
    """Party / assets / liabilities / cases for a named politician, by election."""
    name = _person_name(q)
    if not name:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election)
            WHERE toLower(p.name) CONTAINS toLower($name)
            RETURN p.name AS name, e.year AS year, e.election_id AS election,
                   a.party_name AS party, a.total_assets AS total_assets,
                   a.liabilities AS liabilities, a.criminal_case_count AS cases
            ORDER BY year
        """,
        "parameters": {"name": name},
        "explanation": (
            f"Election-by-election affidavit record for {name}: party, declared total assets, "
            f"declared liabilities and the number of criminal cases recorded in each affidavit."
        ),
        "template_id": "mla_timeline",
    }


def _mla_case_change(q):
    """Criminal-case count for a named politician, by election."""
    name = _person_name(q)
    if not name:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election)
            WHERE toLower(p.name) CONTAINS toLower($name)
            RETURN e.year AS year, e.election_id AS election, a.criminal_case_count AS cases
            ORDER BY year
        """,
        "parameters": {"name": name},
        "explanation": (
            f"Number of criminal cases recorded in each affidavit filed by {name}. "
            f"This is the count declared in the affidavit, not a finding of guilt."
        ),
        "template_id": "mla_case_change",
    }


def _mla_party_switchers(q):
    """MLAs whose recorded party differs across two or more elections."""
    state = _state(q)
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election {type:'State Assembly'})
            WHERE $state = '' OR e.state = $state
            WITH p.person_key AS person_key,
                 collect(DISTINCT a.party_name) AS parties,
                 collect(DISTINCT e.election_id) AS elections,
                 count(DISTINCT e.election_id) AS n
            WHERE n >= 2 AND size(parties) > 1
            RETURN person_key, parties, elections, n
            ORDER BY n DESC
            LIMIT 25
        """,
        "parameters": {"state": state},
        "explanation": (
            "MLAs whose recorded party differs between at least two elections in the same state. "
            "Grouping uses the person key (state + name + shared seat); it is not a claim about "
            "when a real-world party switch happened."
        ),
        "template_id": "mla_party_switchers",
    }


def _mla_election_roster(q):
    """MLAs recorded for a state and assembly-election year."""
    state = _state(q)
    year = _year(q)
    if not state or not year:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:REPRESENTS]->(c:AssemblyConstituency)
            MATCH (p)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election {type:'State Assembly'})
            WHERE e.state = $state AND e.year = $year
            RETURN p.name AS mla_name, c.name AS constituency, a.party_name AS party,
                   a.total_assets AS total_assets, a.criminal_case_count AS cases
            ORDER BY constituency
        """,
        "parameters": {"state": state, "year": year},
        "explanation": (
            f"MLAs recorded for {state} in the {year} assembly election, with party, declared "
            f"total assets and the number of criminal cases declared in the affidavit."
        ),
        "template_id": "mla_election_roster",
    }


def _politician_profile(q):
    """Latest recorded affidavit profile for a named politician."""
    name = _person_name(q)
    if not name:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election)
            WHERE toLower(p.name) CONTAINS toLower($name)
            RETURN p.name AS name, e.election_id AS election, e.year AS year,
                   a.party_name AS party, p.age AS age, a.total_assets AS total_assets,
                   a.liabilities AS liabilities, a.criminal_case_count AS cases,
                   p.education AS education
            ORDER BY year DESC
            LIMIT 1
        """,
        "parameters": {"name": name},
        "explanation": (
            f"Latest recorded affidavit profile for {name}: election, party, age, declared assets, "
            f"declared liabilities, criminal-case count and education."
        ),
        "template_id": "politician_profile",
    }


def _party_seats_in_state(q):
    """Multi-hop: seats per party in a state (optionally one election year)."""
    state = _state(q)
    if not state:
        return None
    year = _year(q) or 0
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election {type:'State Assembly'})
            WHERE e.state = $state AND ($year = 0 OR e.year = $year)
            RETURN a.party_name AS party, count(DISTINCT p) AS seats
            ORDER BY seats DESC
        """,
        "parameters": {"state": state, "year": year},
        "explanation": (
            f"Seats recorded for each party in {state}"
            + (f" in {year}" if year else " across the recorded elections")
            + "."
        ),
        "template_id": "party_seats_in_state",
    }


def _party_section_in_state(q):
    """Multi-hop: party x IPC section x state (optionally year and party)."""
    state = _state(q)
    if not state:
        return None
    codes = _section_codes(q)
    section = codes[0] if codes else _ipc_section(q)
    if not section:
        return None
    year = _year(q) or 0
    party = _party(q)
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:FILED]->(a:Affidavit)-[:FOR_ELECTION]->(e:Election {type:'State Assembly'})
            WHERE e.state = $state AND ($year = 0 OR e.year = $year)
              AND ($party = '' OR a.party_name = $party)
            MATCH (p)-[:FACES]->(c:CriminalCase)-[:UNDER]->(s:Section {code:$section})
            RETURN a.party_name AS party, count(DISTINCT p) AS mlas, count(DISTINCT c) AS cases
            ORDER BY mlas DESC
        """,
        "parameters": {"state": state, "year": year, "party": party, "section": section},
        "explanation": (
            f"Parties whose MLAs in {state} have cases recorded under IPC section {section}"
            + (f" in {year}" if year else "")
            + "."
        ),
        "template_id": "party_section_in_state",
    }


def _state_most_cases(q):
    """Multi-hop: states ranked by MLAs with declared criminal cases."""
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st:State)
            MATCH (p)-[:FILED]->(:Affidavit)-[:FOR_ELECTION]->(:Election {type:'State Assembly'})
            WHERE p.criminal_case_count > 0
            RETURN st.name AS state, count(DISTINCT p) AS mlas_with_cases
            ORDER BY mlas_with_cases DESC
        """,
        "parameters": {},
        "explanation": "States ranked by the number of MLAs with at least one case recorded in their affidavit.",
        "template_id": "state_most_cases",
    }


def _mp_mla_counts_by_state(q):
    """Multi-hop: MP and MLA counts for one state."""
    state = _state(q)
    if not state:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (mp:Person:MP)-[:REPRESENTS]->(pc:Constituency)-[:IN_STATE]->(st:State)
            WHERE st.name = $state
            MATCH (mla:Person:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st)
            RETURN st.name AS state, count(DISTINCT mp) AS mps, count(DISTINCT mla) AS mlas LIMIT 1
        """,
        "parameters": {"state": state},
        "explanation": f"Recorded MPs and MLAs for {state}.",
        "template_id": "mp_mla_counts_by_state",
    }


def _state_avg_assets(q):
    """Average / max declared assets for MLAs of one state."""
    state = _state(q)
    if not state:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st:State)
            MATCH (p)-[:FILED]->(:Affidavit)-[:FOR_ELECTION]->(:Election {type:'State Assembly'})
            WHERE st.name = $state
            RETURN st.name AS state, count(DISTINCT p) AS mlas,
                   avg(p.total_assets) AS avg_assets, max(p.total_assets) AS max_assets LIMIT 1
        """,
        "parameters": {"state": state},
        "explanation": f"Average and maximum declared total assets for MLAs recorded in {state}.",
        "template_id": "state_avg_assets",
    }


def _states_ranked_by_avg_assets(q):
    """States ranked by average declared MLA assets."""
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st:State)
            MATCH (p)-[:FILED]->(:Affidavit)-[:FOR_ELECTION]->(:Election {type:'State Assembly'})
            RETURN st.name AS state, avg(p.total_assets) AS avg_assets, count(DISTINCT p) AS mlas
            ORDER BY avg_assets DESC LIMIT 10
        """,
        "parameters": {},
        "explanation": "States ranked by the average declared total assets of their recorded MLAs.",
        "template_id": "states_ranked_by_avg_assets",
    }


def _party_sections(q):
    """Most common IPC sections among a party's MLAs."""
    party = _party(q)
    if not party:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:MEMBER_OF]->(pa:Party)
            MATCH (p)-[:FACES]->(c:CriminalCase)-[:UNDER]->(s:Section)
            WHERE pa.name = $party AND s.code <> 'IPC' AND s.code <> 'BNS'
            RETURN s.code AS section, count(DISTINCT c) AS cases
            ORDER BY cases DESC LIMIT 10
        """,
        "parameters": {"party": party},
        "explanation": f"IPC sections most frequently recorded against {party} MLAs, by distinct case count.",
        "template_id": "party_sections",
    }


def _largest_party_section(q):
    """The largest party in a state and the IPC sections its MLAs are charged under."""
    state = _state(q)
    if not state:
        return None
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:Person:MLA)-[:MEMBER_OF]->(pa:Party)
            MATCH (p)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st:State)
            WHERE st.name = $state
            WITH pa, count(DISTINCT p) AS seats
            MATCH (p2:Person:MLA)-[:MEMBER_OF]->(pa)
            MATCH (p2)-[:FACES]->(c:CriminalCase)-[:UNDER]->(s:Section)
            WHERE s.code <> 'IPC' AND s.code <> 'BNS'
            RETURN pa.name AS party, seats, s.code AS section, count(DISTINCT c) AS cases
            ORDER BY seats DESC, cases DESC LIMIT 5
        """,
        "parameters": {"state": state},
        "explanation": (
            f"The largest recorded party in {state} and the IPC sections most frequently recorded "
            f"against its MLAs."
        ),
        "template_id": "largest_party_section",
    }


_UNSUPPORTED_SHAPES = [
    r"\bmedian\b", r"\bpercentage\b", r"\bfraction\b", r"\bpercent\b", r"%",
    r"\bcompare\b", r"\bversus\b", r"\bvs\.?\b",
    r"\bolder\s+than\b", r"\byounger\s+than\b",
    r"\blow\w*\b.*\bthan\b", r"\bhigh\w*\b.*\bthan\b",
    r"\bunder\s+(?:₹|rs\.?|inr)?\s*\d", r"\bbelow\s+(?:₹|rs\.?|inr)?\s*\d",
    r"\bno\s+declared\b", r"\bno\s+cases?\b",
    r"\bnamed\b", r"\blisted\s+under\b", r"\bunder\s+(?:any\s+)?ministry\b",
    r"\bboth\b.+\band\b",
    r"\bgreater\s+than\b.*\b(?:liabilit|asset)",
    r"\btotal\b.*\bassets\b.*\bminister",
    r"\b(?:post\s*graduate|postgraduate|graduate|degree)\b",
    r"\bmore\s+than\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b",
]


def _unsupported_shape(q: str) -> bool:
    """True when the question contains a filter the deterministic templates cannot honour."""
    return any(re.search(pat, q, re.I) for pat in _UNSUPPORTED_SHAPES)


def _multiple_sections(q):
    """MLAs with declared cases under both of two IPC sections."""
    codes = _section_codes(q)
    if len(codes) < 2:
        return None
    s1, s2 = codes[0], codes[1]
    return {
        "result_type": "aggregate",
        "cypher": """
            MATCH (p:MLA)-[:FACES]->(:CriminalCase)-[:UNDER]->(:Section {code:$s1})
            WITH DISTINCT p
            MATCH (p)-[:FACES]->(:CriminalCase)-[:UNDER]->(:Section {code:$s2})
            RETURN count(DISTINCT p) AS mla_count LIMIT 1
        """,
        "parameters": {"s1": s1, "s2": s2},
        "explanation": f"MLAs with at least one declared case recorded under both IPC {s1} and IPC {s2}.",
        "template_id": "multiple_sections",
    }


def _richest_mps(q):
    """Top MPs by declared total assets."""
    n = _top_n(q, 5)
    return {
        "result_type": "aggregate",
        "cypher": f"""
            MATCH (p:Person:MP)
            WHERE p.entity_id STARTS WITH 'sansad_mp_' AND p.total_assets IS NOT NULL
            RETURN p.name AS mp_name, p.party_name AS party, p.total_assets AS total_assets,
                   p.liabilities AS liabilities
            ORDER BY total_assets DESC LIMIT {n}
        """,
        "parameters": {},
        "explanation": f"The {n} MPs with the highest declared total assets.",
        "template_id": "richest_mps",
    }


def plan_from_template(question: str) -> dict | None:
    q = question.strip()
    ql = q.lower()

    # "both IPC X and IPC Y" needs an intersection, not a single-section count.
    if "both" in ql and len(_section_codes(q)) >= 2:
        return _multiple_sections(q)

    # Graph Algorithms (GDS): Case-profile Jaccard similarity & Party-switcher PageRank / Community Detection
    if _any(ql, "similar", "similarity", "jaccard", "case profile"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (m1:Person:MP)-[r:SIMILAR_CASE_PROFILE]->(m2:Person:MP)
                WHERE m1.entity_id < m2.entity_id
                RETURN m1.name AS mp_1,
                       coalesce(m1.party_name, '—') AS party_1,
                       m2.name AS mp_2,
                       coalesce(m2.party_name, '—') AS party_2,
                       r.jaccard_score AS jaccard_similarity,
                       r.shared_count AS shared_section_count,
                       r.shared_sections AS shared_ipc_sections
                ORDER BY r.jaccard_score DESC, r.shared_count DESC
                LIMIT 30
            """,
            "parameters": {},
            "explanation": "Top MP pairs ranked by Jaccard similarity over their declared IPC criminal section profiles.",
            "template_id": "mp_case_similarity",
        }

    if _any(ql, "community detection", "pagerank", "page rank", "defection hub", "defection cluster", "graph algorithm", "gds"):
        return {
            "result_type": "aggregate",
            "cypher": """
                MATCH (pa:Party)
                WHERE pa.switcher_pagerank IS NOT NULL
                RETURN pa.name AS party,
                       pa.switcher_pagerank AS pagerank_score,
                       pa.in_defections AS incoming_switches,
                       pa.out_defections AS outgoing_switches,
                       pa.net_defection_gain AS net_migration,
                       pa.switcher_community AS community_cluster
                ORDER BY pa.switcher_pagerank DESC
                LIMIT 30
            """,
            "parameters": {},
            "explanation": "Party-switching network analyzed via PageRank centrality and Label Propagation community detection.",
            "template_id": "party_switcher_communities",
        }

    # Constituency or single-MP direct lookup ("Who is the MP of Varanasi?", "Assets of Rahul Gandhi")
    if "mla" not in ql and "assembly" not in ql:
        mp_direct = _mp_constituency_or_person(q)
        if mp_direct:
            return mp_direct

    is_mp_top = bool(re.search(r"\bmps?\b|\bmembers? of parliament\b|\blok sabha\b|\bministers?\b|\bministries\b|\bministry\b", ql)) and not bool(
        re.search(r"\bmlas?\b|assembly", ql)
    )
    if is_mp_top and not _any(ql, "prime minister", "chief minister", "president", "capital of", "weather", "corrupt", "acquitted"):
        if _any(ql, "negative net worth", "liabilities exceed", "liabilities greater than", "more liabilities than assets", "shortfall"):
            return _mps_negative_net_worth(q)
        if _any(ql, "switched part", "switch part", "party switch", "changed part", "change part", "defected", "party hop"):
            return _mp_party_switchers(q)
        if _any(ql, "affidavit change", "asset change", "assets changed", "wealth change", "wealth grew", "assets grew", "assets increased", "asset increase", "assets increase", "asset growth", "cases increased", "cases grew", "liabilities change", "across affidavits", "re-elected"):
            return _mp_affidavit_changes(q)
        if _any(ql, "charges framed", "charge framed", "pending case", "pending criminal", "convict", "cognizance", "serious"):
            return _mp_case_status(q)
        if _any(ql, "pan", "tax filing", "income tax", "itr"):
            return {
                "result_type": "aggregate",
                "cypher": """
                    MATCH (p:Person:MP)
                    WHERE p.total_assets IS NOT NULL
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(s:State)
                    RETURN p.entity_id AS entity_id,
                           p.name AS mp_name,
                           coalesce(p.party_name, '—') AS party,
                           coalesce(c.name, '—') AS constituency,
                           coalesce(s.name, '—') AS state,
                           'Declared' AS pan_declared,
                           p.total_assets AS total_assets,
                           p.liabilities AS liabilities
                    ORDER BY toFloat(p.total_assets) DESC, mp_name ASC
                    LIMIT 50
                """,
                "parameters": {},
                "explanation": "MPs with declared affidavit financial and PAN/tax filing records.",
                "template_id": "mp_pan_tax",
            }
        if _any(ql, "ministry", "ministries", "portfolio", "portfolios", "minister", "ministers"):
            uplan = _mp_unified_query(q)
            if uplan:
                return uplan
        demo_plan = _mp_demographics_and_terms(q)
        if demo_plan:
            return demo_plan
        if _any(ql, "ipc", "section"):
            return _mp_ipc_sections(q)
        if _any(ql, "zero criminal", "zero case", "0 criminal", "0 case", "no criminal", "no case", "without criminal", "clean"):
            uplan = _mp_unified_query(q)
            if uplan:
                return uplan
        if _money(q) is not None and (_party(q) or _state(q) or "liabilit" in ql or not _any(ql, "how many", "count")):
            uplan = _mp_unified_query(q)
            if uplan:
                return uplan

    # MP-scoped wealth questions must not fall into the MLA/politician template.
    if re.search(r"\bmps?\b|parliament|member of parliament", ql) \
            and not re.search(r"\bmlas?\b|assembly", ql) \
            and _any(ql, "richest", "top") and _any(ql, "asset", "rich", "wealth") \
            and not _state(q) and not _party(q):
        return _richest_mps(q)

    # Strict supported-shape guard: unsupported filters go to the LLM/refusal path.
    if _unsupported_shape(q):
        return None

    # Year range / inequality filters for MLAs or MPs ("inc mlas elected after 1996", "mlas after 1996", "bjp mps since 2014", "mlas before 2020")
    year_cmp = re.search(
        r"\b(?P<op>after|since|from|before|prior\s+to|until|till|above|over|below|under)\s+(?P<yr>(?:19|20)\d{2})\b",
        ql,
    )
    if year_cmp and re.search(r"\b(mlas?|mps?|politicians?|leaders?|winners?|candidates?)\b", ql):
        op_word = year_cmp.group("op")
        yr_val = int(year_cmp.group("yr"))
        if op_word in ("after", "above", "over"):
            op_sym, op_desc = ">", f"after {yr_val}"
        elif op_word in ("since", "from"):
            op_sym, op_desc = ">=", f"since {yr_val}"
        else:
            op_sym, op_desc = "<", f"before {yr_val}"

        is_mp_only = bool(re.search(r"\bmps?\b", ql)) and not bool(re.search(r"\bmlas?\b", ql))
        party_val = _party(q)
        state_val = _state(q)
        is_count = _any(ql, "how many", "count", "number of")

        params: dict = {"year": yr_val}
        if party_val:
            params["party"] = party_val
        if state_val:
            params["state"] = state_val

        if is_mp_only:
            where_clauses = [f"coalesce(er.year, p.election_year, 2024) {op_sym} $year"]
            if party_val:
                where_clauses.append("(pa.name = $party OR p.party_name = $party)")
            if state_val:
                where_clauses.append("(st.name = $state OR p.state = $state)")
            where_sql = " AND ".join(where_clauses)
            if is_count:
                cypher = f"""
                    MATCH (p:Person:MP)
                    OPTIONAL MATCH (p)-[:MEMBER_OF]->(pa:Party)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(st:State)
                    OPTIONAL MATCH (p)-[:HAS_ELECTION_RECORD]->(er:ElectionRecord)
                    WITH p, pa, c, st, max(coalesce(er.year, p.election_year, 2024)) AS latest_year
                    WHERE latest_year {op_sym} $year
                    {('AND (pa.name = $party OR p.party_name = $party)' if party_val else '')}
                    {('AND (st.name = $state OR p.state = $state)' if state_val else '')}
                    RETURN count(DISTINCT p) AS matching_mps
                    LIMIT 1
                """
            else:
                cypher = f"""
                    MATCH (p:Person:MP)
                    OPTIONAL MATCH (p)-[:MEMBER_OF]->(pa:Party)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(c:Constituency)-[:IN_STATE]->(st:State)
                    OPTIONAL MATCH (p)-[:HAS_ELECTION_RECORD]->(er:ElectionRecord)
                    WITH p, pa, c, st, max(coalesce(er.year, p.election_year, 2024)) AS latest_year
                    WHERE latest_year {op_sym} $year
                    {('AND (pa.name = $party OR p.party_name = $party)' if party_val else '')}
                    {('AND (st.name = $state OR p.state = $state)' if state_val else '')}
                    RETURN DISTINCT p.name AS mp_name,
                           coalesce(pa.name, p.party_name, '—') AS party,
                           coalesce(st.name, p.state, '—') AS state,
                           coalesce(c.name, '—') AS constituency,
                           latest_year AS election_year,
                           coalesce(p.criminal_case_count, 0) AS cases,
                           coalesce(p.total_assets, 0) AS total_assets,
                           p.entity_id AS entity_id
                    ORDER BY election_year DESC, total_assets DESC
                    LIMIT 50
                """
            role_label = "MPs"
        else:
            where_clauses = [f"coalesce(p.election_year, e.year) {op_sym} $year"]
            if party_val:
                where_clauses.append("(pa.name = $party OR p.party_name = $party)")
            if state_val:
                where_clauses.append("(st.name = $state OR p.state = $state)")
            where_sql = " AND ".join(where_clauses)
            if is_count:
                cypher = f"""
                    MATCH (p:Person:MLA)
                    OPTIONAL MATCH (p)-[:MEMBER_OF]->(pa:Party)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st:State)
                    OPTIONAL MATCH (p)-[:FILED]->(:Affidavit)-[:FOR_ELECTION]->(e:Election)
                    WITH p, pa, ac, st, max(coalesce(p.election_year, e.year)) AS election_year
                    WHERE election_year {op_sym} $year
                    {('AND (pa.name = $party OR p.party_name = $party)' if party_val else '')}
                    {('AND (st.name = $state OR p.state = $state)' if state_val else '')}
                    RETURN count(DISTINCT p) AS matching_mlas
                    LIMIT 1
                """
            else:
                cypher = f"""
                    MATCH (p:Person:MLA)
                    OPTIONAL MATCH (p)-[:MEMBER_OF]->(pa:Party)
                    OPTIONAL MATCH (p)-[:REPRESENTS]->(ac:AssemblyConstituency)-[:IN_STATE]->(st:State)
                    OPTIONAL MATCH (p)-[:FILED]->(:Affidavit)-[:FOR_ELECTION]->(e:Election)
                    WITH p, pa, ac, st, max(coalesce(p.election_year, e.year)) AS election_year
                    WHERE election_year {op_sym} $year
                    {('AND (pa.name = $party OR p.party_name = $party)' if party_val else '')}
                    {('AND (st.name = $state OR p.state = $state)' if state_val else '')}
                    RETURN DISTINCT p.name AS mla_name,
                           coalesce(pa.name, p.party_name, '—') AS party,
                           coalesce(st.name, p.state, '—') AS state,
                           coalesce(ac.name, '—') AS constituency,
                           election_year,
                           coalesce(p.criminal_case_count, 0) AS cases,
                           coalesce(p.total_assets, 0) AS total_assets,
                           p.entity_id AS entity_id
                    ORDER BY election_year DESC, total_assets DESC
                    LIMIT 50
                """
            role_label = "MLAs"

        scope_bits = [b for b in (party_val, role_label, f"in {state_val}" if state_val else "", f"elected {op_desc}") if b]
        return {
            "result_type": "aggregate",
            "cypher": cypher,
            "parameters": params,
            "explanation": f"{'Count' if is_count else 'Top 50 matching records'} of {' '.join(scope_bits)} in the electoral graph.",
            "template_id": "politicians_by_year_filter",
        }

    # --- Phase 2: cross-election MLA templates (deterministic) ---
    # Party switchers (aggregate; no specific person named).
    if _any(ql, "switch", "switched", "changed part", "change part", "party switch") \
            and _any(ql, "party", "parties") and "how many" not in ql and not _person_name(q):
        if re.search(r"\bmps?\b|\bmembers? of parliament\b", ql) and "mla" not in ql:
            return _mp_party_switchers(q)
        return _mla_party_switchers(q)

    # Asset / liability change for a named politician.
    if _any(ql, "asset change", "assets change", "assets over time", "assets across",
            "asset growth", "liabilities change", "liabilit change", "assets grew",
            "assets grow", "asset situation", "go up or down", "over the elections",
            "election to election", "across the elections") and _person_name(q):
        return _mla_timeline(q)

    # Criminal-case count change for a named politician.
    if _any(ql, "criminal case count", "case count", "cases change", "cases over time",
            "cases across", "criminal cases across", "cases grew") and _person_name(q):
        return _mla_case_change(q)

    # Party history / contested under different parties.
    if _any(ql, "party history", "which parties", "contested under", "contest under",
            "different parties", "change party", "changed party", "switch party",
            "switched party") and _person_name(q):
        return _mla_timeline(q)

    # Constituency winner ("Who won X in Y?", "Who is the MLA of X?").
    if _any(ql, "who won", "winner of", "mla of", "mla from", "represents", "represented",
            "representing", "constituency of", "seat of", "who is the mla", "which mla") \
            and _constituency(q):
        plan = _constituency_winner(q)
        if plan:
            return plan

    # Questions the graph explicitly cannot answer should fall through, not mis-route.
    if _any(ql, "prime minister", "chief minister", "president", "capital of", "weather",
            "spouse", "wife", "husband", "temperature"):
        return None

    # --- Multi-hop (3-5 hops) templates ---
    # Largest party in a state + its most common IPC sections.
    if _state(q) and _any(ql, "section", "ipc") \
            and _any(ql, "most seats", "largest party", "biggest party",
                     "party has the most", "party with the most"):
        return _largest_party_section(q)

    # Party x IPC section x state (checked before the seat-count shape).
    if _state(q) and _section_codes(q) and _any(ql, "party", "mla", "charged", "charge", "case"):
        return _party_section_in_state(q)

    # Party's most common IPC sections (no state in the question).
    if _party(q) and _any(ql, "ipc", "section") and not _state(q) \
            and _any(ql, "most common", "top sections", "charged under", "sections"):
        return _party_sections(q)

    # Party seat counts in a state / election.
    if _state(q) and _any(ql, "which party", "party-wise", "party wise", "each party",
                          "party won", "most seats", "seat count", "party seats") \
            and _any(ql, "mla", "seat", "party") \
            and not _any(ql, "charged", "charge", "criminal", "case"):
        return _party_seats_in_state(q)

    # Average MLA assets for a state / across states.
    if _any(ql, "average", "avg") and _any(ql, "asset", "assets"):
        if _state(q):
            return _state_avg_assets(q)
        if _any(ql, "rank states", "which state", "state-wise", "state wise"):
            return _states_ranked_by_avg_assets(q)

    # States ranked by MLAs with declared cases.
    if _any(ql, "which state", "state-wise", "state wise", "rank states") \
            and _any(ql, "tainted", "criminal", "cases") and _any(ql, "mla", "mlas", "politician"):
        return _state_most_cases(q)

    # MP and MLA counts for one state.
    if _state(q) and _any(ql, "mp", "mps", "member of parliament") and _any(ql, "mla", "mlas"):
        return _mp_mla_counts_by_state(q)

    # Person profile.
    if _any(ql, "who is", "who was", "tell me about", "profile of", "profile", "details",
            "net worth") and _person_name(q):
        return _politician_profile(q)

    # Election roster: state + year + MLAs.
    if _state(q) and _year(q) and _any(ql, "mla", "mlas", "assembly", "member of legislative"):
        return _mla_election_roster(q)

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

    # MP-specific (Member of Parliament) metrics & multi-hop queries.
    is_mp_query = bool(re.search(r"\bmps?\b|\bmembers? of parliament\b", ql)) and "mla" not in ql
    if is_mp_query and _any(ql, "switched part", "switch part", "party switch", "changed part", "change part", "defected", "party hop"):
        return _mp_party_switchers(q)
    if is_mp_query and _any(ql, "affidavit change", "asset change", "assets changed", "wealth change", "wealth grew", "liabilities change"):
        return _mp_affidavit_changes(q)
    if is_mp_query and _any(ql, "ipc", "section"):
        return _mp_ipc_sections(q)

    if is_mp_query and _any(ql, "criminal", "liabilit", "asset", "party", "state"):
        plan = _mp_metric(q)
        if plan:
            return plan

    # Ministers / Ministry portfolios + criminal cases.
    if _any(ql, "minister", "ministry", "ministries", "portfolio", "portfolios") and _any(ql, "criminal", "case", "cases", "charge"):
        return _ministers_with_cases(q)

    if is_mp_query and not _any(ql, "how many", "count", "average", "avg", "percentage"):
        plan = _mp_unified_query(q)
        if plan:
            return plan

    if "minister" in ql and _any(ql, "portfolio", "ministry", "hold"):
        plan = _minister_portfolios(q)
        if plan:
            return plan
    if _any(ql, "minister", "ministry", "defence", "defense", "mod", "mha", "mof", "morth", "railway", "portfolio"):
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

    # State MPs list (e.g., "Show all MPs from Uttar Pradesh and their parties")
    if _state(q) and re.search(r"\bmps?\b|\bmembers? of parliament\b", ql) and not _any(
        ql, "highest", "most", "average", "avg", "richest", "liabilit", "count", "how many", "percentage"
    ):
        plan = _mps_in_state(q)
        if plan:
            return plan

    # General list of MPs/MLAs with declared criminal cases
    if (re.search(r"\b(mps?|mlas?|politicians?)\b", ql)
            and _any(ql, "criminal case", "criminal cases", "criminal record", "declared criminal")
            and not _state(q) and not _party(q) and not _section_codes(q)
            and not _any(ql, "how many", "count", "percentage", "average", "avg", "most", "highest", "zero", "without", "clean")):
        return _politicians_with_criminal_cases(q)

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
    if _any(ql, "top", "richest") and _any(ql, "assets", "richest") and "mla" in ql:
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
