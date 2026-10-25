"""Run a paced, quota-conscious evaluation through the live FastAPI endpoint.

This script never reads the Gemini key. The API reads it server-side. It sends
one unique question per request, records returned token usage, makes no retries,
and stops at the first quota/rate-limit response.
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "hard_research_questions.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "hard_research_eval_results.json"
API_URL = "http://127.0.0.1:8000/api/ask"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-questions", type=int, default=5, help="Hard cap for this run; set explicitly after checking AI Studio quota")
    parser.add_argument("--pause-seconds", type=float, default=4.0, help="Minimum pause between questions to stay gentle on RPM limits")
    parser.add_argument("--start-id", type=int, default=1, help="First bank ID to run")
    args = parser.parse_args()
    if not 1 <= args.max_questions <= 40 or args.pause_seconds < 1:
        raise SystemExit("Use max-questions 1..40 and a pause of at least 1 second.")

    bank = [q for q in QUESTIONS if q["id"] >= args.start_id][:args.max_questions]
    report = {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "endpoint": API_URL,
        "max_questions": args.max_questions,
        "pause_seconds": args.pause_seconds,
        "quota_policy": "No retry; stop immediately after an API quota/rate-limit response; preserve a checkpoint after each question.",
        "results": [],
        "stopped_early": False,
        "stop_reason": None,
    }

    for index, q in enumerate(bank):
        if index:
            time.sleep(args.pause_seconds)
        item = {**q, "http_status": None, "actual_type": None, "neo4j_rows": None, "assessment": "error"}
        payload = json.dumps({"question": q["question"]}).encode("utf-8")
        req = urllib.request.Request(API_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                data = json.loads(response.read().decode("utf-8"))
                item["http_status"] = response.status
                item["gemini_usage_metadata"] = data.get("gemini_usage_metadata", {})
                item["gemini_request_count"] = int(not data.get("plan_cache_hit", False) and bool(item["gemini_usage_metadata"]))
                item["actual_type"] = data.get("result_type")
                item["neo4j_rows"] = data.get("row_count", 0)
                item["plan_cache_hit"] = bool(data.get("plan_cache_hit", False))
                item["explanation"] = str(data.get("explanation", ""))[:350]
                item["cypher"] = data.get("cypher", "")
                if item["actual_type"] == "unsupported":
                    item["assessment"] = "unsupported_as_expected" if not q["expect_supported"] else "unexpectedly_unsupported"
                elif item["actual_type"] != q["expected_type"]:
                    item["assessment"] = "wrong_result_type"
                elif item["actual_type"] == "aggregate":
                    item["assessment"] = "nonempty_result" if data.get("records") else "empty_result"
                    item["result_columns"] = list(data.get("records", [{}])[0].keys()) if data.get("records") else []
                else:
                    item["assessment"] = "nonempty_result" if data.get("nodes") else "empty_result"
                    item["node_count"] = len(data.get("nodes", []))
                    item["edge_count"] = len(data.get("edges", []))
                    item["node_labels"] = sorted({label for node in data.get("nodes", []) for label in node.get("labels", [])})
                    item["relationship_types"] = sorted({edge.get("type", "") for edge in data.get("edges", [])})
        except urllib.error.HTTPError as error:
            try:
                body = json.loads(error.read().decode("utf-8"))
            except Exception:
                body = {}
            item["http_status"] = error.code
            item["error"] = str(body.get("detail", "HTTP error"))[:350]
            item["gemini_request_count"] = int(error.headers.get("X-Gemini-Request", "0"))
            item["gemini_usage_metadata"] = {
                "promptTokenCount": int(error.headers.get("X-Gemini-PromptTokenCount", "0")),
                "candidatesTokenCount": int(error.headers.get("X-Gemini-CandidatesTokenCount", "0")),
                "totalTokenCount": int(error.headers.get("X-Gemini-TotalTokenCount", "0")),
            }
            if error.code == 429 or "quota or rate limit" in item["error"].lower():
                report["stopped_early"] = True
                report["stop_reason"] = "Gemini quota or rate limit reached; the runner did not retry."
        except Exception as error:
            item["error"] = str(error)[:350]
            report["stopped_early"] = True
            report["stop_reason"] = "Local API or transport error; stopped without retry."

        report["results"].append(item)
        report["gemini_requests_recorded"] = sum(row.get("gemini_request_count", 0) for row in report["results"])
        report["gemini_tokens_recorded"] = sum(row.get("gemini_usage_metadata", {}).get("totalTokenCount", 0) for row in report["results"])
        report["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(report['results'])}/{len(bank)}: Q{q['id']} {item['assessment']} (HTTP {item['http_status']})")
        if report["stopped_early"]:
            break

    print(json.dumps({
        "report": OUTPUT.name,
        "questions_attempted": len(report["results"]),
        "gemini_requests_recorded": report.get("gemini_requests_recorded", 0),
        "gemini_tokens_recorded": report.get("gemini_tokens_recorded", 0),
        "stopped_early": report["stopped_early"],
        "stop_reason": report["stop_reason"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
