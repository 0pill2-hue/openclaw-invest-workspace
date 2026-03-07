import os
import json
import time
import subprocess
import sys
import requests
import pandas as pd
from datetime import datetime, timedelta

OUT_DIR = "invest/stages/stage1/outputs/raw/qualitative/kr/dart"
KEY_FILE = "invest/stages/stage1/inputs/config/dart_api_key.txt"
COVERAGE_SCRIPT = "invest/stages/stage1/scripts/stage01_update_coverage_manifest.py"


def load_key():
    """
    Role: load_key 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    key = os.environ.get("DART_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def fetch_list(api_key, bgn_de, end_de, page_no=1, page_count=100, retries=3, timeout=20):
    """
    Role: fetch_list 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": page_no,
        "page_count": page_count,
    }
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            wait = min(5, 1 + i)
            print(f"DART request retry {i+1}/{retries} page={page_no}: {e}")
            time.sleep(wait)
    raise RuntimeError(f"DART request failed page={page_no}: {last_err}")


def main():
    """
    Role: main 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    key = load_key()
    if not key:
        print("DART key not found. skip")
        return

    # collect window (default 2 days, full run can override with DART_LOOKBACK_DAYS)
    # optional hard override: DART_BGN_DE / DART_END_DE (YYYYMMDD)
    bgn_env = os.environ.get('DART_BGN_DE', '').strip()
    end_env = os.environ.get('DART_END_DE', '').strip()
    if bgn_env and end_env:
        bgn = bgn_env
        end = end_env
    elif bgn_env:
        bgn = bgn_env
        end = datetime.now().strftime("%Y%m%d")
    elif end_env:
        end = end_env
        lookback_days = int(os.environ.get('DART_LOOKBACK_DAYS', '2'))
        bgn = (datetime.now() - timedelta(days=max(1, lookback_days))).strftime("%Y%m%d")
    else:
        lookback_days = int(os.environ.get('DART_LOOKBACK_DAYS', '2'))
        end = datetime.now().strftime("%Y%m%d")
        bgn = (datetime.now() - timedelta(days=max(1, lookback_days))).strftime("%Y%m%d")

    print(f"DART request window: {bgn} ~ {end}")
    first = fetch_list(key, bgn, end, page_no=1, page_count=100)
    status = first.get("status")
    msg = first.get("message", "")
    if status != "000":
        print(f"DART API error: {status} {msg}")
        return

    total_count = int(first.get("total_count", 0))
    total_page = int(first.get("total_page", 1))
    max_pages = int(os.environ.get("DART_MAX_PAGES", "1000"))
    rows = first.get("list", [])
    print(f"DART page 1/{total_page} rows={len(rows)} total_count={total_count}")

    page_end = min(total_page, max_pages)
    if total_page > max_pages:
        print(f"DART page limit applied: total_page={total_page} max_pages={max_pages}")
    for p in range(2, page_end + 1):
        data = fetch_list(key, bgn, end, page_no=p, page_count=100)
        if data.get("status") != "000":
            print(f"DART page stop at {p}: {data.get('status')} {data.get('message','')}")
            break
        rows.extend(data.get("list", []))
        if p % 10 == 0 or p == page_end:
            print(f"DART page {p}/{total_page} acc_rows={len(rows)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if rows:
        df = pd.DataFrame(rows)
        csv_path = os.path.join(OUT_DIR, f"dart_list_{ts}.csv")
        df.to_csv(csv_path, index=False)
        print(f"Saved DART disclosures: {len(df)} rows -> {csv_path}")
    else:
        print("Saved DART disclosures: 0 rows")

    rc = subprocess.call([sys.executable, COVERAGE_SCRIPT, "--db", "dart"])
    if rc != 0:
        print(f"WARN: coverage manifest update failed rc={rc}")
    else:
        print("DART coverage manifest updated")


if __name__ == "__main__":
    main()
