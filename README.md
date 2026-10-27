# Bharat Praman (भारत प्रमाण)

A civic-tech platform that turns Indian political data and ministry documents into something a normal citizen can actually use — from *"who is my MLA?"* to a ready-to-file RTI request.

## What it does (three parts)

1. **Politician graph search** — search MLAs/MPs and ask multi-hop questions in plain English ("average age of BJP ministers in North India"). Questions are translated to read-only Cypher against a Neo4j graph, with schema guardrails so the AI can't invent facts.
2. **Ministry GraphRAG** — ask questions about Ministry of Education / Home Affairs annual reports. Hybrid retrieval (semantic `e5` embeddings + full-text) over ingested PDF chunks, answered by an LLM with page citations.
3. **RTI generation** — pick a politician and a topic, and get a ready-made, legally-formatted RTI request (draft), downloadable as a PDF.

## Architecture

```
Browser ──► Frontend (HTML/JS)  :5500
                │
                └──► Backend API (FastAPI)  :8000
                        ├── Neo4j Instance01 (politician graph)
                        ├── Neo4j Instance02 (ministry RAG)
                        └── Gemini (text-to-Cypher + RAG answers)

RTI page ──► RTI server (FastAPI)  :8001  ──► Neo4j Instance01
```

- **Port 8000** — main backend (`main.py`): graph search, text-to-Cypher, RAG, glossary, IPC sections.
- **Port 8001** — RTI server (`rti/server.py`): RTI draft generation (separate service).
- **Port 5500** — static frontend served from the repo root.

## Why templates, not just an LLM

Text-to-Cypher uses a **governed template layer** for common questions:

```
intent router → parameterized Cypher → read-only validator → Neo4j
novel phrasing → LLM fallback → same validator → refuse if unsafe
```

- **Determinism** — "how many MLAs have criminal cases?" must return the same correct number every time, not whatever a model improvises.
- **Auditability** — every template is a visible, reviewed Cypher query a judge can read.
- **Latency + cost** — no model call for high-frequency questions.
- **Honest refusal** — questions the schema can't support (gender, "serious" classification, income, future elections) are refused with an explicit reason, never guessed.

The LLM handles *novel* phrasing, but every query — template or LLM — passes the same read-only, schema-bounded validator. The high-confidence intents are parameterized, not hardcoded, deliberately: for counts and asset/case thresholds, we don't want a model improvising.

## Prerequisites

- **Python 3.14** — required. The optional semantic e5 path uses `torch` + `sentence-transformers`, which have **no wheels for Python 3.15 yet**. MHA now defaults to the complete local TF-IDF index + full-text (`MHA_USE_E5=0`); set `MHA_USE_E5=1` only after a full e5 backfill.
- **Two Neo4j instances** (Aura free tier works):
  - Instance01 — politician graph (MLAs, parties, cases, sections, ministries)
  - Instance02 — ministry RAG (`Chunk`/`MHAChunk` nodes)
- **A Gemini API key** (AI Studio free tier) for text-to-Cypher and RAG answer generation.

## Setup

### 1. Configure environment

Copy the examples and fill in real values. There are two env files; the backend loads **both**, and `BACKEND/.env` wins on conflict.

**`.env`** (repo root):
```ini
NEO4J_URI=neo4j+ssc://xxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
GEMINI_API_KEY=your-gemini-key
LLM_MODEL=gemini-3.5-flash-lite
FRONTEND_ORIGIN=http://localhost:5500
```

**`BACKEND/.env`** — holds **both** database instances plus the RAG LLM key:
```ini
# Instance01 (politician graph)
NEO4J_URI=neo4j+ssc://xxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Instance02 (ministry RAG)
NEO4J_URI1=neo4j+ssc://yyyy.databases.neo4j.io
NEO4J_USERNAME1=neo4j
NEO4J_PASSWORD1=your-password
NEO4J_DATABASE1=neo4j

# LLMs
GEMINI_API_KEY=your-gemini-key
LLM_MODEL=gemini-3.5-flash-lite
```

> ⚠️ Never commit these files. They are already in `.gitignore`.

### 2. Install dependencies (on Python 3.14)

```bash
py -3.14 -m pip install fastapi uvicorn neo4j python-dotenv google-genai sentence-transformers pydantic truststore pypdf
```

`sentence-transformers` pulls in `torch` (~2GB) — a one-time cost.

