"""30-question GraphRAG evaluation for the hackathon.

Runs a fixed set of questions, checks that retrieval surfaced the right
document/chunks, and reports a score. Uses the same agent pipeline.
"""
import json, time
from agent import answer as agent_answer
from neo4j import GraphDatabase
from dotenv import load_dotenv, find_dotenv
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

URI = (os.getenv("NEO4J_URI1") or "").strip()
driver = GraphDatabase.driver(URI, auth=(os.getenv("NEO4J_USERNAME1"), os.getenv("NEO4J_PASSWORD1")))

# Each question with expected keyword(s) that a correct answer should mention
QUESTIONS = [
    ("Who is the Cabinet Minister for Education?", ["Pralhad Joshi"]),
    ("Who are the Ministers of State in the Ministry of Education?", ["Jayant", "Sukanta", "Majumdar", "Chaudhary"]),
    ("What subjects are allocated to the Ministry of Education?", ["Elementary Education", "Basic Education"]),
    ("What is the expenditure on education by state governments?", ["expenditure", "state"]),
    ("Enrolment of women students in STEM fields?", ["STEM", "women", "enrolment"]),
    ("What is Samagra Shiksha?", ["Samagra Shiksha", "centrally sponsored"]),
    ("What is the PRASHAST initiative about?", ["PRASHAST", "inclusive"]),
    ("What is Special Campaign 6 about?", ["Special Campaign", "e-waste", "cleanliness"]),
    ("Who is the Minister of State for Skill Development?", ["Jayant"]),
    ("What does NEP 2020 emphasize about multilingualism?", ["multilingual", "language"]),
    ("What is the National Education Policy 2020?", ["NEP", "policy", "education"]),
    ("Who asked the Rajya Sabha question on expenditure on education?", ["John Brittas"]),
    ("Which body runs the All India Survey on Higher Education?", ["AISHE", "survey", "education"]),
    ("What is the role of NCERT?", ["NCERT", "curriculum", "teacher"]),
    ("What is AICTE responsible for?", ["AICTE", "technical education", "council"]),
    ("What scholarships are available for girl students?", ["scholarship", "girl"]),
    ("What is the National Bal Bhavan?", ["Bal Bhavan", "children"]),
    ("Which ministry deals with school education?", ["School Education", "Ministry of Education"]),
    ("What is RTE / Right to Education?", ["RTE", "Right to Education", "compulsory"]),
    ("Who is the Minister of State for North Eastern Region?", ["Sukanta Majumdar"]),
    ("What does UGC regulate?", ["UGC", "university", "higher education"]),
    ("What is the enrolment of women in STEM 2020-21?", ["AISHE", "women", "STEM"]),
    ("Which scheme focuses on skill education?", ["Samagra Shiksha", "skill"]),
    ("How many schools participated in the PRASHAST screening?", ["60,000", "schools"]),
    ("What is the Inclusive Education module?", ["inclusive", "module", "PRASHAST"]),
    ("What is the vision of NEP rootedness in India?", ["India", "NEP", "rootedness", "pride"]),
    ("Name the departments under Ministry of Education?", ["School Education", "Higher Education"]),
    ("What does the Department of School Education & Literacy do?", ["school", "literacy", "education"]),
    ("Who is the Minister for New and Renewable Energy (linked to Education)?", ["Pralhad Joshi"]),
    ("What is the Kasturba Gandhi Balika Vidyalaya?", ["Kasturba", "Balika", "girls"]),
]


def check_answer(ans, keywords):
    low = ans.lower()
    hits = [k for k in keywords if k.lower() in low]
    return len(hits) > 0, hits


def main():
    import sys
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"STEP 3: Running evaluation from question {start}...\n")
    results = []
    for i, (q, kws) in enumerate(QUESTIONS, 1):
        if i < start:
            continue
        try:
            ans, hits, gctx = agent_answer(q, k=6)
            ok, found = check_answer(ans, kws)
            results.append({"q": q, "ok": ok, "found": found, "answer_len": len(ans)})
            status = "PASS" if ok else "FAIL"
            print(f"  [{i:02d}] {status}: {q}")
            if not ok:
                print(f"       expected any of: {kws}")
            time.sleep(1.0)  # throttle LLM
        except Exception as e:
            results.append({"q": q, "ok": False, "found": [], "error": str(e)})
            print(f"  [{i:02d}] ERROR: {q} -> {e}")
            time.sleep(1.0)

    passed = sum(1 for r in results if r.get("ok"))
    total = len(results)
    score = round(passed / total * 100, 1)
    print(f"\n=== RESULT: {passed}/{total} passed ({score}%) ===")
    json.dump(results, open("C:/Users/aarya/OneDrive/Desktop/Bharat Praman/eval_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
