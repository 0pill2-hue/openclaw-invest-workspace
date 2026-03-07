import json
import os
import time
from datetime import datetime
from pathlib import Path

STAGE1_DIR = Path(__file__).resolve().parents[1]
INVEST_DIR = Path(__file__).resolve().parents[3]
COMMON_INPUT_DATA_DIR = INVEST_DIR / "stages/stage1/outputs"
RAW_ROOT = COMMON_INPUT_DATA_DIR / "raw"
OUT_PATH = STAGE1_DIR / "outputs/runtime/post_collection_validate.json"
OCR_POSTPROCESS_VALIDATE_PATH = STAGE1_DIR / "outputs/runtime/stage01_ocr_postprocess_validate.json"
TELEGRAM_COLLECTOR_STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_collector_status.json"

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
    },
    {
        "name": "raw/signal/us/ohlcv",
        "script": "invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py",
        "patterns": ["raw/signal/us/ohlcv/*.csv"],
        "min_count_env": "STAGE1_VALIDATE_MIN_US_OHLCV",
        "min_count_default": 500,
        "max_age_env": "US_OHLCV_DAILY_MAX_AGE_SEC",
        "max_age_default": 36 * 3600,
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
    {
        "name": "raw/qualitative/text/image_map",
        "script": "invest/stages/stage1/scripts/stage01_image_harvester.py",
        "patterns": ["raw/qualitative/text/image_map/*.json"],
        "min_count_env": "STAGE1_VALIDATE_MIN_TEXT_IMAGE_MAP",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_TEXT_IMAGE_MAP",
        "max_age_default": 168 * 3600,
    },
    {
        "name": "raw/qualitative/text/images_ocr",
        "script": "invest/stages/stage1/scripts/stage01_image_harvester.py",
        "patterns": ["raw/qualitative/text/images_ocr/*"],
        "min_count_env": "STAGE1_VALIDATE_MIN_TEXT_IMAGES_OCR",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_TEXT_IMAGES_OCR",
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


def validate_source(spec: dict, now_ts: float) -> tuple[bool, dict, dict | None]:
    files = _collect_files(spec["patterns"])
    min_count = _safe_int_env(spec["min_count_env"], spec["min_count_default"])
    max_age_sec = _safe_int_env(spec["max_age_env"], spec["max_age_default"])
    total = len(files)
    zero_byte_count = sum(1 for f in files if f.stat().st_size == 0)
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
    runtime_status = _load_runtime_status(spec.get("runtime_status_path"))
    if runtime_status is not None:
        detail["runtime_status"] = runtime_status
        detail["collector_used"] = runtime_status.get("successful_collector") or runtime_status.get("selected_collector")
    failure = None if ok else {"source": spec["name"], "script": spec["script"], "error": "; ".join(errors)}
    return ok, detail, failure


def load_ocr_postprocess_detail() -> tuple[dict, dict | None]:
    if not OCR_POSTPROCESS_VALIDATE_PATH.exists():
        detail = {
            "source": "runtime/stage01_ocr_postprocess_validate.json",
            "ok": False,
            "error": "ocr_postprocess_validate_missing",
        }
        return detail, {
            "source": "runtime/stage01_ocr_postprocess_validate.json",
            "script": "invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py",
            "error": "ocr_postprocess_validate_missing",
        }

    try:
        payload = json.loads(OCR_POSTPROCESS_VALIDATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        detail = {
            "source": "runtime/stage01_ocr_postprocess_validate.json",
            "ok": False,
            "error": f"ocr_postprocess_validate_parse_error:{type(exc).__name__}",
        }
        return detail, {
            "source": "runtime/stage01_ocr_postprocess_validate.json",
            "script": "invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py",
            "error": detail["error"],
        }

    detail = {
        "source": "runtime/stage01_ocr_postprocess_validate.json",
        "ok": bool(payload.get("ok", False)),
        "message": payload.get("message", ""),
        "recent_success_count": payload.get("recent_success_count", 0),
        "recent_failed_count": payload.get("recent_failed_count", 0),
        "latest_txt_age_sec": payload.get("latest_txt_age_sec"),
        "errors": payload.get("errors", []),
    }
    failure = None
    if not detail["ok"]:
        failure = {
            "source": "runtime/stage01_ocr_postprocess_validate.json",
            "script": "invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py",
            "error": "; ".join(detail.get("errors", [])) or detail.get("message", "ocr_postprocess_validate_failed"),
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

    ocr_detail, ocr_failure = load_ocr_postprocess_detail()
    details.append(ocr_detail)
    if ocr_failure is not None:
        failures.append(ocr_failure)

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
