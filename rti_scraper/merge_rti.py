#!/usr/bin/env python3
import sys
from pathlib import Path

# Delegate to rti_scraper/merge_rti.py
target = Path(__file__).resolve().parent / "rti_scraper" / "merge_rti.py"
if target.exists():
    import runpy

    runpy.run_path(str(target), run_name="__main__")
else:
    sys.exit(f"Target script not found: {target}")
