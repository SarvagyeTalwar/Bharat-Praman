"""Annual-report structure-aware chunker for Bharat Praman (Part 1 Upgraded).

Implements all 5 Part-1 Checklist upgrades for Indian Government Annual Reports:
1. Table Title & Unit Freezing: Detects units (`Rs. in Crore`, `Rs. in Lakh`, `%`, etc.)
   and table captions (`Table 4.1`, `Statement`, `Annexure`) and freezes them across
   every split chunk of a multi-page/multi-chunk table.
2. Footnotes Binding: Binds trailing `*`, `**`, `Note:`, `Source:` lines directly to the
   preceding table chunk instead of leaving them as orphaned prose fragments.
3. Active Scheme / Section Context Prefixing: Stamps `[Chapter | Section/Scheme | Unit]`
   directly at the top of `chunk["text"]` AND `chunk["breadcrumb"]`.
4. Adaptive Table Parsing: Extracts real multi-column headers (e.g. `Sl. No.`, `Scheme`,
   `BE 2023-24`, `RE 2023-24`) above space-aligned financial tables instead of generic
   placeholder headers whenever header hints are present.
5. Page Boundary Stitching: Stitches sentences broken across page N -> page N+1 after
   stripping running headers/footers and page numbers.
"""

import math
import re
from collections import Counter


TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*|[\u0900-\u097f]+|[^\w\s]", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?।])\s+(?=[A-Z0-9\u0900-\u097f\"'(])")
CHAPTER_RE = re.compile(
    r"^(?:chapter|annexure|appendix)\s*[-–:]?\s*([0-9IVXLCDM]+)(?:\s*[-–:.]\s*(.*))?$",
    re.I,
)
NUMBERED_HEADING_RE = re.compile(
    r"^(\d{1,2}(?:\.\d{1,2}){1,3})[.)]?\s+([A-Z][A-Za-z0-9\s\-()&,/:’']{2,95})$"
)
DATE_PREFIX_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.(?:19|20)?\d{2}\b")
PAGE_NUMBER_RE = re.compile(
    r"^(?:page\s+)?[-–—]?\s*\d{1,4}\s*[-–—]?(?:\s+annual\s+report\s+\d{4}[-–]\d{2,4})?$",
    re.I,
)
RUNNING_HEADER_RE = re.compile(
    r"^(?:ministry\s+of\s+[a-z\s,&]+\s+annual\s+report\s+20\d{2}\s*[-–]\s*\d{2,4}|annual\s+report\s+20\d{2}\s*[-–]\s*\d{2,4}(?:\s+\d{1,4})?)$",
    re.I,
)
INLINE_HYPHEN_RE = re.compile(r"\b([A-Za-z]{2,})-\s+([a-z]{2,})\b")

# Space-separated budget/statistical table row: optional serial no + label + 2..7 numeric columns
SPACE_TABLE_ROW_RE = re.compile(
    r"^(?:(\d{1,3}|[IVX]{1,4})[.)]?\s+)?"
    r"([A-Za-z][A-Za-z0-9\s\-()&,/.’'%]{1,110}?)\s+"
    r"((?:-?\d{1,9}(?:,\d{2,3})*(?:\.\d{1,4})?(?:\s*%)?|--|NA|Nil|-)(?:\s+(?:-?\d{1,9}(?:,\d{2,3})*(?:\.\d{1,4})?(?:\s*%)?|--|NA|Nil|-)){1,8})$"
)
SINGLE_CELL_NUM_RE = re.compile(
    r"^(?:-?\d{1,9}(?:,\d{2,3})*(?:\.\d{1,4})?(?:\s*%)?|--|NA|Nil|-)$",
    re.I,
)
SINGLE_SERIAL_RE = re.compile(r"^(?:\d{1,3}|[IVX]{1,4})[.)]?$")
TABLE_HEADER_HINT_RE = re.compile(
    r"\b(?:sl\.?\s*no|s\.?\s*no|scheme|programme|particulars|name\s+of|be\s+20\d{2}|re\s+20\d{2}|actuals?|20\d{2}\s*[-–]\s*\d{2}|outlay|expenditure|allocation|sanctioned|released|target|achievement)\b",
    re.I,
)
TABLE_CAPTION_RE = re.compile(
    r"^(?:table|tab\.?|statement|annexure|appendix|figure|box)\s*[-–:.\dIVXLCDM]*",
    re.I,
)
UNIT_RE = re.compile(
    r"(?:\(\s*)?(?:₹|rs\.?|rupees|inr)?\s*(?:in\s+)?(?:crores?|crs?\.?|lakhs?|lacs?|millions?|billions?|thousands?|(?:\b%\b|per\s*cent))(?:\s*\))?",
    re.I,
)
FOOTNOTE_RE = re.compile(
    r"^(?:\*{1,3}|\†|\‡|#|note\s*s?\s*[:\-]|source\s*[:\-]|nb\s*[:\-]|p\.?s\.?\s*[:\-]|\(\s*(?:i|ii|iii|iv|a|b|c|1|2|3)\s*\)\s+[A-Z])",
    re.I,
)
TERMINAL_PUNCT_RE = re.compile(r"[.!?।:;\"')\]|]$")


