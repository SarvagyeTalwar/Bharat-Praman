from dotenv import load_dotenv; load_dotenv('BACKEND/.env')
import os
from neo4j import GraphDatabase

URI = os.getenv('NEO4J_URI', '').strip()
USER = os.getenv('NEO4J_USERNAME')
PW = os.getenv('NEO4J_PASSWORD')

d = GraphDatabase.driver(URI, auth=(USER, PW), max_transaction_retry_time=120)
with d.session() as s:
    print('BEFORE labels:', [r['label'] for r in s.run('CALL db.labels()')])
    print('BEFORE indexes/constraints:', [r['name'] for r in s.run('SHOW INDEXES YIELD name RETURN name')])

    # delete nodes (both naming schemes, in case the Gemini attempt created any)
    for label in ['MoEChunkLocal', 'MoELocalDoc', 'MoEChunk', 'MoEDocument']:
        res = s.run(f'MATCH (n:{label}) DETACH DELETE n RETURN count(n) AS c').consume()
        print(f'deleted :{label} nodes:', res.counters.nodes_deleted)

    for name in ['moe_chunk_embeddings_local', 'moe_chunk_text_fulltext', 'moe_chunk_embeddings',
                 'moe_local_chunk_id', 'moe_local_doc_id', 'moe_chunk_id', 'moe_doc_id']:
        try:
            s.run(f'DROP INDEX {name} IF EXISTS').consume()
            print('dropped index/constraint:', name)
        except Exception as e:
            print('skip', name, str(e)[:120])

    print('AFTER labels:', [r['label'] for r in s.run('CALL db.labels()')])
    print('AFTER indexes/constraints:', [r['name'] for r in s.run('SHOW INDEXES YIELD name RETURN name')])
    # sanity: no MoE nodes
    for label in ['MoEChunkLocal', 'MoELocalDoc', 'MoEChunk', 'MoEDocument']:
        c = s.run(f'MATCH (n:{label}) RETURN count(n) AS c').single()['c']
        print(f':{label} remaining =', c)
d.close()
