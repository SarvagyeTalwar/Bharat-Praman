"""GraphRAG ingester for arbitrary PDFs into Instance02 (Ministry of Education board).

Usage:
  python ingest_bulk.py "C:\path\to\folder" --ministry Education
  python ingest_bulk.py "C:\path\to\file.pdf" --dry-run

It will:
- parse with parser_lite (title inference, markdown if possible)
- classify doc type
- map to existing :Ministry (prefers Education; fuzzy)
- chunk (overlapping)
- embed with TF-IDF (local) + vector index
- create :Document/:Chunk nodes, link to :Ministry/:Person via board
- deduplicate by file sha1
"""
import os, re, sys, json, hashlib, textwrap, math, argparse
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
import fitz

from parser_lite import Parser

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE1") or None

MAX_CHARS = 1100
OVERLAP = 1
MAX_FEATURES = 2048
BATCH = 50

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), max_transaction_retry_time=300)
parser = Parser()


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12]


def classify(title, name):
    t = (title + ' ' + name).lower()
    if 'annual report' in t:
        return 'annual_report'
    if 'press release' in t or t.startswith('pr-') or 'pib' in t:
        return 'press_release'
    if 'press note' in t:
        return 'press_note'
    if 'budget' in t:
        return 'budget'
    if 'notification' in t:
        return 'notification'
    if 'order' in t or 'circular' in t:
        return 'order'
    if 'parliament' in t or 'rajya sabha' in t or 'lok sabha' in t:
        return 'parliament'
    if 'scheme' in t:
        return 'scheme'
    return 'document'


def map_ministry(title, name, hint=None):
    with driver.session(database=NEO4J_DATABASE) as s:
        minis = s.run('MATCH (m:Ministry) RETURN m.name AS name, m.fullName AS fullName, m.aliases AS aliases').data()
    if hint:
        for m in minis:
            if m['name'].lower() == hint.lower():
                return m
    t = (title + ' ' + name).lower()
    # prefer education
    for m in minis:
        cand = [m['name'].lower()] + ([a.lower() for a in (m.get('aliases') or [])])
        for c in cand:
            if 'education' in c and 'education' in t:
                return m
            if c and c in t and len(c) > 4:
                return m
    # direct
    for m in minis:
        if m['name'].lower() in t:
            return m
    return None


def tokenize(text):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", text.lower())


def build_vocab(texts):
    df = Counter()
    for t in texts:
        for tok in set(tokenize(t)):
            df[tok] += 1
    N = len(texts)
    terms = [tok for tok, c in df.items() if 2 <= c <= 0.9 * N]
    terms.sort(key=lambda x: df[x], reverse=True)
    terms = terms[:MAX_FEATURES]
    vocab = {tok: i for i, tok in enumerate(terms)}
    idf = [math.log((N + 1) / (df[terms[i]] + 1)) + 1.0 for i in range(len(terms))]
    return vocab, idf


def vectorize(text, vocab, idf):
    v = [0.0] * len(vocab)
    tf = Counter(tokenize(text))
    for tok, c in tf.items():
        if tok in vocab:
            v[vocab[tok]] = c * idf[vocab[tok]]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def make_chunks(text):
    # split by paragraphs/markdown headers
    paras = re.split(r'\n\s*\n|\n(?=#{1,6}\s)', text)
    out, buf, bp = [], [], 1
    for p in paras:
        p = re.sub(r'\s+', ' ', p).strip()
        if not p:
            continue
        pieces = textwrap.wrap(p, MAX_CHARS) if len(p) > MAX_CHARS else [p]
        for piece in pieces:
            if buf and sum(map(len, buf)) + len(piece) > MAX_CHARS:
                out.append((bp, " ".join(buf)))
                buf, bp = buf[-OVERLAP:], bp
            if not buf:
                bp = bp
            buf.append(piece)
    if buf:
        out.append((bp, " ".join(buf)))
    return out


