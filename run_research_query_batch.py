"""Generate and safely smoke-test the 100-question research query bank.

One Gemini request plans all questions. Neo4j execution is read-only and
bounded; the JSON report keeps examples and observed results out of the UI's
runtime prompt catalog.
"""

import json
import argparse
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
import os
from neo4j import GraphDatabase, READ_ACCESS


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "BACKEND" / ".env")
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")
QUESTIONS = json.loads((ROOT / "research_questions_100.json").read_text(encoding="utf-8"))

SCHEMA = """Labels and properties:
AssemblyConstituency(name, entity_id); Constituency(name, entity_id);
CriminalCase(case_id, case_no, fir_no, status, court, charges_framed, ipc_sections);
MLA(name, entity_id, age, party_name, myneta_id, criminal_case_count, total_assets,
liabilities, movable_assets, immovable_assets, education, election, election_year,
council_section, source_document_date); Ministry(name, portfolio_type, source_document_date);
Party(name, entity_id); Person(name, first_name, last_name, gender, age, party_name,
profession, terms, nSons, nDaughters, myneta_id, myneta_name, criminal_case_count,
total_assets, liabilities, movable_assets, immovable_assets, education,
council_section, source_document_date, special_responsibilities, aliases, election,
election_year, entity_id); Section(code); State(name, entity_id).
MLAs also have the Person label. Relationships and directions:
Person-[:FACES]->CriminalCase; Person-[:HOLDS_PORTFOLIO {role,source_document,source_date}]->Ministry;
Person-[:MEMBER_OF]->Party; Person-[:REPRESENTS]->AssemblyConstituency or Constituency;
AssemblyConstituency/Constituency-[:IN_STATE]->State; CriminalCase-[:UNDER]->Section.
There is no MP label and no spouse/wife property or relationship. No other labels,
relationships, or properties exist."""


def request_plans(questions):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")
    payload = {
        "systemInstruction": {"parts": [{"text": f"""You are a read-only Neo4j Cypher planner. Use only this exact schema:
{SCHEMA}
For each input, return one JSON array item with id, result_type ('graph', 'aggregate', or 'unsupported'), cypher, parameters, explanation.
Use parameterized values, never interpolate user text. Read-only MATCH only. No procedures, writes, semicolons, or multiple statements. Include literal LIMIT 10 (or less) in every supported query. For graph type, return paths exactly as nodes(p) AS path_nodes, relationships(p) AS path_edges with path variable p. Keep relationship traversal to at most 3 hops. Aggregate type returns only named scalar/group columns and includes LIMIT 10. If any requested field/population is not represented, use unsupported and empty cypher/parameters; specifically MP and wife/spouse are unsupported. Do not imply FACES means guilt. Prefer DISTINCT for counts that can duplicate due to multi-hop joins. Return only minified JSON array, no markdown. Questions are numbered and independent."""}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(questions, ensure_ascii=False, separators=(",", ":"))}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 3000},
    }
    model = urllib.parse.quote(MODEL, safe="")
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.loads(response.read().decode("utf-8"))
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    plans = json.loads(text)
    if not isinstance(plans, list):
        raise ValueError("Gemini response was not a JSON array")
    usage = result.get("usageMetadata", {})
    return {int(p["id"]): p for p in plans}, usage


FORBIDDEN = re.compile(r"\b(?:CREATE|MERGE|SET|REMOVE|DELETE|DETACH|CALL|LOAD|CSV|USE|SHOW|DROP|ALTER|GRANT|REVOKE|DENY|TERMINATE|UNION)\b", re.I)


def validate(plan):
    kind = plan.get("result_type")
    query = plan.get("cypher", "")
    if kind == "unsupported":
        if query:
            raise ValueError("unsupported plan must have empty cypher")
        return ""
    if kind not in {"graph", "aggregate"} or not isinstance(query, str):
        raise ValueError("invalid result_type or cypher")
    query = query.strip()
    if len(query) > 6000 or ";" in query or "//" in query or "/*" in query or "*/" in query:
        raise ValueError("query contains too much or unsupported syntax")
    if not re.match(r"^MATCH\b", query, re.I) or FORBIDDEN.search(query) or not re.search(r"\bRETURN\b", query, re.I):
        raise ValueError("query failed read-only MATCH/RETURN checks")
    if not re.search(r"\bLIMIT\s+(?:[1-9]|10)\b", query, re.I):
        raise ValueError("query must include LIMIT 1..10")
    if kind == "graph" and not (re.search(r"\bAS\s+path_nodes\b", query, re.I) and re.search(r"\bAS\s+path_edges\b", query, re.I)):
        raise ValueError("graph query did not return path nodes and edges")
    if kind == "aggregate" and re.search(r"\b(?:nodes|relationships)\s*\(", query, re.I):
        raise ValueError("aggregate query returned graph payload")
    params = plan.get("parameters", {})
    if not isinstance(params, dict) or len(params) > 20:
        raise ValueError("invalid parameters")
    for key, val in params.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", str(key)) or not isinstance(val, (str, int, float, bool, type(None), list)):
            raise ValueError("invalid parameter value")
    return query


