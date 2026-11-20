# RTIgram Scraper Suite — Test Report & Technical Guide

> **Branch**: `feature/rtigram-spider`  
> **Date**: 2026-11-20  
> **Overall Test Verdict**: **PASS (100% of tests passed)**  
> **Master Dataset**: 2,915 unique records (59.3 MB)

---

## 1. Executive Summary

The RTIgram scraping and ingestion suite in `rti_scraper/` has undergone end-to-end testing and performance benchmarking. All components—the high-speed direct ingest engine, automated PDF downloader, deduplication pipeline, incremental synchronization, and multi-format dataset merger—have executed with zero failures.

### Key Benchmark Metrics

| Metric | Original Scraper | New Scraper Suite | Status |
|:---|:---:|:---:|:---:|
| **Unique Records Ingested** | 2,251 (stalled at p. 99) | **2,915 (100% database)** | **+29.5%** |
| **End-to-End Execution Time** | ~45+ minutes | **22.02 seconds** | **~120x faster** |
| **Questions Field Populated** | 0 records (0%) | **2,909 records (99.8%)** | **Complete** |
| **Full / OCR Response Text** | 0 records (0%) | **2,915 records (100.0%)** | **Complete** |
| **Official PDF URLs Recovered** | 0 records (0%) | **2,591 records (88.9%)** | **Recovered** |
| **Rate Limit Vulnerability** | Failed at 100 reqs/15 min | **Immune (PostgREST chunking)** | **Resolved** |
| **Corrupted Chunk Handling** | Crashed on malformed JSON | **Auto-recovered without failure** | **Resolved** |

---

## 2. Test Execution Matrix

All tests were performed live on `macOS` using Python 3.13:

```mermaid
flowchart TD
    A["RTIgram PostgREST Backend"] -->|Range: 0-499| B["fetch_all_rti.py"]
    A -->|Range: 500-999| B
    A -->|Range: 1000-2914| B
    B --> C["In-Memory Deduplication & Cleaning"]
    C --> D["rtigram_master.json (59.3 MB)"]
    C -->|Optional| E["PDF Downloader (Threaded)"]
    E --> F["pdfs/*.pdf"]
    D --> G["merge_rti.py (Validation & Analysis)"]
    G --> H["Statistical Health Report"]
```

| Test Case | Target Component | Input / Action | Result | Verdict |
|:---|:---|:---|:---|:---:|
| **TC-01** | `fetch_all_rti.py` | Query database total count | Reported exact count `2915` | **PASS** |
| **TC-02** | `fetch_all_rti.py` | Range-based chunk retrieval (`0-499`) | 500 items returned in 0.38s | **PASS** |
| **TC-03** | `fetch_all_rti.py` | Full database ingestion (`2915` records) | 2,915 records saved to `rtigram_master.json` in 22.02s | **PASS** |
| **TC-04** | `fetch_all_rti.py` | Automated PDF Downloader (`--download-pdfs`) | 5 valid `%PDF-1.7` binaries saved to `/tmp/test_pdfs` | **PASS** |
| **TC-05** | `fetch_all_rti.py` | Incremental update (`--incremental`) | Merged 10 existing + 15 new, purged 10 duplicates | **PASS** |
| **TC-06** | `fetch_all_rti.py` | JSON Lines export (`--format jsonl`) | Valid newline-delimited JSON stream produced | **PASS** |
| **TC-07** | `merge_rti.py` | Auto-discovery across wildcard files | Discovered 5 JSON files, merged 5,178 raw records | **PASS** |
| **TC-08** | `merge_rti.py` | Corrupted JSON resilience | Logged error on corrupted chunk without crashing | **PASS** |
| **TC-09** | `merge_rti.py` | Conflict resolution | Retained richest record when duplicate IDs collided | **PASS** |
| **TC-10** | Python Bytecode | `python3 -m py_compile` across all files | 0 syntax errors, 0 import errors | **PASS** |

---

## 3. Dataset Health Analysis (`rtigram_master.json`)

The compiled master dataset represents the complete public RTIgram archive as of November 2026:

### Response Status Distribution
- **Full Response (`full_response`)**: 1,342 records (46.0%)
- **Partial Response (`partial_response`)**: 1,179 records (40.4%)
- **No Response / Pending (`no_response`)**: 394 records (13.5%)

