from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase
uri=(os.getenv('NEO4J_URI1') or '').strip()
d=GraphDatabase.driver(uri,auth=(os.getenv('NEO4J_USERNAME1'),os.getenv('NEO4J_PASSWORD1')))
with d.session(database=os.getenv('NEO4J_DATABASE1')) as s:
    for r in s.run("MATCH (c:Chunk) WHERE c.text CONTAINS 'Samagra' RETURN c.text LIMIT 1").data():
        print(r['c.text'][:500])
