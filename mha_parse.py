"""Structure-aware parser for MHA annual reports.

Detects TOC chapters, numbered sections, and builds section-coherent chunks
with breadcrumbs (doc / chapter / section / page). No Neo4j writes.
"""
import re, json, hashlib
from pathlib import Path
import fitz

ROOT = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\ministry of internal affairs\annual reports")
OUT = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman")
MAX_CHARS = 3000
OVERLAP = 250

CH_LINE = re.compile(r"^Chapter\s*[-–:]?\s*(\d+)?\s*$", re.I)
SEC_LINE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s*$")
SEC_INLINE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s+(.+)$")


def parse_toc(doc):
    chapters = {}
    for pno in range(min(12, doc.page_count)):
        lines = [l.strip() for l in (doc[pno].get_text() or "").splitlines() if l.strip()]
        i = 0
        while i < len(lines):
            m = CH_LINE.match(lines[i])
            if m:
                num = m.group(1)
                if num is None and i + 1 < len(lines) and re.match(r"^\d+$", lines[i + 1]):
                    num = lines[i + 1]
                    i += 1
                if num and i + 1 < len(lines):
                    title = lines[i + 1]
                    if not CH_LINE.match(title) and not re.match(r"^\d+$", title):
                        chapters[int(num)] = title
            i += 1
    return chapters


def clean(s):
    s = s.replace("\u00ad", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_long(text, max_chars=MAX_CHARS, overlap=OVERLAP):
    if len(text) <= max_chars:
        return [text]
    parts = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # try to break on sentence
            cut = text.rfind(". ", start, end)
            if cut > start + max_chars // 2:
                end = cut + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in parts if p]


def parse_doc(path):
    doc = fitz.open(str(path))
    chapters = parse_toc(doc)
    chunks = []
    cur_ch_num = None
    cur_ch_title = None
    cur_sec_num = None
    cur_sec_title = None
    buf = []
    buf_page = None

    def flush():
        nonlocal buf
        if not buf:
            return
        text = clean(" ".join(buf))
        buf = []
        if len(text) < 40:
            return
        crumb = " | ".join(x for x in [
            f"Doc: {path.stem}",
            f"Chapter {cur_ch_num}: {cur_ch_title}" if cur_ch_num else None,
            f"Section {cur_sec_num}: {cur_sec_title}" if cur_sec_num else None,
            f"Page {buf_page}" if buf_page else None,
        ] if x)
        for piece in split_long(text):
            chunks.append({
                "text": piece,
                "chars": len(piece),
                "page": buf_page,
                "chapter_num": cur_ch_num,
                "chapter": cur_ch_title,
                "section_num": cur_sec_num,
                "section": cur_sec_title,
                "breadcrumb": crumb,
            })

    for pno in range(doc.page_count):
        lines = [l.strip() for l in (doc[pno].get_text() or "").splitlines() if l.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            m = CH_LINE.match(line)
            if m:
                num = m.group(1)
                if num is None and i + 1 < len(lines) and re.match(r"^\d+$", lines[i + 1]):
                    num = lines[i + 1]; i += 1
                if num:
                    flush()
                    cur_ch_num = int(num)
                    cur_ch_title = chapters.get(cur_ch_num) or (lines[i + 1] if i + 1 < len(lines) else None)
                    if cur_ch_title and CH_LINE.match(cur_ch_title):
                        cur_ch_title = chapters.get(cur_ch_num)
                    cur_sec_num, cur_sec_title = None, None
                i += 1
                continue
            m = SEC_LINE.match(line) or SEC_INLINE.match(line)
            if m:
                flush()
                cur_sec_num = m.group(1)
                title = m.group(2) if m.lastindex and m.lastindex >= 2 else None
                if not title and i + 1 < len(lines):
                    nxt = lines[i + 1]
                    if not SEC_LINE.match(nxt) and not CH_LINE.match(nxt) and len(nxt) > 2:
                        title = nxt
                        i += 1
                cur_sec_title = clean(title) if title else None
                # infer chapter from section prefix if missing
                ch_from_sec = int(cur_sec_num.split(".")[0])
                if cur_ch_num is None or ch_from_sec != cur_ch_num:
                    cur_ch_num = ch_from_sec
                    cur_ch_title = chapters.get(cur_ch_num, cur_ch_title)
                i += 1
                continue
            if not buf:
                buf_page = pno + 1
            buf.append(line)
            if sum(len(x) for x in buf) >= MAX_CHARS:
                flush()
                buf_page = pno + 1
            i += 1
    flush()
    pages = doc.page_count
    doc.close()
    return {
        "file": path.name,
        "id": hashlib.sha1(path.read_bytes()).hexdigest()[:12],
        "pages": pages,
        "chapters": chapters,
        "chunks": chunks,
    }


def main():
    files = sorted(ROOT.glob("*.pdf"))
    manifest = []
    preview = []
    for f in files:
        r = parse_doc(f)
        print(f"\n=== {r['file']} pages={r['pages']} chapters={len(r['chapters'])} chunks={len(r['chunks'])} ===")
        print(" chapters:", list(r["chapters"].items())[:6])
        for c in r["chunks"][:2]:
            print(f"  [{c['breadcrumb']}] ({c['chars']} chars)")
            print(f"    {c['text'][:200]}")
        manifest.append({
            "file": r["file"], "id": r["id"], "pages": r["pages"],
            "chapters": len(r["chapters"]), "chunks": len(r["chunks"]),
            "chapter_titles": r["chapters"],
        })
        preview.extend([{**c, "file": r["file"]} for c in r["chunks"][:3]])
    (OUT / "mha_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "mha_chunks_preview.json").write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== MANIFEST ===")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print("saved manifest + preview")


if __name__ == "__main__":
    main()
