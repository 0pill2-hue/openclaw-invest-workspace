import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

OUT_DIR = "invest/data/dart"
KEY_FILE = "invest/config/dart_api_key.txt"


def load_key():
    key = os.environ.get("DART_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def fetch_list(api_key, bgn_de, end_de, page_no=1, page_count=100):
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": page_no,
        "page_count": page_count,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    key = load_key()
    if not key:
        print("DART key not found. skip")
        return

    # collect last 2 days by default (safe for night runs)
    end = datetime.now().strftime("%Y%m%d")
    bgn = (datetime.now() - timedelta(days=2)).strftime("%Y%m%d")

    first = fetch_list(key, bgn, end, page_no=1, page_count=100)
    status = first.get("status")
    msg = first.get("message", "")
    if status != "000":
        print(f"DART API error: {status} {msg}")
        return

    total_count = int(first.get("total_count", 0))
    total_page = int(first.get("total_page", 1))
    rows = first.get("list", [])

    for p in range(2, total_page + 1):
        data = fetch_list(key, bgn, end, page_no=p, page_count=100)
        if data.get("status") != "000":
            break
        rows.extend(data.get("list", []))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(OUT_DIR, f"dart_list_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"bgn_de": bgn, "end_de": end, "total_count": total_count, "rows": rows}, f, ensure_ascii=False, indent=2)

    if rows:
        df = pd.DataFrame(rows)
        csv_path = os.path.join(OUT_DIR, f"dart_list_{ts}.csv")
        df.to_csv(csv_path, index=False)
        print(f"Saved DART disclosures: {len(df)} rows -> {csv_path}")
    else:
        print("Saved DART disclosures: 0 rows")


if __name__ == "__main__":
    main()
