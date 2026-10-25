from mha_agent import answer as mha_answer
from agent import answer as moe_answer

print("=== MHA ===")
a, h, g = mha_answer("What does MHA do about LWE?", 5)
print(a[:700])
print("SOURCES:", [(x["title"], x["page"]) for x in h[:3]])

print("\n=== MoE ===")
a, h, g = moe_answer("What is GER under NEP?", 5)
print(a[:700])
print("SOURCES:", [(x["title"], x["page"]) for x in h[:3]])
