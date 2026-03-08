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
NEWS_URL_INDEX_DIR = RAW_ROOT / "qualitative/market/news/url_index"
NEWS_SELECTED_DIR = RAW_ROOT / "qualitative/market/news/selected_articles"
TELEGRAM_DIR = RAW_ROOT / "qualitative/text/telegram"
BLOG_DIR = RAW_ROOT / "qualitative/text/blog"
PREMIUM_DIR = RAW_ROOT / "qualitative/text/premium"
MACRO_DIR = RAW_ROOT / "signal/market/macro"

DAILY_UPDATE_STATUS_PATH = RUNTIME_ROOT / "daily_update_status.json"
POST_COLLECTION_VALIDATE_PATH = RUNTIME_ROOT / "post_collection_validate.json"
TELEGRAM_COLLECTOR_STATUS_PATH = RUNTIME_ROOT / "telegram_collector_status.json"
US_OHLCV_STATUS_PATH = RUNTIME_ROOT / "us_ohlcv_status.json"
NEWS_URL_INDEX_STATUS_PATH = RUNTIME_ROOT / "news_url_index_status.json"
NEWS_SELECTED_STATUS_PATH = RUNTIME_ROOT / "news_selected_articles_status.json"

TELEGRAM_ALLOWLIST_PATH = ROOT / "invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt"
TELEGRAM_TERMINAL_STATUS_PATH = ROOT / "invest/stages/stage1/inputs/config/telegram_terminal_status.json"
NEWS_SOURCES_CONFIG_PATH = ROOT / "invest/stages/stage1/inputs/config/news_sources.json"
PREMIUM_DISCOVERY_PATH = PREMIUM_DIR / "startale_channel_direct/_discovery.json"
BUDDIES_PATH = ROOT / "invest/stages/stage1/outputs/master/naver_buddies_full.json"
BLOG_TERMINAL_STATUS_PATH = ROOT / "invest/stages/stage1/inputs/config/blog_terminal_status.json"
BLOG_FIXED_START_DATE = "20160101"
BLOG_TERMINAL_CAUSES = {"empty-posts", "404", "page1-links-0"}
TELEGRAM_TERMINAL_CLASSIFICATIONS = {"bot", "contact", "join-only", "non-channel"}


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_noncomment_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    vals: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        vals.append(s)
    return vals


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


def _years_ago_yyyymmdd(years: int) -> str:
    now = datetime.now(timezone.utc).date()
    try:
        past = now.replace(year=now.year - years)
    except ValueError:
        past = now.replace(month=2, day=28, year=now.year - years)
    return past.strftime("%Y%m%d")


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
        "name": name,
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


def _text_source_summary(*, name: str, kind: str, source_dir: Path, pattern: str, regexes: list[str], min_date: str | None = None) -> dict[str, Any]:
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
                    if min_date is not None and dt < min_date:
                        continue
                    dates.append(dt)

    return _manifest_from_dates(
        name=name,
        kind=kind,
        source_dir=source_dir,
        dates=dates,
        files_scanned=len(files),
        rows_seen=len(dates),
    )


def _jsonl_source_summary(*, name: str, kind: str, source_dir: Path, pattern: str, date_fields: list[str]) -> dict[str, Any]:
    files = sorted(source_dir.glob(pattern)) if source_dir.exists() else []
    dates: list[str] = []
    rows_seen = 0

    for path in files:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    rows_seen += 1
                    for field in date_fields:
                        dt = _normalize_iso_date(obj.get(field, ""))
                        if dt is not None:
                            dates.append(dt)
                            break
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


def _telegram_observed_keys(files: list[Path]) -> set[str]:
    observed: set[str] = set()
    for path in files:
        name = path.name
        if name.endswith("_public_fallback.md"):
            observed.add(name[:-len("_public_fallback.md")].strip().lower())
            continue
        for suffix in ("_full.md", "_recovered.md"):
            if name.endswith(suffix):
                stem = name[:-len(suffix)]
                observed.add(stem.rsplit("_", 1)[-1].strip().lower())
                break
    return observed


