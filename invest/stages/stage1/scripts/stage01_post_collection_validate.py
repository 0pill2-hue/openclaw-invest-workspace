import json
import os
import time
from datetime import datetime
from pathlib import Path

STAGE1_DIR = Path(__file__).resolve().parents[1]
INVEST_DIR = Path(__file__).resolve().parents[3]
COMMON_INPUT_DATA_DIR = INVEST_DIR / "stages/stage1/outputs"
OUT_PATH = STAGE1_DIR / "outputs/runtime/post_collection_validate.json"

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
        "patterns": ["raw/qualitative/kr/dart/dart_list_*.*"],
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
        "name": "raw/qualitative/text/telegram",
        "script": "invest/stages/stage1/scripts/stage01_scrape_telegram_public_fallback.py",
        "patterns": ["raw/qualitative/text/telegram/**/*.md"],
        "min_count_env": "STAGE1_VALIDATE_MIN_TEXT_TELEGRAM",
        "min_count_default": 1,
        "max_age_env": "STAGE1_VALIDATE_MAX_AGE_SEC_TEXT_TELEGRAM",
        "max_age_default": 168 * 3600,
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
        "patterns": ["raw/qualitative/text/premium/**/*.md"],
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
    failure = None if ok else {"source": spec["name"], "script": spec["script"], "error": "; ".join(errors)}
    return ok, detail, failure


def main():
    now_ts = time.time()
    details = []
    failures = []
    for spec in SOURCE_SPECS:
        ok, detail, failure = validate_source(spec, now_ts)
        details.append(detail)
        if not ok and failure is not None:
            failures.append(failure)

    ok = len(failures) == 0
    payload = {
        "timestamp": datetime.now().isoformat(),
        "ok": True if ok else False,
        "message": "post collection validation ok" if ok else f"post collection validation has {len(failures)} failed checks",
        "failed_count": len(failures),
        "mode": "stage1_core_sources",
        "failures": failures,
        "details": details,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
