import json
from pathlib import Path

DATA = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman\rti\data")

auth_path = DATA / "authorities.json"
auth = json.loads(auth_path.read_text(encoding="utf-8"))
auth["VIDHAN_SABHA_SECRETARIAT"] = {
    "name": "State Legislative Assembly Secretariat",
    "level": "STATE",
    "website": None,
    "pio_designation": "Public Information Officer, State Legislative Assembly Secretariat",
    "pio_address": "[State Legislative Assembly Secretariat address to be confirmed]",
    "portal_url": None,
    "on_rtionline": False,
    "fee": None,
    "payment_mode": None,
    "appellate_authority": {"name": None, "address": None},
    "source_url": None,
    "last_verified": None,
    "verified": False,
    "research_note": "State Assembly RTI rules and PIO addresses vary by state; confirm on the state legislature website."
}
auth_path.write_text(json.dumps(auth, indent=2, ensure_ascii=False), encoding="utf-8")

topics_path = DATA / "topics.json"
topics = json.loads(topics_path.read_text(encoding="utf-8"))
for t in topics:
    t["authority_by_house"]["VIDHAN_SABHA"] = "VIDHAN_SABHA_SECRETARIAT"
topics_path.write_text(json.dumps(topics, indent=2, ensure_ascii=False), encoding="utf-8")

print("added VIDHAN_SABHA authorit(ies)")
print(json.dumps(topics, indent=2)[:800])
