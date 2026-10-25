from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase
d=GraphDatabase.driver((os.getenv('NEO4J_URI1') or '').strip(),auth=(os.getenv('NEO4J_USERNAME1'),os.getenv('NEO4J_PASSWORD1')))
with d.session(database=os.getenv('NEO4J_DATABASE1')) as s:
    print('MHA-ish ministries:')
    for r in s.run("MATCH (m:Ministry) WHERE toLower(m.name) CONTAINS 'home' OR toLower(m.name) CONTAINS 'internal' OR toLower(m.name) CONTAINS 'affairs' RETURN m.name AS name, m.kind AS kind").data():
        print(' ', r)
    print('\nMinisters holding Home Affairs:')
    for r in s.run("""
        MATCH (p:Person)-[h:HOLDS]->(m:Ministry)
        WHERE toLower(m.name) CONTAINS 'home'
        OPTIONAL MATCH (p)-[:HAS_RANK]->(r:Rank)
        RETURN p.name AS name, r.name AS rank, r.level AS level
        ORDER BY level
    """).data():
        print(' ', r)
    print('\nExisting doc types:')
    for r in s.run("MATCH (d:Document) RETURN DISTINCT d.doc_type AS t").data():
        print(' ', r)
