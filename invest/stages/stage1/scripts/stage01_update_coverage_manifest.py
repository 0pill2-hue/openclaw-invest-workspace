#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
RAW_ROOT = ROOT / "invest/stages/stage1/outputs/raw"
INDEX_PATH = RAW_ROOT / "source_coverage_index.json"

DART_DIR = RAW_ROOT / "qualitative/kr/dart"
DART_MANIFEST_PATH = DART_DIR / "coverage_summary.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _dart_summary() -> dict[str, Any]:
    years = Counter()
    months = Counter()
    dates = Counter()
    file_rows: dict[str, int] = {}
    files_scanned = 0
    rows_seen = 0
    earliest = None
    latest = None

    for path in sorted(DART_DIR.iterdir() if DART_DIR.exists() else []):
        if not path.is_file() or path.name == "coverage_summary.json":
            continue
        suffix = path.suffix.lower()
        local_rows = 0

        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dt = str(row.get("rcept_dt", "")).strip()
                    if len(dt) < 8 or not dt[:8].isdigit():
                        continue
                    dt = dt[:8]
                    years[dt[:4]] += 1
                    months[dt[:6]] += 1
                    dates[dt] += 1
                    rows_seen += 1
                    local_rows += 1
                    earliest = dt if earliest is None or dt < earliest else earliest
                    latest = dt if latest is None or dt > latest else latest
        elif suffix == ".json":
            data = _load_json(path) or {}
            for row in data.get("rows", []) or []:
                dt = str(row.get("rcept_dt", "")).strip()
                if len(dt) < 8 or not dt[:8].isdigit():
                    continue
                dt = dt[:8]
                years[dt[:4]] += 1
                months[dt[:6]] += 1
                dates[dt] += 1
                rows_seen += 1
                local_rows += 1
                earliest = dt if earliest is None or dt < earliest else earliest
                latest = dt if latest is None or dt > latest else latest
        else:
            continue

        files_scanned += 1
        file_rows[path.name] = local_rows

    missing_months_between_range: list[str] = []
    if earliest and latest:
        sy, sm = int(earliest[:4]), int(earliest[4:6])
        ey, em = int(latest[:4]), int(latest[4:6])
        y, m = sy, sm
        while (y, m) <= (ey, em):
            ym = f"{y:04d}{m:02d}"
            if ym not in months:
                missing_months_between_range.append(ym)
            m += 1
            if m == 13:
                y += 1
                m = 1

    latest_month = latest[:6] if latest else None
    current_month = datetime.now().strftime("%Y%m")
    needs_incremental_update = bool(latest_month and latest_month < current_month)

    return {
        "db": "dart",
        "kind": "qualitative.kr",
        "source_dir": str(DART_DIR),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files_scanned": files_scanned,
        "rows_seen": rows_seen,
        "coverage": {
            "earliest_date": earliest,
            "latest_date": latest,
            "years_present": sorted(years.keys()),
            "months_present": sorted(months.keys()),
            "missing_months_between_range": missing_months_between_range,
            "year_row_counts": {y: years[y] for y in sorted(years.keys())},
            "month_row_counts": {m: months[m] for m in sorted(months.keys())},
            "unique_dates_count": len(dates),
        },
        "status": {
            "coverage_contiguous_by_month": len(missing_months_between_range) == 0,
            "needs_incremental_update": needs_incremental_update,
            "current_month": current_month,
            "latest_month": latest_month,
        },
        "reporting_rule": {
            "ssot": str(DART_MANIFEST_PATH),
            "instruction": "DART 수집 범위/누락/추가수집 필요 여부는 항상 이 파일 기준으로 보고한다.",
        },
        "debug": {
            "files": file_rows,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_dart() -> dict[str, Any]:
    summary = _dart_summary()
    _write_json(DART_MANIFEST_PATH, summary)

    index = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(RAW_ROOT),
        "dbs": {
            "dart": {
                "manifest_path": str(DART_MANIFEST_PATH),
                "source_dir": str(DART_DIR),
                "earliest_date": summary["coverage"]["earliest_date"],
                "latest_date": summary["coverage"]["latest_date"],
                "coverage_contiguous_by_month": summary["status"]["coverage_contiguous_by_month"],
                "needs_incremental_update": summary["status"]["needs_incremental_update"],
                "missing_months_between_range": summary["coverage"]["missing_months_between_range"],
            }
        },
        "policy": {
            "instruction": "DB/source별 수집 범위 판단과 보고는 각 coverage_summary.json 및 이 인덱스를 SSOT로 사용한다.",
            "report_before_using_raw_files": True,
        },
    }
    _write_json(INDEX_PATH, index)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage1 source coverage manifest updater")
    parser.add_argument("--db", choices=["dart"], required=True)
    args = parser.parse_args()

    if args.db == "dart":
        summary = update_dart()
        print(json.dumps({
            "db": "dart",
            "manifest_path": str(DART_MANIFEST_PATH),
            "earliest_date": summary["coverage"]["earliest_date"],
            "latest_date": summary["coverage"]["latest_date"],
            "coverage_contiguous_by_month": summary["status"]["coverage_contiguous_by_month"],
            "needs_incremental_update": summary["status"]["needs_incremental_update"],
        }, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
