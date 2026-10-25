import json, time
from evaluate import QUESTIONS
from agent import answer as agent_answer

out = []
for i, (q, kws) in enumerate(QUESTIONS, 1):
    try:
        ans, hits, gctx = agent_answer(q, k=6)
        ok = any(k.lower() in ans.lower() for k in kws)
        out.append((i, q, ok, ans))
        print(f"### Q{i}: {q}\n{ans}\n", flush=True)
    except Exception as e:
        out.append((i, q, False, f"ERROR: {e}"))
        print(f"### Q{i}: {q}\nERROR: {e}\n", flush=True)
    time.sleep(0.7)

with open("C:/Users/aarya/OneDrive/Desktop/Bharat Praman/eval_answers.txt", "w", encoding="utf-8") as f:
    for i, q, ok, ans in out:
        f.write(f"### Q{i}: {q}\nSTATUS: {'PASS' if ok else 'FAIL'}\n{ans}\n\n")
print("SAVED eval_answers.txt")
