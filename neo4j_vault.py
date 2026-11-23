"""Neo4j-Powered Multi-Tenant Vector Vault & Document Knowledge Graph.

Ingests user documents into Neo4j under a dedicated multi-tenant schema:
(:User {id})-[:OWNS]->(:UserDocument {id, title, filename})-[:HAS_CHUNK]->(:UserChunk {id, text, embedding_bge, page, section})
(:UserChunk)-[:NEXT]->(:UserChunk)

Provides real-time structure-aware chunking (chunking_utils.py), 384-d BGE
vectorization (embeddings.py), and hybrid vector + fulltext retrieval.
"""
from __future__ import annotations

import logging
import os
import uuid
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

import chunking_utils
import embeddings

HERE = Path(__file__).resolve().parent
load_dotenv(find_dotenv())
load_dotenv(HERE / ".env")
load_dotenv(HERE / "BACKEND" / ".env")

logger = logging.getLogger("uvicorn.error")

NEO4J_URI = (os.getenv("NEO4J_URI1") or os.getenv("NEO4J_URI") or "").strip()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME1") or os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD1") or os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE1") or os.getenv("NEO4J_DATABASE")

_driver = None
_indexes_ensured = False


def get_driver():
    global _driver
    if _driver is None and NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_connection_pool_size=int(os.getenv("NEO4J_MAX_POOL_SIZE", "50")),
            max_connection_lifetime=3600,
            connection_acquisition_timeout=30.0,
            keep_alive=True,
        )
    return _driver


def ensure_user_indexes():
    """Ensure constraints and vector/fulltext indexes for User and UserChunk exist."""
    global _indexes_ensured
    if _indexes_ensured:
        return
    drv = get_driver()
    if not drv:
        logger.warning("Neo4j driver unavailable; skipping user index check.")
        return

    queries = [
        "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
        "CREATE CONSTRAINT user_doc_id_unique IF NOT EXISTS FOR (d:UserDocument) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT user_chunk_id_unique IF NOT EXISTS FOR (c:UserChunk) REQUIRE c.id IS UNIQUE",
        """
        CREATE VECTOR INDEX user_chunk_embeddings IF NOT EXISTS
        FOR (c:UserChunk) ON (c.embedding_bge)
        OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
        """,
        """
        CREATE FULLTEXT INDEX user_chunk_fulltext IF NOT EXISTS
        FOR (c:UserChunk) ON EACH [c.text, c.section, c.breadcrumb]
        """,
    ]

    try:
        with drv.session(database=NEO4J_DATABASE) as session:
            for q in queries:
                try:
                    session.run(q).consume()
                except Exception as exc:
                    logger.debug("Neo4j index statement notice: %s", exc)
        _indexes_ensured = True
        logger.info("Neo4j User Vault constraints and vector indexes verified.")
    except Exception as exc:
        logger.warning("ensure_user_indexes notice: %s", exc)


