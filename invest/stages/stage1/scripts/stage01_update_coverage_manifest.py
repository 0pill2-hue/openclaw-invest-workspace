#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
RAW_ROOT = ROOT / "invest/stages/stage1/outputs/raw"
RUNTIME_ROOT = ROOT / "invest/stages/stage1/outputs/runtime"
INDEX_PATH = RAW_ROOT / "source_coverage_index.json"

DART_DIR = RAW_ROOT / "qualitative/kr/dart"
DART_MANIFEST_PATH = DART_DIR / "coverage_summary.json"
KR_OHLCV_DIR = RAW_ROOT / "signal/kr/ohlcv"
KR_SUPPLY_DIR = RAW_ROOT / "signal/kr/supply"
US_OHLCV_DIR = RAW_ROOT / "signal/us/ohlcv"
RSS_DIR = RAW_ROOT / "qualitative/market/rss"
TELEGRAM_DIR = RAW_ROOT / "qualitative/text/telegram"
BLOG_DIR = RAW_ROOT / "qualitative/text/blog"
PREMIUM_DIR = RAW_ROOT / "qualitative/text/premium"

DAILY_UPDATE_STATUS_PATH = RUNTIME_ROOT / "daily_update_status.json"
POST_COLLECTION_VALIDATE_PATH = RUNTIME_ROOT / "post_collection_validate.json"
TELEGRAM_COLLECTOR_STATUS_PATH = RUNTIME_ROOT / "telegram_collector_status.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _normalize_yyyymmdd(raw: str) -> str | None:
    s = str(raw or "").strip()
    if len(s) >= 8 and s[:8].isdigit():
        return s[:8]
    return None


def _normalize_iso_date(raw: str) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10].replace("-", "")
    return _normalize_yyyymmdd(s)


def _manifest_from_dates(*, name: str, kind: str, source_dir: Path, dates: list[str], files_scanned: int, rows_seen: int, reporting_ssot: Path | None = None) -> dict[str, Any]:
    years = Counter()
    months = Counter()
    unique_dates = Counter()
    earliest = None
    latest = None

    for dt in dates:
        years[dt[:4]] += 1
        months[dt[:6]] += 1
        unique_dates[dt] += 1
        earliest = dt if earliest is None or dt < earliest else earliest
        latest = dt if latest is None or dt > latest else latest

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

    payload = {
        "db": name,
        "kind": kind,
        "source_dir": _rel(source_dir),
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
            "unique_dates_count": len(unique_dates),
        },
        "status": {
            "coverage_contiguous_by_month": len(missing_months_between_range) == 0,
            "needs_incremental_update": needs_incremental_update,
            "current_month": current_month,
            "latest_month": latest_month,
        },
    }
    if reporting_ssot is not None:
        payload["reporting_rule"] = {
            "ssot": _rel(reporting_ssot),
            "instruction": f"{name} 수집 범위/누락/추가수집 필요 여부는 항상 이 파일 기준으로 보고한다.",
        }
    return payload


def _dart_summary() -> dict[str, Any]:
    dates: list[str] = []
    files_scanned = 0
    rows_seen = 0
    file_rows: dict[str, int] = {}

    for path in sorted(DART_DIR.iterdir() if DART_DIR.exists() else []):
        if not path.is_file() or path.name == "coverage_summary.json":
            continue
        if path.suffix.lower() != ".csv":
            continue
        local_rows = 0
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dt = _normalize_yyyymmdd(row.get("rcept_dt", ""))
                if dt is None:
                    continue
                dates.append(dt)
                rows_seen += 1
                local_rows += 1
        files_scanned += 1
        file_rows[path.name] = local_rows

    payload = _manifest_from_dates(
        name="dart",
        kind="qualitative.kr",
        source_dir=DART_DIR,
        dates=dates,
        files_scanned=files_scanned,
        rows_seen=rows_seen,
        reporting_ssot=DART_MANIFEST_PATH,
    )
    payload["debug"] = {"files": file_rows}
    return payload