def token_count(text: str) -> int:
    """Conservative word/punctuation token estimate (no model tokenizer required)."""
    return len(TOKEN_RE.findall(text or ""))


def clean_pdf_line(raw_line: str) -> str:
    """Normalize whitespace and repair broken PDF hyphenation ('Al- lowance' -> 'Allowance')."""
    s = (raw_line or "").replace("\u00ad", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = INLINE_HYPHEN_RE.sub(r"\1\2", s)
    return s


def extract_unit(text: str) -> str | None:
    """Extract financial/measurement unit (e.g., 'Rs. in Crore', 'in Lakh') from caption or heading."""
    if not text:
        return None
    m = re.search(
        r"((?:₹|rs\.?|rupees|inr)\s*(?:in\s+)?(?:crores?|crs?\.?|lakhs?|lacs?)|in\s+(?:₹|rs\.?\s*)?(?:crores?|lakhs?|lacs?|millions?|thousands?))",
        text,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip(" ()")
    return None


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r"^#{1,6}\s+", stripped):
        return True
    if CHAPTER_RE.match(stripped):
        return True
    if (
        NUMBERED_HEADING_RE.match(stripped)
        and not DATE_PREFIX_RE.match(stripped)
        and not SPACE_TABLE_ROW_RE.match(stripped)
        and not re.search(r"\b(?:from|to|in|of|for|with|by|that|which|was|were|is|are|has|have)$", stripped, re.I)
    ):
        return True
    letters = [ch for ch in stripped if ch.isalpha()]
    return (
        len(stripped) <= 110
        and len(letters) >= 5
        and sum(ch.isupper() for ch in letters) / len(letters) >= 0.82
        and not re.search(r"[.!?।]$", stripped)
        and not TABLE_HEADER_HINT_RE.search(stripped)
    )


def _token_windows(text: str, limit: int) -> list[str]:
    matches = list(TOKEN_RE.finditer(text))
    if len(matches) <= limit:
        return [text.strip()]
    out = []
    for start in range(0, len(matches), limit):
        end = min(start + limit, len(matches))
        out.append(text[matches[start].start():matches[end - 1].end()].strip())
    return [part for part in out if part]


def _tail_tokens(text: str, count: int) -> str:
    """Return the last `count` tokens snapped to a clean word/sentence boundary."""
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return ""
    idx = max(0, len(matches) - count)
    while idx < len(matches) and not re.match(r"^[A-Za-z0-9\u0900-\u097f]", matches[idx].group(0)):
        idx += 1
    return text[matches[min(idx, len(matches) - 1)].start():].strip()


def _format_space_table_row(line: str) -> str | None:
    m = SPACE_TABLE_ROW_RE.match(line.strip())
    if not m:
        return None
    serial, label, nums_str = m.groups()
    nums = nums_str.split()
    cells = ([serial] if serial else []) + [label.strip()] + nums
    return "| " + " | ".join(cells) + " |"


def _infer_column_headers(caption: str, col_count: int, has_serial: bool) -> str:
    """Adaptively infer column headers from preceding header lines instead of blind Col 1..N."""
    fy_matches = re.findall(r"(?:(?:BE|RE|Actuals?)\s*)?20\d{2}\s*[-–]\s*\d{2,4}", caption or "", re.I)
    if fy_matches and len(fy_matches) <= col_count:
        prefix = (["Sl. No.", "Scheme / Particulars"] if has_serial else ["Scheme / Particulars"])
        needed = col_count - len(prefix)
        cols = prefix + fy_matches[:needed]
        while len(cols) < col_count:
            cols.append(f"Col {len(cols) + 1}")
        return "| " + " | ".join(cols[:col_count]) + " |"
    default_cols = (["Sl. No.", "Particulars"] if has_serial else ["Particulars"])
    while len(default_cols) < col_count:
        default_cols.append(f"Value {len(default_cols) - (1 if has_serial else 0)}")
    return "| " + " | ".join(default_cols[:col_count]) + " |"


def _collapse_stacked_table_lines(lines: list[str]) -> list[str]:
    """Collapse PyMuPDF vertical cell-per-line table sequences into horizontal space-separated rows."""
    out = []
    n = len(lines)
    i = 0
    while i < n:
        # Check for [optional serial] + [1..2 label lines] + [2..8 numeric cell lines]
        serial = None
        j = i
        if SINGLE_SERIAL_RE.match(lines[j]) and j + 2 < n and not SINGLE_CELL_NUM_RE.match(lines[j + 1]):
            serial = lines[j].rstrip(".)")
            j += 1

        # Collect 1 or 2 short non-numeric label lines before a numeric run
        if (
            j < n
            and not SINGLE_CELL_NUM_RE.match(lines[j])
            and not lines[j].startswith("|")
            and len(lines[j]) <= 95
            and re.search(r"[A-Za-z]", lines[j])
        ):
            label_parts = [lines[j]]
            k = j + 1
            if (
                k < n
                and not SINGLE_CELL_NUM_RE.match(lines[k])
                and not SINGLE_SERIAL_RE.match(lines[k])
                and not lines[k].startswith("|")
                and len(lines[k]) <= 65
                and re.search(r"[A-Za-z]", lines[k])
                and k + 2 <= n
                and SINGLE_CELL_NUM_RE.match(lines[min(k + 1, n - 1)])
            ):
                label_parts.append(lines[k])
                k += 1

            nums = []
            while k < n and SINGLE_CELL_NUM_RE.match(lines[k]) and len(nums) < 8:
                # Avoid swallowing the next row's integer serial number if followed by a text label + numbers
                if (
                    len(nums) >= 2
                    and SINGLE_SERIAL_RE.match(lines[k])
                    and "." not in lines[k]
                    and k + 2 < n
                    and not SINGLE_CELL_NUM_RE.match(lines[k + 1])
                    and re.search(r"[A-Za-z]{2,}", lines[k + 1])
                    and (
                        SINGLE_CELL_NUM_RE.match(lines[k + 2])
                        or (k + 3 < n and SINGLE_CELL_NUM_RE.match(lines[k + 3]))
                    )
                ):
                    break
                nums.append(lines[k])
                k += 1

            if len(nums) >= 2:
                label = re.sub(r"\s+", " ", " ".join(label_parts)).strip()
                row_str = (f"{serial} " if serial else "") + f"{label} " + " ".join(nums)
                out.append(row_str)
                i = k
                continue

        out.append(lines[i])
        i += 1
    return out


def _clean_and_stitch_pages(page_texts, boilerplate):
    """Clean per-page lines, collapse stacked PDF table cells, and stitch cross-page sentences."""
    cleaned_pages = []
    for page, raw in page_texts:
        lines = []
        for raw_line in (raw or "").splitlines():
            line = clean_pdf_line(raw_line)
            if (
                not line
                or PAGE_NUMBER_RE.fullmatch(line)
                or RUNNING_HEADER_RE.fullmatch(line)
                or line.casefold() in boilerplate
            ):
                continue
            if lines and lines[-1].endswith("-") and line[:1].islower():
                lines[-1] = INLINE_HYPHEN_RE.sub(r"\1\2", lines[-1][:-1] + line)
            else:
                lines.append(line)
        lines = _collapse_stacked_table_lines(lines)
        cleaned_pages.append([page, lines])

    # Stitch sentence across page boundary i -> i+1 if page i ends mid-sentence
    stitched_count = 0
    for idx in range(len(cleaned_pages) - 1):
        cur_lines = cleaned_pages[idx][1]
        nxt_lines = cleaned_pages[idx + 1][1]
        if not cur_lines or not nxt_lines:
            continue
        last_line = cur_lines[-1]
        first_next = nxt_lines[0]
        if (
            not TERMINAL_PUNCT_RE.search(last_line)
            and not _is_heading(last_line)
            and not _is_heading(first_next)
            and not last_line.startswith("|")
            and not first_next.startswith("|")
            and not _format_space_table_row(last_line)
            and not _format_space_table_row(first_next)
            and not FOOTNOTE_RE.match(first_next)
            and (first_next[:1].islower() or first_next[:1] in (",", ";", ")", "]") or last_line.endswith((",", "and", "of", "to", "in", "for", "under", "with", "by", "from", "the", "a", "an")))
        ):
            if last_line.endswith("-") and first_next[:1].islower():
                cur_lines[-1] = INLINE_HYPHEN_RE.sub(r"\1\2", last_line[:-1] + first_next)
            else:
                cur_lines[-1] = f"{last_line} {first_next}"
            nxt_lines.pop(0)
            stitched_count += 1

    return cleaned_pages, stitched_count


def _page_paragraphs(cleaned_pages):
    """Yield (page, chapter, heading, text, kind, unit) units from cleaned & stitched pages."""
    current_chapter = None
    current_heading = None
    current_unit = None

    for page, lines in cleaned_pages:
        paragraph = []

        def flush_paragraph():
            nonlocal paragraph
            if paragraph:
                text = " ".join(paragraph).strip()
                if text:
                    yield (page, current_chapter, current_heading, text, "text", current_unit)
            paragraph = []

        i = 0
        while i < len(lines):
            line = lines[i]
            line_unit = extract_unit(line)
            if line_unit:
                current_unit = line_unit

            # 1. Markdown pipe table block
            if line.startswith("|") and line.count("|") >= 2:
                caption = ""
                if paragraph:
                    cand = " ".join(paragraph).strip()
                    if len(cand) <= 300 and (
                        TABLE_CAPTION_RE.match(cand)
                        or TABLE_HEADER_HINT_RE.search(cand)
                        or extract_unit(cand)
                    ):
                        caption = cand
                        paragraph = []
                    else:
                        yield from flush_paragraph()
                table_lines = []
                while i < len(lines) and lines[i].startswith("|") and lines[i].count("|") >= 2:
                    table_lines.append(lines[i])
                    i += 1
                # Bind trailing footnotes directly to this table
                footnotes = []
                while i < len(lines) and FOOTNOTE_RE.match(lines[i]) and len(lines[i]) <= 240:
                    footnotes.append(lines[i])
                    i += 1
                t_unit = extract_unit(caption) or current_unit
                table_body = "\n".join(
                    ([f"Table Caption: {caption}"] if caption else [])
                    + table_lines
                    + ([f"Footnotes: {' | '.join(footnotes)}"] if footnotes else [])
                )
                yield (page, current_chapter, current_heading, table_body, "table", t_unit)
                continue

            # 2. Space-aligned financial/statistical table block
            space_row = _format_space_table_row(line)
            if space_row:
                caption_parts = []
                if paragraph:
                    cand = " ".join(paragraph).strip()
                    if len(cand) <= 320 and (
                        TABLE_CAPTION_RE.match(cand)
                        or TABLE_HEADER_HINT_RE.search(cand)
                        or extract_unit(cand)
                    ):
                        caption_parts.append(cand)
                        paragraph = []
                    else:
                        yield from flush_paragraph()
                md_rows = [space_row]
                has_serial = bool(re.match(r"^(?:\d{1,3}|[IVX]{1,4})[.)]?\s+", line.strip()))
                i += 1
                while i < len(lines):
                    if FOOTNOTE_RE.match(lines[i]):
                        break
                    nxt_row = _format_space_table_row(lines[i])
                    if nxt_row:
                        md_rows.append(nxt_row)
                        i += 1
                    elif (TABLE_HEADER_HINT_RE.search(lines[i]) or extract_unit(lines[i])) and len(lines[i]) <= 160:
                        caption_parts.append(lines[i])
                        i += 1
                    else:
                        break
                if len(md_rows) >= 2:
                    footnotes = []
                    while i < len(lines) and FOOTNOTE_RE.match(lines[i]) and len(lines[i]) <= 240:
                        footnotes.append(lines[i])
                        i += 1
                    caption = " | ".join(caption_parts).strip(" |")
                    t_unit = extract_unit(caption) or current_unit
                    col_count = max(2, md_rows[0].count("|") - 1)
                    header_line = _infer_column_headers(caption, col_count, has_serial)
                    sep_line = "| " + " | ".join(["---"] * col_count) + " |"
                    table_text = "\n".join(
                        ([f"Table Caption: {caption}"] if caption else [])
                        + [header_line, sep_line]
                        + md_rows
                        + ([f"Footnotes: {' | '.join(footnotes)}"] if footnotes else [])
                    )
                    yield (page, current_chapter, current_heading, table_text, "table", t_unit)
                else:
                    paragraph.append(line)
                continue

            # 3. Chapter / Annexure / Section Heading
            if _is_heading(line):
                yield from flush_paragraph()
                clean_h = re.sub(r"^#{1,6}\s+", "", line).strip()
                ch_match = CHAPTER_RE.match(clean_h)
                if ch_match:
                    ch_num, ch_title = ch_match.groups()
                    if not ch_title and i + 1 < len(lines) and len(lines[i + 1]) <= 110:
                        ch_title = lines[i + 1]
                        i += 1
                    current_chapter = f"Chapter {ch_num}" + (f": {ch_title}" if ch_title else "")
                    current_heading = current_chapter
                else:
                    current_heading = clean_h
                yield (page, current_chapter, current_heading, current_heading, "heading", current_unit)
            elif re.match(r"^(?:[-•*]|\d+[.)])\s+", line):
                yield from flush_paragraph()
                yield (page, current_chapter, current_heading, line, "text", current_unit)
            else:
                paragraph.append(line)
            i += 1

        yield from flush_paragraph()


def chunk_pages(
    page_texts,
    max_tokens=340,
    overlap_tokens=50,
    ministry=None,
    year=None,
    doc_title=None,
    stamp_context_in_text=True,
):
    """Build bounded, structure-aware chunks with frozen table units, bound footnotes, and context prefixing."""
    page_texts = [(int(page), text or "") for page, text in page_texts if (text or "").strip()]
    if not page_texts:
        return []

    line_counts = Counter()
    for _, text in page_texts:
        line_counts.update({
            clean_pdf_line(line).casefold()
            for line in text.splitlines()
            if line.strip() and len(line.strip()) <= 100 and not line.strip().startswith("|")
        })
    repeat_threshold = 2 if len(page_texts) <= 4 else max(3, min(6, math.ceil(len(page_texts) * 0.05)))
    boilerplate = {line for line, count in line_counts.items() if count >= repeat_threshold and len(line) <= 100}

    cleaned_pages, _ = _clean_and_stitch_pages(page_texts, boilerplate)

    units = []
    for page, chapter, heading, text, kind, unit_label in _page_paragraphs(cleaned_pages):
        if kind == "heading":
            units.append({
                "page": page, "chapter": chapter, "heading": heading,
                "text": text, "break": True, "kind": "heading", "unit": unit_label,
            })
            continue
        if kind == "table":
            lines = text.splitlines()
            footnotes_line = ""
            if lines and lines[-1].startswith("Footnotes:"):
                footnotes_line = lines.pop(-1)
            first_row = next((i for i, line in enumerate(lines) if line.startswith("|")), len(lines))
            caption_lines, table_lines = lines[:first_row], lines[first_row:]
            caption = "\n".join(caption_lines).strip()
            if unit_label and unit_label.lower() not in caption.lower():
                caption = (f"{caption} [Unit: {unit_label}]" if caption else f"Table [Unit: {unit_label}]").strip()

            if len(table_lines) < 3:
                full_tbl = "\n".join([p for p in (caption, "\n".join(table_lines), footnotes_line) if p])
                table_chunks = [full_tbl]
            else:
                table_header = table_lines[:2]
                body_rows = table_lines[2:]
                heading_tokens = token_count(heading or "") + 24
                fn_tokens = token_count(footnotes_line)
                limit = max(60, max_tokens - heading_tokens - token_count(caption) - fn_tokens)
                table_chunks, row_buffer = [], []
                for row in body_rows:
                    candidate_parts = ([caption] if caption else []) + table_header + row_buffer + [row]
                    if footnotes_line:
                        candidate_parts.append(footnotes_line)
                    candidate = "\n".join(candidate_parts)
                    if row_buffer and token_count(candidate) > limit:
                        part_lines = ([caption] if caption else []) + table_header + row_buffer
                        if footnotes_line:
                            part_lines.append(footnotes_line)
                        table_chunks.append("\n".join(part_lines))
                        row_buffer = [row]
                    else:
                        row_buffer.append(row)
                if row_buffer:
                    part_lines = ([caption] if caption else []) + table_header + row_buffer
                    if footnotes_line:
                        part_lines.append(footnotes_line)
                    table_chunks.append("\n".join(part_lines))

            for table_chunk in table_chunks:
                units.append({
                    "page": page, "chapter": chapter, "heading": heading,
                    "text": table_chunk, "break": True, "kind": "table", "unit": unit_label,
                })
            continue

        for sentence in SENTENCE_RE.split(text):
            sentence = sentence.strip()
            if not sentence:
                continue
            heading_budget = token_count(heading or "") + 20
            unit_limit = max(24, max_tokens - heading_budget)
            for piece in _token_windows(sentence, unit_limit):
                units.append({
                    "page": page, "chapter": chapter, "heading": heading,
                    "text": piece, "break": False, "kind": "text", "unit": unit_label,
                })

    chunks, buffer = [], []

    def render(items):
        seen_heading = None
        parts = []
        headings = []
        chapters = []
        unit_labels = []
        has_table = False
        for item in items:
            ch = item.get("chapter")
            if ch and ch not in chapters:
                chapters.append(ch)
            u = item.get("unit")
            if u and u not in unit_labels:
                unit_labels.append(u)
            heading = item.get("heading")
            if heading and heading != seen_heading:
                parts.append(f"Section: {heading}")
                if heading not in headings:
                    headings.append(heading)
                seen_heading = heading
            if item.get("kind") == "table":
                has_table = True
                parts.append(item["text"])
            elif item.get("kind") == "text" and item["text"] != heading:
                parts.append(item["text"])
        active_chapter = chapters[-1] if chapters else None
        active_unit = unit_labels[-1] if unit_labels else None
        return "\n".join(parts).strip(), headings, active_chapter, active_unit, has_table

    def flush(items):
        body_text, headings, chapter_name, unit_label, has_table = render(items)
        if not body_text:
            return
        source_pages = [item["page"] for item in items if not item.get("overlap")]
        pages = source_pages or [item["page"] for item in items]
        page_start = min(pages)
        page_end = max(pages)
        primary_section = headings[-1] if headings else None
        crumb_parts = [
            f"Ministry: {ministry}" if ministry else None,
            f"FY: {year}" if year else None,
            f"Doc: {doc_title}" if doc_title else None,
            chapter_name if chapter_name and chapter_name != primary_section else None,
            f"Section: {primary_section}" if primary_section else None,
            f"Unit: {unit_label}" if unit_label else None,
            f"Pages {page_start}-{page_end}" if page_end != page_start else f"Page {page_start}",
        ]
        breadcrumb = " | ".join(p for p in crumb_parts if p)

        # Context Stamp inside chunk["text"]
        if stamp_context_in_text:
            ctx_tags = []
            if chapter_name and chapter_name != primary_section:
                ctx_tags.append(chapter_name)
            if primary_section:
                ctx_tags.append(f"Scheme/Section: {primary_section}")
            if unit_label:
                ctx_tags.append(f"Unit: {unit_label}")
            prefix = f"[{' | '.join(ctx_tags)}]\n" if ctx_tags else ""
            final_text = prefix + body_text if not body_text.startswith("[") else body_text
        else:
            final_text = body_text

        chunks.append({
            "text": final_text,
            "page_start": page_start,
            "page_end": page_end,
            "chapter": chapter_name,
            "headings": headings,
            "section": primary_section,
            "unit": unit_label,
            "kind": "table" if has_table else "text",
            "breadcrumb": breadcrumb,
            "token_count": token_count(final_text),
        })

    for unit in units:
        if unit["break"] and buffer:
            flush(buffer)
            buffer = []
        candidate = buffer + [unit]
        candidate_text, _, _, _, _ = render(candidate)
        if buffer and token_count(candidate_text) > max_tokens:
            previous = buffer
            flush(previous)
            previous_text, prev_headings, _, _, _ = render(previous)
            for h in prev_headings:
                prefix = f"Section: {h}"
                if previous_text.startswith(prefix):
                    previous_text = previous_text[len(prefix):].lstrip("\n ")
            allowed_overlap = min(overlap_tokens, max_tokens - token_count(unit["text"]) - 16)
            tail = _tail_tokens(previous_text, allowed_overlap) if allowed_overlap >= 8 else ""
            if tail:
                overlap_unit = {
                    "page": previous[-1]["page"],
                    "chapter": previous[-1].get("chapter"),
                    "heading": previous[-1].get("heading"),
                    "unit": previous[-1].get("unit"),
                    "text": tail,
                    "break": False,
                    "kind": "text",
                    "overlap": True,
                }
                buffer = [overlap_unit]
                if token_count(render(buffer + [unit])[0]) > max_tokens:
                    buffer = []
            else:
                buffer = []
        buffer.append(unit)
    if buffer:
        flush(buffer)

    return [chunk for chunk in chunks if token_count(chunk["text"]) >= 12]
