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

VEC_INDEX = "mha_chunk_embeddings_e5"
LOCAL_VEC_INDEX = "mha_chunk_embeddings_local"
# e5 is opt-in: torch/model loading is memory-heavy on the demo machine, and the
# e5 index was historically empty. The complete TF-IDF index is the default.
USE_E5 = os.getenv("MHA_USE_E5", "0").strip().lower() in {"1", "true", "yes"}
LOCAL_VOCAB_PATH = Path(os.getenv("MHA_VOCAB_PATH", str(HERE / "data" / "mha_vocab.json")))
FT_INDEX = "mha_chunk_text_fulltext"
_LOCAL_VOCAB = None

driver = GraphDatabase.driver(URI, auth=(USER, PW), max_transaction_retry_time=120, notifications_min_severity="OFF")
client = genai.Client(api_key=KEY)


def tokenize(t):
    return re.findall(r"[A-Za-z0-9\u0900-\u097f]+", t.lower())


def known_states():
    with driver.session(database=DB) as s:
        return [r["n"] for r in s.run("MATCH (s:StateUT) RETURN s.name AS n")]


def _where(state=None, chapter=None, year=None):
    """Shared retrieval filters. Page 3+ keeps the front-matter org chapters."""
    clauses = ["node.page >= 3", "size(node.text) > 150"]
    if state:
        clauses.append("toLower(node.text) CONTAINS toLower($state)")
    if chapter:
        clauses.append("toLower(node.chapter) CONTAINS toLower($chapter)")
    if year:
        clauses.append("d.title CONTAINS $year")
    return " AND ".join(clauses)


def _vector_query(index_name, vector, k, state=None, chapter=None, year=None):
    params = {"k": k, "v": vector}
    if state:
        params["state"] = state
    if chapter:
        params["chapter"] = chapter
    if year:
        params["year"] = year
    with driver.session(database=DB) as s:
        return s.run(f"""
            CALL db.index.vector.queryNodes('{index_name}', $k, $v) YIELD node, score
            MATCH (d:MHADocument)-[:HAS_CHUNK]->(node)
            WHERE {_where(state, chapter, year)}
            RETURN node.id AS id, d.title AS title, node.page AS page, node.text AS text,
                   node.breadcrumb AS breadcrumb, score
            ORDER BY score DESC
        """, **params).data()


def _local_query_vector(text):
    """TF-IDF query vector matching the populated :MHAChunk.embedding index."""
    global _LOCAL_VOCAB
    if _LOCAL_VOCAB is None:
        try:
            data = json.loads(LOCAL_VOCAB_PATH.read_text(encoding="utf-8"))
            _LOCAL_VOCAB = (data.get("vocab") or {}, data.get("idf") or [])
        except Exception:
            _LOCAL_VOCAB = ({}, [])
    vocab, idf = _LOCAL_VOCAB
    if not vocab:
        return None
    v = [0.0] * len(vocab)
    for tok, count in Counter(tokenize(text)).items():
        idx = vocab.get(tok)
        if idx is not None and idx < len(idf):
            v[idx] = count * idf[idx]
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def vector_search(q, k, state=None, chapter=None, year=None):
    # Merge semantic e5 (opt-in) with the complete TF-IDF index. The e5 index
    # may be partially backfilled; merging means missing e5 chunks do not create
    # a silent blind spot, while the semantic hits still contribute when present.
    rows = []
    if USE_E5:
        try:
            from embeddings import embed_query
            rows = _vector_query(VEC_INDEX, embed_query(q), k, state, chapter, year)
        except Exception:
            rows = []
    local = _local_query_vector(q)
    if local:
        rows += _vector_query(LOCAL_VEC_INDEX, local, k, state, chapter, year)
    return rows


def fulltext_search(q, k, state=None, chapter=None, year=None):
    qq = " ".join(tokenize(q))
    if not qq:
        return []
    params = {"q": qq, "k": k}
    if state:
        params["state"] = state
    if chapter:
        params["chapter"] = chapter
    if year:
        params["year"] = year
    with driver.session(database=DB) as s:
        return s.run(f"""
            CALL db.index.fulltext.queryNodes('{FT_INDEX}', $q) YIELD node, score
            MATCH (d:MHADocument)-[:HAS_CHUNK]->(node)
            WHERE {_where(state, chapter, year)}
            RETURN node.id AS id, d.title AS title, node.page AS page, node.text AS text,
                   node.breadcrumb AS breadcrumb, score
            ORDER BY score DESC LIMIT $k
        """, **params).data()


