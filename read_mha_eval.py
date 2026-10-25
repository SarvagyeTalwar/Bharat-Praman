import json
p = r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\mha_eval_results.json"
d = json.load(open(p, encoding="utf-8"))
print("count:", len(d))
for r in d:
    print(f"Q{r['i']}: {'PASS' if r['ok'] else 'FAIL'} | {r['q']}")
    print("   found:", r['found'])
    print("   answer:", r['answer'][:300].replace("\n", " "))
    print()
