import os, re, json, subprocess, time
from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO, "BACKEND", ".env"))

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
pwd = os.getenv("NEO4J_PASSWORD")
db = os.getenv("NEO4J_DATABASE") or None

print("1. Extracting 2,915 RTI records from commit a650730...")
master_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rtigram_master.json")
with open(master_path, "r", encoding="utf-8") as _f:
    records = json.load(_f)
print(f"   Loaded {len(records)} RTI records.")

driver = GraphDatabase.driver(uri, auth=(user, pwd))
driver.verify_connectivity()

# Fetch all MPs from Instance 01 so we can match MP names mentioned in RTI titles/subjects
mp_rows, _, _ = driver.execute_query(
    "MATCH (p:Person:MP) WHERE p.name IS NOT NULL RETURN elementId(p) AS eid, p.name AS name",
    database_=db,
    routing_="r",
)
print(f"2. Fetched {len(mp_rows)} MPs from Neo4j Instance 01 for entity linking.")

# Build clean name tokens for exact full-name and distinctive last-name matching
mp_exact = {}
mp_by_token = {}
COMMON_TOKENS = {
    "kumar", "singh", "sharma", "verma", "rao", "reddy", "patel", "yadav", "devi",
    "prasad", "lal", "ram", "das", "khan", "ali", "ahmed", "roy", "sen", "gupta",
    "mishra", "pandey", "tiwari", "dubey", "joshi", "nair", "menon", "pillai",
    "choudhary", "chaudhary", "patil", "deshmukh", "pawara", "shinde", "chavan",
    "rathore", "chauhan", "thakur", "meena", "mundra", "mandal", "majhi", "murmu",
    "sooren", "soren", "isku", "gandhi", "modi"
}
for r in mp_rows:
    name = (r["name"] or "").strip()
    if len(name) < 4:
        continue
    mp_exact[name.lower()] = name
    parts = [p for p in re.split(r"\s+", name) if len(p) >= 6 and p.lower() not in COMMON_TOKENS]
    for p in parts:
        mp_by_token.setdefault(p.lower(), []).append(name)

# Normalize authority name
def norm_dept(dept):
    d = (dept or "").strip()
    if not d:
        return "Central Public Information Officer (CPIO)"
    if "लोक सभा" in d or "lok sabha" in d.lower() or "सूचना प्रकोष्ठ" in d:
        return "Lok Sabha Secretariat (Information Cell)"
    if "राज्य सभा" in d or "rajya sabha" in d.lower():
        return "Rajya Sabha Secretariat"
    return d[:140]

batch_items = []
linked_mp_count = 0
for r in records:
    rid = str(r.get("id") or "").strip()
    if not rid:
        continue
    title = (r.get("title") or "RTI Application").strip()
    subject = (r.get("subject") or "").strip()
    dept = norm_dept(r.get("department"))
    raw_dept = (r.get("department") or "").strip()
    state = (r.get("state") or "Central Government").strip()
    questions = [str(q).strip() for q in (r.get("questions") or []) if q][:6]
    summary = (r.get("response_summary") or "").strip()[:1500]
    status = (r.get("response_status") or "partial_response").strip()
    date_filed = str(r.get("date_filed") or "")[:10]
    pdf_url = (r.get("admin_pdf_url") or r.get("file_url") or "").strip()
    tags = [str(t).strip() for t in (r.get("tags") or []) if t][:8]

    # Match MP name if explicitly mentioned in title/subject
    hay = f"{title} {subject}"
    hay_low = hay.lower()
    matched_mps = []
    for full_low, orig_name in mp_exact.items():
        if full_low in hay_low:
            matched_mps.append(orig_name)
    if not matched_mps and re.search(r"\b(?:mp|lok sabha|shri|smt)\b", hay_low):
        words = set(re.findall(r"[A-Za-z]{6,}", hay_low))
        for w in words:
            cands = mp_by_token.get(w)
            if cands and len(cands) == 1:
                matched_mps.append(cands[0])
    matched_mps = list(dict.fromkeys(matched_mps))[:3]
    if matched_mps:
        linked_mp_count += 1

    batch_items.append({
        "id": rid,
        "name": title,
        "title": title,
        "department": dept,
        "raw_department": raw_dept,
        "state": state,
        "subject": subject[:600],
        "questions": questions,
        "response_summary": summary,
        "response_status": status,
        "date_filed": date_filed,
        "admin_pdf_url": pdf_url,
        "tags": tags,
        "matched_mps": matched_mps,
    })

print(f"3. Prepared {len(batch_items)} clean RTI items ({linked_mp_count} linked to specific sitting MPs).")

# Create uniqueness constraint on RTIRecord.id and PublicAuthority.name
driver.execute_query("CREATE CONSTRAINT rti_record_id IF NOT EXISTS FOR (r:RTIRecord) REQUIRE r.id IS UNIQUE", database_=db, routing_="w")
driver.execute_query("CREATE CONSTRAINT pub_auth_name IF NOT EXISTS FOR (a:PublicAuthority) REQUIRE a.name IS UNIQUE", database_=db, routing_="w")

INGEST_CYPHER = """
UNWIND $batch AS item
MERGE (r:RTIRecord {id: item.id})
SET r.name = item.name,
    r.title = item.title,
    r.department = item.department,
    r.raw_department = item.raw_department,
    r.state = item.state,
    r.subject = item.subject,
    r.questions = item.questions,
    r.response_summary = item.response_summary,
    r.response_status = item.response_status,
    r.date_filed = item.date_filed,
    r.admin_pdf_url = item.admin_pdf_url,
    r.tags = item.tags
MERGE (a:PublicAuthority {name: item.department})
MERGE (r)-[:FILED_TO]->(a)
WITH r, item
OPTIONAL MATCH (st:State)
WHERE toLower(st.name) = toLower(item.state)
FOREACH (_ IN CASE WHEN st IS NOT NULL THEN [1] ELSE [] END |
  MERGE (r)-[:IN_STATE]->(st)
)
WITH r, item
UNWIND (CASE WHEN size(item.matched_mps) > 0 THEN item.matched_mps ELSE [null] END) AS mp_name
OPTIONAL MATCH (p:Person:MP)
WHERE mp_name IS NOT NULL AND p.name = mp_name
FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END |
  MERGE (r)-[:FILED_ABOUT]->(p)
)
"""

t0 = time.time()
CHUNK = 400
for i in range(0, len(batch_items), CHUNK):
    part = batch_items[i:i + CHUNK]
    driver.execute_query(INGEST_CYPHER, parameters_={"batch": part}, database_=db, routing_="w")
    print(f"   Ingested {min(i + CHUNK, len(batch_items))} / {len(batch_items)}...")

print(f"4. Ingestion finished in {time.time() - t0:.2f}s.")

# Verify counts in Neo4j
verify_q = """
MATCH (r:RTIRecord)
OPTIONAL MATCH (r)-[fa:FILED_ABOUT]->(p:Person)
OPTIONAL MATCH (r)-[ft:FILED_TO]->(a:PublicAuthority)
RETURN count(DISTINCT r) AS rti_nodes,
       count(DISTINCT a) AS authority_nodes,
       count(DISTINCT fa) AS filed_about_rels,
       count(DISTINCT ft) AS filed_to_rels
"""
v_rows, _, _ = driver.execute_query(verify_q, database_=db, routing_="r")
print("5. Neo4j Verification:", v_rows[0].data())
driver.close()