def _extract_pages_from_pdf(pdf_bytes: bytes) -> List[tuple[int, str]]:
    """Extract page number and text tuples from PDF binary."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for i in range(len(doc)):
            page_text = doc[i].get_text("text").strip()
            if page_text:
                pages.append((i + 1, page_text))
        return pages or [(1, "Empty document")]
    except Exception as exc:
        logger.warning("fitz PDF extraction failed, falling back to pypdf: %s", exc)

    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                pages.append((i + 1, txt.strip()))
        return pages or [(1, "Empty document")]
    except Exception as exc:
        logger.error("pypdf extraction failed: %s", exc)
        return [(1, "Could not extract text from document.")]


def _split_text_to_pseudo_pages(text: str, chars_per_page: int = 1600) -> List[tuple[int, str]]:
    """Split plain text or markdown into pseudo-pages for structured chunking."""
    lines = text.splitlines(keepends=True)
    pages = []
    curr = []
    curr_len = 0
    p_num = 1
    for line in lines:
        curr.append(line)
        curr_len += len(line)
        if curr_len >= chars_per_page:
            p_text = "".join(curr).strip()
            if p_text:
                pages.append((p_num, p_text))
                p_num += 1
            curr = []
            curr_len = 0
    if curr:
        p_text = "".join(curr).strip()
        if p_text:
            pages.append((p_num, p_text))
    return pages or [(1, text[:chars_per_page])]


def index_user_document(
    user_id: str,
    user_email: str,
    title: str,
    filename: str,
    text: str = "",
    pdf_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Structure-aware chunking, BGE vectorization, and Neo4j commit for a private user document."""
    ensure_user_indexes()
    drv = get_driver()
    if not drv:
        raise RuntimeError("Neo4j database connection unavailable.")

    doc_id = f"udoc_{uuid.uuid4().hex[:12]}"
    clean_title = (title or filename or "Private Document").strip()

    # 1. Page extraction
    if pdf_bytes:
        page_tuples = _extract_pages_from_pdf(pdf_bytes)
        full_text = "\n\n".join(p[1] for p in page_tuples)
    else:
        full_text = text.strip()
        page_tuples = _split_text_to_pseudo_pages(full_text)

    # 2. Structure-aware chunking (chunking_utils.py)
    raw_chunks = chunking_utils.chunk_pages(
        page_tuples,
        max_tokens=320,
        overlap_tokens=40,
        doc_title=clean_title,
        stamp_context_in_text=True,
    )

    if not raw_chunks:
        raw_chunks = [{
            "text": full_text[:1500],
            "page_start": 1,
            "page_end": 1,
            "section": "General",
            "breadcrumb": f"Doc: {clean_title}",
            "unit": None,
        }]

    # 3. Vectorization via BGE-small-en-v1.5 (embeddings.py)
    texts_to_embed = [c["text"] for c in raw_chunks]
    embeddings_list = embeddings.embed_texts(texts_to_embed)

    chunk_payloads = []
    for idx, (chunk, emb) in enumerate(zip(raw_chunks, embeddings_list)):
        chunk_payloads.append({
            "id": f"uchk_{uuid.uuid4().hex[:14]}",
            "chunkIndex": idx,
            "page": chunk.get("page_start", 1),
            "page_end": chunk.get("page_end", 1),
            "section": chunk.get("section") or "Body",
            "breadcrumb": chunk.get("breadcrumb") or f"Doc: {clean_title} | Page {chunk.get('page_start', 1)}",
            "text": chunk["text"],
            "unit": chunk.get("unit"),
            "embedding": emb,
        })

    # 4. Ingest into Neo4j in a single transaction
    cypher_ingest = """
    MERGE (u:User {id: $user_id})
      ON CREATE SET u.email = $user_email, u.tier = 'premium', u.createdAt = timestamp()
      ON MATCH SET u.tier = 'premium'
    CREATE (d:UserDocument {
      id: $doc_id,
      title: $title,
      filename: $filename,
      chars: $chars,
      chunkCount: size($chunks),
      uploadedAt: timestamp()
    })
    CREATE (u)-[:OWNS]->(d)
    WITH d
    UNWIND $chunks AS chk
    CREATE (c:UserChunk {
      id: chk.id,
      userId: $user_id,
      docId: $doc_id,
      chunkIndex: chk.chunkIndex,
      page: chk.page,
      page_end: chk.page_end,
      section: chk.section,
      breadcrumb: chk.breadcrumb,
      unit: chk.unit,
      text: chk.text,
      embedding_bge: chk.embedding
    })
    CREATE (d)-[:HAS_CHUNK]->(c)
    """

    cypher_link_next = """
    MATCH (d:UserDocument {id: $doc_id})-[:HAS_CHUNK]->(c:UserChunk)
    WITH c ORDER BY c.chunkIndex ASC
    WITH collect(c) AS chunk_list
    FOREACH (i IN range(0, size(chunk_list)-2) |
      FOREACH (c1 IN [chunk_list[i]] |
        FOREACH (c2 IN [chunk_list[i+1]] |
          MERGE (c1)-[:NEXT]->(c2)
        )
      )
    )
    """

    with drv.session(database=NEO4J_DATABASE) as session:
        session.run(
            cypher_ingest,
            user_id=user_id,
            user_email=user_email,
            doc_id=doc_id,
            title=clean_title,
            filename=filename or "document.pdf",
            chars=len(full_text),
            chunks=chunk_payloads,
        ).consume()

        session.run(cypher_link_next, doc_id=doc_id).consume()

    return {
        "status": "ok",
        "doc_id": doc_id,
        "title": clean_title,
        "filename": filename,
        "chunk_count": len(chunk_payloads),
        "chars": len(full_text),
        "created_at": time.time(),
    }


