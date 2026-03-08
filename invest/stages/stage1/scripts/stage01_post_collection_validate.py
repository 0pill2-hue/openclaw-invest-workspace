from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

STAGE1_DIR = Path(__file__).resolve().parents[1]
INVEST_DIR = Path(__file__).resolve().parents[3]
COMMON_INPUT_DATA_DIR = INVEST_DIR / "stages/stage1/outputs"
RAW_ROOT = COMMON_INPUT_DATA_DIR / "raw"
OUT_PATH = STAGE1_DIR / "outputs/runtime/post_collection_validate.json"
TELEGRAM_COLLECTOR_STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_collector_status.json"
TELEGRAM_ALLOWLIST_PATH = STAGE1_DIR / "inputs/config/telegram_channel_allowlist.txt"
TELEGRAM_LAST_RUN_STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_last_run_status.json"
TELEGRAM_PUBLIC_FALLBACK_STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_public_fallback_status.json"
BLOG_LAST_RUN_STATUS_PATH = STAGE1_DIR / "outputs/runtime/blog_last_run_status.json"
BLOG_BUDDIES_PATH = STAGE1_DIR / "outputs/master/naver_buddies_full.json"
TELEGRAM_TERMINAL_STATUS_PATH = STAGE1_DIR / "inputs/config/telegram_terminal_status.json"
BLOG_TARGET_DATE = os.environ.get("BLOG_DEFAULT_TARGET_DATE", "2016-01-01").strip() or "2016-01-01"
BLOG_DATE_RE = re.compile(r"(?m)^PublishedDate:\s*(\d{4}-\d{2}-\d{2})")
BLOG_TERMINAL_CAUSES = {"empty-posts", "404", "page1-links-0"}
TELEGRAM_TERMINAL_CLASSIFICATIONS = {"bot", "contact", "join-only", "non-channel"}
KR_OHLCV_BENCHMARK_CODE = os.environ.get("STAGE1_VALIDATE_KR_OHLCV_BENCHMARK_CODE", "005930").strip() or "005930"

