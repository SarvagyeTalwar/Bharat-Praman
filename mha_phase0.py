"""Phase 0: inventory + structure-aware chunking preview for MHA annual reports.
No Neo4j writes. Prints manifest, detected chapters/sections, and sample chunks.
"""
import re, json
from pathlib import Path
import fitz

ROOT = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\ministry of internal affairs\annual reports")
MAX_CHARS = 3500          # ~900-1000 tokens
OVERLAP_PARAS = 1

CH_RE = re.compile(r"^\s*Chapter\s*[-–:]?\s*(\d+)\s*[:\-–]?\s*(.+)$", re.I)
SEC_RE = re.compile(r"^\s*(\d+\.\d+(?:\.\d+)?)\s+([A-Z][^\n]{2,120})$")


def detect_structure(doc, max_pages=None):
    """Return (chapters, sections, chunks) preview."""
    chapters, sections = [], []
    chunks = []
    cur_ch = None
    cur_sec = None
    buf, buf_meta = [], {}

    def flush():
        nonlocal buf, buf_meta
        if buf:
            text = " ".join(buf).strip()
            if text:
                crumb = " | ".join(x for x in [
                    f"Doc: {Path(buf_meta.get('file','')).stem}",
                    f"Chapter: {buf_meta.get('chapter','')}" if buf_meta.get('chapter') else None,
                    f"Section: {buf_meta.get('section','')}" if buf_meta.get('section') else None,
                    f"Page: {buf_meta.get('page','')}" if buf_meta.get('page') else None,
                ] if x)
                chunks.append({"breadcrumb": crumb, "text": text, "chars": len(text)})
            buf = []

    pages = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
    for pno in range(pages):
        text = doc[pno].get_text() or ""
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            m = CH_RE.match(s)
            if m:
                cur_ch = f"{m.group(1)}. {m.group(2).strip()}"
                chapters.append({"page": pno + 1, "title": cur_ch})
                continue
            m = SEC_RE.match(s)
            if m:
                flush()
                cur_sec = f"{m.group(1)} {m.group(2).strip()}"
                sections.append({"page": pno + 1, "title": cur_sec, "chapter": cur_ch})
                continue
            # accumulate paragraph-sized piece
            if len(s) < 8:
                continue
            if not buf:
                buf_meta = {"file": doc.name, "chapter": cur_ch, "section": cur_sec, "page": pno + 1}
            buf.append(s)
            if sum(len(x) for x in buf) >= MAX_CHARS:
                flush()
                # overlap: keep last paragraph
                if OVERLAP_PARAS and len(buf) > 0:
                    pass
                buf_meta = {"file": doc.name, "chapter": cur_ch, "section": cur_sec, "page": pno + 1}
    flush()
    return chapters, sections, chunks


def main():
    files = sorted(ROOT.glob("*.pdf"))
    print(f"FILES: {len(files)}")
    manifest = []
    for f in files:
        doc = fitz.open(str(f))
        chapters, sections, chunks = detect_structure(doc, max_pages=40)
        print(f"\n=== {f.name} | pages={doc.page_count} ===")
        print(f"  chapters detected (first 40p): {len(chapters)}")
        for c in chapters[:8]:
            print(f"    p{c['page']}: {c['title']}")
        print(f"  sections detected (first 40p): {len(sections)}")
        for s in sections[:6]:
            print(f"    p{s['page']}: {s['title']}")
        print(f"  sample chunks (first 40p): {len(chunks)}")
        for c in chunks[:2]:
            print(f"    [{c['breadcrumb']}] ({c['chars']} chars)")
            print(f"      {c['text'][:220]}")
        manifest.append({
            "file": f.name, "pages": doc.page_count,
            "chapters_first40": len(chapters), "sections_first40": len(sections),
            "chunks_first40": len(chunks),
        })
        doc.close()
    print("\n=== MANIFEST ===")
    print(json.dumps(manifest, indent=2))
    out = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\mha_phase0_manifest.json")
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("saved:", out)


if __name__ == "__main__":
    main()
