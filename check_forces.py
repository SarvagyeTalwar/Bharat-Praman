from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase
d=GraphDatabase.driver((os.getenv('NEO4J_URI1') or '').strip(),auth=(os.getenv('NEO4J_USERNAME1'),os.getenv('NEO4J_PASSWORD1')),notifications_min_severity='OFF')
with d.session(database=os.getenv('NEO4J_DATABASE1')) as s:
    print('Chapters with Police:')
    for r in s.run("MATCH (c:MHAChunk) WHERE toLower(c.chapter) CONTAINS 'police' RETURN DISTINCT c.chapter AS ch, count(*) AS n").data():
        print(' ', r)
    print('\nChunks mentioning CRPF/BSF:')
    rows=s.run("MATCH (c:MHAChunk) WHERE c.text CONTAINS 'CRPF' OR c.text CONTAINS 'BSF' RETURN c.page AS p, c.chapter AS ch, c.text AS t LIMIT 5").data()
    for r in rows:
        print(f"  page {r['p']} | {r['ch']} | {r['t'][:200]}")
    print('\nOrganizations linked to MHA docs:')
    for r in s.run("MATCH (e:Organization)-[:MENTIONED_IN]->(d:MHADocument) RETURN e.name AS n, count(DISTINCT d) AS docs ORDER BY docs DESC, n LIMIT 30").data():
        print(' ', r['n'])
