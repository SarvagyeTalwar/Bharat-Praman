# Bharat Praman (भारत प्रमाण)

**Live Demo:** https://bharat-praman-production.up.railway.app  
**Full Viva & Architecture Guide:** [`BHARAT_PRAMAN_GUIDE.md`](BHARAT_PRAMAN_GUIDE.md)

A civic-tech platform that turns Indian political data and Union Ministry documents into something a normal citizen can actually use — from *"who is my MLA?"* and Union Budget BE-vs-RE audits to a ready-to-file RTI Act 2005 request.

## What it does (four parts)

1. **Politician graph search** — search 540 active Lok Sabha MPs and 5,691 MLAs across 38,755 nodes / 104,548 relationships in plain English. Deterministic templates + DeepSeek V3 (`deepseek-chat`) Text-to-Cypher translate queries into read-only Cypher with strict schema guardrails.
2. **Ministry GraphRAG** — hybrid retrieval (`BAAI/bge-small-en-v1.5` 384-dim vectors in `bge_chunk_embeddings` + Lucene full-text RRF) across 49 Union Ministry & Budget PDFs (`44,453` chunks), synthesized by DeepSeek V3/R1 with page citations and linked directly to accountable Cabinet Ministers.
3. **Graph Analytics (GDS) & Wealth Trajectories** — MP criminal-case Jaccard similarity, party-switcher PageRank/Community detection, and multi-election net-worth growth trajectories.
4. **RTI generation** — pick a politician and a topic, and get a legally formatted Section 6(1) RTI Act 2005 draft with exact CPIO routing.

## Architecture

```
Production (Railway single-port Docker):
  Browser ──► https://bharat-praman-production.up.railway.app (FastAPI :$PORT)
                ├── Unified UI (/ -> graphdashboard2.html, node.html, mps.html, rti/)
                ├── Rate Limiter (15 RPM AI/RAG, 90 RPM API) + Read-Only Cypher AST Guard
                ├── Neo4j Instance01 (politician graph) + Instance02 (bge_chunk_embeddings GraphRAG)
                └── DeepSeek V3/R1 primary (Gemini 3.5 Flash-Lite fallback)

Local multi-port (`python start_all.py`):
  Frontend (:5500) ──► Backend API (:8000) & RTI service (:8001)
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

- **Python 3.12–3.14** — Docker/Railway runs Python 3.12 (`Dockerfile` installs CPU-only `torch` and pre-bakes `BAAI/bge-small-en-v1.5`); locally tested on Python 3.14 (`py -3.14 start_all.py`).
- **Two Neo4j instances** (Aura free tier works):
  - Instance01 — politician graph (MLAs, MPs, parties, cases, sections, ministries)
  - Instance02 — ministry RAG (`Document`, `Chunk` with `bge_chunk_embeddings` + `chunk_fulltext`)
- **DeepSeek (`DEEPSEEK_API_KEY`)** primary + **Gemini (`GEMINI_API_KEY`)** fallback for text-to-Cypher and RAG answer synthesis.

## Quick start (portable)

Requires Python 3.13+ (tested on 3.14) and network access to Neo4j Aura + Gemini.

```bash
python -m pip install -r requirements.txt
python start_all.py
```

Then open `http://127.0.0.1:5500/graphdashboard2.html`.

`start_all.py` binds all three services to `0.0.0.0`, so another machine on the
same network can use `http://<this-machine-ip>:5500/graphdashboard2.html`.
Override ports with `API_PORT`, `RTI_PORT`, `WEB_PORT`, and the bind address
with `BP_HOST`.

The runtime uses the local TF-IDF indexes; `torch`/`sentence-transformers` are
not required. Vocabulary files live in `data/` and can be overridden with
`MOE_VOCAB_PATH` and `MHA_VOCAB_PATH`.

## Setup

### Instance02 PDF chunking

The Education `:Document` / `:Chunk` ingestion uses page-aware, heading-aware passages (about 320 lexical tokens with up to 45 tokens of overlap). Each chunk stores its starting/ending PDF pages and detected headings. PDFs up to 60 pages use PyMuPDF4LLM Markdown extraction, and detected Markdown tables repeat their headers when split across chunks. Larger reports use fast per-page text extraction; their tables can be flattened, so numeric table answers may need a dedicated layout/table extraction pass. Scanned pages and garbled embedded text can need OCR or manual review. Preview a PDF or folder without writing chunks:

```powershell
python ingest_bulk.py "C:\path\to\pdf-or-folder" --ministry Education --dry-run
```

To replace the old chunks and vectors after reviewing the preview, use `--rechunk`:

```powershell
python ingest_bulk.py "C:\path\to\pdf-or-folder" --ministry Education --rechunk
```

