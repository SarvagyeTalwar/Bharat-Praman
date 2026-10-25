import json, time
from mha_agent import answer

QS = [
    (12, "Which organisations are under the Ministry of Home Affairs?", ["NIA", "CRPF", "BSF", "NHRC", "BPR", "Central Reserve", "Border Security", "Investigation Agency"]),
    (14, "Which police forces are under the Ministry of Home Affairs?", ["CRPF", "BSF", "CISF", "ITBP", "SSB", "Central Reserve", "Border Security", "Indo-Tibetan", "Sashastra Seema"]),
    (22, "What is the role of the NDMA?", ["NDMA", "disaster", "authority", "management"]),
    (23, "What does the report say about international cooperation?", ["international", "cooperation", "bilateral", "security"]),
    (24, "What are the schemes for LWE-affected states?", ["LWE", "scheme", "affected", "security"]),
    (25, "Which state has the highest number of LWE incidents?", ["LWE", "incident", "state", "highest"]),
]

out = []
for i, q, kws in QS:
    ans, hits, gctx = answer(q, k=8)
    low = ans.lower()
    found = [k for k in kws if k.lower() in low]
    ok = len(found) > 0
    out.append({"i": i, "q": q, "ok": ok, "found": found,
                "answer": ans, "sources": [(h["title"], h["page"]) for h in hits[:4]]})
    print(f"### Q{i}: {q}\nSTATUS: {'PASS' if ok else 'FAIL'}\n{ans}\n", flush=True)
    with open(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\mha_eval_rest.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    time.sleep(5)
print("DONE")
