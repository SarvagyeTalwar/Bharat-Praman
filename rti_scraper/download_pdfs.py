#!/usr/bin/env python3
"""Multi-threaded PDF Downloader and Verifier for RTI Records.

Downloads official scanned RTI PDFs from Supabase storage into a local directory,
verifies their binary integrity, tracks their status in a manifest, and can generate
formatted official docket PDFs for text-only RTIs.
"""

import argparse
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MASTER_FILE = BASE_DIR / "rtigram_master.json"
DEFAULT_PDF_DIR = BASE_DIR / "pdfs"
MANIFEST_FILE = BASE_DIR / "pdf_manifest.json"


def get_ssl_context():
    """Create a resilient SSL context across environments."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def is_valid_pdf(file_path: Path) -> bool:
    """Verify that a file exists, is non-empty, and starts with the %PDF magic header."""
    if not file_path.exists() or file_path.stat().st_size < 100:
        return False
    try:
        with open(file_path, "rb") as f:
            header = f.read(1024)
            return b"%PDF-" in header
    except Exception:
        return False


def generate_docket_pdf(record: dict, output_path: Path):
    """Generate a clean, standardized PDF for RTIs that only have text/questions in the database."""
    title = (record.get("title") or "RTI Document").strip()
    dept = (record.get("department") or record.get("ministry") or "Public Authority").strip()
    state = (record.get("state") or "Government of India").strip()
    status = (record.get("response_status") or "Disposed").replace("_", " ").title()
    date_filed = record.get("date_filed") or "Not Specified"
    created_at = (record.get("created_at") or "")[:10]
    record_id = record.get("id")

    questions = record.get("questions") or []
    summary = record.get("response_summary") or record.get("response_full_text") or record.get("extracted_text") or "No text provided."

    # Build plain text lines
    lines = [
        "RIGHT TO INFORMATION (RTI) APPLICATION & RESPONSE RECORD",
        "============================================================",
        f"Record ID: {record_id}",
        f"Public Authority: {dept}",
        f"Jurisdiction: {state}",
        f"Status: {status} | Date Filed: {date_filed} | Ingest Date: {created_at}",
        "------------------------------------------------------------",
        f"Subject / Title: {title}",
        "------------------------------------------------------------",
        "",
        "QUESTIONS SOUGHT UNDER RTI ACT, 2005:",
    ]

    if questions:
        for idx, q in enumerate(questions, 1):
            lines.append(f"{idx}. {q}")
    else:
        lines.append("[No point-wise questions specified]")

    lines.extend([
        "",
        "OFFICIAL RESPONSE / EXTRACTED TEXT:",
        "------------------------------------------------------------",
    ])
    lines.extend(summary.splitlines())

    # Build PDF 1.4 stream
    content_lines = []
    y = 750
    # Header
    content_lines.append("BT /F2 14 Tf 50 750 Td (RIGHT TO INFORMATION RECORD) Tj ET")
    content_lines.append(f"BT /F1 9 Tf 50 735 Td (Record ID: {record_id} | Authority: {dept[:50]}) Tj ET")
    content_lines.append("0.5 w 50 725 m 562 725 l S")

    y = 705
    for raw_line in lines[5:]:
        if y < 60:
            break
        # Wrap long lines
        chunk_size = 85
        sublines = [raw_line[i:i + chunk_size] for i in range(0, max(1, len(raw_line)), chunk_size)]
        for sub in sublines:
            if y < 60:
                break
            safe_text = (
                sub.replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .encode("ascii", "replace")
                .decode("ascii")
            )
            font = "/F2" if (sub.isupper() and len(sub) < 50) else "/F1"
            size = 10 if font == "/F2" else 9
            content_lines.append(f"BT {font} {size} Tf 50 {y} Td ({safe_text}) Tj ET")
            y -= 13

    stream_data = "\n".join(content_lines).encode("latin-1", "replace")
    compressed = zlib.compress(stream_data)

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = []

    # 1: Catalog
    offsets.append(len(pdf))
    pdf.extend(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2: Pages
    offsets.append(len(pdf))
    pdf.extend(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3: Page
    offsets.append(len(pdf))
    pdf.extend(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>\nendobj\n")
    # 4: Regular Font (Helvetica)
    offsets.append(len(pdf))
    pdf.extend(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    # 5: Bold Font (Helvetica-Bold)
    offsets.append(len(pdf))
    pdf.extend(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")
    # 6: Stream
    offsets.append(len(pdf))
    pdf.extend(f"6 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii") + compressed + b"\nendstream\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)+1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(pdf)


def download_single_pdf(record: dict, pdf_dir: Path, ctx: ssl.SSLContext, generate_missing: bool = False):
    """Download single PDF with retry and validation."""
    record_id = record.get("id")
    target_file = (pdf_dir / f"{record_id}.pdf").resolve()
    base_dir = BASE_DIR.resolve()
    try:
        rel_path = str(target_file.relative_to(base_dir))
    except ValueError:
        rel_path = str(target_file)
    url = record.get("admin_pdf_url") or record.get("file_url")

    # If already downloaded and valid
    if is_valid_pdf(target_file):
        size = target_file.stat().st_size
        return {
            "id": record_id,
            "status": "cached",
            "path": rel_path,
            "size": size,
            "url": url,
            "source": "remote" if url else "generated",
        }

    # If no URL exists
    if not url:
        if generate_missing:
            try:
                generate_docket_pdf(record, target_file)
                return {
                    "id": record_id,
                    "status": "generated",
                    "path": rel_path,
                    "size": target_file.stat().st_size,
                    "url": None,
                    "source": "generated",
                }
            except Exception as e:
                return {
                    "id": record_id,
                    "status": "generation_failed",
                    "error": str(e),
                    "url": None,
                }
        else:
            return {
                "id": record_id,
                "status": "no_url",
                "url": None,
            }

    # Attempt download from remote
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                data = resp.read()

            if not data.startswith(b"%PDF-"):
                raise ValueError("Downloaded file is not a valid PDF header")

            # Save to temp then rename
            temp_path = target_file.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                f.write(data)
            temp_path.replace(target_file)

            return {
                "id": record_id,
                "status": "downloaded",
                "path": rel_path,
                "size": len(data),
                "url": url,
                "source": "remote",
            }
        except Exception as e:
            if attempt == 2:
                return {
                    "id": record_id,
                    "status": "failed",
                    "error": str(e),
                    "url": url,
                }
            time.sleep(1 + attempt)


def sync_all_pdfs(
    master_file: Path = MASTER_FILE,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    limit: int = None,
    workers: int = 8,
    generate_missing: bool = True,
    update_master: bool = True,
):
    """Sync all PDFs, write manifest, and optionally update master JSON with local paths."""
    if not master_file.exists():
        print(f"[Error] Master file not found: {master_file}", file=sys.stderr)
        return

    with open(master_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    if limit:
        records = records[:limit]

    pdf_dir.mkdir(parents=True, exist_ok=True)
    ctx = get_ssl_context()

    print(f"[*] Processing {len(records)} RTI records for PDF synchronization...")
    print(f"[*] Target directory: {pdf_dir.resolve()}")
    print(f"[*] Concurrency workers: {workers} | Generate missing: {generate_missing}")

    stats = {
        "downloaded": 0,
        "cached": 0,
        "generated": 0,
        "failed": 0,
        "no_url": 0,
    }

    manifest = {}
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    start_time = time.time()
    total = len(records)
    processed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_single_pdf, r, pdf_dir, ctx, generate_missing): r["id"]
            for r in records
        }

        for future in as_completed(futures):
            res = future.result()
            rec_id = res["id"]
            status = res["status"]
            manifest[rec_id] = res

            if status in stats:
                stats[status] += 1
            else:
                stats["failed"] += 1

            processed += 1
            if processed % 50 == 0 or processed == total:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                print(
                    f"  [{processed:>4}/{total}] Done: {stats['downloaded'] + stats['cached'] + stats['generated']} "
                    f"(Cached: {stats['cached']}, New: {stats['downloaded']}, Gen: {stats['generated']}, Fail: {stats['failed']}) "
                    f"[{rate:.1f} rec/s]"
                )

    # Save manifest
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 55)
    print("              PDF SYNCHRONIZATION SUMMARY")
    print("=" * 55)
    print(f"Total Records Checked    : {total}")
    print(f"Already Cached & Valid   : {stats['cached']}")
    print(f"Newly Downloaded PDFs    : {stats['downloaded']}")
    print(f"Generated Docket PDFs    : {stats['generated']}")
    print(f"Failed Downloads         : {stats['failed']}")
    print(f"Skipped (No URL/No Gen)  : {stats['no_url']}")
    total_accessible = stats['cached'] + stats['downloaded'] + stats['generated']
    coverage = (total_accessible / total) * 100 if total > 0 else 0
    print(f"Overall PDF Accessibility: {total_accessible}/{total} ({coverage:.1f}%)")
    print("=" * 55 + "\n")

    # Update master file with local_pdf_path and unified pdf_url
    if update_master and master_file.exists():
        print("[*] Updating master JSON with verified local PDF paths and URLs...")
        with open(master_file, "r", encoding="utf-8") as f:
            all_records = json.load(f)

        updated_count = 0
        for r in all_records:
            rid = r.get("id")
            info = manifest.get(rid)
            r["pdf_url"] = r.get("admin_pdf_url") or r.get("file_url")
            if info and info.get("status") in ("cached", "downloaded", "generated"):
                r["local_pdf_path"] = info.get("path")
                r["has_pdf"] = True
                updated_count += 1
            else:
                r["local_pdf_path"] = None
                r["has_pdf"] = bool(r.get("pdf_url"))

        with open(master_file, "w", encoding="utf-8") as f:
            json.dump(all_records, f, indent=2, ensure_ascii=False)
        print(f"[+] Updated {updated_count} records in {master_file.name} with local PDF paths.")


def verify_local_pdfs(pdf_dir: Path = DEFAULT_PDF_DIR):
    """Audit all downloaded PDFs for corruption or 0-byte errors."""
    if not pdf_dir.exists():
        print(f"PDF directory does not exist: {pdf_dir}")
        return

    pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"[*] Auditing {len(pdfs)} local PDF files in {pdf_dir}...")
    valid = 0
    invalid = 0
    total_size = 0

    for p in pdfs:
        if is_valid_pdf(p):
            valid += 1
            total_size += p.stat().st_size
        else:
            invalid += 1
            print(f"  [CORRUPT] {p.name}")

    print(f"\n[+] Audit Complete: {valid} valid PDFs, {invalid} corrupt PDFs.")
    print(f"[+] Total Storage Used: {total_size / (1024 * 1024):.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Sync and Verify RTI PDFs locally.")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Target directory to store PDFs",
    )
    parser.add_argument(
        "--master-file",
        type=Path,
        default=MASTER_FILE,
        help="Path to rtigram_master.json",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit number of records to process",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=8,
        help="Parallel download threads",
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Do not generate docket PDFs for text-only records",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Audit existing local PDFs without downloading",
    )

    args = parser.parse_args()

    if args.verify:
        verify_local_pdfs(args.pdf_dir)
    else:
        sync_all_pdfs(
            master_file=args.master_file,
            pdf_dir=args.pdf_dir,
            limit=args.limit,
            workers=args.workers,
            generate_missing=not args.no_generate,
        )


if __name__ == "__main__":
    main()
