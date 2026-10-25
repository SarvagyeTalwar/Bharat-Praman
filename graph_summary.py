from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os, json
from neo4j import GraphDatabase

uri=(os.getenv('NEO4J_URI1') or '').strip()
db=os.getenv('NEO4J_DATABASE1') or None
d=GraphDatabase.driver(uri,auth=(os.getenv('NEO4J_USERNAME1'),os.getenv('NEO4J_PASSWORD1')),max_transaction_retry_time=60)

with d.session(database=db) as s:
    print('=== NODE COUNTS BY LABEL ===')
    for r in s.run('MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC').data():
        print(f"  :{r['l']}: {r['c']}")
    print()
    print('=== RELATIONSHIP TYPES ===')
    for r in s.run('MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC').data():
        print(f"  {r['t']}: {r['c']}")
    print()
    print('=== DOCUMENTS ===')
    for r in s.run('MATCH (d:Document) RETURN d.file AS f, d.title AS t, d.doc_type AS dt, d.year AS y ORDER BY d.file').data():
        print(f"  {r['f']} | {r['t'][:55]} | {r['dt']} | {r['y']}")
    print()
    print('=== ENTITIES ===')
    for label in ['Scheme','Policy','Organization','PersonMentioned']:
        print(f"  :{label}:")
        for r in s.run(f'MATCH (e:{label}) RETURN e.name AS n ORDER BY n').data():
            print(f"      - {r['n']}")
    print()
    print('=== MINISTRY BOARD ===')
    for r in s.run('''
        MATCH (m:Ministry {name:"Education"})<-[:HOLDS]-(p:Person)-[:HAS_RANK]->(r:Rank)
        RETURN p.name AS name, r.name AS rank, r.level AS level
        ORDER BY level
    ''').data():
        print(f"  {r['name']} | {r['rank']} (level {r['level']})")
    print()
    print('=== SAMPLE DOC->MINISTRY->MINISTER LINK ===')
    for r in s.run('''
        MATCH (d:Document)-[:ABOUT_MINISTRY]->(m:Ministry)<-[:HOLDS]-(p:Person)
        RETURN d.title AS doc, m.name AS ministry, collect(p.name) AS ministers
        LIMIT 5
    ''').data():
        print(f"  {r['doc'][:40]} -> {r['ministry']} -> {r['ministers']}")
    print()
    print('=== ENTITY LINK SAMPLE ===')
    for r in s.run('MATCH (e:Scheme)-[:MENTIONED_IN]->(d:Document) RETURN e.name AS scheme, d.title AS doc LIMIT 10').data():
        print(f"  {r['scheme']} -> {r['doc'][:40]}")
d.close()
