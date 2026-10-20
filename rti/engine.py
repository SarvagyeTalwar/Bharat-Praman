"""RTI draft engine: pure functions, no web or database code."""
import json
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


TOPICS = {t["topic_id"]: t for t in _load("topics.json")}
AUTHORITIES = _load("authorities.json")
TEMPLATES = _load("templates.json")
BANK = _load("question_bank.json")

# Set to True once a person has checked every question in question_bank.json.
ONLY_REVIEWED = False
MIN_SCORE = 60
STOPWORDS = set("a an the is are was were of to in on for and or me my i he she his her him they their it its "
                "how many much what which who whom when where why did does do has have had can could will would "
                "please give show list tell about with from by this that these those any all get".split())

# VERIFY against an official source before relying on this default.
DEFAULT_TERM_START = {"LOK_SABHA": "2024-06-04"}
USER_FIELDS = ["applicant_name", "applicant_address", "applicant_contact"]
HOUSE_NAME = {"LOK_SABHA": "Lok Sabha", "RAJYA_SABHA": "Rajya Sabha", "VIDHAN_SABHA": "Vidhan Sabha"}
MEMBER_TITLE = {
    "LOK_SABHA": "Member of Parliament (Lok Sabha)",
    "RAJYA_SABHA": "Member of Parliament (Rajya Sabha)",
    "VIDHAN_SABHA": "Member of the Legislative Assembly",
}

BODY = """To,
The Public Information Officer,
{authority_name}
{pio_address}

Subject: Request for information under the RTI Act, 2005: {subject}

Sir/Madam,

Under Section 6(1) of the Right to Information Act, 2005, I request the following information for the period {term_start} to {today}:

{questions}

{fee_line}
If any part of this information is held by another public authority, please transfer this application to it under Section 6(3) of the Act. If any information is refused, please cite the specific provision relied on and give the particulars of the first appellate authority.

Yours faithfully,
{applicant_name}
{applicant_address}
{applicant_contact}
Date: {today}
"""

FIELD_KEYS = {
    "name": ["name", "myneta_name", "full_name"],
    "constituency": ["constituency", "current_constituency"],
    "state": ["state"],
    "district": ["district"],
    "house": ["house", "chamber"],
    "term_start": ["term_start", "term_start_date"],
    "term_end": ["term_end", "term_end_date"],
    "party": ["party"],
}


class RtiError(Exception):
    pass


class _Keep(dict):
    """Leave unknown {placeholders} as they are."""
    def __missing__(self, key):
        return "{" + key + "}"


def _pick(props, keys):
    for k in keys:
        v = props.get(k)
        if v not in (None, ""):
            return v
    return None


def _date(v):
    return str(v)[:10] if v else None


def _house(value, constituency, labels=(), entity_id=""):
    """House comes from the REPRESENTS link first, then a stored value, then guesses."""
    if "Constituency" in labels:
        return "LOK_SABHA", False
    if "AssemblyConstituency" in labels:
        return "VIDHAN_SABHA", False
    if str(entity_id).startswith("mla_"):
        return "VIDHAN_SABHA", False
    if value:
        v = str(value).lower()
        if "lok" in v:
            return "LOK_SABHA", False
        if "rajya" in v:
            return "RAJYA_SABHA", False
        if "vidhan" in v or "assembly" in v or "mla" in v:
            return "VIDHAN_SABHA", False
    if constituency:
        return "LOK_SABHA", True  # guess: has a constituency but no house stored
    return None, False


def normalize_person(entity_id, props, cons_labels=None, cons_props=None):
    """Turn raw database records (person + the constituency node it REPRESENTS) into the RTI fields."""
    cons_labels, cons_props = cons_labels or [], cons_props or {}
    merged = dict(props)
    for k in ("state", "district"):
        if cons_props.get(k) not in (None, ""):
            merged[k] = cons_props[k]
    cname = _pick(cons_props, ["name", "constituency_name", "cons_name", "constituency"])
    if cname:
        merged["constituency"] = cname
    p = {k: _pick(merged, keys) for k, keys in FIELD_KEYS.items()}
    house, assumed = _house(p["house"], p["constituency"], cons_labels, entity_id)
    return {
        "id": str(entity_id), "name": p["name"], "house": house, "house_assumed": assumed,
        "state": p["state"], "constituency": p["constituency"], "district": p["district"],
        "term_start": _date(p["term_start"]), "term_end": _date(p["term_end"]),
        "party": p["party"] or props.get("party_name"),
    }


def fmt_date(iso):
    try:
        d = date.fromisoformat(iso)
        return "{} {}".format(d.day, d.strftime("%B %Y"))
    except (TypeError, ValueError):
        return str(iso)


def topic_list():
    return [{k: t[k] for k in ("topic_id", "label", "description", "already_on_profile", "profile_section")}
            for t in TOPICS.values()]


