"""GraphRAG agent for the Ministry of Home Affairs annual reports.

Hybrid retrieval (full-text + TF-IDF vector) over :MHAChunk, with graph
context from :MHADocument -> :Ministry {name:"Home Affairs"} -> ministers.
"""
import os, re, json, math
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv, find_dotenv
from neo4j import GraphDatabase
from google import genai

from glossary import expand_query, annotate_answer

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / "BACKEND" / ".env")

URI = (os.getenv("NEO4J_URI1") or "").strip()
USER = os.getenv("NEO4J_USERNAME1")
PW = os.getenv("NEO4J_PASSWORD1")
DB = os.getenv("NEO4J_DATABASE1")
KEY = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

VOCAB = Path(r"C:\Users\aarya\OneDrive\Documents\Default Project\mha_vocab.json")
VEC_INDEX = "mha_chunk_embeddings_local"
FT_INDEX = "mha_chunk_text_fulltext"

driver = GraphDatabase.driver(URI, auth=(USER, PW), max_transaction_retry_time=120, notifications_min_severity="OFF")
client = genai.Client(api_key=KEY)


def tokenize(t):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", t.lower())


class Embedder:
    def __init__(self):
        v = json.loads(VOCAB.read_text(encoding="utf-8"))
        self.vocab, self.idf = v["vocab"], v["idf"]

    def vec(self, text):
        x = [0.0] * len(self.vocab)
        tf = Counter(tokenize(text))
        for tok, c in tf.items():
            if tok in self.vocab:
                x[self.vocab[tok]] = c * self.idf[self.vocab[tok]]
        n = math.sqrt(sum(a * a for a in x)) or 1.0
        return [a / n for a in x]


embedder = Embedder()


def known_states():
    with driver.session(database=DB) as s:
        return [r["n"] for r in s.run("MATCH (s:StateUT) RETURN s.name AS n")]


def vector_search(q, k, state=None, chapter=None):
    qv = embedder.vec(q)
    where = "AND toLower(node.text) CONTAINS toLower($state)" if state else ""
    if chapter:
        where += " AND toLower(node.chapter) CONTAINS toLower($chapter)"
    with driver.session(database=DB) as s:
        return s.run(f"""
            CALL db.index.vector.queryNodes('{VEC_INDEX}', $k, $v) YIELD node, score
            MATCH (d:MHADocument)-[:HAS_CHUNK]->(node)
            WHERE node.page > 5 AND size(node.text) > 150 {where}
            RETURN node.id AS id, d.title AS title, node.page AS page, node.text AS text,
                   node.breadcrumb AS breadcrumb, score
            ORDER BY score DESC
        """, k=k, v=qv, state=state, chapter=chapter).data()


def fulltext_search(q, k, state=None, chapter=None):
    qq = " ".join(tokenize(q))
    if not qq:
        return []
    where = "AND toLower(node.text) CONTAINS toLower($state)" if state else ""
    if chapter:
        where += " AND toLower(node.chapter) CONTAINS toLower($chapter)"
    with driver.session(database=DB) as s:
        return s.run(f"""
            CALL db.index.fulltext.queryNodes('{FT_INDEX}', $q) YIELD node, score
            MATCH (d:MHADocument)-[:HAS_CHUNK]->(node)
            WHERE node.page > 5 AND size(node.text) > 150 {where}
            RETURN node.id AS id, d.title AS title, node.page AS page, node.text AS text,
                   node.breadcrumb AS breadcrumb, score
            ORDER BY score DESC LIMIT $k
        """, q=qq, k=k, state=state, chapter=chapter).data()


def hybrid(q, k=6):
    states = known_states()
    state = next((s for s in states if s.lower() in q.lower()), None)
    ql = q.lower()
    chapter = None
    if ("police force" in ql or "central armed police" in ql or "capf" in ql
            or any(x in ql for x in ["crpf", "bsf", "cisf", "itbp", "ssb", "assam rifles"])):
        chapter = "Police Forces"
    pool = max(k * 5, 30)
    ft = fulltext_search(q, pool, state, chapter)
    vec = vector_search(q, pool, state, chapter)
    out, seen = [], set()
    for r in ft + vec:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
        if len(out) >= k:
            break
    return out, state


