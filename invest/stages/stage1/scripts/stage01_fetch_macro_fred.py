import os
import time
import pandas as pd
from datetime import datetime

DATA_DIR = "invest/stages/stage1/outputs/raw/signal/market/macro"

SERIES = {
    "FEDFUNDS": "Fed Funds Rate",
    "CPIAUCSL": "CPI",
    "UNRATE": "Unemployment Rate",
    "DGS10": "US 10Y Treasury",
    "DGS2": "US 2Y Treasury",
    "T10Y2Y": "10Y-2Y Spread",
    "VIXCLS": "VIX",
    "BAA10Y": "Moody's BAA - 10Y Spread",
    "AAA10Y": "Moody's AAA - 10Y Spread",
    "TEDRATE": "TED Spread",
    "DEXKOUS": "KRW/USD",
    "IRLTLT01KRM156N": "Korea Long-term Interest Rate (OECD)",
    "WILL5000INDFC": "Wilshire 5000 Index",
    "GDP": "US Nominal GDP",
}


def ensure_dir(path):
    """
    Role: ensure_dir 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs(path, exist_ok=True)


def ten_years_ago_start() -> str:
    """
    Role: ten_years_ago_start 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-03-05
    """
    today = datetime.now().date()
    try:
        start = today.replace(year=today.year - 10)
    except ValueError:
        # Handle leap day (e.g., Feb 29 -> Feb 28)
        start = today.replace(year=today.year - 10, day=28)
    return start.strftime("%Y-%m-%d")


def fetch_series(series_id, start=None, retries=3):
    """
    Role: fetch_series 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    if start is None:
        start = ten_years_ago_start()

    last_err = None
    for i in range(retries):
        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            df = pd.read_csv(url)
            if df is None or df.empty:
                raise ValueError("empty response")

            cols = {str(c).strip().lstrip("\ufeff").lower(): c for c in df.columns}
            date_col = cols.get("date") or cols.get("observation_date") or list(df.columns)[0]
            value_col = cols.get(series_id.lower()) or list(df.columns)[-1]

            out = df[[date_col, value_col]].copy()
            out.columns = ["date", "value"]
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out = out[out["date"] >= pd.to_datetime(start)]
            out["value"] = pd.to_numeric(out["value"], errors="coerce")
            out = out.dropna(subset=["date", "value"]).sort_values("date")
            return out
        except Exception as e:
            last_err = e
            time.sleep(1 + i)
    print(f"Failed {series_id}: {last_err}")
    return None


if __name__ == "__main__":
    ensure_dir(DATA_DIR)
    for sid, name in SERIES.items():
        df = fetch_series(sid)
        if df is None:
            continue
        out = os.path.join(DATA_DIR, f"{sid}.csv")
        df.to_csv(out, index=False)
        print(f"Saved {sid} ({name}) -> {out} ({len(df)})")