def _rrf(fulltext_hits, vector_hits, k):
    """Reciprocal rank fusion: neither retriever gets to monopolise the context."""
    scores, rows = {}, {}
    for rank, r in enumerate(fulltext_hits):
        scores[r["id"]] = scores.get(r["id"], 0.0) + 1.0 / (60 + rank)
        rows[r["id"]] = r
    for rank, r in enumerate(vector_hits):
        scores[r["id"]] = scores.get(r["id"], 0.0) + 1.0 / (60 + rank)
        rows[r["id"]] = r
    return sorted(rows.values(), key=lambda r: scores[r["id"]], reverse=True)[:k]


def hybrid(q, k=8):
    states = known_states()
    state = next((s for s in states if s.lower() in q.lower()), None)
    ql = q.lower()
    chapter = None
    if ("police force" in ql or "central armed police" in ql or "capf" in ql
            or any(x in ql for x in ["crpf", "bsf", "cisf", "itbp", "ssb", "assam rifles"])):
        chapter = "Police Forces"
    pool = max(k * 5, 30)
    years = sorted(set(re.findall(r"20\d{2}-\d{2}", q)))
    ft, vec = [], []
    # For comparison questions, pull evidence from each report year separately.
    if years:
        for y in years:
            ft += fulltext_search(q, 12, None, chapter, y)
            vec += vector_search(q, 12, None, chapter, y)
    # Always add the global pool so single-year and topic questions still work.
    ft += fulltext_search(q, pool, None, chapter)
    vec += vector_search(q, pool, None, chapter)
    # State is returned for the prompt, but not used as a hard text filter:
    # "Jammu & Kashmir" vs "Jammu and Kashmir" was silently dropping the best chunks.
    return _rrf(ft, vec, k), state


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


def expand_neighbors(hits, hops=4, max_add=6):
    """Pull the chunks immediately after a hit so split lists/tables stay together."""
    seen = {h["id"] for h in hits}
    out = list(hits)
    added = 0
    for h in hits[:2]:
        if added >= max_add:
            break
        with driver.session(database=DB) as s:
            rows = s.run(f"""
                MATCH (d:MHADocument)-[:HAS_CHUNK]->(c:MHAChunk {{id: $id}})
                MATCH (c)-[:NEXT*1..{hops}]->(n:MHAChunk)
                MATCH (d)-[:HAS_CHUNK]->(n)
                RETURN n.id AS id, d.title AS title, n.page AS page, n.text AS text,
                       n.breadcrumb AS breadcrumb, 0.0 AS score
                ORDER BY n.page, n.idx
                LIMIT {max_add - added}
            """, id=h["id"]).data()
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                out.append(r)
                added += 1
    return out


DOMAIN_EXPANSIONS = {
    "narcotic": "NCB NDPS Narcotics Control Bureau drug seizure",
    "ndps": "NCB Narcotics Control Bureau drug seizure",
    "drug": "NCB NDPS Narcotics Control Bureau seizure",
    "capf": "BSF CRPF CISF ITBP SSB Assam Rifles battalions sanctioned strength",
    "central armed police": "BSF CRPF CISF ITBP SSB Assam Rifles battalions sanctioned strength",
}


def content_query(q):
    """Strip citation boilerplate so the TOC page does not outrank the content."""
    s = re.sub(r"(?i)^according to\s+", "", q)
    s = re.sub(r"(?i)^what does\s+", "", s)
    s = re.sub(r"(?i)\s+say about\s+", " ", s)
    s = re.sub(r"(?i)\bannual report(s)?\b", " ", s)
    s = re.sub(r"(?i)^the\s+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,.")


def expand_domain(q):
    ql = q.lower()
    for key, extra in DOMAIN_EXPANSIONS.items():
        if key in ql:
            return f"{q} {extra}"
    return q


def answer(q, k=8):
    expanded_q, gmatches = expand_query(q, "Home Affairs")
    hits, state = hybrid(expand_domain(content_query(expanded_q)), k)
    if any(w in q.lower() for w in ("division", "department", "organisation", "organization",
                                    "structure", "list", "schemes")):
        hits = expand_neighbors(hits)
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
