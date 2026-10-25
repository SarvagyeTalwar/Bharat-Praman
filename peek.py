import fitz
from pathlib import Path
p = Path(r'C:\Users\aarya\OneDrive\Desktop\Bharat Praman')
for f in ['46dc633a306ba9fbb56bd6d29710955b.pdf','626fca4e9870f1641ac69bf99056b40f.pdf','ca37b84d5f0ccbce68aaa243c7c402b6.pdf','dbc9999251af4345e53444f80c3be81c.pdf']:
    d=fitz.open(str(p/f))
    t=d[0].get_text()
    print(f+':', t[:300].replace('\n',' | '))
    d.close()
