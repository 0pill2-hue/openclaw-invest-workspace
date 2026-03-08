import glob
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

STAGE1_DIR = Path(__file__).resolve().parents[1]
INVEST_DIR = Path(__file__).resolve().parents[3]
COMMON_INPUT_DATA_DIR = INVEST_DIR / "stages/stage1/outputs"
RAW_ROOT = COMMON_INPUT_DATA_DIR / "raw"
OUT = STAGE1_DIR / "outputs/reports/data_quality/stage01_checkpoint_status.json"


CHECKS = [
    ("kr_ohlcv", "raw/signal/kr/ohlcv/*.csv", 2800),
    ("kr_supply", "raw/signal/kr/supply/*_supply.csv", 2800),
    ("us_ohlcv", "raw/signal/us/ohlcv/*.csv", 500),
    ("market_macro", "raw/signal/market/macro/*", 5),
    ("kr_dart", "raw/qualitative/kr/dart/dart_list_*.csv", 100),
    ("market_rss", "raw/qualitative/market/rss/*.json", 1),
    ("market_news_url_index", "raw/qualitative/market/news/url_index/*.jsonl", 1),
    ("market_news_selected_articles", "raw/qualitative/market/news/selected_articles/*.jsonl", 1),
    ("text_blog", "raw/qualitative/text/blog/**/*.md", 1000),
    ("text_telegram", "raw/qualitative/text/telegram/**/*.md", 10),
    ("text_premium", "raw/qualitative/text/premium/**/*.md", 1),
]


def latest_age_hours(pattern: str):
    files = glob.glob(str(COMMON_INPUT_DATA_DIR / pattern), recursive=True)
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        return None, 0
    latest = max(files, key=os.path.getmtime)
    age_h = (datetime.now().timestamp() - os.path.getmtime(latest)) / 3600
    return age_h, len(files)


def check_basic_sources():
    failures = []
    details = {}
    for name, pattern, min_count in CHECKS:
        age_h, count = latest_age_hours(pattern)
        details[name] = {
            "pattern": pattern,
            "count": count,
            "latest_age_h": None if age_h is None else round(age_h, 2),
            "min_count": min_count,
        }
        if count < min_count:
            failures.append(f"{name}: count={count} < min_count={min_count}")
    return failures, details


def check_dart_continuity(max_gap_days: int = 14):
    files = glob.glob(str(COMMON_INPUT_DATA_DIR / "raw/qualitative/kr/dart/dart_list_*.csv"))
    if not files:
        return ["dart: no files"], {}

    all_days = set()
    for f in files:
        try:
            for chunk in pd.read_csv(f, usecols=["rcept_dt"], chunksize=200000):
                s = pd.to_datetime(chunk["rcept_dt"].astype(str), format="%Y%m%d", errors="coerce").dropna()
                all_days.update(s.dt.date.tolist())
        except Exception:
            continue

    if not all_days:
        return ["dart: no valid rcept_dt"], {}

    sd = sorted(all_days)
    gaps = []
    max_gap = 0
    for a, b in zip(sd, sd[1:]):
        d = (b - a).days
        max_gap = max(max_gap, d)
        if d > max_gap_days:
            gaps.append((str(a), str(b), d))

    details = {
        "min_date": str(sd[0]),
        "max_date": str(sd[-1]),
        "unique_days": len(sd),
        "max_gap_days": max_gap,
        "gap_limit_days": max_gap_days,
        "gaps_over_limit": gaps[:20],
    }

    failures = []
    if gaps:
        failures.append(f"dart: {len(gaps)} gaps over {max_gap_days} days")
    return failures, details


def _leaf_directories(root: Path) -> list[Path]:
    if not root.exists():
        return []
    leaves = []
    for directory in sorted([p for p in root.rglob("*") if p.is_dir()]):
        child_dirs = [c for c in directory.iterdir() if c.is_dir() and not c.name.startswith(".")]
        if child_dirs:
            continue
        leaves.append(directory)
    return leaves


def check_raw_tree_coverage():
    dirs = []
    for directory in _leaf_directories(RAW_ROOT):
        files = sorted([p for p in directory.rglob("*") if p.is_file() and not p.name.startswith(".")])
        latest_mtime = max((f.stat().st_mtime for f in files), default=None)
        dirs.append(
            {
                "dir": str(directory.relative_to(COMMON_INPUT_DATA_DIR)),
                "file_count": len(files),
                "latest_age_h": None
                if latest_mtime is None
                else round((datetime.now().timestamp() - latest_mtime) / 3600, 2),
            }
        )

    details = {
        "leaf_dir_count": len(dirs),
        "covered_leaf_dirs": len([item for item in dirs if item["file_count"] > 0]),
        "empty_leaf_dir_count": len([item for item in dirs if item["file_count"] == 0]),
        "empty_leaf_dirs": [item["dir"] for item in dirs if item["file_count"] == 0],
        "dirs": dirs,
    }
    return [], details


def main():
    failures = []
    details = {}

    f1, d1 = check_basic_sources()
    f2, d2 = check_dart_continuity()
    f3, d3 = check_raw_tree_coverage()

    failures.extend(f1)
    failures.extend(f2)
    failures.extend(f3)
    details.update(d1)
    details["dart_continuity"] = d2
    details["raw_tree_coverage"] = d3

    payload = {
        "timestamp": datetime.now().isoformat(),
        "grade": "VALIDATED" if not failures else "DRAFT",
        "ok": len(failures) == 0,
        "failed_count": len(failures),
        "failures": failures,
        "details": details,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if not payload["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