def normalize_plan(question, plan):
    """Normalize minor JSON-shape drift and repair inline-map/path syntax errors."""
    normalized = dict(plan)
    if not normalized.get("result_type"):
        if question.get("topic", "").startswith("unsupported"):
            normalized["result_type"] = "unsupported"
        elif re.search(r"\b(?:avg|average|count|total|min|max|minimum|maximum|rank|compare|comparison|how many|number of)\b", question["question"], re.I) or re.search(r"\b(?:count|avg|min|max|sum)\s*\(", str(normalized.get("cypher", "")), re.I):
            normalized["result_type"] = "aggregate"
        else:
            normalized["result_type"] = "graph"
    if "parameters" not in normalized and isinstance(normalized.get("parameter"), dict):
        normalized["parameters"] = normalized["parameter"]
    # Gemini sometimes places a node property map before a relationship without
    # closing the node pattern, e.g. (p:Party {name:$party}<-[:MEMBER_OF]-...).
    filters = []
    node_map = re.compile(r"\((?P<head>[A-Za-z]\w*(?::[A-Za-z]\w*)*)\s*\{(?P<props>[^{}]+)\}(?P<rel>\s*(?:<-|->|-)\s*\[)")
    def lift_map(match):
        variable = match.group("head").split(":", 1)[0]
        for part in match.group("props").split(","):
            pair = part.split(":", 1)
            if len(pair) == 2 and pair[0].strip().isidentifier():
                filters.append(f"{variable}.{pair[0].strip()} = {pair[1].strip()}")
        return f"({match.group('head')}){match.group('rel')}"
    query = normalized.get("cypher", "")
    if isinstance(query, str):
        query = node_map.sub(lift_map, query)
        if filters:
            condition = " AND ".join(filters)
            where = re.search(r"\bWHERE\b", query, re.I)
            ret = re.search(r"\bRETURN\b", query, re.I)
            if ret:
                if where:
                    query = query[:where.end()] + " (" + condition + ") AND " + query[where.end():]
                else:
                    query = query[:ret.start()] + "WHERE " + condition + " " + query[ret.start():]
        # Close any unbalanced path-node pattern introduced by a malformed
        # inline property map, dropping only unmatched closing parentheses.
        boundary = re.search(r"\bWHERE\b|\bRETURN\b", query, re.I)
        pattern_end = boundary.start() if boundary else len(query)
        prefix, suffix = query[:pattern_end], query[pattern_end:]
        depth = 0
        balanced = []
        for char in prefix:
            if char == "(":
                depth += 1
                balanced.append(char)
            elif char == ")":
                if depth:
                    depth -= 1
                    balanced.append(char)
            else:
                balanced.append(char)
        query = "".join(balanced) + suffix
        normalized["cypher"] = query
    return normalized


def safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return str(value)


