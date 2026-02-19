import glob
import json
import os
from datetime import datetime, timedelta

STATUS_PATH = "invest/data/runtime/daily_update_status.json"
OUT_PATH = "invest/data/runtime/post_collection_validate.json"
US_DIR = "invest/data/raw/us/ohlcv"
RSS_DIR = "invest/data/raw/market/news/rss"


def _file_mtime(path):
    """
    
        Role: 파일의 마지막 수정 시각(mtime)을 반환한다.
        Input: path (파일 경로)
        Output: datetime 객체 또는 None
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
    try:
        return datetime.fromtimestamp(os.path.getmtime(path))
    except Exception:
        return None


def _is_us_active_window_kst(now):
    """
    
        Role: KST 기준으로 미국 주식 시장이 활성 상태인 시간대인지 판단한다.
        Input: now (현재 시각)
        Output: bool
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
    # KST 기준 대략적 미국장 활성 구간(서머타임/비서머타임 오차를 흡수하기 위해 완충)
    # 22:00~07:00 구간은 엄격 기준, 그 외 시간은 완화 기준 적용
    return now.hour >= 22 or now.hour < 7


def _validate_hourly_freshness(now):
    """
    
        Role: 미국 주가 및 RSS 데이터의 최신성(freshness)을 검증한다. 시장 활성 여부에 따라 임계치를 조정한다.
        Input: now (현재 시각)
        Output: failures (실패 내역 리스트)
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
    failures = []

    # US OHLCV freshness: market-active window는 엄격, 비활성 구간은 완화
    us_files = glob.glob(os.path.join(US_DIR, "*.csv"))
    if not us_files:
        failures.append({"script": "invest/scripts/stage01_fetch_us_ohlcv.py", "error": "us_ohlcv files not found"})
    else:
        recent_cut = now - timedelta(hours=3)
        recent = [p for p in us_files if _file_mtime(p) and _file_mtime(p) >= recent_cut]
        latest_ts = max((_file_mtime(p) for p in us_files if _file_mtime(p)), default=None)

        active_window = _is_us_active_window_kst(now)
        min_recent = 300 if active_window else 80
        max_age = timedelta(hours=6) if active_window else timedelta(hours=24)

        recent_ok = len(recent) >= min_recent
        latest_ok = latest_ts is not None and (now - latest_ts) <= max_age

        if not (recent_ok and latest_ok):
            failures.append(
                {
                    "script": "invest/scripts/stage01_fetch_us_ohlcv.py",
                    "error": (
                        f"us_ohlcv freshness insufficient: recent={len(recent)}/{len(us_files)} in 3h, "
                        f"latest={latest_ts.isoformat() if latest_ts else 'unknown'}, "
                        f"mode={'active' if active_window else 'offhours'}"
                    ),
                }
            )

    # RSS freshness
    rss_files = glob.glob(os.path.join(RSS_DIR, "rss_*.json"))
    if not rss_files:
        failures.append({"script": "invest/scripts/stage01_fetch_news_rss.py", "error": "rss files not found"})
    else:
        latest = max(rss_files, key=os.path.getmtime)
        latest_ts = _file_mtime(latest)
        if not latest_ts or latest_ts < now - timedelta(hours=3):
            failures.append(
                {
                    "script": "invest/scripts/stage01_fetch_news_rss.py",
                    "error": f"rss not fresh enough: latest={latest_ts.isoformat() if latest_ts else 'unknown'}",
                }
            )

    return failures


def main():
    """
    Role: main 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
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
