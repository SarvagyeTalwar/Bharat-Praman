#!/usr/bin/env python3
"""RTI Dataset Merger and Deduplication Utility.

Merges multiple scraped RTI JSON/JSONL files into a single consolidated,
deduplicated master dataset. Analyzes data quality and completeness.
"""

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path


def load_records_from_file(file_path: Path):
    """Load records from a JSON array file or JSON Lines file."""
    if not file_path.exists():
        print(f"[Warning] File does not exist: {file_path}", file=sys.stderr)
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            if content.startswith("["):
                data = json.loads(content)
                if isinstance(data, list):
                    return data
            # Try reading as JSON Lines
            return [json.loads(line) for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"[Error] Failed to load {file_path}: {e}", file=sys.stderr)
        return []


def merge_and_deduplicate(files, output_file: Path, format_type: str = "json"):
    all_records = []
    print(f"[*] Processing {len(files)} file(s)...")

    for fpath in files:
        records = load_records_from_file(fpath)
        print(f"  - {fpath.name:<35}: {len(records):>5} records")
        all_records.extend(records)

    print(f"\n[*] Total records loaded before deduplication: {len(all_records)}")

    # Deduplicate by UUID, keeping the record with richer information
    unique_records = {}
    missing_ids = 0
    duplicates = 0

    for record in all_records:
        record_id = record.get("id")
        if not record_id:
            missing_ids += 1
            continue

        if record_id in unique_records:
            duplicates += 1
            existing = unique_records[record_id]
            # Keep whichever record has more populated attributes
            ex_score = sum(1 for v in existing.values() if v is not None and v != "")
            new_score = sum(1 for v in record.values() if v is not None and v != "")
            if new_score > ex_score:
                unique_records[record_id] = record
        else:
            unique_records[record_id] = record

    final_records = list(unique_records.values())

    # Sort deterministically by date or ID
    final_records.sort(key=lambda r: (r.get("created_at") or "", r.get("id") or ""), reverse=True)

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        if format_type == "jsonl":
            for r in final_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            json.dump(final_records, f, ensure_ascii=False, indent=2)

    # Summary report
    print("\n" + "=" * 50)
    print("           MERGE COMPLETED SUCCESSFULLY")
    print("=" * 50)
    print(f"Total raw records input : {len(all_records)}")
    print(f"Duplicate records purged: {duplicates}")
    print(f"Records missing ID      : {missing_ids}")
    print(f"Final unique records    : {len(final_records)}")
    print(f"Saved to                : {output_file.resolve()}")

    if final_records:
        statuses = Counter(r.get("response_status") or "unspecified" for r in final_records)
        print("\n--- Response Status Breakdown ---")
        for status, count in statuses.most_common():
            pct = (count / len(final_records)) * 100
            print(f"  {status:<20}: {count:>5} ({pct:.1f}%)")

        has_questions = sum(1 for r in final_records if r.get("questions"))
        has_full_text = sum(1 for r in final_records if r.get("response_full_text") or r.get("extracted_text"))
        has_pdf = sum(1 for r in final_records if r.get("admin_pdf_url") or r.get("file_url"))

        print("\n--- Content Completeness ---")
        print(f"  With Questions        : {has_questions:>5} ({has_questions/len(final_records)*100:.1f}%)")
        print(f"  With Full/OCR Text    : {has_full_text:>5} ({has_full_text/len(final_records)*100:.1f}%)")
        print(f"  With Direct PDF Links : {has_pdf:>5} ({has_pdf/len(final_records)*100:.1f}%)")
    print("=" * 50 + "\n")


def main():
    base_dir = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description="Merge and deduplicate RTI JSON/JSONL datasets.")
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Input files to merge. If omitted, discovers all rtigram_*.json in project directory.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=base_dir / "rtigram_master.json",
        help="Master output file path (default: rti_scraper/rtigram_master.json)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "jsonl"],
        default="json",
        help="Output format (json or jsonl)",
    )

    args = parser.parse_args()

    files = args.inputs
    if not files:
        # Auto-discover
        pattern = str(base_dir / "rtigram_*.json")
        discovered = [Path(p) for p in glob.glob(pattern) if Path(p).resolve() != args.output.resolve()]
        if not discovered:
            print(f"[Error] No input files found matching '{pattern}'", file=sys.stderr)
            sys.exit(1)
        files = discovered

    merge_and_deduplicate(files, args.output, args.format)


if __name__ == "__main__":
    main()
