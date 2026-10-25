"""Docling-lite parser for Ministry of Education documents (GraphRAG ready).

Uses pymupdf + pymupdf4llm (already installed) to extract:
- text with reading order
- headings/tables as markdown
- metadata (title, dates, refs)

Falls back gracefully.
"""
import os, re, json, hashlib
from pathlib import Path

import fitz
try:
    import pymupdf4llm
except Exception:
    pymupdf4llm = None

# Use markdown (preserves tables/headings) only for small docs; large
# annual reports use fast per-page text extraction to avoid long CPU stalls.
MARKDOWN_MAX_PAGES = 60


class Parser:
    def parse(self, pdf_path):
        p = Path(pdf_path)
        doc = fitz.open(str(p))
        meta = doc.metadata or {}
        title = self.infer_title(p, doc, meta)
        text = None
        mode = 'text'
        if pymupdf4llm and doc.page_count <= MARKDOWN_MAX_PAGES:
            try:
                md = pymupdf4llm.to_markdown(str(p))
                if md and md.strip():
                    text = md
                    mode = 'markdown'
            except Exception as e:
                print('pymupdf4llm failed, falling back to text:', e)
        if text is None:
            parts = []
            for i in range(doc.page_count):
                t = doc[i].get_text('text') or ''
                if t.strip():
                    parts.append(t)
            text = '\n\n'.join(parts)
            mode = 'text'
        pages = doc.page_count
        doc.close()
        return {
            'file': p.name,
            'path': str(p),
            'title': title,
            'mode': mode,
            'text': text,
            'pages': pages,
        }

    def infer_title(self, p, doc, meta):
        # try metadata
        for key in ['title', 'Title']:
            if meta.get(key) and meta[key].strip() and meta[key].strip().lower() != 'microsoft word':
                return meta[key].strip()
        # try first few pages
        for i in range(min(3, doc.page_count)):
            t = doc[i].get_text('text') or ''
            for line in t.splitlines():
                s = line.strip()
                if not s:
                    continue
                if len(s) > 10 and len(s) < 200 and re.search(r'(Ministry|Government of India|Annual Report|Press Release|Press Note|Notification)', s, re.I):
                    # skip page numbers
                    if re.match(r'^\d+$', s):
                        continue
                    return s
        # filename heuristic
        stem = re.sub(r'[_-]+', ' ', p.stem).strip()
        return stem.title()