### 3. (Optional) semantic embeddings

The RAG uses `intfloat/multilingual-e5-small` embeddings (384-dim). If the ministry chunks haven't been re-embedded yet, run:

```bash
py -3.14 reembed_e5.py
```

This is a one-time, resumable migration from the old TF-IDF vectors. The model downloads ~100MB on first use.

## Starting the website

Open **three terminals** from the repo root:

### Terminal 1 — backend (required)
```bash
py -3.14 -m uvicorn main:app --host 127.0.0.1 --port 8000
```
(or run `./start_backend.ps1`). Health check: http://127.0.0.1:8000/health

### Terminal 2 — RTI server (needed for the RTI feature)
```bash
py -3.14 -m uvicorn rti.server:app --port 8001
```
RTI page: http://127.0.0.1:8001/rti-page

### Terminal 3 — frontend (serves the static site)
```bash
python -m http.server 5500
```
(or in VS Code: right-click `graphdashboard2.html` → **Open with Live Server**)

### Then open
**http://localhost:5500/graphdashboard2.html**

---

## Project layout

| Path | What it is |
|---|---|
| `main.py` | FastAPI backend — graph search, text-to-Cypher, RAG, glossary, IPC sections |
| `agent.py` | RAG over Ministry of Education (Instance02) |
| `mha_agent.py` | RAG over Ministry of Home Affairs (Instance02) |
| `embeddings.py` | Local `e5` embedding helper (384-dim) |
| `rti/server.py`, `rti/engine.py` | RTI draft generation (port 8001) |
| `ipc_sections.py` | Curated one-line explanations of major IPC sections |
| `glossary.py` | Acronym glossary (expand + annotate) |
| `reembed_e5.py` | One-time migration: TF-IDF → e5 embeddings |
| `chunking.py`, `moe_ingest*.py`, `mha_ingest.py` | PDF → chunks → Neo4j ingestion |
| `MLAs/`, `MPs_everything/` | Scraping / ingestion scripts and parsed data |
| `graphdashboard2.html` | Main frontend dashboard |
| `graph.html`, `node.html`, `ask.html` | Frontend pages (search, node detail, RAG ask) |
| `cypher_templates.py`, `cypher_examples.json` | Text-to-Cypher examples / templates |

## Notes & caveats

- **Python 3.14, not 3.15.** The optional e5 semantic path needs `torch`/`sentence-transformers`; those have no 3.15 wheels. MHA defaults to the local TF-IDF + full-text path (`MHA_USE_E5=0`). Always launch with `py -3.14 -m uvicorn ...`.
- **Data freshness.** Politician data is scraped from MyNeta and reflects the scrape date. See `DOCS/DEMO_ACCURACY.md` for tested graph limits and demo guidance.
- **Text-to-Cypher is read-only and schema-bounded.** The LLM only ever generates `MATCH` queries against a whitelisted schema; it refuses rather than guessing when the graph can't answer.
- **Demo day:** warm the Neo4j instances (free Aura pauses after ~3 days idle), and prefer pre-tested questions.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'sentence_transformers'` | You launched with Python 3.15. Use `py -3.14 -m uvicorn ...` instead of `python -m uvicorn ...`. |
| `/health` returns `503` (Neo4j unreachable) | The free Aura instance paused (after ~3 days idle). Open the Aura console, resume it, then warm it with one query. |
| RAG returns "No relevant chunks found" | Semantic re-embed isn't done yet. Run `py -3.14 reembed_e5.py`. |
| `[Errno 10048]` / "port already in use" | Something is already on that port. Find and stop it: `Get-NetTCPConnection -LocalPort 8000 -State Listen | Select OwningProcess`, then `Stop-Process -Id <PID>`. |
| `GET /v1/models 404` in server logs | Harmless — an LLM client probing the wrong endpoint. Ignore it. |
| Text-to-Cypher returns 400 or a wrong answer | Rephrase, or stick to pre-tested demo questions. See `DOCS/DEMO_ACCURACY.md`. |
| `pip install` of torch/sentence-transformers fails | You're on Python 3.15. Re-run with `py -3.14 -m pip install -r requirements.txt`. |
| Model download is slow (HF warning) | The ~100MB e5 model downloads once from HuggingFace. Slow in some regions; try `$env:HF_ENDPOINT = "https://hf-mirror.com"` first. |
