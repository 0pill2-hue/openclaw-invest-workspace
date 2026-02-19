import os
import time
import pandas as pd
from pandas_datareader import data as pdr
from datetime import datetime

DATA_DIR = "invest/data/raw/market/macro"

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


def fetch_series(series_id, start="2000-01-01", retries=3):
    """
    Role: fetch_series 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    last_err = None
    for i in range(retries):
        try:
            df = pdr.DataReader(series_id, "fred", start)
            df.reset_index(inplace=True)
            df.rename(columns={series_id: "value", "DATE": "date"}, inplace=True)
            return df
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