SOURCE_SPECS = [
    {
        "name": "raw/signal/kr/ohlcv",
        "script": "invest/stages/stage1/scripts/stage01_fetch_ohlcv.py",
        "patterns": ["raw/signal/kr/ohlcv/*.csv"],
        "min_count_env": "STAGE1_VALIDATE_MIN_KR_OHLCV",
        "min_count_default": 2800,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_KR_OHLCV",
        "max_age_default": 48 * 3600,
    },
    {
        "name": "raw/signal/kr/supply",
        "script": "invest/stages/stage1/scripts/stage01_fetch_supply.py",
        "patterns": ["raw/signal/kr/supply/*_supply.csv"],
        "min_count_env": "STAGE1_VALIDATE_MIN_KR_SUPPLY",
        "min_count_default": 2800,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_KR_SUPPLY",
        "max_age_default": 96 * 3600,
        "runtime_status_path": STAGE1_DIR / "outputs/runtime/kr_supply_status.json",
    },
    {
        "name": "raw/signal/us/ohlcv",
        "script": "invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py",
        "patterns": ["raw/signal/us/ohlcv/*.csv"],
        "min_count_env": "STAGE1_VALIDATE_MIN_US_OHLCV",
        "min_count_default": 500,
        "max_age_env": "US_OHLCV_DAILY_MAX_AGE_SEC",
        "max_age_default": 36 * 3600,
        "runtime_status_path": STAGE1_DIR / "outputs/runtime/us_ohlcv_status.json",
    },
    {
        "name": "raw/signal/market/macro",
        "script": "invest/stages/stage1/scripts/stage01_fetch_global_macro.py",
        "patterns": ["raw/signal/market/macro/*"],
        "min_count_env": "STAGE1_VALIDATE_MIN_MARKET_MACRO",
        "min_count_default": 5,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_MARKET_MACRO",
        "max_age_default": 72 * 3600,
    },
    {
        "name": "raw/qualitative/kr/dart",
        "script": "invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py",
        "patterns": ["raw/qualitative/kr/dart/dart_list_*.csv"],
        "min_count_env": "STAGE1_VALIDATE_MIN_KR_DART",
        "min_count_default": 100,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_KR_DART",
        "max_age_default": 72 * 3600,
    },
    {
        "name": "raw/qualitative/market/rss",
        "script": "invest/stages/stage1/scripts/stage01_fetch_news_rss.py",
        "patterns": ["raw/qualitative/market/rss/*.json"],
        "min_count_env": "STAGE1_VALIDATE_MIN_NEWS_RSS",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_NEWS_RSS",
        "max_age_default": 72 * 3600,
    },
    {
        "name": "raw/qualitative/market/news/url_index",
        "script": "invest/stages/stage1/scripts/stage01_build_news_url_index.py",
        "patterns": ["raw/qualitative/market/news/url_index/*.jsonl"],
        "min_count_env": "STAGE1_VALIDATE_MIN_NEWS_URL_INDEX",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_NEWS_URL_INDEX",
        "max_age_default": 72 * 3600,
    },
    {
        "name": "raw/qualitative/market/news/selected_articles",
        "script": "invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py",
        "patterns": ["raw/qualitative/market/news/selected_articles/*.jsonl"],
        "min_count_env": "STAGE1_VALIDATE_MIN_NEWS_SELECTED_ARTICLES",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_NEWS_SELECTED_ARTICLES",
        "max_age_default": 72 * 3600,
    },
    {
        "name": "raw/qualitative/text/telegram",
        "script": "invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py",
        "patterns": ["raw/qualitative/text/telegram/**/*.md"],
        "min_count_env": "STAGE1_VALIDATE_MIN_TEXT_TELEGRAM",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_TEXT_TELEGRAM",
        "max_age_default": 168 * 3600,
        "runtime_status_path": TELEGRAM_COLLECTOR_STATUS_PATH,
    },
    {
        "name": "raw/qualitative/text/blog",
        "script": "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py",
        "patterns": ["raw/qualitative/text/blog/**/*.md"],
        "min_count_env": "STAGE1_VALIDATE_MIN_TEXT_BLOG",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_TEXT_BLOG",
        "max_age_default": 168 * 3600,
        "runtime_status_path": BLOG_LAST_RUN_STATUS_PATH,
    },
    {
        "name": "raw/qualitative/text/premium",
        "script": "invest/stages/stage1/scripts/stage01_collect_premium_startale_channel_auth.py",
        "patterns": ["raw/qualitative/text/premium/**/*.md", "raw/qualitative/text/premium/**/*.json"],
        "min_count_env": "STAGE1_VALIDATE_MIN_TEXT_PREMIUM",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_TEXT_PREMIUM",
        "max_age_default": 168 * 3600,
    },
]


def _safe_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        val = int(raw)
    except ValueError:
        return default
    return val


def _collect_files(patterns: list[str]) -> list[Path]:
    files = []
    for pattern in patterns:
        files.extend(COMMON_INPUT_DATA_DIR.glob(pattern))
    uniq = sorted({f.resolve() for f in files if f.is_file()})
    return [Path(x) for x in uniq]


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


def _dir_snapshot(directory: Path, now_ts: float) -> dict:
    files = sorted([p for p in directory.rglob("*") if p.is_file() and not p.name.startswith(".")])
    latest_mtime = max((f.stat().st_mtime for f in files), default=None)
    suffix_counts = {}
    zero_byte_count = 0
    for file_path in files:
        if file_path.stat().st_size == 0:
            zero_byte_count += 1
        suffix = file_path.suffix or "<no_ext>"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
    return {
        "dir": str(directory.relative_to(COMMON_INPUT_DATA_DIR)),
        "file_count": len(files),
        "zero_byte_count": zero_byte_count,
        "latest": datetime.fromtimestamp(latest_mtime).isoformat() if latest_mtime else None,
        "latest_age_sec": int(now_ts - latest_mtime) if latest_mtime else None,
        "suffix_counts": dict(sorted(suffix_counts.items())),
    }


def build_raw_tree_coverage(now_ts: float) -> dict:
    leaf_dirs = _leaf_directories(RAW_ROOT)
    snapshots = [_dir_snapshot(directory, now_ts) for directory in leaf_dirs]
    empty_leaf_dirs = [item["dir"] for item in snapshots if item["file_count"] == 0]
    return {
        "root": str(RAW_ROOT.relative_to(COMMON_INPUT_DATA_DIR)),
        "leaf_dir_count": len(snapshots),
        "covered_leaf_dirs": len([item for item in snapshots if item["file_count"] > 0]),
        "empty_leaf_dir_count": len(empty_leaf_dirs),
        "empty_leaf_dirs": empty_leaf_dirs,
        "dirs": snapshots,
    }


