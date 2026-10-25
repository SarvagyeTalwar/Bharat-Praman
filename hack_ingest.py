"""
Safe, throttled, and status-updating ingester for hackathon.
Handles large PDFs and small ones, auto-titling and linking.
"""
import os, re, sys, json, hashlib, textwrap, math, time
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
import fitz

from parser_lite import Parser

# Configuration
MAX_CHARS = 1100
OVERLAP = 1
MAX_FEATURES = 2048
BATCH = 40 # Smaller batch for safety
THROTTLE_SEC = 0.8 # Breathing room for Neo4j/Aura

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE1") or None

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), max_transaction_retry_time=300)
parser = Parser()

def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12]

def tokenize(text):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", text.lower())

def vectorize(text, vocab, idf):
    v = [0.0] * len(vocab)
    tf = Counter(tokenize(text))
    for tok, c in tf.items():
        if tok in vocab:
            v[vocab[tok]] = c * idf[vocab[tok]]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def make_chunks(text):
    paras = re.split(r'\n\s*\n|\n(?=#{1,6}\s)', text)
    out, buf, bp = [], [], 1
    for p in paras:
        p = re.sub(r'\s+', ' ', p).strip()
        if not p: continue
        pieces = textwrap.wrap(p, MAX_CHARS) if len(p) > MAX_CHARS else [p]
        for piece in pieces:
            if buf and sum(map(len, buf)) + len(piece) > MAX_CHARS:
                out.append((bp, " ".join(buf)))
                buf = buf[-OVERLAP:]
            buf.append(piece)
    if buf:
        out.append((bp, " ".join(buf)))
    return out

def classify(title, name):
    t = (title + ' ' + name).lower()
    if 'annual report' in t: return 'annual_report'
    if 'press release' in t or 'posted on' in t or 'pib' in t: return 'press_release'
    if 'parliament' in t or 'rajya sabha' in t or 'unstarred' in t: return 'parliamentary_response'
    return 'document'

def ingest_one(pdf_path):
    print(f"STEP: Processing {pdf_path.name}")
    doc_id = sha1(pdf_path)
    
    # Skip check
    with driver.session(database=NEO4J_DATABASE) as s:
        if s.run("MATCH (d:Document {id:$id}) RETURN count(d) AS c", id=doc_id).single()['c'] > 0:
            print(f"STATUS: {pdf_path.name} already exists. Skipping.")
            return

    res = parser.parse(pdf_path)
    print(f"STATUS: {pdf_path.name} parsed ({res['pages']} pages, mode={res['mode']}, title='{res['title'][:60]}')")
    dtype = classify(res['title'], res['file'])
    
    # Load global vocab
    gv = json.loads(Path(r"C:\Users\aarya\OneDrive\Documents\Default Project\moe24-25_vocab_local.json").read_text(encoding='utf-8'))
    vocab, idf = gv['vocab'], gv['idf']

    chunks = make_chunks(res['text'])
    rows = []
    for i, (pg, t) in enumerate(chunks):
        rows.append({'id': f"{doc_id}_{i}", 'i': i, 'page': pg, 'text': t, 'vec': vectorize(t, vocab, idf)})

    print(f"STATUS: {res['file']} -> {len(rows)} chunks found. Writing to Neo4j...")

    with driver.session(database=NEO4J_DATABASE) as s:
        # Create Doc and Link
        s.run("""
            MERGE (d:Document {id:$id})
            SET d.file=$file, d.title=$title, d.doc_type=$dtype, d.ministry='Education'
            WITH d
            MATCH (m:Ministry {name:'Education'})
            MERGE (d)-[:ABOUT_MINISTRY]->(m)
            MERGE (d)-[:PUBLISHED_BY]->(m)
            WITH d, m
            MATCH (p:Person)-[:HOLDS]->(m)
            MERGE (d)-[:CONCERNS_MINISTER]->(p)
        """, id=doc_id, file=res['file'], title=res['title'], dtype=dtype).consume()

        # Write chunks in batches
        for i in range(0, len(rows), BATCH):
            b = rows[i:i + BATCH]
            s.execute_write(lambda tx, b=b: tx.run("""
                UNWIND $rows AS r
                MATCH (d:Document {id:$doc})
                MERGE (c:Chunk {id:r.id})
                SET c.text=r.text, c.page=r.page, c.idx=r.i
                WITH c,r,d
                CALL db.create.setNodeVectorProperty(c, 'embedding', r.vec)
                MERGE (d)-[:HAS_CHUNK]->(c)
            """, rows=b, doc=doc_id).consume())
            time.sleep(THROTTLE_SEC)
            print(f"  Progress: {min(i+BATCH, len(rows))}/{len(rows)} chunks...")

        # Link NEXT
        s.run("""MATCH (d:Document {id:$doc})-[:HAS_CHUNK]->(a), (d)-[:HAS_CHUNK]->(b)
                WHERE b.idx = a.idx + 1
                MERGE (a)-[:NEXT]->(b)""", doc=doc_id).consume()
    
    print(f"SUCCESS: {res['file']} completed.")

if __name__ == "__main__":
    folder = Path(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman")
    files = sorted(folder.glob('*.pdf'))
    print(f"START: Ingesting {len(files)} documents.")
    for f in files:
        try:
            ingest_one(f)
        except Exception as e:
            print(f"ERROR on {f.name}: {e}")
    print("FINISH: All documents processed.")
