"""Canonical registry of real PDF sources for Bharat Praman.

Maps every ingested document filename (e.g. `moe24-25.pdf`, `mof_outcome_2024-25.pdf`,
`mha24-25.pdf`, `def24-25.pdf`) and local cached PDFs to:
1. Local filesystem path (if present on the host machine)
2. Direct official Government of India PDF URL
3. Structured metadata (ministry, fiscal year, title)

Used by `reports_agent.py` to build direct `#page=N` links on citation cards,
and by `main.py` to expose `GET /api/sources/list` and `GET /api/sources/pdf/{filename}`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent
PARENT_DIR = REPO_DIR.parent
CACHE_DIR = REPO_DIR / "data" / "cache"

# Official PDF registry for all 49 ingested documents + local PDFs
PDF_SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # Ministry of Home Affairs (MHA)
    # -------------------------------------------------------------------------
    "mha24-25.pdf": {
        "ministry": "Home Affairs",
        "year": "2024-25",
        "title": "Ministry of Home Affairs Annual Report 2024-25",
        "official_pdf_url": "https://www.mha.gov.in/sites/default/files/2026-03/AREnglish_24032026.pdf",
        "local_candidates": [
            PARENT_DIR / "ministry of internal affairs" / "annual reports" / "AREnglish_24032026.pdf",
        ],
    },
    "mha23-24.pdf": {
        "ministry": "Home Affairs",
        "year": "2023-24",
        "title": "Ministry of Home Affairs Annual Report 2023-24",
        "official_pdf_url": "https://www.mha.gov.in/sites/default/files/2024-12/AnnualReport_27122024.pdf",
        "local_candidates": [
            PARENT_DIR / "ministry of internal affairs" / "annual reports" / "AnnualReport_27122024.pdf",
        ],
    },
    "mha22-23.pdf": {
        "ministry": "Home Affairs",
        "year": "2022-23",
        "title": "Ministry of Home Affairs Annual Report 2022-23",
        "official_pdf_url": "https://www.mha.gov.in/sites/default/files/AnnualReportEngLish_11102023.pdf",
        "local_candidates": [
            PARENT_DIR / "ministry of internal affairs" / "annual reports" / "AnnualReportEngLish_11102023.pdf",
        ],
    },

    # -------------------------------------------------------------------------
    # Ministry of Education (MoE)
    # -------------------------------------------------------------------------
    "moe25-26.pdf": {
        "ministry": "Education",
        "year": "2025-26",
        "title": "Ministry of Education Annual Report 2025-26",
        "official_pdf_url": "https://www.education.gov.in/sites/upload_files/mhrd/files/document-reports/AR_2025_26_Eng.pdf",
        "local_candidates": [PARENT_DIR / "moe25-26.pdf"],
    },
    "moe24-25.pdf": {
        "ministry": "Education",
        "year": "2024-25",
        "title": "Ministry of Education Annual Report 2024-25",
        "official_pdf_url": "https://www.education.gov.in/sites/upload_files/mhrd/files/document-reports/AR_2024_25_Eng.pdf",
        "local_candidates": [PARENT_DIR / "moe24-25.pdf"],
    },
    "moe23-24.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "Ministry of Education Annual Report 2023-24",
        "official_pdf_url": "https://www.education.gov.in/sites/upload_files/mhrd/files/document-reports/AR_2023_24_Eng.pdf",
        "local_candidates": [PARENT_DIR / "moe23-24.pdf"],
    },
    "moe22-23.pdf": {
        "ministry": "Education",
        "year": "2022-23",
        "title": "Ministry of Education Annual Report 2022-23",
        "official_pdf_url": "https://www.education.gov.in/sites/upload_files/mhrd/files/document-reports/AR_2022_23_Eng.pdf",
        "local_candidates": [PARENT_DIR / "moe22-23.pdf", PARENT_DIR / "ad6112a56601bb49a8816037f139aa5b.pdf"],
    },
    "moe21-22.pdf": {
        "ministry": "Education",
        "year": "2021-22",
        "title": "Ministry of Education Annual Report 2021-22",
        "official_pdf_url": "https://www.education.gov.in/sites/upload_files/mhrd/files/document-reports/AR_2021_22_Eng.pdf",
        "local_candidates": [PARENT_DIR / "moe21-22.pdf", PARENT_DIR / "1abcda540a90235e846eaa3fa4b97249.pdf"],
    },
    "hi_moe.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "Department of Higher Education Annual Report 2023-24",
        "official_pdf_url": "https://www.education.gov.in/documents_reports",
        "local_candidates": [PARENT_DIR / "b4e8b30be0e3fb45bade24aee3f1cd5f.pdf"],
    },
    "hi2_moe.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "AISHE Higher Education Statistics Report",
        "official_pdf_url": "https://aishe.gov.in/",
        "local_candidates": [PARENT_DIR / "426440f1daac445265cdea027ae6a00d.pdf"],
    },
    "moe_ttn.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "Ministry of Education Compendium / RTE Reference",
        "official_pdf_url": "https://www.education.gov.in/documents_reports",
        "local_candidates": [PARENT_DIR / "ee3cf9ae4ddbc3d0582e98f050290edc.pdf"],
    },
    "moe_udise_001.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "UDISE+ School Education Report (Part 1)",
        "official_pdf_url": "https://udiseplus.gov.in/",
        "local_candidates": [],
    },
    "moe_udise_002.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "UDISE+ School Education Report (Part 2)",
        "official_pdf_url": "https://udiseplus.gov.in/",
        "local_candidates": [],
    },
    "moe_udise_003.pdf": {
        "ministry": "Education",
        "year": "2023-24",
        "title": "UDISE+ School Education Report (Part 3)",
        "official_pdf_url": "https://udiseplus.gov.in/",
        "local_candidates": [],
    },

    # -------------------------------------------------------------------------
    # Ministry of Defence (MoD)
    # -------------------------------------------------------------------------
    "def24-25.pdf": {
        "ministry": "Defence",
        "year": "2024-25",
        "title": "Ministry of Defence Annual Report 2024-25",
        "official_pdf_url": "https://mod.gov.in/sites/default/files/Annual-Report-2024-25.pdf",
        "local_candidates": [PARENT_DIR / "def24-25.pdf"],
    },
    "def25-24.pdf": {
        "ministry": "Defence",
        "year": "2024-25",
        "title": "Ministry of Defence Annual Report 2024-25 (Vol II)",
        "official_pdf_url": "https://mod.gov.in/sites/default/files/Annual-Report-2024-25.pdf",
        "local_candidates": [PARENT_DIR / "def25-24.pdf"],
    },
    "def23-24.pdf": {
        "ministry": "Defence",
        "year": "2023-24",
        "title": "Ministry of Defence Annual Report 2023-24",
        "official_pdf_url": "https://mod.gov.in/sites/default/files/Annual-Report-2023-24.pdf",
        "local_candidates": [PARENT_DIR / "def23-24.pdf"],
    },
    "def.pdf": {
        "ministry": "Defence",
        "year": "2023-24",
        "title": "Ministry of Defence Summary Report 2023-24",
        "official_pdf_url": "https://mod.gov.in/documents/annual-report",
        "local_candidates": [PARENT_DIR / "def.pdf"],
    },
    "def1.pdf": {
        "ministry": "Defence",
        "year": "2023-24",
        "title": "Ministry of Defence Compendium 2023-24",
        "official_pdf_url": "https://mod.gov.in/documents/annual-report",
        "local_candidates": [PARENT_DIR / "def1.pdf"],
    },

    # -------------------------------------------------------------------------
    # Local ECI Election & Council PDFs
    # -------------------------------------------------------------------------
    "Union_Council_of_Ministers_25_jul_2026.pdf": {
        "ministry": "Cabinet Secretariat",
        "year": "2026-27",
        "title": "Union Council of Ministers (July 2026)",
        "official_pdf_url": "https://cabsec.gov.in/",
        "local_candidates": [PARENT_DIR / "Union_Council_of_Ministers_25_jul_2026.pdf"],
    },
}

# Dynamically populate all 29 Ministry of Finance / Union Budget PDFs
_BUDGET_SPECS = [
    ("2026-27", "https://www.indiabudget.gov.in/doc", "https://www.indiabudget.gov.in/economicsurvey/doc"),
    ("2025-26", "https://www.indiabudget.gov.in/budget2025-26/doc", "https://www.indiabudget.gov.in/budget2025-26/economicsurvey/doc"),
    ("2024-25", "https://www.indiabudget.gov.in/budget2024-25/doc", "https://www.indiabudget.gov.in/budget2024-25/economicsurvey/doc"),
    ("2023-24", "https://www.indiabudget.gov.in/budget2023-24/doc", "https://www.indiabudget.gov.in/budget2023-24/economicsurvey/doc"),
    ("2022-23", "https://www.indiabudget.gov.in/budget2022-23/doc", "https://www.indiabudget.gov.in/budget2022-23/economicsurvey/doc"),
    ("2021-22", "https://www.indiabudget.gov.in/budget2021-22/doc", "https://www.indiabudget.gov.in/budget2021-22/economicsurvey/doc"),
]

for fy, doc_base, eco_base in _BUDGET_SPECS:
    fy_long = fy.replace("-", "_20")  # e.g. 2024-25 -> 2024_2025
    PDF_SOURCE_REGISTRY[f"mof_outcome_{fy}.pdf"] = {
        "ministry": "Finance",
        "year": fy,
        "title": f"Output-Outcome Framework {fy}",
        "official_pdf_url": f"{doc_base}/OutcomeBudgetE{fy_long}.pdf",
        "local_candidates": [],
    }
    PDF_SOURCE_REGISTRY[f"mof_allsbe_{fy}.pdf"] = {
        "ministry": "Finance",
        "year": fy,
        "title": f"Expenditure Budget (All SBE) {fy}",
        "official_pdf_url": f"{doc_base}/eb/allsbe.pdf",
        "local_candidates": [],
    }
    PDF_SOURCE_REGISTRY[f"mof_alldg_{fy}.pdf"] = {
        "ministry": "Finance",
        "year": fy,
        "title": f"Demands for Grants (All DG) {fy}",
        "official_pdf_url": f"{doc_base}/eb/alldg.pdf",
        "local_candidates": [],
    }
    PDF_SOURCE_REGISTRY[f"mof_exp_vol1_{fy}.pdf"] = {
        "ministry": "Finance",
        "year": fy,
        "title": f"Expenditure Profile Vol 1 {fy}",
        "official_pdf_url": f"{doc_base}/eb/vol1.pdf",
        "local_candidates": [],
    }
    PDF_SOURCE_REGISTRY[f"mof_ecosurvey_{fy}.pdf"] = {
        "ministry": "Finance",
        "year": fy,
        "title": f"Economic Survey {fy}",
        "official_pdf_url": f"{eco_base}/echapter.pdf",
        "local_candidates": [],
    }
    PDF_SOURCE_REGISTRY[f"mof_receipt_{fy}.pdf"] = {
        "ministry": "Finance",
        "year": fy,
        "title": f"Receipts Budget {fy}",
        "official_pdf_url": f"{doc_base}/rec/allrec.pdf",
        "local_candidates": [],
    }

# Add ECI Lok Sabha PDFs in data/cache/
for ls_year in ("1996", "1998", "1999", "2004", "2009", "2014"):
    fname = f"eci_ls{ls_year}.pdf"
    PDF_SOURCE_REGISTRY[fname] = {
        "ministry": "Election Commission",
        "year": ls_year,
        "title": f"ECI Lok Sabha Statistical Report {ls_year}",
        "official_pdf_url": "https://www.eci.gov.in/statistical-reports",
        "local_candidates": [CACHE_DIR / fname],
    }


def resolve_local_pdf_path(file_name: str) -> Path | None:
    """Return the local filesystem Path if this PDF exists on the running machine."""
    if not file_name:
        return None
    clean = os.path.basename(file_name.strip())
    entry = PDF_SOURCE_REGISTRY.get(clean)
    if entry:
        for cand in entry.get("local_candidates", []):
            p = Path(cand)
            if p.is_file():
                return p
    # Fallback check directly in PARENT_DIR or CACHE_DIR
    for base in (PARENT_DIR, CACHE_DIR):
        p = base / clean
        if p.is_file():
            return p
    return None


def resolve_source_pdf_url(
    ministry: str = "",
    title: str = "",
    file_name: str = "",
    page: int | str | None = None,
) -> str:
    """Resolve the best real PDF URL for a citation card, with `#page=N` anchor."""
    clean = os.path.basename((file_name or "").strip()) if file_name else ""
    page_anchor = f"#page={page}" if page and str(page).isdigit() and int(page) > 0 else ""

    if clean and clean in PDF_SOURCE_REGISTRY:
        entry = PDF_SOURCE_REGISTRY[clean]
        # Prefer direct local backend PDF route if the file exists locally on disk
        if resolve_local_pdf_path(clean) is not None:
            return f"/api/sources/pdf/{clean}{page_anchor}"
        # Otherwise return the direct official .gov.in PDF URL
        url = entry.get("official_pdf_url", "")
        if url:
            if url.lower().endswith(".pdf") and page_anchor:
                return f"{url}{page_anchor}"
            return url

    # Fallback by title keywords if file_name was missing (e.g. MOE Annual Report 2023-24)
    t_low = (title or "").lower()
    if "moe annual report 2023-24" in t_low:
        return resolve_source_pdf_url("Education", title, "moe23-24.pdf", page)
    if "moe annual report 2024-25" in t_low:
        return resolve_source_pdf_url("Education", title, "moe24-25.pdf", page)

    return ""


def list_pdf_sources() -> list[dict[str, Any]]:
    """Return a clean list of all registered PDFs and their local availability."""
    items = []
    for fname, meta in sorted(PDF_SOURCE_REGISTRY.items()):
        local_path = resolve_local_pdf_path(fname)
        items.append({
            "file": fname,
            "ministry": meta["ministry"],
            "year": meta["year"],
            "title": meta["title"],
            "official_pdf_url": meta["official_pdf_url"],
            "local_available": local_path is not None,
            "local_url": f"/api/sources/pdf/{fname}" if local_path is not None else None,
        })
    return items
