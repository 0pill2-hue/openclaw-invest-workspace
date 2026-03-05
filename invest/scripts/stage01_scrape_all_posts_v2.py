#!/usr/bin/env python3
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py"), run_name="__main__")