def entity_context(q):
    """Return document-extracted entities for list-type questions."""
    ql = q.lower()
    labels = []
    if any(w in ql for w in ["organisation", "organization", "body", "bodies", "agency", "agencies", "force", "forces", "police"]):
        labels.append("Organization")
    if "scheme" in ql:
        labels.append("Scheme")
    if "committee" in ql or "commission" in ql:
        labels.append("Committee")
    if "state" in ql or "union territor" in ql:
        labels.append("StateUT")
    if "rank" in ql:
        labels.append("Rank")
    if "act" in ql or "policy" in ql:
        labels.append("Policy")
    if not labels:
        return ""
    lines = []
    with driver.session(database=DB) as s:
        for label in labels:
            names = [r["n"] for r in s.run(
                f"MATCH (e:{label})-[:MENTIONED_IN]->(:MHADocument) RETURN DISTINCT e.name AS n ORDER BY n"
            )]
            if names:
                lines.append(f"{label}: " + ", ".join(names))
    return "\n".join(lines)


def graph_context(titles):
    if not titles:
        return ""
    with driver.session(database=DB) as s:
        rows = s.run("""
            MATCH (d:MHADocument)-[:ABOUT_MINISTRY]->(m:Ministry {name:'Home Affairs'})
            WHERE d.title IN $titles
            OPTIONAL MATCH (p:Person)-[:HOLDS]->(m)
            OPTIONAL MATCH (p)-[:HAS_RANK]->(r:Rank)
            RETURN d.title AS title, d.year AS year, m.fullName AS ministry,
                   collect(DISTINCT {name:p.name, rank:r.name}) AS ministers
        """, titles=titles).data()
    lines = []
    for r in rows:
        mins = ", ".join(f"{x['name']} ({x['rank']})" for x in r["ministers"] if x.get("name"))
        lines.append(f"- {r['title']} ({r['year']}) | {r['ministry']} | Ministers: {mins}")
    return "\n".join(lines)


def build_prompt(q, hits, gctx, state, ectx, glossary_note=""):
    ctx = []
    for i, h in enumerate(hits, 1):
        ctx.append(f"[Source {i} | {h['title']} | page {h['page']}]\n{h['text']}")
    passages = "\n\n---\n\n".join(ctx)
    aggregation = bool(re.search(r"\b(most|highest|lowest|least|top|rank|compare|versus|vs)\b", q, re.I))
    extra = ""
    if aggregation:
        extra = ("\nThe question asks for a comparison/ranking. Extract the relevant numbers from the passages, "
                 "compare them explicitly, and state the winner. If the passages do not contain the full data, "
                 "say what is missing instead of guessing.\n")
    if state:
        extra += f"\nThe question is about {state}. Prefer evidence about that state/UT.\n"
    return f"""You are a GraphRAG assistant for the Ministry of Home Affairs, Government of India.

Answer ONLY from the graph context, entity list and passages below. Cite pages like [page 42].
If the answer is not supported, say you don't know. Do not invent numbers.
{extra}
GRAPH CONTEXT:
{gctx or '(no linked ministry found)'}

GRAPH ENTITY LIST (extracted from these documents):
{ectx or '(none)'}

GLOSSARY (acronyms in the question):
{glossary_note or '(none)'}

PASSAGES:
{passages}

QUESTION:
{q}

ANSWER:"""


def answer(q, k=6):
    expanded_q, gmatches = expand_query(q, "Home Affairs")
    hits, state = hybrid(expanded_q, k)
    if not hits:
        return "No relevant chunks found.", hits, ""
    titles = list({h["title"] for h in hits})
    gctx = graph_context(titles)
    ectx = entity_context(q)
    glossary_note = "; ".join(f"{m['acronym']} = {m['expansion']}" for m in gmatches)
    prompt = build_prompt(q, hits, gctx, state, ectx, glossary_note)
    for attempt in range(5):
        try:
            r = client.models.generate_content(model=MODEL, contents=prompt)
            ans, _ = annotate_answer(r.text, "Home Affairs")
            return ans, hits, gctx
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                import time; time.sleep(65)
            else:
                return f"ERROR: {e}", hits, gctx
    return "ERROR: rate limited", hits, gctx