def main():
    # Small bounded batches stay below Gemini's per-response output cap. Do not
    # retry a failed request: quota/rate-limit responses should stop the run.
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-checkpoint", action="store_true", help="Re-test saved Gemini plans without making more Gemini requests")
    args = parser.parse_args()
    plans = {}
    batches = []
    usage_total = {}
    if args.execute_checkpoint:
        checkpoint = json.loads((ROOT / "research_query_plans_checkpoint.json").read_text(encoding="utf-8"))
        plans = {int(plan["id"]): plan for plan in checkpoint.get("plans", [])}
        batches = checkpoint.get("batches", [])
        usage_total = checkpoint.get("usage_metadata_total", {})
    else:
        for offset in range(0, len(QUESTIONS), 10):
            batch = QUESTIONS[offset:offset + 10]
            try:
                batch_plans, usage = request_plans(batch)
            except Exception as error:
                batches.append({"first_id": batch[0]["id"], "last_id": batch[-1]["id"], "status": "stopped", "error": str(error)[:350]})
                print(f"Stopped before batch {batch[0]['id']}-{batch[-1]['id']}; saved no retry.")
                break
            plans.update(batch_plans)
            batches.append({"first_id": batch[0]["id"], "last_id": batch[-1]["id"], "status": "ok", "returned_plans": len(batch_plans), "usage": usage})
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    usage_total[key] = usage_total.get(key, 0) + value
            (ROOT / "research_query_plans_checkpoint.json").write_text(
                json.dumps({"model": MODEL, "batches": batches, "usage_metadata_total": usage_total,
                            "plans": [{"id": qid, **plan} for qid, plan in sorted(plans.items())]},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Gemini planned {len(plans)}/{len(QUESTIONS)} questions in {len(batches)} batches")
    by_id = {q["id"]: q for q in QUESTIONS}
    previous = {}
    if args.execute_checkpoint and (ROOT / "research_query_results_100.json").exists():
        old_report = json.loads((ROOT / "research_query_results_100.json").read_text(encoding="utf-8"))
        previous = {item["id"]: item for item in old_report.get("results", [])}
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": MODEL,
        "gemini_api_requests": sum(batch.get("status") == "ok" for batch in batches) + sum(batch.get("status") == "stopped" for batch in batches),
        "gemini_usage_metadata_total": usage_total,
        "gemini_batches": batches,
        "schema_note": "Graph contains MLA, Person, Party, CriminalCase, Section, Ministry, constituency, State; no MP label or spouse/wife field/relation.",
        "results": [],
    }
    settings = [os.getenv(k) for k in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")]
    if not all(settings):
        raise RuntimeError("Neo4j settings are missing from .env")
    driver = GraphDatabase.driver(settings[0], auth=(settings[1], settings[2]))
    try:
        for qid in sorted(by_id):
            question = by_id[qid]
            prior = previous.get(qid)
            if prior and prior.get("neo4j_status") in {"ok", "not_run_unsupported"}:
                report["results"].append(prior)
                continue
            item = {**question, "gemini_status": "missing_plan"}
            plan = plans.get(qid)
            if plan is None:
                report["results"].append(item)
                continue
            plan = normalize_plan(question, plan)
            item["result_type"] = plan.get("result_type")
            item["explanation"] = str(plan.get("explanation", ""))[:300]
            try:
                query = validate(plan)
                item["cypher"] = query
                item["parameters"] = plan.get("parameters", {})
                item["gemini_status"] = "planned"
                if not query:
                    item["neo4j_status"] = "not_run_unsupported"
                    report["results"].append(item)
                    continue
                started = time.monotonic()
                with driver.session(database=os.getenv("NEO4J_DATABASE") or None, default_access_mode=READ_ACCESS) as session:
                    rows = session.execute_read(lambda tx: [dict(row) for row in tx.run(query, plan.get("parameters", {}), timeout=8)])
                elapsed = round((time.monotonic() - started) * 1000)
                item["neo4j_status"] = "ok"
                item["row_count"] = len(rows)
                item["elapsed_ms"] = elapsed
                if plan.get("result_type") == "aggregate":
                    item["sample_rows"] = safe(rows[:5])
                else:
                    node_ids, edge_types = set(), set()
                    for row in rows:
                        node_ids.update(getattr(node, "element_id", str(node)) for node in row.get("path_nodes", []) if not isinstance(node, (str, bytes)))
                        edge_types.update(getattr(edge, "type", "?") for edge in row.get("path_edges", []))
                    item["distinct_nodes_in_samples"] = len(node_ids)
                    item["relationship_types_in_samples"] = sorted(edge_types)
            except Exception as error:
                item["neo4j_status"] = "skipped_or_error"
                item["error"] = str(error)[:350]
            report["results"].append(item)
            if qid % 10 == 0:
                print(f"Processed {qid}/100")
    finally:
        driver.close()
    output = ROOT / "research_query_results_100.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for row in report["results"]:
        key = row.get("neo4j_status", row.get("gemini_status", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps({"report": output.name, "questions": len(report["results"]), "results": counts, "gemini_api_requests": report["gemini_api_requests"], "gemini_usage_metadata_total": usage_total}, ensure_ascii=False))


if __name__ == "__main__":
    main()
