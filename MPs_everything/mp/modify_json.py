
import json
from pathlib import Path

# =========================
# CONFIGURATION
# =========================

INPUT_FILE = Path("members.json")
OUTPUT_FILE = Path("mp_entities.json")


# =========================
# HELPER FUNCTIONS
# =========================

def clean(value):
    """Strip whitespace from strings; preserve other value types."""
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def extract_phones(value):
    """
    Convert phone data into a flat list of strings.
    Handles strings, numbers, None, lists, and nested lists.
    """
    if value is None:
        return []

    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(extract_phones(item))
        return result

    value = str(value).strip()

    if not value:
        return []

    return [value]


def extract_emails(value):
    """Convert email data into a flat list of non-empty strings."""
    if value is None:
        return []

    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(extract_emails(item))
        return result

    value = str(value).strip()

    if not value:
        return []

    return [value]


def unique_preserving_order(values):
    """Remove duplicates while preserving order."""
    seen = set()
    result = []

    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result


def make_mp(mp):
    """Transform one Sansad API member record."""

    source_id = mp.get("mpsno")

    if source_id is None:
        return None, None

    entity_id = f"sansad_mp_{source_id}"

    # Normalize gender to M/F where recognized.
    raw_gender = clean(mp.get("gender"))

    gender_map = {
        "male": "M",
        "female": "F",
        "m": "M",
        "f": "F",
    }

    gender = (
        gender_map.get(raw_gender.casefold())
        if isinstance(raw_gender, str)
        else None
    )

    # Keep both profession fields without duplicates.
    professions = unique_preserving_order([
        value
        for value in [
            clean(mp.get("profession")),
            clean(mp.get("profession2")),
        ]
        if value is not None
    ])

    # Flatten phone fields safely.
    phones = []

    for field in (
        "personalPhone",
        "phone",
        "delhiPhone",
    ):
        phones.extend(extract_phones(mp.get(field)))

    phones = unique_preserving_order(phones)

    # Flatten email fields safely.
    emails = unique_preserving_order(
        extract_emails(mp.get("email"))
    )

    # Prefer the party short name.
    party = (
        clean(mp.get("partySname"))
        or clean(mp.get("partyFname"))
    )

    record = {
        "name": {
            "first": clean(mp.get("firstName")),
            "last": clean(mp.get("lastName")),
        },

        "gender": gender,
        "age": mp.get("age"),
        "party": party,

        "profession": professions,

        "constituency": {
            "state": clean(mp.get("stateName")),
            "name": clean(mp.get("constName")),
        },

        "address": {
            "present": {
                "address": clean(mp.get("presentFaddr")),
                "pincode": clean(mp.get("presentLaddr")),
            },
            "permanent": {
                "address": clean(mp.get("permanentFaddr")),
                "pincode": clean(mp.get("permanentLaddr")),
            },
        },

        "contact": {
            "emails": emails,
            "phones": phones,
        },

        "family_info": {
            "nSons": mp.get("numberOfSons"),
            "nDaughters": mp.get("numberOfDaughters"),
        },

        "terms": mp.get("noOfTerms"),
    }

    return entity_id, record


# =========================
# MAIN PIPELINE
# =========================

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE.resolve()}\n"
            "Place members.json in the same folder as this script."
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        source_data = json.load(file)

    if not isinstance(source_data, dict):
        raise ValueError("Expected the JSON root to be an object.")

    members = source_data.get("membersDtoList")

    if not isinstance(members, list):
        raise ValueError(
            "Expected a list at the JSON key 'membersDtoList'."
        )

    output = {}
    skipped = 0

    for index, mp in enumerate(members):
        if not isinstance(mp, dict):
            print(f"Skipping record {index}: expected an object.")
            skipped += 1
            continue

        entity_id, record = make_mp(mp)

        if entity_id is None:
            print(f"Skipping record {index}: missing mpsno.")
            skipped += 1
            continue

        # Duplicate mpsno values overwrite earlier records.
        output[entity_id] = record

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\nProcessing complete.")
    print(f"Input records: {len(members)}")
    print(f"Unique MP IDs: {len(output)}")
    print(f"Skipped records: {skipped}")
    print(f"Output file: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