def build_response(person, topic_id, district_override=None, today=None):
    today = today or date.today()
    topic = TOPICS.get(topic_id)
    if topic is None:
        raise RtiError("Unknown topic: " + str(topic_id))
    house = person.get("house")
    if house is None:
        raise RtiError("Cannot tell which house this member belongs to.")

    notes, missing = [], []
    if person.get("house_assumed"):
        notes.append("House was assumed to be Lok Sabha because none is stored. Please confirm.")

    aid = topic["authority_by_house"].get(house)
    if aid is None:
        return {"politician": person, "authority": None, "template": None, "missing_fields": [],
                "notes": notes + ["No authority is configured for this house and topic yet. Check the official site."]}

    district = person.get("district") or district_override
    if topic["needs_district"] and not district:
        missing.append("district")

    authority = dict(AUTHORITIES[aid])
    if authority["level"] == "DISTRICT":
        authority["name"] = authority["name"].format_map(_Keep(district=district or "[district]"))
    if not authority["verified"]:
        notes.append("Authority details are not yet verified. Confirm the PIO address on the official website before sending.")

    term_start = person.get("term_start")
    if not term_start:
        term_start = DEFAULT_TERM_START.get(house)
        if term_start:
            notes.append("Term start date was assumed. Edit the period if it is wrong.")
        else:
            missing.append("term_start")

    area = person.get("constituency") or person.get("state") or "[area]"
    ctx = _Keep(
        mp_name=person.get("name") or "[name]", mp_title=MEMBER_TITLE[house], area=area,
        house_name=HOUSE_NAME[house], district=district or "[district]",
        term_start=fmt_date(term_start) if term_start else "[start date]", today=fmt_date(today.isoformat()),
    )
    tpl = TEMPLATES[topic_id]
    questions = "\n".join("{}. {}".format(i, q.format_map(ctx)) for i, q in enumerate(tpl["questions"], 1))
    fee = authority.get("fee")
    fee_line = ("I am paying the application fee of Rs. {}/- as prescribed.".format(fee) if fee
                else "I am paying the application fee as prescribed under the applicable rules.")
    ctx.update(
        authority_name=authority["name"], pio_address=authority["pio_address"] or "[PIO address to be confirmed]",
        subject=tpl["subject"].format_map(ctx), questions=questions, fee_line=fee_line,
    )

    reply_due = today + timedelta(days=30)
    return {
        "politician": person, "authority": authority,
        "template": {"template_id": "T_" + topic_id, "language": "en",
                     "text": BODY.format_map(ctx), "user_fields": USER_FIELDS},
        "missing_fields": missing,
        "deadlines": {"reply_due": reply_due.isoformat(),
                      "first_appeal_by": (reply_due + timedelta(days=30)).isoformat()},
        "notes": notes,
    }


try:
    from rapidfuzz import fuzz

    def _score(q, doc):
        return fuzz.WRatio(q, doc)
except ImportError:  # works without the library, just less well with typos
    from difflib import SequenceMatcher

    def _score(q, doc):
        words, qs = doc.split(), q.split()
        if not qs:
            return 0
        hits = sum(1 for w in qs if any(SequenceMatcher(None, w, d).ratio() >= 0.75 for d in words))
        return 60 + 40 * hits / len(qs) if hits else 0


def suggest(person, topic_id, query="", district_override=None, limit=5):
    """Ready-made questions for a topic. Empty query lists the topic's questions; otherwise fuzzy matches."""
    if topic_id not in TOPICS:
        raise RtiError("Unknown topic: " + str(topic_id))
    house = person.get("house")
    if house is None:
        raise RtiError("Cannot tell which house this member belongs to.")
    ctx = _Keep(
        mp_name=person.get("name") or "[name]", mp_title=MEMBER_TITLE[house],
        area=person.get("constituency") or person.get("state") or "[area]",
        house_name=HOUSE_NAME[house], district=person.get("district") or district_override or "[district]",
    )
    pool = [b for b in BANK if b["reviewed"] or not ONLY_REVIEWED]
    here = [b for b in pool if b["topic_id"] == topic_id]
    item = lambda b: {"id": b["id"], "topic_id": b["topic_id"], "text": b["text"].format_map(ctx)}
    words = query.lower().split()
    q = " ".join(w for w in words if w not in STOPWORDS)
    if not q:
        return {"matches": [item(b) for b in here], "other_topics": []}
    score = lambda b: max(_score(q, b["text"].lower()), _score(q, b["keywords"].lower()))
    ranked = sorted(((score(b), b) for b in here), key=lambda x: -x[0])
    matches = [item(b) for s, b in ranked if s >= MIN_SCORE][:limit]
    other = []
    if not matches:
        other = sorted({TOPICS[b["topic_id"]]["label"] for b in pool
                        if b["topic_id"] != topic_id and score(b) >= MIN_SCORE})
    return {"matches": matches, "other_topics": other}
