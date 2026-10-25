from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase
d=GraphDatabase.driver((os.getenv('NEO4J_URI1') or '').strip(),auth=(os.getenv('NEO4J_USERNAME1'),os.getenv('NEO4J_PASSWORD1')))
with d.session(database=os.getenv('NEO4J_DATABASE1')) as s:
    rows=s.run("CALL db.index.fulltext.queryNodes('chunk_text_fulltext','National Bal Bhavan') YIELD node,score RETURN node.text AS t, score ORDER BY score DESC LIMIT 3").data()
for r in rows:
    print('---')
    print(r['t'][:900])
