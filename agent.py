"""GraphRAG agent wrapper for Ministry of Education annual reports.

Delegates to the unified multi-ministry `reports_agent` engine (1024-dim Qwen3
embeddings + Neo4j hybrid RRF + DeepSeek/Gemini structured synthesis).
"""
import argparse
from reports_agent import answer_reports, stratified_hybrid_search


def hybrid_search(question, k=6):
    return stratified_hybrid_search(question, ministries=["Education"], top_k=k)


def answer(question, k=8):
    return answer_reports(question, ministry=["Education"], top_k=k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()
    q = " ".join(args.question)
    ans, hits, gctx = answer(q, args.k)
    print(ans)
    if gctx:
        print("\nGraph context:\n" + gctx)
    print(f"\nSources ({len(hits)}):")
    for h in hits:
        print(f"  - {h.get('title')} ({h.get('year')}) | p.{h.get('page')} (score {h.get('score', 0):.3f})")


if __name__ == "__main__":
    main()