def _csv_source_summary(*, name: str, kind: str, source_dir: Path, pattern: str, date_columns: list[str]) -> dict[str, Any]:
    files = sorted(source_dir.glob(pattern)) if source_dir.exists() else []
    dates: list[str] = []
    rows_seen = 0

    for path in files:
        try:
            with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dt = None
                    for col in date_columns:
                        raw = row.get(col, "")
                        dt = _normalize_iso_date(raw) or _normalize_yyyymmdd(raw)
                        if dt is not None:
                            break
                    if dt is None:
                        continue
                    dates.append(dt)
                    rows_seen += 1
        except Exception:
            continue

    return _manifest_from_dates(
        name=name,
        kind=kind,
        source_dir=source_dir,
        dates=dates,
        files_scanned=len(files),
        rows_seen=rows_seen,
    )


def _text_source_summary(*, name: str, kind: str, source_dir: Path, pattern: str, regexes: list[str]) -> dict[str, Any]:
    files = sorted(source_dir.rglob(pattern)) if source_dir.exists() else []
    dates: list[str] = []
    compiled = [re.compile(p) for p in regexes]

    for path in files:
        try:
            txt = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for rgx in compiled:
            for m in rgx.finditer(txt):
                raw = m.group(1).strip()
                if "미확인" in raw:
                    continue
                dt = _normalize_iso_date(raw) or _normalize_yyyymmdd(raw)
                if dt is not None:
                    dates.append(dt)

    return _manifest_from_dates(
        name=name,
        kind=kind,
        source_dir=source_dir,
        dates=dates,
        files_scanned=len(files),
        rows_seen=len(dates),
    )


def _rss_summary() -> dict[str, Any]:
    files = sorted(RSS_DIR.glob("rss_*.json")) if RSS_DIR.exists() else []
    dates: list[str] = []
    rows_seen = 0
    for path in files:
        data = _load_json(path) or {}
        if not isinstance(data, dict):
            continue
        for key, arr in data.items():
            if key == "_meta" or not isinstance(arr, list):
                continue
            for item in arr:
                if not isinstance(item, dict):
                    continue
                rows_seen += 1
                for field in ("published", "published_date", "published_raw"):
                    dt = _normalize_iso_date(item.get(field, ""))
                    if dt is not None:
                        dates.append(dt)
                        break
    return _manifest_from_dates(
        name="rss",
        kind="qualitative.market",
        source_dir=RSS_DIR,
        dates=dates,
        files_scanned=len(files),
        rows_seen=rows_seen,
    )


def _runtime_health() -> dict[str, Any]:
    daily = _load_json(DAILY_UPDATE_STATUS_PATH) or {}
    validate = _load_json(POST_COLLECTION_VALIDATE_PATH) or {}
    telegram = _load_json(TELEGRAM_COLLECTOR_STATUS_PATH)

    daily_failed = None
    if isinstance(daily.get("failures"), list) and daily["failures"]:
        first = daily["failures"][0]
        if isinstance(first, dict):
            daily_failed = {
                "script": first.get("script"),
                "error": first.get("error"),
            }
    elif isinstance(daily.get("steps"), list):
        for step in daily["steps"]:
            if not step.get("ok", False):
                daily_failed = {
                    "script": step.get("script"),
                    "error": step.get("error"),
                }
                break

    validate_failed = None
    if isinstance(validate.get("details"), list):
        for detail in validate["details"]:
            if not detail.get("ok", False):
                validate_failed = {
                    "source": detail.get("source"),
                    "reason": "; ".join(detail.get("errors", [])) if isinstance(detail.get("errors"), list) else None,
                }
                break

    return {
        "last_checked_utc": datetime.now(timezone.utc).isoformat(),
        "daily_update": {
            "ok": daily.get("ok"),
            "failed_count": daily.get("failed_count"),
            "known_failure": daily_failed.get("script") if daily_failed else None,
            "known_error_summary": daily_failed.get("error") if daily_failed else None,
        },
        "post_collection_validate": {
            "ok": validate.get("ok"),
            "failed_count": validate.get("failed_count"),
            "known_failure_source": validate_failed.get("source") if validate_failed else None,
            "known_failure_reason": validate_failed.get("reason") if validate_failed else None,
        },
        "telegram_collector_status": {
            "expected_path": _rel(TELEGRAM_COLLECTOR_STATUS_PATH),
            "exists": TELEGRAM_COLLECTOR_STATUS_PATH.exists(),
            "selected_collector": telegram.get("selected_collector") if telegram else None,
            "successful_collector": telegram.get("successful_collector") if telegram else None,
            "fallback_used": telegram.get("fallback_used") if telegram else None,
        },
    }


