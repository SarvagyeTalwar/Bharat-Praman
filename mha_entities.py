"""Entity extraction for MHA annual reports using Gemini.

Creates :Scheme, :Policy, :Organization, :PersonMentioned, :StateUT,
:Committee, :Rank, :Topic nodes linked to :MHADocument via MENTIONED_IN.
"""
import os, re, json, time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
from google import genai

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

URI = (os.getenv("NEO4J_URI1") or "").strip()
USER = os.getenv("NEO4J_USERNAME1")
PW = os.getenv("NEO4J_PASSWORD1")
DB = os.getenv("NEO4J_DATABASE1")
KEY = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

driver = GraphDatabase.driver(URI, auth=(USER, PW), max_transaction_retry_time=120)
client = genai.Client(api_key=KEY)

PROMPT = """Extract named entities from this Ministry of Home Affairs (India) annual report text.
Return STRICT JSON only, with these keys (use [] if none):
- "schemes": government schemes/initiatives (e.g. BADP, I4C, NATGRID, Nirbhaya Fund)
- "acts_policies": Acts, rules, policies (e.g. Citizenship Act, UAPA, NIA Act)
- "organizations": bodies/forces (e.g. NIA, CBI, CRPF, BSF, NDRF, NHRC, RGI)
- "persons": named people (ministers, officials, MPs)
- "states_uts": Indian states/UTs mentioned (e.g. Jammu and Kashmir, Delhi)
- "committees": committees/commissions (e.g. Punchhi Commission, Kargil Review Committee)
- "ranks": police/administrative ranks (e.g. DG, ADG, IG, DIG, IPS)
- "topics": 5-10 key themes (e.g. internal security, border management, cyber crime)

Output ONLY the JSON object. No markdown, no commentary.

TEXT:
{text}
"""


def sample_text(doc_id, n=22000):
    with driver.session(database=DB) as s:
        chunks = s.run("""
            MATCH (d:MHADocument {id:$id})-[:HAS_CHUNK]->(c:MHAChunk)
            RETURN c.text AS t ORDER BY c.idx
        """, id=doc_id).data()
    if not chunks:
        return ""
    texts = [c["t"] for c in chunks]
    # take beginning, middle, end
    third = max(1, len(texts) // 3)
    picks = texts[:third] + texts[len(texts)//2:len(texts)//2 + third] + texts[-third:]
    out, total = [], 0
    for t in picks:
        out.append(t)
        total += len(t)
        if total >= n:
            break
    return " ".join(out)[:n]


def extract(doc_id, title):
    text = sample_text(doc_id)
    if not text:
        print("  no text, skip")
        return None
    for attempt in range(6):
        try:
            r = client.models.generate_content(model=MODEL, contents=PROMPT.format(text=text))
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.text.strip())
            return json.loads(raw)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                print("  rate limited, waiting 65s")
                time.sleep(65)
            else:
                print("  error:", str(e)[:200])
                return None
    return None


def write_entities(doc_id, data):
    mapping = [
        ("schemes", "Scheme"),
        ("acts_policies", "Policy"),
        ("organizations", "Organization"),
        ("persons", "PersonMentioned"),
        ("states_uts", "StateUT"),
        ("committees", "Committee"),
        ("ranks", "Rank"),
        ("topics", "Topic"),
    ]
    with driver.session(database=DB) as s:
        for key, label in mapping:
            for name in data.get(key, []):
                name = str(name).strip()
                if not name or len(name) < 2:
                    continue
                s.run(
                    f"MERGE (e:{label} {{name:$name}}) "
                    "WITH e MATCH (d:MHADocument {id:$id}) "
                    "MERGE (e)-[:MENTIONED_IN]->(d)",
                    name=name, id=doc_id
                ).consume()


def main():
    with driver.session(database=DB) as s:
        docs = s.run("MATCH (d:MHADocument) RETURN d.id AS id, d.title AS title ORDER BY d.title").data()
    print(f"STEP: extracting entities from {len(docs)} MHA documents")
    for d in docs:
        print(f"  processing: {d['title']}")
        data = extract(d["id"], d["title"])
        if not data:
            continue
        write_entities(d["id"], data)
        print("    " + ", ".join(f"{k}={len(data.get(k, []))}" for k in
              ["schemes", "acts_policies", "organizations", "persons", "states_uts", "committees", "ranks", "topics"]))
        time.sleep(5)
    with driver.session(database=DB) as s:
        print("\nENTITY COUNTS:")
        for label in ["Scheme", "Policy", "Organization", "PersonMentioned", "StateUT", "Committee", "Rank", "Topic"]:
            c = s.run(f"MATCH (e:{label}) RETURN count(e) AS c").single()["c"]
            print(f"  :{label}: {c}")


if __name__ == "__main__":
    main()
