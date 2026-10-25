"""Agentic RAG over the MoE document stored in Neo4j.

Usage:
    python agent.py "What subjects are allocated to the Ministry of Education?"
    python agent.py --k 8 "Tell me about scholarships"
"""
import argparse, json, math, re, os
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
from google import genai

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

VOCAB_PATH = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project\moe24-25_vocab_local.json")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), max_transaction_retry_time=120)
gemini = genai.Client(api_key=GEMINI_API_KEY)


def tokenize(t):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", t.lower())


class LocalEmbedder:
    def __init__(self):
        v = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
        self.vocab = v["vocab"]
        self.idf = v["idf"]

    def vec(self, text):
        x = [0.0] * len(self.vocab)
        tf = Counter(tokenize(text))
        for tok, c in tf.items():
            if tok in self.vocab:
                x[self.vocab[tok]] = c * self.idf[self.vocab[tok]]
        n = math.sqrt(sum(a * a for a in x)) or 1.0
        return [a / n for a in x]


embedder = LocalEmbedder()


def retrieve(question, k=5):
    qv = embedder.vec(question)
    with driver.session() as s:
        rows = s.run(
            "CALL db.index.vector.queryNodes('moe_chunk_embeddings_local', $k, $v) "
            "YIELD node, score "
            "MATCH (d:MoELocalDoc)-[:HAS_CHUNK]->(node) "
            "RETURN d.file AS file, node.page AS page, node.text AS text, score "
            "ORDER BY score DESC",
            k=k, v=qv,
        ).data()
    return rows


def build_prompt(question, hits):
    ctx = []
    for i, h in enumerate(hits, 1):
        ctx.append(f"[Source {i} | page {h['page']} | score {h['score']:.3f}]\n{h['text']}")
    context = "\n\n---\n\n".join(ctx)
    return f"""You are an assistant answering questions about the Ministry of Education (MoE) 2024-25 document.

Use ONLY the provided context. If the answer is not in the context, say you don't know.
Cite sources by their page numbers in brackets like [page 42]. Be concise and factual.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def answer(question, k=5):
    hits = retrieve(question, k)
    if not hits:
        return "No relevant chunks found. Has the document been ingested?", hits
    prompt = build_prompt(question, hits)
    r = gemini.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return r.text, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()
    question = " ".join(args.question)
    print(f"\nQuestion: {question}\n")
    ans, hits = answer(question, args.k)
    print("Answer:\n" + ans + "\n")
    print("Retrieved sources:")
    for h in hits:
        print(f"  - page {h['page']} (score {h['score']:.3f})")


if __name__ == "__main__":
    main()
