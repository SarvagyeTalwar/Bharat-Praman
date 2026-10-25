"""Entity extraction + title fixing for MoE documents using Gemini.

Extracts from each document:
- Schemes / initiatives (Samagra Shiksha, PM SHRI, etc.)
- Acts / policies (NEP 2020, RTE Act, etc.)
- Organizations / bodies (NCERT, AICTE, UGC, etc.)
- Key persons (MPs asking questions, ministers mentioned)

Batches Gemini calls, updates titles, and writes entities as graph nodes
linked to the :Document node. Stays well under token budget.
"""
import os, re, json, time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
from google import genai

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

NEO4J_URI = (os.getenv("NEO4J_URI1") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), max_transaction_retry_time=120)
client = genai.Client(api_key=GEMINI_API_KEY)

TITLE_PROMPT = """Given the filename and first text of an Indian government document,
return ONLY a concise, human-readable title (max 12 words) describing what it is.
If it's an annual report, say "Ministry of Education Annual Report <year>".
Filename: {fname}
Text start: {text}
Title:"""

ENTITY_PROMPT = """Extract named entities from this Indian Ministry of Education document text.
Return strict JSON with these keys (empty list if none):
- "schemes": list of scheme/initiative names (e.g. Samagra Shiksha, PM SHRI, RTE)
- "policies": list of policies/acts (e.g. NEP 2020, RTE Act 2009)
- "organizations": list of bodies (e.g. NCERT, AICTE, UGC, NIOS)
- "persons": list of person names (MPs, ministers, officials)
Only use entities actually mentioned. Output ONLY the JSON object, nothing else.

Text: {text}"""


def llm_json(prompt):
    r = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    txt = r.text.strip()
    # strip code fences
    txt = re.sub(r'^```(?:json)?\s*|\s*```$', '', txt).strip()
    return txt


def get_docs():
    with driver.session(database=NEO4J_DATABASE) as s:
        rows = s.run(
            "MATCH (d:Document) WHERE d.doc_type <> 'existing' "
            "RETURN d.id AS id, d.file AS file, d.title AS title ORDER BY d.file"
        ).data()
    return rows


def sample_text(doc_id, n=4000):
    with driver.session(database=NEO4J_DATABASE) as s:
        chunks = s.run(
            "MATCH (d:Document {id:$id})-[:HAS_CHUNK]->(c:Chunk) "
            "RETURN c.text AS t ORDER BY c.idx LIMIT 40", id=doc_id
        ).data()
    parts = []
    total = 0
    for r in chunks:
        parts.append(r["t"])
        total += len(r["t"])
        if total >= n:
            break
    return " ".join(parts)


def fix_titles(docs):
    print("STEP 2a: Fixing document titles...")
    for d in docs:
        if d["title"] and not re.match(r'^[0-9A-Fa-f]{30,}$', d["title"]):
            continue  # already has a real title
        txt = sample_text(d["id"], 1500)
        try:
            t = llm_json(TITLE_PROMPT.format(fname=d["file"], text=txt[:1500]))
            t = t.strip().strip('"').strip()
            with driver.session(database=NEO4J_DATABASE) as s:
                s.run("MATCH (d:Document {id:$id}) SET d.title=$t", id=d["id"], t=t)
            print(f"  title fixed: {d['file']} -> {t}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  title error {d['file']}: {e}")


def extract_entities(docs):
    print("STEP 2b: Extracting entities...")
    for d in docs:
        txt = sample_text(d["id"], 6000)
        if not txt:
            print(f"  skip {d['file']} (no text)")
            continue
        try:
            j = llm_json(ENTITY_PROMPT.format(text=txt[:6000]))
            data = json.loads(j)
            with driver.session(database=NEO4J_DATABASE) as s:
                for kind, label in [("schemes", "Scheme"), ("policies", "Policy"),
                                    ("organizations", "Organization"), ("persons", "PersonMentioned")]:
                    for name in data.get(kind, []):
                        name = str(name).strip()[:120]
                        if not name or len(name) < 2:
                            continue
                        s.run(
                            f"MERGE (e:{label} {{name:$name}}) "
                            "WITH e MATCH (d:Document {id:$id}) "
                            f"MERGE (e)-[:MENTIONED_IN]->(d)",
                            name=name, id=d["id"]
                        ).consume()
                # also count how many entities
            print(f"  {d['file']}: schemes={len(data.get('schemes',[]))}, policies={len(data.get('policies',[]))}, "
                  f"orgs={len(data.get('organizations',[]))}, persons={len(data.get('persons',[]))}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  entity error {d['file']}: {e}")


def summarize():
    with driver.session(database=NEO4J_DATABASE) as s:
        print("\n=== ENTITY COUNTS ===")
        for label in ["Scheme", "Policy", "Organization", "PersonMentioned"]:
            c = s.run(f"MATCH (e:{label}) RETURN count(e) AS c").single()["c"]
            print(f"  :{label}: {c}")


if __name__ == "__main__":
    docs = get_docs()
    print(f"STEP 2: {len(docs)} documents to process")
    fix_titles(docs)
    extract_entities(docs)
    summarize()
    print("STEP 2 COMPLETE")