This writes versioned chunks first, then removes the old derived chunks after the new batches are stored. The PDF source files are required; legacy `:Document` nodes do not retain reliable local paths. Restart the RAG service after updating its code. MHA uses a separate `:MHAChunk` pipeline and is not changed by this command.

### 1. Configure environment

Copy the examples and fill in real values. There are two env files; the backend loads **both**, and `BACKEND/.env` wins on conflict.

**`.env`** (repo root) — copy from [`.env.example`](.env.example):
```ini
NEO4J_URI=neo4j+ssc://xxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
GEMINI_API_KEY=your-gemini-key
LLM_MODEL=gemini-3.5-flash-lite
FRONTEND_ORIGIN=http://localhost:5500
```

**`BACKEND/.env`** — copy from [`.env.example`](BACKEND/.env.example). Holds **both** database instances plus the RAG LLM key:
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
python -m pip install -r requirements.txt
```

This installs only the runtime packages (fastapi, uvicorn, neo4j, python-dotenv, google-genai, pydantic, truststore). `torch` / `sentence-transformers` are **not** needed unless you use the optional semantic e5 path (see step 3).

### 3. (Optional) semantic embeddings

The RAG uses `intfloat/multilingual-e5-small` embeddings (384-dim). If the ministry chunks haven't been re-embedded yet, run:

```bash
py -3.14 reembed_e5.py
```

This is a one-time, resumable migration from the old TF-IDF vectors. The model downloads ~100MB on first use.

## For the Judges — how to run Bharat Praman

If the judges get the repo and want to run the app themselves, here is the complete path:

### 1. Requirements
- **Python 3.14** (recommended; `py -3.14` launcher is used in docs).
- Internet access to **Neo4j Aura** and **Gemini** (Google AI Studio).

### 2. Install dependencies
```bash
python -m pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp BACKEND/.env.example BACKEND/.env
```
Then edit `BACKEND/.env` and fill in real values:
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` — Neo4j instance **01** (politician graph)
- `NEO4J_URI1`, `NEO4J_USERNAME1`, `NEO4J_PASSWORD1`, `NEO4J_DATABASE1` — Neo4j instance **02** (ministry RAG)
- `GEMINI_API_KEY`, `GEMINI_API_KEY1`, `LLM_MODEL`, `LLM_MODEL1` — Gemini keys/models

Full templates: [`.env.example`](.env.example) and [`BACKEND/.env.example`](BACKEND/.env.example).

### 4. Start the app (one command)
```bash
python start_all.py
```

This starts:
- Backend API → `http://127.0.0.1:8000` (health: `http://127.0.0.1:8000/health`)
- RTI server → `http://127.0.0.1:8001` (RTI page: `http://127.0.0.1:8001/rti-page`)
- Frontend → `http://127.0.0.1:5500`

### 5. Open in browser
```
http://127.0.0.1:5500/graphdashboard2.html
```

### What the judges need before step 3
- A **Neo4j Aura** free-tier account with both databases created and loaded (or a local Neo4j instance + data).
- A **Gemini API key** (free tier from Google AI Studio).

> Note: the live demo used the author's Neo4j Aura instances. A public GitHub repo can't embed live database access, so judges must supply their own Neo4j credentials (and Gemini key) to run the full stack end-to-end.

---

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

> 💡 **Easiest way:** just run `python start_all.py` from the repo root — it starts the backend, RTI server, and frontend together, then prints the URLs. (You can also use the three-terminal method above.)

---

## Project layout

| Path | What it is |
|---|---|
| `main.py` | FastAPI backend — graph search, text-to-Cypher, RAG, glossary, IPC sections |
| `agent.py` | RAG over Ministry of Education (Instance02) |
| `mha_agent.py` | RAG over Ministry of Home Affairs (Instance02) |
| `embeddings.py` | Local TF-IDF / e5 embedding helper |
| `rti/server.py`, `rti/engine.py` | RTI draft generation (port 8001) |
| `ipc_sections.py` | Curated one-line explanations of major IPC sections |
| `glossary.py` | Acronym glossary (expand + annotate) |
| `reembed_e5.py` | One-time migration: TF-IDF → e5 embeddings |
| `chunking.py`, `moe_ingest*.py`, `mha_ingest.py` | PDF → chunks → Neo4j ingestion |
| `MLAs/`, `MPs_everything/` | Scraping / ingestion scripts and parsed data |
| `data/` | Local TF-IDF vocab files (`moe_vocab.json`, `mha_vocab.json`) |
| `start_all.py`, `start_backend.ps1` | One-command / Windows launchers |
| `.env.example`, `BACKEND/.env.example` | Environment templates (real `.env` files are gitignored) |
| `requirements.txt` | Runtime Python dependencies |
| `graphdashboard2.html` | Main frontend dashboard |
| `graph.html`, `node.html`, `ask.html` | Frontend pages (search, node detail, RAG ask) |
| `bp-config.js` | Host-aware frontend API config |
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