def ingest_one(pdf_path, ministry_hint=None, dry_run=False):
    res = parser.parse(pdf_path)
    doc_id = sha1(pdf_path)
    dtype = classify(res['title'], res['file'])
    m = map_ministry(res['title'], res['file'], ministry_hint)
    print(f"\nFILE: {res['file']}")
    print(f"TITLE: {res['title']}")
    print(f"TYPE: {dtype} | MINISTRY: {m['name'] if m else 'UNMAPPED'} | MODE: {res['mode']} | PAGES?: {res['pages']}")

    chunks = make_chunks(res['text'])
    print(f"CHUNKS: {len(chunks)}")
    if dry_run:
        print(res['text'][:400])
        return

    with driver.session(database=NEO4J_DATABASE) as s:
        n = s.run("MATCH (d:Document {id:$id}) RETURN count(d) AS c", id=doc_id).single()['c']
        if n:
            print('ALREADY INGESTED, SKIPPING')
            return

    texts = [t for _, t in chunks]
    vocab, idf = build_vocab(texts)  # local to this batch? we'll use global? easier: build combined? but keep simple
    # use existing global vocab if exists? else build
    # better: build from all docs we ingest in this run? but run is per call; just build from this doc's corpus is weak
    # load global
    try:
        gv = json.loads(Path(r"C:\Users\aarya\OneDrive\Documents\Default Project\moe24-25_vocab_local.json").read_text(encoding='utf-8'))
        vocab, idf = gv['vocab'], gv['idf']
        print('USING GLOBAL VOCAB')
    except Exception:
        vocab, idf = build_vocab(texts)
        print('BUILT VOCAB FOR THIS DOC')

    rows = []
    for i, (pg, t) in enumerate(chunks):
        rows.append({'id': f"{doc_id}_{i}", 'i': i, 'page': pg, 'text': t, 'vec': vectorize(t, vocab, idf)})

    with driver.session(database=NEO4J_DATABASE) as s:
        s.run("""MERGE (d:Document {id:$id})
                SET d.file=$file, d.title=$title, d.path=$path, d.doc_type=$dtype, d.ministry_hint=$mh""",
              id=doc_id, file=res['file'], title=res['title'], path=res['path'], dtype=dtype, mh=m['name'] if m else None).consume()
        if m:
            s.run("""MATCH (d:Document {id:$id}), (m:Ministry {name:$mn})
                    SET m.fullName = coalesce(m.fullName, m.name), m.aliases = coalesce(m.aliases, [])
                    MERGE (d)-[:ABOUT_MINISTRY]->(m)
                    MERGE (d)-[:PUBLISHED_BY]->(m)
                    WITH d,m MATCH (p:Person)-[:HOLDS]->(m)
                    MERGE (d)-[:CONCERNS_MINISTER]->(p)""", id=doc_id, mn=m['name']).consume()
        for i in range(0, len(rows), BATCH):
            b = rows[i:i + BATCH]
            s.execute_write(lambda tx, b=b: tx.run("""
                UNWUNWIND $rows AS r
                MATCH (d:Document {id:$doc})
                MERGE (c:Chunk {id:r.id})
                SET c.text=r.text, c.page=r.page, c.idx=r.i
                WITH c,r,d
                CALL db.create.setNodeVectorProperty(c, 'embedding', r.vec)
                MERGE (d)-[:HAS_CHUNK]->(c)
            """, rows=b, doc=doc_id).consume())
        s.run("""MATCH (d:Document {id:$doc})-[:HAS_CHUNK]->(a), (d)-[:HAS_CHUNK]->(b)
                WHERE b.idx = a.idx + 1
                MERGE (a)-[:NEXT]->(b)""", doc=doc_id).consume()
    print(f'INGESTED: {len(rows)} chunks')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--ministry', default='Education')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    p = Path(args.target)
    if p.is_dir():
        for f in sorted(p.glob('*.pdf')):
            ingest_one(f, args.ministry, args.dry_run)
    elif p.is_file():
        ingest_one(p, args.ministry, args.dry_run)
    else:
        print('not found')


if __name__ == '__main__':
    main()