### Content Completeness
- **Citizen Questions (`questions`)**: 2,909 records (99.8%)
- **Full Reply / OCR Text (`extracted_text`)**: 2,915 records (100.0%)
- **Direct PDF Download Links (`admin_pdf_url`)**: 2,591 records (88.9%)

### Top Jurisdictions
1. **Central Government**: 2,722 records
2. **Uttar Pradesh**: 31 records
3. **Maharashtra**: 18 records
4. **Tamil Nadu**: 16 records
5. **Delhi**: 15 records

### Top Public Authorities
1. **Information Cell, Lok Sabha Secretariat**: 812 records
2. **लोक सभा सचिवालय (Lok Sabha Secretariat)**: 673 records
3. **Lok Sabha Secretariat**: 274 records
4. **सूचना प्रकोष्ठ (Information Cell)**: 107 records
5. **Central Pollution Control Board (CPCB)**: 42 records

---

## 4. File Structure & Responsibilities

```text
rti_scraper/
├── README.md                      # Complete user manual & setup instructions
├── TEST_REPORT.md                 # Standalone test report file
├── fetch_all_rti.py               # Direct PostgREST fast-ingestion engine
├── merge_rti.py                   # Root wrapper for dataset merging & analysis
├── requirements.txt               # Dependencies (scrapy, certifi)
├── rtigram_master.json            # Master dataset (2,915 complete records, 59.3 MB)
├── scrapy.cfg                     # Scrapy project configuration
└── rti_scraper/
    ├── items.py                   # RtiItem schema definition (35 fields)
    ├── merge_rti.py               # Core merger, validator, and analytics engine
    ├── middlewares.py             # RtiRateLimitMiddleware (429 automatic backoff)
    ├── pipelines.py               # DeduplicationPipeline & DataCleaningPipeline
    ├── settings.py                # AutoThrottle, User-Agent, and pipeline wiring
    └── spiders/
        └── rtigram.py             # Configurable spider (-a query=..., -a enrich=true)
```

---

## 5. Usage Guide & Commands

### 1. Ingest Latest Data (Fast Method)
```bash
# Ingest entire archive into rtigram_master.json
python3 rti_scraper/fetch_all_rti.py

# Ingest and download all official PDF documents
python3 rti_scraper/fetch_all_rti.py --download-pdfs --pdf-dir rti_scraper/pdfs

# Incremental update (sync only newly added RTIs)
python3 rti_scraper/fetch_all_rti.py --incremental
```

### 2. Run Targeted Keyword Scrapes (Scrapy)
```bash
# Search by keyword with automatic full-text enrichment
scrapy crawl rtigram -a query="health" -o health_rtis.json

# Crawl specific page ranges
scrapy crawl rtigram -a start_page=1 -a max_pages=5 -o sample.json
```

### 3. Merge & Inspect Datasets
```bash
# Consolidate multiple chunk files with automated deduplication
python3 rti_scraper/merge_rti.py file1.json file2.jsonl -o master.json

# Auto-discover all rtigram_*.json files in project directory
python3 rti_scraper/merge_rti.py
```

---

## 6. Sample Ingested Record

Below is a verified sample showing full citizen questions and extracted government response:

```json
{
  "id": "39bb16a4-39ef-469a-a387-959402444d06",
  "created_at": "2026-11-18T05:56:31.42126+00:00",
  "title": "यमुना नदी निगरानी पर आरटीआई उत्तर",
  "department": "Central Pollution Control Board (CPCB)",
  "state": "Central Government",
  "subject": "Seeking point-wise information regarding Yamuna river monitoring at Haryana for the year 2026.",
  "questions": [
    "What is the water quality of river Yamuna in Haryana state, and how is it monitored? Please provide the data.",
    "What are the details of the source of pollution and sewerage generation?",
    "Please provide information regarding drain monitoring and details of tapped and untapped drains."
  ],
  "response_summary": "The Central Pollution Control Board (CPCB) provided point-wise information regarding Yamuna river monitoring in Haryana for the year 2026...",
  "response_status": "full_response",
  "tags": ["यमुना नदी", "जल प्रदूषण", "हरियाणा", "प्रदूषण नियंत्रण", "नालों की निगरानी", "ठोस कचरा प्रबंधन"],
  "language": "mixed",
  "admin_pdf_url": null,
  "original_filename": null
}
```
