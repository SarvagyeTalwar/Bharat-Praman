"""Async orchestrator: 3 workers fetch MLA candidate pages, enrich in batches."""
import sys, os, time, random, subprocess, threading
from pathlib import Path
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import requests
from neo4j import GraphDatabase, READ_ACCESS

load_dotenv()
URI = os.getenv("NEO4J_URI", "neo4j+ssc://c1bf4c50.databases.neo4j.io")
USER = os.getenv("NEO4J_USERNAME", "c1bf4c50")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
CACHE = Path("/tmp/opencode/mla_pages")
STATUS = Path("/tmp/opencode/async_status.txt")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
with driver.session(default_access_mode=READ_ACCESS) as s:
    rows = [{"slug": r["slug"], "cid": r["cid"]} for r in s.run("""
        MATCH (p:Person {source:'myneta:winners-index'})
        RETURN p.election AS slug, p.myneta_id AS cid ORDER BY slug, cid
    """)]
driver.close()

todo = deque(r for r in rows if not (CACHE / r["slug"] / f"{r['cid']}.html").exists())
total = len(rows)
print(f"total={total} queued={len(todo)}", flush=True)
STATUS.write_text(f"start total={total} queued={len(todo)}\n")

lock = threading.Lock()
done = [0]
fail = [0]
consec_fail = [0]

def fetch_one(r):
    p = CACHE / r["slug"] / f"{r['cid']}.html"
    if p.exists() and p.stat().st_size > 20000:
        return True
    session = requests.Session()
    session.headers.update(H)
    for attempt in range(8):
        with lock:
            if consec_fail[0] >= 12:
                wait = 60
            else:
                wait = 0
        if wait:
            time.sleep(wait)
        time.sleep(random.uniform(0.2, 0.8))
        try:
            resp = session.get(f"https://www.myneta.info/{r['slug']}/candidate.php?candidate_id={r['cid']}", timeout=60)
            if resp.status_code == 200 and len(resp.text) > 20000:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(resp.text, encoding="utf-8")
                with lock:
                    consec_fail[0] = 0
                return True
            prev = resp.status_code
        except Exception as e:
            prev = type(e).__name__
        with lock:
            consec_fail[0] += 1
        time.sleep(min(60, 4 * (attempt + 1)))
    print("FAILED", r["slug"], r["cid"], prev, flush=True)
    return False

def enrich():
    try:
        subprocess.run([sys.executable, "/tmp/opencode/enrich_mla.py", "--write", "--pending"],
                       check=False, timeout=3600)
    except Exception as e:
        print("enrich err", type(e).__name__, flush=True)

start = time.time()
batches_since_enrich = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(fetch_one, r): r for r in todo}
    for i, f in enumerate(futs, 1):
        ok = False
        try:
            ok = f.result()
        except Exception:
            ok = False
        with lock:
            done[0] += 1
            if not ok:
                fail[0] += 1
        batches_since_enrich += 1
        if i % 20 == 0 or i == len(todo):
            elapsed = time.time() - start
            rate = done[0] / elapsed * 60 if elapsed else 0
            remaining = len(todo) - done[0]
            eta = remaining / rate / 60 if rate else -1
            msg = (f"{done[0]}/{len(todo)} fail={fail[0]} rate={rate:.1f}/min "
                   f"eta={eta:.1f}h elapsed={elapsed/60:.0f}m")
            print(msg, flush=True)
            STATUS.write_text(msg + "\n")
            if batches_since_enrich >= 200:
                batches_since_enrich = 0
                print("running batch enrichment...", flush=True)
                enrich()
                print("batch enrichment done", flush=True)

print("fetch phase done, final enrichment", flush=True)
enrich()
with lock:
    msg = f"DONE done={done[0]} fail={fail[0]} elapsed={(time.time()-start)/60:.0f}m"
print(msg, flush=True)
STATUS.write_text(msg + "\n")