def search_user_vault(user_id: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Query user's private Neo4j UserChunk vector index using BGE-small embeddings."""
    ensure_user_indexes()
    drv = get_driver()
    if not drv or not user_id:
        return []

    try:
        query_vec = embeddings.embed_query(query)
    except Exception as exc:
        logger.warning("embed_query failed in search_user_vault: %s", exc)
        return []

    pool = max(k * 4, 20)
    cypher = """
    CALL db.index.vector.queryNodes('user_chunk_embeddings', $pool, $v)
    YIELD node, score
    WHERE node.userId = $user_id
    MATCH (d:UserDocument {id: node.docId})
    OPTIONAL MATCH (node)-[:NEXT]->(nxt:UserChunk)
    RETURN node.id AS id,
           d.title AS title,
           d.filename AS file,
           'Private Vault' AS ministry,
           'User Dossier' AS year,
           coalesce(node.page, 1) AS page,
           node.page_end AS page_end,
           coalesce(node.section, 'General') AS section,
           node.breadcrumb AS breadcrumb,
           node.text AS text,
           nxt.text AS next_text,
           score,
           true AS is_private_byod
    ORDER BY score DESC
    LIMIT $k
    """

    try:
        with drv.session(database=NEO4J_DATABASE) as session:
            rows = session.run(cypher, pool=pool, v=query_vec, user_id=user_id, k=k).data()
            return rows
    except Exception as exc:
        logger.warning("search_user_vault failed: %s", exc)
        # Fallback to direct label scan if index query has issues
        try:
            cypher_scan = """
            MATCH (u:User {id: $user_id})-[:OWNS]->(d:UserDocument)-[:HAS_CHUNK]->(c:UserChunk)
            WHERE toLower(c.text) CONTAINS toLower($q)
            RETURN c.id AS id, d.title AS title, d.filename AS file, 'Private Vault' AS ministry,
                   'User Dossier' AS year, c.page AS page, c.section AS section,
                   c.breadcrumb AS breadcrumb, c.text AS text, 0.9 AS score, true AS is_private_byod
            LIMIT $k
            """
            with drv.session(database=NEO4J_DATABASE) as session:
                return session.run(cypher_scan, user_id=user_id, q=query[:40], k=k).data()
        except Exception:
            return []


def list_user_documents(user_id: str) -> List[Dict[str, Any]]:
    """List all private documents vaulted in Neo4j for a user."""
    drv = get_driver()
    if not drv or not user_id:
        return []

    cypher = """
    MATCH (u:User {id: $user_id})-[:OWNS]->(d:UserDocument)
    RETURN d.id AS doc_id,
           d.title AS title,
           d.filename AS filename,
           d.chars AS chars,
           coalesce(d.chunkCount, 0) AS chunk_count,
           d.uploadedAt AS uploaded_at
    ORDER BY d.uploadedAt DESC
    """
    try:
        with drv.session(database=NEO4J_DATABASE) as session:
            return session.run(cypher, user_id=user_id).data()
    except Exception as exc:
        logger.warning("list_user_documents failed: %s", exc)
        return []


def delete_user_document(user_id: str, doc_id: str) -> bool:
    """Delete a user document and all its chunks from Neo4j."""
    drv = get_driver()
    if not drv or not user_id or not doc_id:
        return False

    cypher = """
    MATCH (u:User {id: $user_id})-[:OWNS]->(d:UserDocument {id: $doc_id})
    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:UserChunk)
    DETACH DELETE c, d
    RETURN count(d) AS deleted_docs
    """
    try:
        with drv.session(database=NEO4J_DATABASE) as session:
            res = session.run(cypher, user_id=user_id, doc_id=doc_id).single()
            return bool(res and res["deleted_docs"] > 0)
    except Exception as exc:
        logger.error("delete_user_document failed: %s", exc)
        return False