def _load_telegram_terminal_status_map() -> dict[str, dict[str, Any]]:
    payload = _load_json(TELEGRAM_TERMINAL_STATUS_PATH) or {}
    entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
    if not isinstance(entries, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in entries.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key or not isinstance(value, dict):
            continue
        normalized[normalized_key] = value
    return normalized


def _load_blog_terminal_statuses() -> dict[str, dict[str, Any]]:
    terminal: dict[str, dict[str, Any]] = {}

    runtime_payload = _load_json(RUNTIME_ROOT / "blog_last_run_status.json") or {}
    if isinstance(runtime_payload, dict):
        for row in runtime_payload.get("buddy_results", []):
            if not isinstance(row, dict):
                continue
            bid = str(row.get("id", "")).strip()
            cause = str(row.get("cause", "")).strip().lower()
            if bid and cause in BLOG_TERMINAL_CAUSES:
                terminal[bid] = {
                    "cause": cause,
                    "status": row.get("status"),
                    "picked_count": row.get("picked_count"),
                    "saved_count": row.get("saved_count"),
                    "normal_completion_class": "MAX_AVAILABLE_OK",
                }

    registry_payload = _load_json(BLOG_TERMINAL_STATUS_PATH) or {}
    registry_entries = registry_payload.get("entries", {}) if isinstance(registry_payload, dict) else {}
    if isinstance(registry_entries, dict):
        for key, value in registry_entries.items():
            bid = str(key).strip()
            cause = str((value or {}).get("cause", "")).strip().lower()
            if not bid or not isinstance(value, dict) or cause not in BLOG_TERMINAL_CAUSES:
                continue
            terminal[bid] = {
                "cause": cause,
                "status": value.get("status") or "terminal-registry",
                "picked_count": value.get("picked_count"),
                "saved_count": value.get("saved_count"),
                "classification": value.get("classification"),
                "evidence": value.get("evidence"),
                "direct_status": value.get("direct_status"),
                "frame_postview_link_count": value.get("frame_postview_link_count"),
                "frame_logno_query_count": value.get("frame_logno_query_count"),
                "rss_item_count": value.get("rss_item_count"),
                "normal_completion_class": "MAX_AVAILABLE_OK",
            }
    return terminal


def _telegram_scope() -> dict[str, Any]:
    allowlist = [item.strip().lower() for item in _read_noncomment_lines(TELEGRAM_ALLOWLIST_PATH)]
    files = sorted(TELEGRAM_DIR.glob("*.md")) if TELEGRAM_DIR.exists() else []
    public_files = sorted(TELEGRAM_DIR.glob("*_public_fallback.md")) if TELEGRAM_DIR.exists() else []
    full_files = [p for p in files if p.name.endswith("_full.md")]
    recovered_files = [p for p in files if p.name.endswith("_recovered.md")]
    observed_keys = _telegram_observed_keys(files)
    raw_missing_allowlist_entries = [x for x in allowlist if x not in observed_keys]
    terminal_status_map = _load_telegram_terminal_status_map()
    terminal_allowlist_entries = []
    unresolved_missing_allowlist_entries = []
    for item in raw_missing_allowlist_entries:
        terminal_info = terminal_status_map.get(item)
        classification = str((terminal_info or {}).get("classification", "")).strip().lower()
        if classification in TELEGRAM_TERMINAL_CLASSIFICATIONS:
            terminal_allowlist_entries.append(
                {
                    "id": item,
                    "classification": classification,
                    "final_url": terminal_info.get("final_url"),
                    "page_title": terminal_info.get("page_title"),
                    "messages": terminal_info.get("messages"),
                    "normal_completion_class": "MAX_AVAILABLE_OK",
                }
            )
        else:
            unresolved_missing_allowlist_entries.append(item)
    collector_status = _load_json(TELEGRAM_COLLECTOR_STATUS_PATH) or {}
    return {
        "coverage_basis": "telegram allowlist registry + observed markdown artifacts + terminal/non-archive registry",
        "allowlist_path": _rel(TELEGRAM_ALLOWLIST_PATH),
        "allowlist_count": len(allowlist),
        "terminal_registry_path": _rel(TELEGRAM_TERMINAL_STATUS_PATH),
        "observed_channel_keys": len(observed_keys),
        "public_fallback_files": len(public_files),
        "full_files": len(full_files),
        "recovered_files": len(recovered_files),
        "raw_missing_allowlist_entries": raw_missing_allowlist_entries,
        "terminal_allowlist_entries": terminal_allowlist_entries,
        "missing_allowlist_entries": unresolved_missing_allowlist_entries,
        "all_channels_satisfied": len(allowlist) > 0 and len(unresolved_missing_allowlist_entries) == 0,
        "dynamic_registry": True,
        "auto_expands_on_allowlist_update": True,
        "current_registry_ssot": _rel(TELEGRAM_ALLOWLIST_PATH),
        "collector_status": collector_status if isinstance(collector_status, dict) else None,
        "note": "telegram coverage는 allowlist 전체를 기준으로 보되, 직접 확인된 contact/join-only/non-channel/bot 대상은 terminal registry로 MAX_AVAILABLE_OK 정상종결 처리한다.",
    }


def _load_blog_buddy_ids() -> list[str]:
    data = _load_json(BUDDIES_PATH) or []
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        bid = str(row.get("id", "")).strip()
        if bid:
            ids.append(bid)
    return ids


def _blog_scope() -> dict[str, Any]:
    subdirs = sorted([p for p in BLOG_DIR.iterdir() if p.is_dir()]) if BLOG_DIR.exists() else []
    buddy_ids = _load_blog_buddy_ids()
    covered_buddy_ids: list[str] = []
    raw_missing_buddy_ids: list[str] = []
    for bid in buddy_ids:
        blog_dir = BLOG_DIR / bid
        has_md = blog_dir.exists() and any(p.is_file() for p in blog_dir.glob("*.md"))
        if has_md:
            covered_buddy_ids.append(bid)
        else:
            raw_missing_buddy_ids.append(bid)
    terminal_statuses = _load_blog_terminal_statuses()
    terminal_missing_buddies = [
        {"id": bid, **terminal_statuses[bid]}
        for bid in raw_missing_buddy_ids
        if bid in terminal_statuses
    ]
    unresolved_missing_buddy_ids = [bid for bid in raw_missing_buddy_ids if bid not in terminal_statuses]
    return {
        "coverage_basis": "naver buddies registry + observed blogId subdirectories + runtime/direct-verified terminal max-available registry",
        "buddy_registry_path": _rel(BUDDIES_PATH),
        "buddy_registry_count": len(buddy_ids),
        "blog_ids_count": len(subdirs),
        "buddies_with_files_count": len(covered_buddy_ids),
        "raw_missing_buddy_count": len(raw_missing_buddy_ids),
        "raw_missing_buddy_ids": raw_missing_buddy_ids,
        "terminal_registry_path": _rel(BLOG_TERMINAL_STATUS_PATH),
        "terminal_missing_buddy_count": len(terminal_missing_buddies),
        "terminal_missing_buddies": terminal_missing_buddies,
        "missing_buddy_count": len(unresolved_missing_buddy_ids),
        "missing_buddy_ids": unresolved_missing_buddy_ids,
        "active_from": BLOG_FIXED_START_DATE,
        "all_buddies_satisfied": len(buddy_ids) > 0 and len(unresolved_missing_buddy_ids) == 0,
        "dynamic_registry": True,
        "auto_expands_on_registry_update": True,
        "current_registry_ssot": _rel(BUDDIES_PATH),
        "note": "blog coverage는 registry 전체를 기준으로 보되 runtime cause(empty-posts/404/page1-links-0)와 direct-verified terminal registry가 가리키는 더 가져올 원문이 없는 케이스를 MAX_AVAILABLE_OK 정상종결로 처리한다.",
    }


def _us_scope() -> dict[str, Any]:
    status = _load_json(US_OHLCV_STATUS_PATH) or {}
    return {
        "coverage_basis": "current S&P500 universe fetch with local csv fallback + observed per-ticker csv files",
        "status_path": _rel(US_OHLCV_STATUS_PATH),
        "status_exists": US_OHLCV_STATUS_PATH.exists(),
        "ticker_source": status.get("ticker_source") if isinstance(status, dict) else None,
        "universe_total": status.get("universe_total") if isinstance(status, dict) else None,
        "stale_ticker_count_before": status.get("stale_ticker_count_before") if isinstance(status, dict) else None,
        "stale_ticker_count_after": status.get("stale_ticker_count_after") if isinstance(status, dict) else None,
        "auto_expands_on_universe_update": True,
        "note": "US OHLCV는 매 run마다 현재 S&P500 universe를 다시 계산하고, 신규 편입 종목도 자동 포함한다. 원격 universe fetch 실패 시에는 로컬 csv 캐시로 계속 수집한다.",
    }


def _news_scope() -> dict[str, Any]:
    cfg = _load_json(NEWS_SOURCES_CONFIG_PATH) or {}
    feeds = cfg.get("feeds", {}) if isinstance(cfg, dict) else {}
    latest_index = sorted(NEWS_URL_INDEX_DIR.glob("*.jsonl"))[-1] if NEWS_URL_INDEX_DIR.exists() and list(NEWS_URL_INDEX_DIR.glob("*.jsonl")) else None
    latest_selected = sorted(NEWS_SELECTED_DIR.glob("*.jsonl"))[-1] if NEWS_SELECTED_DIR.exists() and list(NEWS_SELECTED_DIR.glob("*.jsonl")) else None
    return {
        "coverage_basis": "configured_news_feeds + observed url_index/selected_articles",
        "configured_feed_count": len(feeds) if isinstance(feeds, dict) else 0,
        "config_path": _rel(NEWS_SOURCES_CONFIG_PATH),
        "latest_url_index_file": _rel(latest_index) if latest_index else None,
        "latest_selected_articles_file": _rel(latest_selected) if latest_selected else None,
    }


def _premium_scope() -> dict[str, Any]:
    discovery = _load_json(PREMIUM_DISCOVERY_PATH) or {}
    if not isinstance(discovery, dict):
        discovery = {}
    return {
        "coverage_basis": "premium discovery json + observed markdown files",
        "discovery_path": _rel(PREMIUM_DISCOVERY_PATH),
        "discovery_exists": PREMIUM_DISCOVERY_PATH.exists(),
        "discovery_unique_urls": discovery.get("unique_urls"),
        "discovery_url_source": discovery.get("url_source"),
    }


def _folder_entry(path: Path) -> dict[str, Any]:
    direct_files = [p for p in path.iterdir() if p.is_file()] if path.exists() else []
    recursive_files = [p for p in path.rglob('*') if p.is_file()] if path.exists() else []
    latest = None
    if recursive_files:
        latest = max(recursive_files, key=lambda p: p.stat().st_mtime).stat().st_mtime
    return {
        "path": _rel(path),
        "direct_file_count": len(direct_files),
        "recursive_file_count": len(recursive_files),
        "subdir_count": sum(1 for p in path.iterdir() if p.is_dir()) if path.exists() else 0,
        "latest_mtime_utc": datetime.fromtimestamp(latest, tz=timezone.utc).isoformat() if latest else None,
    }


def _raw_tree_catalog() -> list[dict[str, Any]]:
    if not RAW_ROOT.exists():
        return []
    dirs = sorted([RAW_ROOT] + [p for p in RAW_ROOT.rglob('*') if p.is_dir()])
    return [_folder_entry(p) for p in dirs]


def _runtime_health() -> dict[str, Any]:
    daily = _load_json(DAILY_UPDATE_STATUS_PATH) or {}
    validate = _load_json(POST_COLLECTION_VALIDATE_PATH) or {}
    telegram = _load_json(TELEGRAM_COLLECTOR_STATUS_PATH)
    news_url_status = _load_json(NEWS_URL_INDEX_STATUS_PATH)
    news_selected_status = _load_json(NEWS_SELECTED_STATUS_PATH)

    daily_failures = daily.get("failures", []) if isinstance(daily, dict) else []
    failed_sources: list[dict[str, Any]] = []
    if isinstance(validate, dict) and isinstance(validate.get("details"), list):
        for detail in validate["details"]:
            if not isinstance(detail, dict) or detail.get("ok", False):
                continue
            failed_sources.append({
                "source": detail.get("source"),
                "errors": detail.get("errors", []),
                "collector_used": detail.get("collector_used"),
            })

    return {
        "last_checked_utc": datetime.now(timezone.utc).isoformat(),
        "daily_update": {
            "ok": daily.get("ok") if isinstance(daily, dict) else None,
            "failed_count": daily.get("failed_count") if isinstance(daily, dict) else None,
            "failures": daily_failures,
            "fallbacks_used": daily.get("fallbacks_used", []) if isinstance(daily, dict) else [],
        },
        "post_collection_validate": {
            "ok": validate.get("ok") if isinstance(validate, dict) else None,
            "failed_count": validate.get("failed_count") if isinstance(validate, dict) else None,
            "failed_sources": failed_sources,
        },
        "telegram_collector_status": {
            "expected_path": _rel(TELEGRAM_COLLECTOR_STATUS_PATH),
            "exists": TELEGRAM_COLLECTOR_STATUS_PATH.exists(),
            "payload": telegram if isinstance(telegram, dict) else None,
        },
        "us_ohlcv_status": {
            "expected_path": _rel(US_OHLCV_STATUS_PATH),
            "exists": US_OHLCV_STATUS_PATH.exists(),
            "payload": _load_json(US_OHLCV_STATUS_PATH) if US_OHLCV_STATUS_PATH.exists() else None,
        },
        "news_url_index_status": {
            "expected_path": _rel(NEWS_URL_INDEX_STATUS_PATH),
            "exists": NEWS_URL_INDEX_STATUS_PATH.exists(),
            "payload": news_url_status if isinstance(news_url_status, dict) else None,
        },
        "news_selected_articles_status": {
            "expected_path": _rel(NEWS_SELECTED_STATUS_PATH),
            "exists": NEWS_SELECTED_STATUS_PATH.exists(),
            "payload": news_selected_status if isinstance(news_selected_status, dict) else None,
        },
    }


def _strip_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
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


def update_index() -> dict[str, Any]:
    dart = _dart_summary()
    _write_json(DART_MANIFEST_PATH, dart)

    blog_min_date = BLOG_FIXED_START_DATE

    db_summaries = {
        "dart": dart,
        "kr_ohlcv": _csv_source_summary(name="kr_ohlcv", kind="signal.kr", source_dir=KR_OHLCV_DIR, pattern="*.csv", date_columns=["Date"]),
        "kr_supply": _csv_source_summary(name="kr_supply", kind="signal.kr", source_dir=KR_SUPPLY_DIR, pattern="*_supply.csv", date_columns=["날짜", "Date"]),
        "us_ohlcv": _csv_source_summary(name="us_ohlcv", kind="signal.us", source_dir=US_OHLCV_DIR, pattern="*.csv", date_columns=["Date"]),
        "macro": _csv_source_summary(name="macro", kind="signal.market", source_dir=MACRO_DIR, pattern="*.csv", date_columns=["date", "Date"]),
    }

    source_summaries = {
        "rss": _rss_summary(),
        "news_url_index": _jsonl_source_summary(name="news_url_index", kind="qualitative.market.news", source_dir=NEWS_URL_INDEX_DIR, pattern="*.jsonl", date_fields=["published_date", "published_at"]),
        "news_selected_articles": _jsonl_source_summary(name="news_selected_articles", kind="qualitative.market.news", source_dir=NEWS_SELECTED_DIR, pattern="*.jsonl", date_fields=["published_date", "published_at", "collected_at"]),
        "telegram": _text_source_summary(name="telegram", kind="qualitative.text", source_dir=TELEGRAM_DIR, pattern="*.md", regexes=[r"(?m)^PostDate:\s*([^\n]+)", r"(?m)^Date:\s*([^\n]+)"]),
        "blog": _text_source_summary(name="blog", kind="qualitative.text", source_dir=BLOG_DIR, pattern="*.md", regexes=[r"(?m)^PublishedDate:\s*([^\n]+)"], min_date=blog_min_date),
        "premium": _text_source_summary(name="premium", kind="qualitative.text", source_dir=PREMIUM_DIR, pattern="*.md", regexes=[r"(?m)^PublishedDate:\s*([^\n]+)", r"(?m)^PostDate:\s*([^\n]+)", r"(?m)^Date:\s*([^\n]+)"]),
    }

    dbs: dict[str, Any] = {}
    for key, summary in db_summaries.items():
        dbs[key] = _strip_summary(summary)
        if key == "dart":
            dbs[key]["manifest_path"] = _rel(DART_MANIFEST_PATH)

    sources: dict[str, Any] = {}
    for key, summary in source_summaries.items():
        sources[key] = _strip_summary(summary)

    dbs["us_ohlcv"]["scope"] = _us_scope()
    sources["telegram"]["scope"] = _telegram_scope()
    sources["blog"]["scope"] = _blog_scope()
    sources["news_url_index"]["scope"] = _news_scope()
    sources["news_selected_articles"]["scope"] = _news_scope()
    sources["premium"]["scope"] = _premium_scope()

    taxonomy = {
        "db_types": [
            {"name": "dart", "kind": "qualitative.kr", "path": _rel(DART_DIR), "description": "DART disclosure metadata", "catalog_mode": "date_coverage"},
            {"name": "kr_ohlcv", "kind": "signal.kr", "path": _rel(KR_OHLCV_DIR), "description": "Korean OHLCV by symbol", "catalog_mode": "date_coverage"},
            {"name": "kr_supply", "kind": "signal.kr", "path": _rel(KR_SUPPLY_DIR), "description": "Korean supply/demand by symbol", "catalog_mode": "date_coverage"},
            {"name": "us_ohlcv", "kind": "signal.us", "path": _rel(US_OHLCV_DIR), "description": "US OHLCV by symbol", "catalog_mode": "date_coverage"},
            {"name": "macro", "kind": "signal.market", "path": _rel(MACRO_DIR), "description": "Market macro time series", "catalog_mode": "date_coverage"},
        ],
        "text_types": [
            {"name": "rss", "kind": "qualitative.market", "path": _rel(RSS_DIR), "description": "RSS item snapshots", "catalog_mode": "date_coverage"},
            {"name": "news_url_index", "kind": "qualitative.market.news", "path": _rel(NEWS_URL_INDEX_DIR), "description": "News URL index jsonl", "catalog_mode": "date_coverage"},
            {"name": "news_selected_articles", "kind": "qualitative.market.news", "path": _rel(NEWS_SELECTED_DIR), "description": "Selected article bodies jsonl", "catalog_mode": "date_coverage"},
            {"name": "telegram", "kind": "qualitative.text", "path": _rel(TELEGRAM_DIR), "description": "Telegram channel markdown captures (allowlist full coverage)", "catalog_mode": "date_coverage"},
            {"name": "blog", "kind": "qualitative.text", "path": _rel(BLOG_DIR), "description": "Blog markdown captures by blog id (buddy registry full coverage)", "catalog_mode": "date_coverage"},
            {"name": "premium", "kind": "qualitative.text", "path": _rel(PREMIUM_DIR), "description": "Premium/startale markdown captures", "catalog_mode": "date_coverage"},
        ],
        "note": "Stage1 source taxonomy. blog/telegram coverage is judged against the current full registry/allowlist, and newly added targets are auto-included on the next collection/catalog update.",
    }

    index = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": _rel(RAW_ROOT),
        "taxonomy": taxonomy,
        "dbs": dbs,
        "sources": sources,
        "raw_tree": _raw_tree_catalog(),
        "runtime_health": _runtime_health(),
        "policy": {
            "instruction": "DB/source별 수집 범위 판단과 보고는 source_coverage_index.json 및 개별 coverage summary 기준으로 수행한다.",
            "report_before_using_raw_files": True,
            "raw_tree_instruction": "raw 전체 폴더 구조와 파일 수는 raw_tree를 기준으로 확인한다.",
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
    _ = parser.parse_args()

    index = update_index()
    print(json.dumps({
        "ok": True,
        "dbs": sorted(index.get("dbs", {}).keys()),
        "sources": sorted(index.get("sources", {}).keys()),
        "raw_tree_dirs": len(index.get("raw_tree", [])),
        "index_path": _rel(INDEX_PATH),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
