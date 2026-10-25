import fitz
from pathlib import Path

p = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\ministry of internal affairs")
for f in sorted(p.rglob("*.pdf")):
    try:
        d = fitz.open(str(f))
        pages = d.page_count
        # sample first 5 and middle pages
        idxs = list(range(min(5, pages))) + ([pages//2] if pages > 10 else [])
        lens = [len((d[i].get_text() or "").strip()) for i in idxs]
        first = (d[0].get_text() or "").strip().replace("\n", " ")[:180]
        d.close()
        print(f"{f.name}")
        print(f"  pages={pages} sample_text_lens={lens}")
        print(f"  first_page={first!r}")
    except Exception as e:
        print(f"{f.name}: ERROR {e}")
