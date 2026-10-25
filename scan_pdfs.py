from parser_lite import Parser
from pathlib import Path
import json

p = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman")
parser = Parser()
out = []
for f in sorted(p.glob('*.pdf')):
    try:
        r = parser.parse(f)
        out.append({
            'file': r['file'],
            'inferred_title': r['title'],
            'mode': r['mode'],
            'text_len': len(r['text']),
            'preview': r['text'][:200].replace('\n',' ')
        })
        print('OK', r['file'], '->', r['title'][:60])
    except Exception as e:
        print('ERR', f.name, e)
Path('C:/Users/aarya/OneDrive/Desktop/Bharat Praman/scan_report.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('SAVED scan_report.json')