def update_index() -> dict[str, Any]:
    dart = _dart_summary()
    _write_json(DART_MANIFEST_PATH, dart)

    dbs = {
        "dart": {
            "manifest_path": _rel(DART_MANIFEST_PATH),
            "source_dir": _rel(DART_DIR),
            "earliest_date": dart["coverage"]["earliest_date"],
            "latest_date": dart["coverage"]["latest_date"],
            "coverage_contiguous_by_month": dart["status"]["coverage_contiguous_by_month"],
            "needs_incremental_update": dart["status"]["needs_incremental_update"],
            "missing_months_between_range": dart["coverage"]["missing_months_between_range"],
        }
    }

    for name, summary in {
        "kr_ohlcv": _csv_source_summary(name="kr_ohlcv", kind="signal.kr", source_dir=KR_OHLCV_DIR, pattern="*.csv", date_columns=["Date"]),
        "kr_supply": _csv_source_summary(name="kr_supply", kind="signal.kr", source_dir=KR_SUPPLY_DIR, pattern="*_supply.csv", date_columns=["날짜", "Date"]),
        "us_ohlcv": _csv_source_summary(name="us_ohlcv", kind="signal.us", source_dir=US_OHLCV_DIR, pattern="*.csv", date_columns=["Date"]),
    }.items():
        dbs[name] = {
            "source_dir": summary["source_dir"],
            "earliest_date": summary["coverage"]["earliest_date"],
            "latest_date": summary["coverage"]["latest_date"],
            "coverage_contiguous_by_month": summary["status"]["coverage_contiguous_by_month"],
            "needs_incremental_update": summary["status"]["needs_incremental_update"],
            "missing_months_between_range": summary["coverage"]["missing_months_between_range"],
            "unique_dates_count": summary["coverage"]["unique_dates_count"],
            "files_scanned": summary["files_scanned"],
            "rows_seen": summary["rows_seen"],
        }

    sources = {
        "rss": _rss_summary(),
        "telegram": _text_source_summary(name="telegram", kind="qualitative.text", source_dir=TELEGRAM_DIR, pattern="*.md", regexes=[r"(?m)^PostDate:\s*([^\n]+)", r"(?m)^Date:\s*([^\n]+)"]),
        "blog": _text_source_summary(name="blog", kind="qualitative.text", source_dir=BLOG_DIR, pattern="*.md", regexes=[r"(?m)^PublishedDate:\s*([^\n]+)"]),
        "premium": _text_source_summary(name="premium", kind="qualitative.text", source_dir=PREMIUM_DIR, pattern="*.md", regexes=[r"(?m)^PublishedDate:\s*([^\n]+)", r"(?m)^PostDate:\s*([^\n]+)", r"(?m)^Date:\s*([^\n]+)"]),
    }

    index = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": _rel(RAW_ROOT),
        "dbs": dbs,
        "sources": {
            key: {
                "source_dir": value["source_dir"],
                "earliest_date": value["coverage"]["earliest_date"],
                "latest_date": value["coverage"]["latest_date"],
                "coverage_contiguous_by_month": value["status"]["coverage_contiguous_by_month"],
                "needs_incremental_update": value["status"]["needs_incremental_update"],
                "missing_months_between_range": value["coverage"]["missing_months_between_range"],
                "unique_dates_count": value["coverage"]["unique_dates_count"],
                "files_scanned": value["files_scanned"],
                "rows_seen": value["rows_seen"],
            }
            for key, value in sources.items()
        },
        "runtime_health": _runtime_health(),
        "policy": {
            "instruction": "DB/source별 수집 범위 판단과 보고는 source_coverage_index.json 및 개별 coverage summary 기준으로 수행한다.",
            "report_before_using_raw_files": True,
        },
    }
    _write_json(INDEX_PATH, index)
    return index


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage1 source coverage manifest updater")
    parser.add_argument("--db", choices=["dart", "all"], default="all")
    args = parser.parse_args()

    index = update_index()
    print(json.dumps({
        "ok": True,
        "dbs": sorted(index.get("dbs", {}).keys()),
        "sources": sorted(index.get("sources", {}).keys()),
        "index_path": _rel(INDEX_PATH),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
