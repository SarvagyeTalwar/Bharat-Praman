from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase

uri = (os.getenv('NEO4J_URI1') or '').strip()
db = os.getenv('NEO4J_DATABASE1') or None
d = GraphDatabase.driver(uri, auth=(os.getenv('NEO4J_USERNAME1'), os.getenv('NEO4J_PASSWORD1')), max_transaction_retry_time=60)

with d.session(database=db) as s:
    print('=== TOTALS ===')
    print('Documents:', s.run('MATCH (d:Document) RETURN count(d) AS c').single()['c'])
    print('Chunks:', s.run('MATCH (c:Chunk) RETURN count(c) AS c').single()['c'])
    print('All nodes:', s.run('MATCH (n) RETURN count(n) AS c').single()['c'])
    print()
    print('=== DOCUMENTS INGESTED ===')
    for r in s.run('MATCH (d:Document) RETURN d.file AS file, d.title AS title, d.doc_type AS t ORDER BY d.file').data():
        print(f"  - {r['file']} | {r['title'][:55]} | {r['t']}")
    print()
    print('=== ZERO-CHUNK DOCS (need OCR attention) ===')
    for r in s.run('MATCH (d:Document) WHERE NOT (d)-[:HAS_CHUNK]->() RETURN d.file AS file, d.title AS title').data():
        print(f"  - {r['file']}")
    print()
    print('=== LINKED TO MINISTRY ===')
    for r in s.run('MATCH (d:Document)-[:ABOUT_MINISTRY]->(m:Ministry) RETURN count(d) AS docs, m.name AS m').data():
        print(f"  - {r['docs']} docs -> {r['m']}")
d.close()
