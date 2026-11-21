"""RTI endpoints. Run from the repo root:  python3 -m uvicorn rti.server:app --reload --port 8001"""
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import engine

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Bharat-Praman RTI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

_driver = None


def driver():
    global _driver
    if _driver is None:
        import truststore
        truststore.inject_into_ssl()
        from dotenv import load_dotenv
        from neo4j import GraphDatabase
        load_dotenv(ROOT / ".env")
        _driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))
    return _driver


def load_person(entity_id):
    from neo4j import READ_ACCESS
    ids = [entity_id] + ([int(entity_id)] if entity_id.isdigit() else [])
    with driver().session(default_access_mode=READ_ACCESS) as s:
        rec = s.run("MATCH (p:Person) WHERE p.entity_id IN $ids "
                    "OPTIONAL MATCH (p)-[:REPRESENTS]->(c) "
                    "RETURN properties(p) AS props, labels(c) AS clabels, properties(c) AS cprops LIMIT 1",
                    ids=ids).single()
    if not rec:
        return None
    return engine.normalize_person(entity_id, rec["props"], rec["clabels"], rec["cprops"])


def person_or_404(entity_id):
    person = load_person(entity_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")
    return person


@app.get("/rti/topics")
def topics():
    return engine.topic_list()


@app.get("/politicians/{entity_id}/rti-details")
def rti_details(entity_id: str):
    return person_or_404(entity_id)


@app.get("/politicians/{entity_id}/rti/{topic_id}")
def rti_for_topic(entity_id: str, topic_id: str, district: Optional[str] = None):
    person = person_or_404(entity_id)
    try:
        return engine.build_response(person, topic_id, district_override=district)
    except engine.RtiError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/politicians/{entity_id}/rti/{topic_id}/suggest")
def suggest(entity_id: str, topic_id: str, q: str = "", district: Optional[str] = None):
    person = person_or_404(entity_id)
    try:
        return engine.suggest(person, topic_id, q, district)
    except engine.RtiError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/rti-page")
def rti_page():
    return FileResponse(Path(__file__).resolve().parent / "rti_page.html")


@app.get("/rti-archive")
@app.get("/rti-documents")
def rti_archive_page():
    archive_file = ROOT / "rti_archive.html"
    if archive_file.exists():
        return FileResponse(archive_file)
    raise HTTPException(status_code=404, detail="Archive page not found")


@app.get("/rti/curated")
@app.get("/curated")
def get_curated_rtis():
    curated_file = ROOT / "rti" / "data" / "curated_rtis.json"
    if curated_file.exists():
        import json
        with open(curated_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ---------- RTI Documents & PDF Access ----------
_rti_records_cache = None


def get_rti_records_index():
    global _rti_records_cache
    if _rti_records_cache is None:
        master_path = ROOT / "rti_scraper" / "rtigram_master.json"
        if master_path.exists():
            import json
            try:
                with open(master_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                _rti_records_cache = {r.get("id"): r for r in records if r.get("id")}
            except Exception:
                _rti_records_cache = {}
        else:
            _rti_records_cache = {}
    return _rti_records_cache


@app.get("/rti/documents/{rti_id}/pdf")
@app.get("/documents/{rti_id}/pdf")
@app.get("/pdfs/{rti_id}.pdf")
@app.get("/pdfs/{rti_id}")
def get_rti_pdf_endpoint(rti_id: str):
    """Serve the PDF for an RTI: streams local file if downloaded, or redirects to cloud storage."""
    pdf_dir = ROOT / "rti_scraper" / "pdfs"
    local_path = pdf_dir / f"{rti_id}.pdf"
    if local_path.exists() and local_path.stat().st_size > 0:
        return FileResponse(local_path, media_type="application/pdf", filename=f"{rti_id}.pdf")

    records = get_rti_records_index()
    record = records.get(rti_id)
    if record:
        remote_url = record.get("admin_pdf_url") or record.get("file_url") or record.get("pdf_url")
        if remote_url:
            return RedirectResponse(url=remote_url, status_code=307)

    raise HTTPException(status_code=404, detail=f"PDF not available for RTI record '{rti_id}'")


@app.get("/rti/documents/{rti_id}")
@app.get("/documents/{rti_id}")
def get_rti_document_meta(rti_id: str):
    """Retrieve full RTI metadata with direct PDF access links."""
    records = get_rti_records_index()
    record = records.get(rti_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"RTI record '{rti_id}' not found")

    pdf_dir = ROOT / "rti_scraper" / "pdfs"
    local_path = pdf_dir / f"{rti_id}.pdf"
    remote_url = record.get("admin_pdf_url") or record.get("file_url") or record.get("pdf_url")

    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "department": record.get("department"),
        "ministry": record.get("ministry"),
        "state": record.get("state"),
        "subject": record.get("subject"),
        "questions": record.get("questions"),
        "response_summary": record.get("response_summary"),
        "response_status": record.get("response_status"),
        "date_filed": record.get("date_filed"),
        "tags": record.get("tags"),
        "has_pdf": bool(remote_url or local_path.exists()),
        "pdf_url": f"/rti/documents/{rti_id}/pdf",
        "remote_pdf_url": remote_url,
        "is_cached_locally": local_path.exists(),
    }
