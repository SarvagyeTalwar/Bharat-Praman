"""Crawl election winner archives for every Lok Sabha election in this dataset.

This builds election-level rows for all elected MPs, not only MPs in the 2024 roster.
MyNeta has candidate affidavit data for 2004 onward; ECI reports supply winners/party
records for 1996, 1998, and 1999.
"""

import collections
import difflib
import hashlib
import json
import os
import re
from pathlib import Path

import build_mp_history as source

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def key_for_name(name):
    return " ".join(sorted(source.clean_tokens(name)))


def stable_record_id(year, candidate):
    cid = str(candidate.get("candidate_id") or "").strip()
    if cid:
        return f"election_{year}_{cid}"
    token = "|".join((key_for_name(candidate.get("name", "")), source.compact(candidate.get("constituency", ""))))
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]
    return f"election_{year}_{digest}"


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    candidates_by_election = source.load_all_election_candidates()
    eci_winners = source.load_eci_winners()

    # Reuse the complete 2024 baseline already present in the project/database.
    baseline_2024 = []
    current_ids_by_key = {}
    baseline_file = DATA_DIR / "mp_history.jsonl"
    if baseline_file.exists():
        with baseline_file.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    if row.get("election_year") == 2024:
                        candidate_key = key_for_name(row.get("candidate_name", ""))
                        current_ids_by_key[candidate_key] = row.get("mp_entity_id")
                        baseline_2024.append({
                            "name": row.get("candidate_name", ""),
                            "constituency": row.get("constituency", ""),
                            "party": row.get("party", ""),
                            "age": row.get("age"),
                            "education": row.get("education", ""),
                            "total_assets": row.get("total_assets"),
                            "liabilities": row.get("liabilities"),
                            "criminal_cases": row.get("criminal_cases_count"),
                            "source_url": row.get("source_url", ""),
                            "affidavit_id": row.get("affidavit_id"),
                            "is_winner": True,
                            "record_type": "affidavit_winner",
                        })

    events = []
    # Earlier elections have official winner and party data, but no affidavit
    # records in the scope of this dataset.
    for year in (1996, 1998, 1999):
        for winner in eci_winners.get(year, []):
            events.append({
                "election_id": winner.get("affidavit_id") or stable_record_id(year, winner),
                "candidate_key": key_for_name(winner["name"]),
                "candidate_name": winner["name"],
                "election": f"Lok Sabha {year}",
                "election_year": year,
                "constituency": winner.get("constituency", ""),
                "party": winner.get("party", ""),
                "is_winner": True,
                "record_type": "party_only_election_result",
                "source_url": winner.get("source_url", ""),
                "data_source": "ECI",
            })
    for election, info in source.ELECTIONS.items():
        year = info["year"]
        if year == 2024:
            winners = baseline_2024
        elif year in eci_winners:
            # ECI is authoritative for winners/seats/party. Enrich its rows with the
            # closest same-seat MyNeta winner where available, avoiding duplicate events.
            myneta = [r for r in candidates_by_election[election] if r.get("is_winner")]
            winners = []
            used = set()
            for official in eci_winners[year]:
                seat = source.compact(official.get("constituency", ""))
                candidates = [(i, r) for i, r in enumerate(myneta)
                              if source.compact(r.get("constituency", "")) == seat]
                if not candidates:
                    candidates = [(i, r) for i, r in enumerate(myneta)
                                  if i not in used and difflib.SequenceMatcher(
                                      None, source.compact(r.get("constituency", "")), seat
                                  ).ratio() >= 0.82]
                candidates = [(i, r) for i, r in candidates if i not in used]
                best = max(candidates, key=lambda ir: difflib.SequenceMatcher(
                    None, key_for_name(official["name"]), key_for_name(ir[1].get("name", ""))
                ).ratio(), default=None)
                record = dict(official)
                if best:
                    idx, affidavit = best
                    similarity = difflib.SequenceMatcher(
                        None, key_for_name(official["name"]), key_for_name(affidavit.get("name", ""))
                    ).ratio()
                    if similarity >= 0.55:
                        used.add(idx)
                        record.update({k: v for k, v in affidavit.items()
                                       if k not in {"name", "constituency", "party", "state", "is_winner"}})
                        record["name"] = official["name"]
                        record["constituency"] = official["constituency"]
                        record["party"] = official["party"]
                        record["is_winner"] = True
                        record["record_type"] = "affidavit_winner"
                winners.append(record)
        else:
            winners = [r for r in candidates_by_election[election] if r.get("is_winner")]
        seen = set()
        for winner in winners:
            name = winner.get("name", "").strip()
            constituency = winner.get("constituency", "").strip()
            dedupe_key = (source.compact(name), source.compact(constituency))
            if not name or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            row = {
                "election_id": stable_record_id(year, winner),
                "candidate_key": key_for_name(name),
                "candidate_name": name,
                "election": info["name"],
                "election_year": year,
                "constituency": constituency,
                "state": winner.get("state", ""),
                "party": winner.get("party", ""),
                "age": winner.get("age"),
                "education": winner.get("education", ""),
                "total_assets": winner.get("total_assets"),
                "liabilities": winner.get("liabilities"),
                "criminal_cases_count": winner.get("criminal_cases"),
                "is_winner": True,
                "record_type": winner.get("record_type", "affidavit_winner" if winner.get("candidate_id") or winner.get("profile_url") else "party_only_election_result"),
                "source_url": winner.get("profile_url") or winner.get("source_url", ""),
                "data_source": "MyNeta/ADR" if winner.get("profile_url") or winner.get("candidate_id") else "ECI"
            }
            events.append(row)

    events.sort(key=lambda row: (row["election_year"], row["candidate_key"], row["constituency"]))
    people = {}
    for row in events:
        candidate_key = row["candidate_key"]
        person_id = current_ids_by_key.get(candidate_key)
        if not person_id:
            digest = hashlib.sha1(candidate_key.encode("utf-8")).hexdigest()[:20]
            person_id = f"historical_mp_{digest}"
        row["person_entity_id"] = person_id
        people.setdefault(person_id, {
            "person_entity_id": person_id,
            "candidate_key": candidate_key,
            "name": row["candidate_name"],
            "is_current_mp": person_id in current_ids_by_key.values()
        })
    groups = collections.defaultdict(list)
    for row in events:
        if row["candidate_key"]:
            groups[row["candidate_key"]].append(row)

    party_changes = []
    affidavit_changes = []
    for person_key, rows in groups.items():
        by_year = collections.defaultdict(list)
        for row in rows:
            by_year[row["election_year"]].append(row)
        # A repeated name in multiple seats in one election is ambiguous; retain raw events
        # but avoid assigning a potentially false personal history across years.
        unique_rows = [year_rows[0] for year, year_rows in sorted(by_year.items()) if len(year_rows) == 1]
        for previous, current in zip(unique_rows, unique_rows[1:]):
            old_party = (previous.get("party") or "").strip()
            new_party = (current.get("party") or "").strip()
            if old_party and new_party and source.compact(old_party) != source.compact(new_party):
                party_changes.append({
                    "candidate_key": person_key,
                    "person_entity_id": current["person_entity_id"],
                    "candidate_name": current["candidate_name"],
                    "from_year": previous["election_year"],
                    "to_year": current["election_year"],
                    "from_party": old_party,
                    "to_party": new_party,
                    "from_election_id": previous["election_id"],
                    "to_election_id": current["election_id"],
                    "from_constituency": previous.get("constituency", ""),
                    "to_constituency": current.get("constituency", ""),
                    "source_from": previous.get("source_url", ""),
                    "source_to": current.get("source_url", "")
                })

        affidavit_rows = [row for row in unique_rows if row["record_type"] == "affidavit_winner"]
        for previous, current in zip(affidavit_rows, affidavit_rows[1:]):
            change = {
                "candidate_key": person_key,
                "person_entity_id": current["person_entity_id"],
                "candidate_name": current["candidate_name"],
                "from_year": previous["election_year"],
                "to_year": current["election_year"],
                "from_election_id": previous["election_id"],
                "to_election_id": current["election_id"],
                "from_party": previous.get("party", ""),
                "to_party": current.get("party", ""),
                "fields": {}
            }
            for field in ("total_assets", "liabilities", "criminal_cases_count"):
                before, after = previous.get(field), current.get(field)
                if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                    change["fields"][field] = {"from": before, "to": after, "change": after - before}
                    if field in ("total_assets", "liabilities"):
                        change["fields"][field]["percent_change"] = round((after - before) / before * 100, 2) if before else None
            change["source_from"] = previous.get("source_url", "")
            change["source_to"] = current.get("source_url", "")
            affidavit_changes.append(change)

    write_jsonl(DATA_DIR / "all_mp_elections.jsonl", events)
    write_jsonl(DATA_DIR / "all_mp_people.jsonl", people.values())
    write_jsonl(DATA_DIR / "all_party_changes.jsonl", party_changes)
    write_jsonl(DATA_DIR / "all_affidavit_changes.jsonl", affidavit_changes)
    print("Elected-MP election rows by year:")
    for year, count in sorted(collections.Counter(row["election_year"] for row in events).items()):
        print(f"  {year}: {count}")
    print(f"Wrote {len(events)} election records, {len(party_changes)} party changes, and {len(affidavit_changes)} affidavit comparisons.")
    print(f"Wrote {len(people)} distinct MP identities ({sum(1 for p in people.values() if not p['is_current_mp'])} historical-only).")
    print("Assets are reported in nominal rupees; they are not inflation-adjusted.")


if __name__ == "__main__":
    main()
