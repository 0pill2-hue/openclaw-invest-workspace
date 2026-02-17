import glob
import json
import os
from datetime import datetime, timedelta

STATUS_PATH = "invest/data/runtime/daily_update_status.json"
OUT_PATH = "invest/data/runtime/post_collection_validate.json"
US_DIR = "invest/data/raw/us/ohlcv"
RSS_DIR = "invest/data/raw/market/news/rss"


def _file_mtime(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path))
    except Exception:
        return None


def _validate_hourly_freshness(now):
    failures = []

    # US OHLCV freshness: enough files updated recently
    us_files = glob.glob(os.path.join(US_DIR, "*.csv"))
    if not us_files:
        failures.append({"script": "invest/scripts/fetch_us_ohlcv.py", "error": "us_ohlcv files not found"})
    else:
        recent_cut = now - timedelta(hours=3)
        recent = [p for p in us_files if _file_mtime(p) and _file_mtime(p) >= recent_cut]
        if len(recent) < 300:
            failures.append(
                {
                    "script": "invest/scripts/fetch_us_ohlcv.py",
                    "error": f"recently updated us_ohlcv files too few: {len(recent)}/{len(us_files)} within 3h",
                }
            )

    # RSS freshness
    rss_files = glob.glob(os.path.join(RSS_DIR, "rss_*.json"))
    if not rss_files:
        failures.append({"script": "invest/scripts/fetch_news_rss.py", "error": "rss files not found"})
    else:
        latest = max(rss_files, key=os.path.getmtime)
        latest_ts = _file_mtime(latest)
        if not latest_ts or latest_ts < now - timedelta(hours=3):
            failures.append(
                {
                    "script": "invest/scripts/fetch_news_rss.py",
                    "error": f"rss not fresh enough: latest={latest_ts.isoformat() if latest_ts else 'unknown'}",
                }
            )

    return failures


def main():
    now = datetime.now()
    result = {
        "timestamp": now.isoformat(),
        "status_file_exists": os.path.exists(STATUS_PATH),
        "ok": True,
        "message": "validation passed",
        "failed_count": 0,
        "mode": "hourly_freshness",
    }

    # Legacy mode: only trust daily status when it's recent (within 6h)
    trusted_daily = False
    if os.path.exists(STATUS_PATH):
        status_mtime = _file_mtime(STATUS_PATH)
        if status_mtime and status_mtime >= now - timedelta(hours=6):
            trusted_daily = True

    if trusted_daily:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            status = json.load(f)
        failed = int(status.get("failed_count", 0))
        result["mode"] = "daily_status_recent"
        result["failed_count"] = failed
        if failed > 0:
            result["ok"] = False
            result["message"] = f"daily update has {failed} failed scripts"
            result["failures"] = status.get("failures", [])
    else:
        failures = _validate_hourly_freshness(now)
        failed = len(failures)
        result["failed_count"] = failed
        if failed > 0:
            result["ok"] = False
            result["message"] = f"hourly freshness has {failed} failed checks"
            result["failures"] = failures

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
