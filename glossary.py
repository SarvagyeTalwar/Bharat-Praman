"""Glossary runtime: load validated acronyms, expand queries, annotate answers.

The glossary is JSON (not Neo4j) and is scoped by ministry.
"""
import json, re
from pathlib import Path

BASE = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project")
VALIDATED = BASE / "glossary_validated.json"
OVERRIDES = BASE / "glossary_overrides.json"

# Short/ambiguous tokens we do not auto-expand in free text (still shown in the UI).
STOP = {"IT", "UP", "AI", "SC", "ST", "PG", "UG", "GD", "CAP", "NE", "PDS",
        "PET", "SNA", "HPC", "PLA", "SDG", "UAE", "IIM", "IIT", "NIT", "BPL",
        "GEN", "OBC", "EWS", "M.Sc", "B.Sc", "M.A", "B.A", "PH.D"}

MINISTRY_ALIASES = {
    "home affairs": "Home Affairs",
    "mha": "Home Affairs",
    "internal affairs": "Home Affairs",
    "education": "Education",
    "moe": "Education",
    "ministry of education": "Education",
}


def _norm_ministry(m):
    if not m:
        return None
    return MINISTRY_ALIASES.get(m.strip().lower(), m.strip())


def load(ministry=None):
    data = {}
    if VALIDATED.exists():
        data = json.loads(VALIDATED.read_text(encoding="utf-8"))
    if OVERRIDES.exists():
        data.update(json.loads(OVERRIDES.read_text(encoding="utf-8")))
    if ministry:
        want = _norm_ministry(ministry).lower()
        data = {k: v for k, v in data.items()
                if not v.get("ministry") or v.get("ministry", "").lower() == want
                or want in v.get("ministry", "").lower()}
    return data


def lookup(acronym, ministry=None):
    data = load(ministry)
    return data.get(acronym)


def search(q, ministry=None, limit=100):
    data = load(ministry)
    q = (q or "").strip().lower()
    rows = []
    for acr, v in data.items():
        exp = v.get("expansion", "")
        if not q or q in acr.lower() or q in exp.lower():
            rows.append({"acronym": acr, **v})
    rows.sort(key=lambda r: (-r.get("count", 0), r["acronym"]))
    return rows[:limit]


def _tokens(text):
    return re.findall(r"\b[A-Z][A-Z0-9&]{1,9}\b", text)


def expand_query(text, ministry=None):
    """Append expansions for known acronyms in the query."""
    data = load(ministry)
    found, seen = [], set()
    for tok in _tokens(text):
        if tok in seen or tok in STOP:
            continue
        v = data.get(tok)
        if v and v.get("confidence") in ("high", "medium"):
            seen.add(tok)
            found.append({"acronym": tok, "expansion": v["expansion"]})
    if not found:
        return text, []
    suffix = "; ".join(f"{f['acronym']} = {f['expansion']}" for f in found)
    return f"{text}\n(Expand acronyms: {suffix})", found


def annotate_answer(text, ministry=None):
    """Annotate the first occurrence of known acronyms with their expansion."""
    data = load(ministry)
    if not text:
        return text, []
    found, seen = [], set()
    out = text
    for tok in _tokens(text):
        if tok in seen or tok in STOP:
            continue
        v = data.get(tok)
        if not v or v.get("confidence") not in ("high", "medium"):
            continue
        seen.add(tok)
        exp = v["expansion"]
        # skip if the text already contains "Expansion (ACR)" or "ACR (Expansion)"
        already = re.search(rf"{re.escape(exp)}\s*\(\s*{re.escape(tok)}\s*\)", out, re.I) or \
                  re.search(rf"{re.escape(tok)}\s*\(\s*{re.escape(exp)}\s*\)", out, re.I)
        if already:
            continue
        # avoid annotating if the acronym is immediately followed by "("
        pat = re.compile(rf"\b{re.escape(tok)}\b(?!\s*\()")
        if pat.search(out):
            out = pat.sub(f"{tok} ({exp})", out, count=1)
            found.append({"acronym": tok, "expansion": exp})
    return out, found


if __name__ == "__main__":
    print("loaded:", len(load()), "acronyms")
    for q in ["What does MHA do about LWE?", "What is GER under NEP?", "Explain CCTNS"]:
        print("\nQ:", q)
        print("expanded:", expand_query(q)[0])
    ans = "MHA coordinates LWE policy with CAPFs and NDRF."
    print("\nannotated:", annotate_answer(ans)[0])
