"""25-question hard evaluation for the MHA GraphRAG."""
import json, time, sys
from mha_agent import answer

QUESTIONS = [
    ("What is the mandate of the Ministry of Home Affairs?", ["internal security", "border management", "Centre-State", "Union Territories"]),
    ("Which chapter of the annual report covers border management?", ["Border Management", "Chapter 3"]),
    ("What is the role of the NDRF?", ["NDRF", "disaster", "response"]),
    ("What are the major initiatives and schemes of the Ministry of Home Affairs?", ["scheme", "initiative"]),
    ("What is NATGRID?", ["NATGRID", "intelligence", "database"]),
    ("What is the I4C scheme?", ["I4C", "cyber", "coordination"]),
    ("What does the NIA do?", ["NIA", "investigation", "terror"]),
    ("What is the role of the Registrar General and Census Commissioner of India?", ["census", "registrar", "vital statistics"]),
    ("What does the annual report say about Jammu and Kashmir?", ["Jammu", "Kashmir", "security"]),
    ("What is the Border Area Development Programme (BADP)?", ["BADP", "border", "development"]),
    ("What is the Coastal Security Scheme?", ["coastal", "security", "scheme"]),
    ("Which organisations are under the Ministry of Home Affairs?", ["NIA", "CRPF", "BSF", "CISF", "NHRC", "BPR", "NSG", "Intelligence Bureau"]),
    ("What is the role of the NHRC?", ["NHRC", "human rights", "commission"]),
    ("Which police forces are under the Ministry of Home Affairs?", ["CRPF", "BSF", "CISF", "ITBP", "SSB", "Assam Rifles"]),
    ("What is the role of the BSF?", ["BSF", "border", "Pakistan", "Bangladesh"]),
    ("What is the National Police Mission?", ["police mission", "police reform"]),
    ("What does the report say about police reform?", ["police", "reform", "modernisation"]),
    ("What is the cyber crime portal?", ["cyber crime", "portal", "complaint"]),
    ("What is the Nirbhaya Fund?", ["Nirbhaya", "women", "safety"]),
    ("What does the report say about women's safety?", ["women", "safety", "crime"]),
    ("What is the disaster management framework?", ["disaster", "NDMA", "management"]),
    ("What is the role of the NDMA?", ["NDMA", "disaster", "authority"]),
    ("What does the report say about international cooperation?", ["international", "cooperation", "bilateral"]),
    ("What are the schemes for LWE-affected states?", ["LWE", "scheme", "affected"]),
    ("Which state has the highest number of LWE incidents?", ["LWE", "incidents", "state"]),
]


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    results = []
    for i, (q, kws) in enumerate(QUESTIONS, 1):
        if i < start:
            continue
        ans, hits, gctx = answer(q, k=8)
        low = ans.lower()
        found = [k for k in kws if k.lower() in low]
        ok = len(found) > 0
        results.append({"i": i, "q": q, "ok": ok, "found": found, "answer": ans,
                        "sources": [(h["title"], h["page"]) for h in hits[:3]]})
        print(f"### Q{i}: {q}\nSTATUS: {'PASS' if ok else 'FAIL'}\n{ans}\n", flush=True)
        json.dump(results, open(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\mha_eval_results.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        time.sleep(5)
    passed = sum(1 for r in results if r["ok"])
    print(f"\nRESULT: {passed}/{len(results)} passed ({100*passed/len(results):.1f}%)")
    json.dump(results, open(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\mha_eval_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
