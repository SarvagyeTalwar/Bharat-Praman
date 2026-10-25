"""RTI endpoints. Run from the repo root:  python3 -m uvicorn rti.server:app --reload --port 8001"""
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
