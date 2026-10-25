# Bharat-Praman
praman of bharat

For Text-to-Cypher behavior, the tested graph limits, data-freshness caveats, and demo guidance, see [DOCS/DEMO_ACCURACY.md](DOCS/DEMO_ACCURACY.md).

## Setup
1. Copy `.env.example` to `.env` (or `BACKEND/.env`) and fill in Neo4j and Gemini credentials.
2. Install dependencies: `pip install -r requirements.txt` (create this file from your environment).
3. Run the API: `uvicorn main:app --reload --port 8000`

## Project layout
- `main.py` — FastAPI backend (graph search + Text-to-Cypher).
- `agent.py` — RAG over the MoE document (Neo4j vector + full-text).
- `MLAs/`, `MPs_everything/` — scraping / ingestion scripts and parsed data.
- `cache/`, `myneta_*_cache/` — generated scrape caches (gitignored).
- `graph*.html`, `node.html` — frontend prototypes.
