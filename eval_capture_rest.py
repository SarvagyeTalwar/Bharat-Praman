import json, time, sys
from evaluate import QUESTIONS
from agent import answer as agent_answer

start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
end = int(sys.argv[2]) if len(sys.argv) > 2 else len(QUESTIONS)

out = []
for i, (q, kws) in enumerate(QUESTIONS, 1):
    if i < start or i > end:
        continue
    ans = ""
    for attempt in range(4):
        try:
            ans, hits, gctx = agent_answer(q, k=6)
            break
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = 65
                print(f"### Q{i}: rate limited, waiting {wait}s", flush=True)
                time.sleep(wait)
            else:
                ans = f"ERROR: {e}"
                break
    ok = any(k.lower() in ans.lower() for k in kws)
    out.append((i, q, ok, ans))
    print(f"### Q{i}: {q}\nSTATUS: {'PASS' if ok else 'FAIL'}\n{ans}\n", flush=True)
    time.sleep(5)  # 12 requests/min, safely under the 15/min free-tier limit

with open(f"C:/Users/aarya/OneDrive/Desktop/Bharat Praman/eval_answers_{start}_{end}.txt", "w", encoding="utf-8") as f:
    for i, q, ok, ans in out:
        f.write(f"### Q{i}: {q}\nSTATUS: {'PASS' if ok else 'FAIL'}\n{ans}\n\n")
print("SAVED")