def _load_runtime_status(path_value) -> dict | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return {"exists": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["exists"] = True
            return payload
    except Exception as exc:
        return {"exists": False, "parse_error": type(exc).__name__}
    return {"exists": False}


def _read_noncomment_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    vals: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        vals.append(value)
    return vals


def _load_blog_buddy_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item.get("id", "")).strip() for item in payload if isinstance(item, dict) and str(item.get("id", "")).strip()]


def _count_blog_pre_target_files(target_date: str) -> int:
    blog_root = RAW_ROOT / "qualitative/text/blog"
    if not blog_root.exists():
        return 0
    count = 0
    for path in blog_root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        match = BLOG_DATE_RE.search(text)
        if not match:
            continue
        if match.group(1) < target_date:
            count += 1
    return count


def _count_blogs_with_files(buddy_ids: list[str]) -> tuple[int, list[str]]:
    blog_root = RAW_ROOT / "qualitative/text/blog"
    covered = 0
    missing: list[str] = []
    for buddy_id in buddy_ids:
        buddy_dir = blog_root / buddy_id
        has_md = buddy_dir.exists() and any(p.is_file() for p in buddy_dir.glob("*.md"))
        if has_md:
            covered += 1
        else:
            missing.append(buddy_id)
    return covered, missing


def _load_telegram_terminal_status_map(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
    if not isinstance(entries, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in entries.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key or not isinstance(value, dict):
            continue
        normalized[normalized_key] = value
    return normalized


def _terminal_blog_statuses(runtime_status: dict | None, buddy_ids: list[str]) -> list[dict]:
    if not isinstance(runtime_status, dict):
        return []
    wanted = {str(item).strip() for item in buddy_ids if str(item).strip()}
    if not wanted:
        return []
    matched: list[dict] = []
    for row in runtime_status.get("buddy_results", []):
        if not isinstance(row, dict):
            continue
        bid = str(row.get("id", "")).strip()
        cause = str(row.get("cause", "")).strip().lower()
        if bid in wanted and cause in BLOG_TERMINAL_CAUSES:
            matched.append(
                {
                    "id": bid,
                    "cause": cause,
                    "status": row.get("status"),
                    "normal_completion_class": "MAX_AVAILABLE_OK",
                    "picked_count": row.get("picked_count"),
                    "saved_count": row.get("saved_count"),
                }
            )
    matched.sort(key=lambda item: item["id"])
    return matched


def _read_csv_last_date(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        value = (line or "").split(",", 1)[0].strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
    return None


def _probe_kr_ohlcv_market_closed() -> dict:
    benchmark_path = RAW_ROOT / "signal/kr/ohlcv" / f"{KR_OHLCV_BENCHMARK_CODE}.csv"
    local_latest_date = _read_csv_last_date(benchmark_path)
    probe = {
        "benchmark_code": KR_OHLCV_BENCHMARK_CODE,
        "benchmark_file": str(benchmark_path.relative_to(COMMON_INPUT_DATA_DIR)) if benchmark_path.exists() else str(benchmark_path),
        "local_latest_date": local_latest_date,
        "waive_freshness": False,
    }
    if not local_latest_date:
        probe["reason"] = "benchmark_local_latest_date_missing"
        return probe

    try:
        import FinanceDataReader as fdr
    except Exception as exc:
        probe["reason"] = f"fdr_import_failed:{type(exc).__name__}"
        return probe

    try:
        local_dt = datetime.fromisoformat(local_latest_date)
    except Exception:
        probe["reason"] = "benchmark_local_latest_date_invalid"
        return probe

    start_date = (local_dt - timedelta(days=10)).date().isoformat()
    end_date = datetime.now().date().isoformat()
    probe["probe_window_start"] = start_date
    probe["probe_window_end"] = end_date

    try:
        df = fdr.DataReader(KR_OHLCV_BENCHMARK_CODE, start_date, end_date)
    except Exception as exc:
        probe["reason"] = f"live_probe_failed:{type(exc).__name__}"
        return probe

    if df is None or df.empty:
        probe["reason"] = "live_probe_empty"
        return probe

    live_latest_date = df.index.max().date().isoformat()
    probe["live_latest_date"] = live_latest_date
    if live_latest_date <= local_latest_date:
        probe["waive_freshness"] = True
        probe["reason"] = "market_closed_or_no_new_trading_day_on_live_probe"
    else:
        probe["reason"] = "live_probe_found_newer_trading_day"
    return probe


def _telegram_observed_keys(files: list[Path]) -> set[str]:
    observed: set[str] = set()
    for file_path in files:
        name = file_path.name
        if name.endswith("_public_fallback.md"):
            observed.add(name[:-len("_public_fallback.md")].strip().lower())
            continue
        for suffix in ("_full.md", "_recovered.md"):
            if name.endswith(suffix):
                stem = name[:-len(suffix)]
                observed.add(stem.rsplit("_", 1)[-1].strip().lower())
                break
    return observed


def _telegram_uses_public_fallback(collector_status: dict | None) -> bool:
    if not isinstance(collector_status, dict):
        return False
    selected = str(
        collector_status.get("successful_collector") or collector_status.get("selected_collector") or ""
    ).strip().lower()
    if "public_fallback" in selected:
        return True
    return bool(collector_status.get("fallback_used"))


def validate_source(spec: dict, now_ts: float) -> tuple[bool, dict, dict | None]:
    files = _collect_files(spec["patterns"])
    min_count = _safe_int_env(spec["min_count_env"], spec["min_count_default"])
    max_age_sec = _safe_int_env(spec["max_age_env"], spec["max_age_default"])
    total = len(files)
    zero_byte_count = sum(1 for f in files if f.stat().st_size == 0)
    ignored_zero_byte_files: list[str] = []
    if spec["name"] == "raw/qualitative/market/news/selected_articles":
        ignored_zero_byte_files = [str(f.relative_to(COMMON_INPUT_DATA_DIR)) for f in files if f.stat().st_size == 0]
        if total - len(ignored_zero_byte_files) > 0:
            zero_byte_count = 0
    latest_mtime = max((f.stat().st_mtime for f in files), default=None)
    latest_age_sec = int(now_ts - latest_mtime) if latest_mtime is not None else None
    freshness_applied = max_age_sec >= 0
    freshness_ok = (latest_age_sec is not None and latest_age_sec <= max_age_sec) if freshness_applied else True

    errors = []
    if total < min_count:
        errors.append(f"count={total} < min_count={min_count}")
    if zero_byte_count > 0:
        errors.append(f"zero_byte_count={zero_byte_count} > 0")
    if freshness_applied and not freshness_ok:
        errors.append(f"latest_age_sec={latest_age_sec} > max_age_sec={max_age_sec}")

    ok = len(errors) == 0
    detail = {
        "source": spec["name"],
        "script": spec["script"],
        "ok": ok,
        "failed_count": 0 if ok else 1,
        "count": total,
        "min_count": min_count,
        "zero_byte_count": zero_byte_count,
        "freshness_applied": freshness_applied,
        "latest": datetime.fromtimestamp(latest_mtime).isoformat() if latest_mtime else None,
        "latest_age_sec": latest_age_sec,
        "max_age_sec": max_age_sec if freshness_applied else None,
        "errors": errors,
    }
    if ignored_zero_byte_files:
        detail["ignored_zero_byte_files"] = ignored_zero_byte_files
        detail["ignored_zero_byte_count"] = len(ignored_zero_byte_files)
    if spec["name"] == "raw/signal/kr/ohlcv" and freshness_applied and any(e.startswith("latest_age_sec=") for e in errors):
        freshness_probe = _probe_kr_ohlcv_market_closed()
        detail["freshness_probe"] = freshness_probe
        if freshness_probe.get("waive_freshness"):
            waived_errors = [e for e in errors if not e.startswith("latest_age_sec=")]
            detail["freshness_waived_reason"] = freshness_probe.get("reason")
            detail["errors"] = waived_errors
            ok = len(waived_errors) == 0
            errors = waived_errors
            detail["ok"] = ok
            detail["failed_count"] = 0 if ok else 1
    runtime_status = _load_runtime_status(spec.get("runtime_status_path"))
    if runtime_status is not None:
        detail["runtime_status"] = runtime_status
        detail["collector_used"] = runtime_status.get("successful_collector") or runtime_status.get("selected_collector")
        if spec["name"] == "raw/signal/kr/supply" and runtime_status.get("external_blocked_login_required") and runtime_status.get("source") == "krx_supply":
            waived_errors = [e for e in errors if not e.startswith("latest_age_sec=")]
            detail["freshness_waived_reason"] = runtime_status.get("reason") or "external_blocked_login_required"
            detail["errors"] = waived_errors
            ok = len(waived_errors) == 0
            errors = waived_errors
            detail["ok"] = ok
            detail["failed_count"] = 0 if ok else 1
        if spec["name"] == "raw/signal/us/ohlcv":
            stale_after = runtime_status.get("stale_ticker_count_after")
            if stale_after not in (None, ""):
                try:
                    stale_after_i = int(stale_after)
                except Exception:
                    stale_after_i = None
                if stale_after_i is not None and stale_after_i != 0:
                    errors.append(f"stale_ticker_count_after={stale_after_i} != 0")
                    detail["errors"] = errors
                    ok = False
                    detail["ok"] = False
                    detail["failed_count"] = 1
    failure = None if ok else {"source": spec["name"], "script": spec["script"], "error": "; ".join(errors)}
    return ok, detail, failure


def validate_blog_full_coverage() -> tuple[dict, dict | None]:
    runtime_status = _load_runtime_status(BLOG_LAST_RUN_STATUS_PATH)
    buddy_ids = _load_blog_buddy_ids(BLOG_BUDDIES_PATH)
    buddies_total = len(buddy_ids)
    buddies_with_files, raw_missing_buddy_ids = _count_blogs_with_files(buddy_ids)
    terminal_buddies = _terminal_blog_statuses(runtime_status, raw_missing_buddy_ids)
    terminal_buddy_ids = {item["id"] for item in terminal_buddies}
    unresolved_missing_buddy_ids = [item for item in raw_missing_buddy_ids if item not in terminal_buddy_ids]
    pre_target_files = _count_blog_pre_target_files(BLOG_TARGET_DATE)

    errors = []
    if not runtime_status or not runtime_status.get("exists"):
        errors.append("blog_last_run_status_missing")
    if buddies_total <= 0:
        errors.append("buddies_total_missing")
    if buddies_total > 0 and unresolved_missing_buddy_ids:
        errors.append(f"unresolved_missing_buddies={len(unresolved_missing_buddy_ids)} != 0")
    if pre_target_files != 0:
        errors.append(f"pre_2016_blog_files={pre_target_files} != 0")

    ok = len(errors) == 0
    detail = {
        "source": "runtime/blog_full_coverage",
        "script": "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py",
        "ok": ok,
        "target_date": BLOG_TARGET_DATE,
        "buddies_total": buddies_total,
        "buddies_with_files": buddies_with_files,
        "raw_missing_buddy_count": len(raw_missing_buddy_ids),
        "raw_missing_buddy_ids": raw_missing_buddy_ids,
        "terminal_missing_buddy_count": len(terminal_buddies),
        "terminal_missing_buddies": terminal_buddies,
        "missing_buddy_count": len(unresolved_missing_buddy_ids),
        "missing_buddy_ids": unresolved_missing_buddy_ids,
        "all_buddies_satisfied": buddies_total > 0 and len(unresolved_missing_buddy_ids) == 0,
        "normal_completion_class": "MAX_AVAILABLE_OK",
        "pre_2016_blog_files": pre_target_files,
        "runtime_status": runtime_status,
        "errors": errors,
    }
    failure = None if ok else {
        "source": "runtime/blog_full_coverage",
        "script": "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py",
        "error": "; ".join(errors),
    }
    return detail, failure


def validate_telegram_full_coverage() -> tuple[dict, dict | None]:
    collector_status = _load_runtime_status(TELEGRAM_COLLECTOR_STATUS_PATH)
    selected = (collector_status or {}).get("successful_collector") or (collector_status or {}).get("selected_collector") or "미확인"
    uses_public_fallback = _telegram_uses_public_fallback(collector_status)
    run_status_path = TELEGRAM_PUBLIC_FALLBACK_STATUS_PATH if uses_public_fallback else TELEGRAM_LAST_RUN_STATUS_PATH
    run_status = _load_runtime_status(run_status_path)
    run_status_proxy_used = False
    if (
        uses_public_fallback
        and (not run_status or not run_status.get("exists"))
        and collector_status
        and collector_status.get("exists")
        and int(collector_status.get("final_returncode", 1)) == 0
    ):
        run_status = {
            **collector_status,
            "status_proxy": "collector_status",
            "status_proxy_reason": "public_fallback_status_missing",
        }
        run_status_proxy_used = True

    allowlist = [item.strip().lower() for item in _read_noncomment_lines(TELEGRAM_ALLOWLIST_PATH) if item.strip()]
    allowlist_total = len(allowlist)
    telegram_files = _collect_files(["raw/qualitative/text/telegram/**/*.md"])
    observed_keys = _telegram_observed_keys(telegram_files)
    raw_missing_channels = [item for item in allowlist if item not in observed_keys]
    terminal_status_map = _load_telegram_terminal_status_map(TELEGRAM_TERMINAL_STATUS_PATH)
    terminal_channels = []
    unresolved_missing_channels = []
    for item in raw_missing_channels:
        terminal_info = terminal_status_map.get(item)
        classification = str((terminal_info or {}).get("classification", "")).strip().lower()
        if classification in TELEGRAM_TERMINAL_CLASSIFICATIONS:
            terminal_channels.append(
                {
                    "id": item,
                    "classification": classification,
                    "final_url": terminal_info.get("final_url"),
                    "page_title": terminal_info.get("page_title"),
                    "messages": terminal_info.get("messages"),
                    "normal_completion_class": "MAX_AVAILABLE_OK",
                    "evidence": terminal_info.get("evidence"),
                }
            )
        else:
            unresolved_missing_channels.append(item)

    errors = []
    if not collector_status or not collector_status.get("exists"):
        errors.append("telegram_collector_status_missing")
    if allowlist_total <= 0:
        errors.append("telegram_allowlist_total_missing")
    if not run_status or not run_status.get("exists"):
        errors.append("telegram_run_status_missing")
    if allowlist_total > 0 and len(unresolved_missing_channels) != 0:
        errors.append(f"missing_channels={len(unresolved_missing_channels)} != 0")

    ok = len(errors) == 0
    detail = {
        "source": "runtime/telegram_full_coverage",
        "script": "invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py",
        "ok": ok,
        "selected_collector": selected,
        "uses_public_fallback": uses_public_fallback,
        "run_status_path": str(run_status_path.relative_to(STAGE1_DIR)),
        "run_status_proxy_used": run_status_proxy_used,
        "allowlist_total": allowlist_total,
        "observed_channel_keys": len(observed_keys),
        "raw_missing_channel_count": len(raw_missing_channels),
        "raw_missing_channels": raw_missing_channels,
        "terminal_channel_count": len(terminal_channels),
        "terminal_channels": terminal_channels,
        "missing_channel_count": len(unresolved_missing_channels),
        "missing_channels": unresolved_missing_channels,
        "all_channels_satisfied": allowlist_total > 0 and len(unresolved_missing_channels) == 0,
        "collector_status": collector_status,
        "run_status": run_status,
        "errors": errors,
    }
    failure = None if ok else {
        "source": "runtime/telegram_full_coverage",
        "script": "invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py",
        "error": "; ".join(errors),
    }
    return detail, failure


def main():
    now_ts = time.time()
    details = []
    failures = []
    for spec in SOURCE_SPECS:
        ok, detail, failure = validate_source(spec, now_ts)
        details.append(detail)
        if not ok and failure is not None:
            failures.append(failure)

    blog_detail, blog_failure = validate_blog_full_coverage()
    details.append(blog_detail)
    if blog_failure is not None:
        failures.append(blog_failure)

    telegram_detail, telegram_failure = validate_telegram_full_coverage()
    details.append(telegram_detail)
    if telegram_failure is not None:
        failures.append(telegram_failure)

    raw_tree_coverage = build_raw_tree_coverage(now_ts)
    ok = len(failures) == 0
    payload = {
        "timestamp": datetime.now().isoformat(),
        "ok": True if ok else False,
        "message": "post collection validation ok" if ok else f"post collection validation has {len(failures)} failed checks",
        "failed_count": len(failures),
        "mode": "stage1_raw_full_coverage",
        "failures": failures,
        "details": details,
        "raw_tree_coverage": raw_tree_coverage,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
