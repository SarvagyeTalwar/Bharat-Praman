from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase
d=GraphDatabase.driver((os.getenv('NEO4J_URI1') or '').strip(),auth=(os.getenv('NEO4J_USERNAME1'),os.getenv('NEO4J_PASSWORD1')),notifications_min_severity='OFF')
with d.session(database=os.getenv('NEO4J_DATABASE1')) as s:
    print('=== MHA GRAPH ===')
    print('MHADocument:', s.run('MATCH (d:MHADocument) RETURN count(d) AS c').single()['c'])
    print('MHAChunk:', s.run('MATCH (c:MHAChunk) RETURN count(c) AS c').single()['c'])
    print('Total nodes:', s.run('MATCH (n) RETURN count(n) AS c').single()['c'])
    print('\nMHA relationships:')
    for r in s.run('''
        MATCH (a)-[r]->(b)
        WHERE (a:MHADocument OR a:MHAChunk) OR (b:MHADocument OR b:MHAChunk)
        RETURN type(r) AS t, count(*) AS c ORDER BY c DESC
    ''').data():
        print(f"  {r['t']}: {r['c']}")
    print('\nDocuments:')
    for r in s.run('MATCH (d:MHADocument) RETURN d.title AS t, d.year AS y, d.pages AS p ORDER BY y').data():
        print(f"  {r['t']} | {r['y']} | {r['p']} pages")
    print('\nMinisters linked:')
    for r in s.run("MATCH (d:MHADocument)-[:CONCERNS_MINISTER]->(p:Person) RETURN DISTINCT p.name AS n").data():
        print(' ', r['n'])
    print('\nMHA-linked entities:')
    for label in ['Scheme','Policy','Organization','PersonMentioned','StateUT','Committee','Rank','Topic']:
        c=s.run(f'MATCH (e:{label})-[:MENTIONED_IN]->(:MHADocument) RETURN count(DISTINCT e) AS c').single()['c']
        print(f'  :{label}: {c}')
d.close()
