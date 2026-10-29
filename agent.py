"""GraphRAG agent over the Ministry of Education knowledge graph.

Retrieval = unified Neo4j vector index + full-text index (hybrid), then
graph expansion to the owning Ministry and its Ministers.

Usage:
    python agent.py "What subjects are allocated to the Ministry of Education?"
    python agent.py "Who are the ministers in the Ministry of Education?"
    python agent.py --k 8 "Tell me about scholarships"
"""
import argparse, json, math, re, os
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
from google import genai

from glossary import expand_query, annotate_answer

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

VECTOR_INDEX = "chunk_embeddings_local"
FULLTEXT_INDEX = "chunk_text_fulltext"
LOCAL_VOCAB_PATH = Path(os.getenv("MOE_VOCAB_PATH", str(HERE / "data" / "moe_vocab.json")))
_LOCAL_VOCAB = None

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), max_transaction_retry_time=120)
gemini = genai.Client(api_key=GEMINI_API_KEY)


def tokenize(t):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", t.lower())


def _local_query_vector(text):
    global _LOCAL_VOCAB
    if _LOCAL_VOCAB is None:
        data = json.loads(LOCAL_VOCAB_PATH.read_text(encoding="utf-8"))
        _LOCAL_VOCAB = (data["vocab"], data["idf"])
    vocab, idf = _LOCAL_VOCAB
    v = [0.0] * len(vocab)
    for tok, count in Counter(tokenize(text)).items():
        idx = vocab.get(tok)
        if idx is not None and idx < len(idf):
            v[idx] = count * idf[idx]
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def vector_search(question, k):
    qv = _local_query_vector(question)
    with driver.session() as s:
        return s.run(
            "CALL db.index.vector.queryNodes($idx, $k, $v) YIELD node, score "
            "MATCH (d:Document)-[:HAS_CHUNK]->(node) "
            "WHERE node.page > 5 AND size(node.text) > 150 "
            "RETURN node.id AS id, d.file AS file, d.title AS title, node.page AS page, node.text AS text, score "
            "ORDER BY score DESC",
            idx=VECTOR_INDEX, k=k, v=qv,
        ).data()


def fulltext_search(question, k):
    q = " ".join(tokenize(question))
    if not q:
        return []
    with driver.session() as s:
        return s.run(
            "CALL db.index.fulltext.queryNodes($idx, $q) YIELD node, score "
            "MATCH (d:Document)-[:HAS_CHUNK]->(node) "
            "WHERE node.page > 5 AND size(node.text) > 150 "
            "RETURN node.id AS id, d.file AS file, d.title AS title, node.page AS page, node.text AS text, score "
            "ORDER BY score DESC LIMIT $k",
            idx=FULLTEXT_INDEX, q=q, k=k,
        ).data()


def hybrid_search(question, k=5):
    pool = max(k * 4, 20)
    ft = fulltext_search(question, pool)
    vec = vector_search(question, pool)
    out, seen = [], set()
    for r in ft + vec:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
        if len(out) >= k:
            break
    return out


def graph_context(files):
    """For each retrieved document, fetch its ministry and ministers."""
    if not files:
        return ""
    with driver.session() as s:
        rows = s.run(
            """
            MATCH (d:Document)-[:ABOUT_MINISTRY]->(m:Ministry)
            WHERE d.file IN $files
            OPTIONAL MATCH (p:Person)-[:HOLDS]->(m)
            OPTIONAL MATCH (p)-[:HAS_RANK]->(r:Rank)
            RETURN d.file AS file, d.title AS title, d.doc_type AS doc_type, d.year AS year,
                   m.fullName AS ministry, m.name AS ministry_name,
                   collect(DISTINCT {name: p.name, rank: r.name, level: r.level}) AS ministers
            """,
            files=files,
        ).data()
    lines = []
    for r in rows:
        mins = ", ".join(
            f"{x['name']} ({x['rank']})" for x in r["ministers"] if x.get("name")
        )
        lines.append(
            f"- Document: {r['title'] or r['file']} | type: {r['doc_type'] or 'document'} | year: {r['year'] or 'n/a'}\n"
            f"  Ministry: {r['ministry'] or r['ministry_name']}\n"
            f"  Ministers: {mins or 'unknown'}"
        )
    return "\n".join(lines)


def build_prompt(question, hits, gctx, glossary_note=""):
    ctx = []
    for i, h in enumerate(hits, 1):
        ctx.append(f"[Source {i} | {h['title']} | page {h['page']}]\n{h['text']}")
    context = "\n\n---\n\n".join(ctx)
    return f"""You are a GraphRAG assistant for the Government of India, specialised in the Ministry of Education.

Use the GRAPH CONTEXT and the PASSAGES below. Prefer the graph context for questions about
ministers, portfolios and ministry structure. Use passages for document facts. Cite pages like [page 42].
If the answer is not supported by the context, say you don't know.

GRAPH CONTEXT:
{gctx or '(no linked ministry found)'}

GLOSSARY (acronyms in the question):
{glossary_note or '(none)'}

PASSAGES:
{context}

QUESTION:
{question}

ANSWER:"""


def answer(question, k=5):
    expanded_q, gmatches = expand_query(question, "Education")
    hits = hybrid_search(expanded_q, k)
    if not hits:
        return "No relevant chunks found. Has the document been ingested?", hits, ""
    files = list({h["file"] for h in hits})
    gctx = graph_context(files)
    glossary_note = "; ".join(f"{m['acronym']} = {m['expansion']}" for m in gmatches)
    prompt = build_prompt(question, hits, gctx, glossary_note)
    r = gemini.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    ans, _ = annotate_answer(r.text, "Education")
    return ans, hits, gctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()
    question = " ".join(args.question)
    print(f"\nQuestion: {question}\n")
    ans, hits, gctx = answer(question, args.k)
    print("Answer:\n" + ans + "\n")
    if gctx:
        print("Graph context:")
        print(gctx + "\n")
    print("Retrieved sources:")
    for h in hits:
        print(f"  - {h['title']} | page {h['page']} (score {h['score']:.2f})")


if __name__ == "__main__":
    main()
