# Lok Sabha MP Historical Affidavit Extraction & Matching

This pipeline builds an elected-MP timeline for Lok Sabha elections in 1996, 1998, 1999, 2004, 2009, 2014, 2019, and 2024. There was no Lok Sabha election in 1994. `build_all_mp_history.py` combines ECI successful-candidate reports with MyNeta (ADR) winner/affidavit pages, enriching official winners where a same-seat candidate match is available. Affidavit comparisons begin in 2004 because candidate financial disclosures became mandatory starting in 2003. The 2024 baseline supports change comparisons, while its election rows are excluded from import because they already exist in the database.

## Output Files

1. **`data/mp_history.jsonl`**:
   - Rebuilt on each run from the available baseline and cached/downloaded election pages.
   - Includes 2024 baseline records and matched historical candidates from 2004, 2009, 2014, and 2019 for the sitting-MP view.
   - Every record is formatted as an independent `Affidavit` node with the 24 properties:
     - `affidavit_id`, `mp_entity_id`, `election`, `election_year`, `candidate_name`, `constituency`, `state`, `party`, `age`, `education`, `total_assets`, `movable_assets`, `immovable_assets`, `liabilities`, `criminal_cases_count`, `is_winner`, `source_url`, `match_method`, `match_confidence`, `status`, `extracted_at`.
2. **`review/mp_ambiguous.csv`**:
   - Records where multiple potential matches exist across the state/seat, requiring human disambiguation before acceptance.
3. **`review/possible_seat_changes.csv`**:
   - Possible matches for MPs who contested in a different constituency or state in prior elections.
4. **`data/cache/`**:
   - Disk cache of downloaded HTML pages (`ls2024`, `ls2019`, `ls2014`, `ls2009`, `ls2004`). By default the script reuses cached candidate pages and fetches each election's winners list. Set `MP_FETCH_ALL_CANDIDATES=1` to download every constituency candidate page as well; this takes substantially longer.
5. **`data/mp_election_history.jsonl`**: one timeline with affidavit records plus party-only winners for 1996, 1998, and 1999.
6. **`data/party_changes.jsonl`**: party changes between consecutive matched election records.
7. **`data/affidavit_changes.jsonl`**: nominal changes in declared assets, liabilities, criminal cases, and education between matched affidavit elections. Asset amounts are not inflation-adjusted.
8. **Full winner history** (run `python build_all_mp_history.py`):
   - `all_mp_elections.jsonl`, `all_mp_people.jsonl`, `all_party_changes.jsonl`, and `all_affidavit_changes.jsonl` contain the wider election roster and observed changes.
   - ECI winner lists cover 1996, 1998, 1999, 2004, 2009, and 2014; MyNeta/ADR supplies 2019 winner/affidavit rows; the existing project baseline supplies 2024.
   - Winners without a matched affidavit remain as party-only election results. Check per-year output counts before importing because source coverage is incomplete in some years.

## How to Rerun the Scraper & Matcher

```bash
# 1. Activate your Python environment
python -m pip install beautifulsoup4 requests PyMuPDF

# 2. Run the sitting-MP pipeline (resumable, reads from local backup and disk cache)
python build_mp_history.py

# 3. Build the full elected-MP timeline and preview the import
python build_all_mp_history.py
python import_mp_history.py
```

The script uses the graph backup at `instance01_backup.json` when present. To point it at a different backup, set `MP_BACKUP_PATH` before running. If no backup exists, it can use existing 2024 baseline records in `data/mp_history.jsonl`.

To fetch full candidate lists in PowerShell:

```powershell
$env:MP_FETCH_ALL_CANDIDATES = "1"
python build_mp_history.py
```

Preview the Neo4j import counts without connecting to the database:

```powershell
python import_mp_history.py
```

To write the historical affidavit, election-result, party-change, and affidavit-change nodes, run `python import_mp_history.py --apply` after reviewing the preview. The import skips 2024 affidavit rows and uses stable IDs with `MERGE` so reruns do not duplicate rows.

## Graph Schema Reference (Read-Only)

When ready to import into Neo4j, the `Affidavit` node connects as:
```cypher
MATCH (p:Person:MP {entity_id: $mp_entity_id})
MERGE (a:Affidavit {id: $affidavit_id})
SET a += {
    election: $election,
    year: $election_year,
    constituency: $constituency,
    party: $party,
    total_assets: $total_assets,
    liabilities: $liabilities,
    criminal_cases_count: $criminal_cases_count,
    source_url: $source_url
}
MERGE (p)-[:FILED_AFFIDAVIT]->(a)
```
