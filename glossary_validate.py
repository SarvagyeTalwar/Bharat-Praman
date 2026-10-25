"""Validate/clean extracted acronym glossaries with Gemini.

Inputs:  glossary_mha.json, glossary_moe.json
Outputs: glossary_mha_validated.json, glossary_moe_validated.json,
         glossary_validated.json, glossary_discarded.json
"""
import os, re, json, time
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv('BACKEND/.env')
KEY = os.getenv('GEMINI_API_KEY1') or os.getenv('GEMINI_API_KEY')
MODEL = os.getenv('LLM_MODEL', 'gemini-3.5-flash-lite')
OUT = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")
TOP_N = 300          # per ministry
BATCH = 40

client = genai.Client(api_key=KEY)

PROMPT = """You are cleaning an acronym glossary extracted from Indian government documents.
For each entry, decide the correct expansion. Remove junk/false positives
(e.g. "IT -> M.Sc", "UP -> Ghaziabad", "GD -> CAPFs and Rifleman").
Fix truncations (e.g. "AIIMS -> Institute of Medical Sciences" -> "All India Institute of Medical Sciences").
Return a STRICT JSON array, one object per input entry:
{{"acronym":"...", "expansion":"... or null", "confidence":"high|medium|low",
  "category":"ministry|scheme|organisation|rank|policy|place|other", "aliases":["..."]}}
If the entry is not a real acronym/expansion pair, set expansion to null and confidence to "low".
Output ONLY the JSON array.

ENTRIES:
{entries}
"""


def clean_json(txt):
    txt = re.sub(r'^```(?:json)?\s*|\s*```$', '', txt.strip())
    return json.loads(txt)


def validate(items):
    """items: list of (acronym, expansion, count). Returns validated + discarded."""
    validated, discarded = {}, {}
    for i in range(0, len(items), BATCH):
        batch = items[i:i + BATCH]
        entries = "\n".join(f"- {a} => {e} (seen {c}x)" for a, e, c in batch)
        for attempt in range(5):
            try:
                r = client.models.generate_content(model=MODEL, contents=PROMPT.format(entries=entries))
                data = clean_json(r.text)
                for obj in data:
                    acr = str(obj.get("acronym", "")).strip()
                    exp = obj.get("expansion")
                    if not acr:
                        continue
                    if exp:
                        validated[acr] = {
                            "expansion": str(exp).strip(),
                            "confidence": obj.get("confidence", "medium"),
                            "category": obj.get("category", "other"),
                            "aliases": obj.get("aliases", []),
                        }
                    else:
                        discarded[acr] = {"candidate": next((e for a, e, c in batch if a == acr), ""),
                                          "reason": "llm_rejected"}
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    print("  rate limited, waiting 65s")
                    time.sleep(65)
                else:
                    print("  error:", msg[:200])
                    break
        time.sleep(5)
        print(f"  validated {min(i+BATCH, len(items))}/{len(items)}")
    return validated, discarded


def main():
    mha = json.loads((OUT / "glossary_mha.json").read_text(encoding="utf-8"))
    moe = json.loads((OUT / "glossary_moe.json").read_text(encoding="utf-8"))

    def top(g):
        items = sorted(g.items(), key=lambda kv: -kv[1]["count"])[:TOP_N]
        return [(k, v["expansion"], v["count"]) for k, v in items]

    print(f"Validating top {TOP_N} MHA + {TOP_N} MoE acronyms...")
    print("MHA:")
    v_mha, d_mha = validate(top(mha))
    print("MoE:")
    v_moe, d_moe = validate(top(moe))

    # keep counts from source
    for g, v in ((mha, v_mha), (moe, v_moe)):
        for acr, obj in v.items():
            obj["count"] = g.get(acr, {}).get("count", 0)

    combined = {}
    for acr, obj in {**v_mha, **v_moe}.items():
        combined[acr] = obj

    (OUT / "glossary_mha_validated.json").write_text(json.dumps(v_mha, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "glossary_moe_validated.json").write_text(json.dumps(v_moe, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "glossary_validated.json").write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "glossary_discarded.json").write_text(json.dumps({**d_mha, **d_moe}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nValidated: MHA={len(v_mha)} MoE={len(v_moe)} combined={len(combined)} discarded={len(d_mha)+len(d_moe)}")
    print("\nSample MHA:")
    for k, v in list(v_mha.items())[:15]:
        print(f"  {k}: {v['expansion']} ({v['confidence']}, {v['category']}, {v['count']})")
    print("\nSample MoE:")
    for k, v in list(v_moe.items())[:15]:
        print(f"  {k}: {v['expansion']} ({v['confidence']}, {v['category']}, {v['count']})")


if __name__ == "__main__":
    main()
