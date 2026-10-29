"""Add ministry tags to the validated glossaries and rebuild the merged file."""
import json
from pathlib import Path

OUT = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")
mha = json.loads((OUT / "glossary_mha_validated.json").read_text(encoding="utf-8"))
moe = json.loads((OUT / "glossary_moe_validated.json").read_text(encoding="utf-8"))

for acr, v in mha.items():
    v["ministry"] = "Home Affairs"
    v["ministries"] = ["Home Affairs"]

for acr, v in moe.items():
    v["ministry"] = "Education"
    v["ministries"] = ["Education"]

# Merge; if an acronym exists in both, keep the higher-count expansion and list both ministries.
combined = {}
for acr, v in mha.items():
    combined[acr] = dict(v)
for acr, v in moe.items():
    if acr in combined:
        existing = combined[acr]
        # keep the expansion with the higher count, but remember both ministries
        if v.get("count", 0) > existing.get("count", 0):
            existing["expansion"] = v["expansion"]
            existing["category"] = v.get("category", existing.get("category"))
        existing["ministries"] = sorted(set(existing.get("ministries", []) + ["Education"]))
        existing["ministry"] = " / ".join(existing["ministries"])
        existing["count"] = max(existing.get("count", 0), v.get("count", 0))
    else:
        combined[acr] = dict(v)

(OUT / "glossary_mha_validated.json").write_text(json.dumps(mha, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "glossary_moe_validated.json").write_text(json.dumps(moe, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "glossary_validated.json").write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")

from collections import Counter
print("tagged MHA:", len(mha), "MoE:", len(moe), "combined:", len(combined))
print("ministry counts:", Counter(v.get("ministry") for v in combined.values()))
print("sample:", {k: combined[k] for k in list(combined)[:3]})
