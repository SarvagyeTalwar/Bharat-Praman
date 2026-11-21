#!/usr/bin/env python3
"""CLI utility to find, view, or stream any RTI PDF by ID, title, or keyword."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MASTER_FILE = BASE_DIR / "rtigram_master.json"
PDF_DIR = BASE_DIR / "pdfs"


def load_master():
    if not MASTER_FILE.exists():
        sys.exit(f"Master file not found at {MASTER_FILE}")
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_records(records, query):
    q = query.lower().strip()
    # 1. Exact ID match
    for r in records:
        if r.get("id") == q:
            return [r]

    # 2. ID prefix match
    matches = [r for r in records if r.get("id", "").lower().startswith(q)]
    if matches:
        return matches

    # 3. Substring in title, department, or subject
    matches = [
        r for r in records
        if q in (r.get("title") or "").lower()
        or q in (r.get("department") or "").lower()
        or q in (r.get("subject") or "").lower()
    ]
    return matches


def main():
    parser = argparse.ArgumentParser(description="Find, view, or open RTI PDFs.")
    parser.add_argument("query", help="RTI ID (or prefix), or search keyword")
    parser.add_argument("--url-only", "-u", action="store_true", help="Print the direct PDF URL only")
    parser.add_argument("--download", "-d", action="store_true", help="Ensure local PDF is downloaded")
    parser.add_argument("--open", "-o", action="store_true", default=True, help="Open in default PDF viewer / browser")
    parser.add_argument("--no-open", dest="open", action="store_false", help="Do not open the file")

    args = parser.parse_args()

    records = load_master()
    matches = find_records(records, args.query)

    if not matches:
        sys.exit(f"No RTI record found matching query: '{args.query}'")

    if len(matches) > 1 and not args.url_only:
        print(f"Found {len(matches)} matching RTI records:")
        for idx, m in enumerate(matches[:8], 1):
            print(f"  [{idx}] {m.get('id')[:8]} | {m.get('title')[:60]} ({m.get('department') or m.get('state')})")
        print("\nSelecting first match...")

    target = matches[0]
    rid = target.get("id")
    title = target.get("title")
    pdf_url = target.get("admin_pdf_url") or target.get("file_url")
    local_file = PDF_DIR / f"{rid}.pdf"

    print("\n" + "=" * 50)
    print(f"RTI Record ID  : {rid}")
    print(f"Title          : {title}")
    print(f"Public URL     : {pdf_url or '[No remote URL - Text Docket Only]'}")
    print(f"Local PDF File : {local_file if local_file.exists() else '[Not downloaded yet]'}")
    print("=" * 50 + "\n")

    if args.url_only:
        if pdf_url:
            print(pdf_url)
        else:
            print(f"file://{local_file.resolve()}" if local_file.exists() else "None")
        return

    # Check if local file exists or if we should download
    to_open = None
    if local_file.exists():
        to_open = str(local_file.resolve())
    elif pdf_url:
        if args.download:
            print("[*] Downloading PDF...")
            import download_pdfs
            ctx = download_pdfs.get_ssl_context()
            res = download_pdfs.download_single_pdf(target, PDF_DIR, ctx, generate_missing=True)
            if res.get("status") in ("downloaded", "cached", "generated"):
                to_open = str(local_file.resolve())
            else:
                to_open = pdf_url
        else:
            to_open = pdf_url
    else:
        # Generate on the fly
        print("[*] Generating official docket PDF...")
        import download_pdfs
        download_pdfs.generate_docket_pdf(target, local_file)
        to_open = str(local_file.resolve())

    if args.open and to_open:
        print(f"[*] Opening: {to_open}")
        if sys.platform == "darwin":
            subprocess.run(["open", to_open])
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", to_open])
        elif sys.platform == "win32":
            os.startfile(to_open)


if __name__ == "__main__":
    main()
