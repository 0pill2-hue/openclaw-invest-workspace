import os
import time

import pandas as pd
import yfinance as yf

from fetch_us_sp500 import fetch_sp500_list
from pipeline_logger import append_pipeline_event

DATA_DIR = "invest/data/us/ohlcv"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def get_last_date(csv_path):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    if df.empty:
        return None
    return pd.to_datetime(df['Date']).max().date()


def fetch_and_append(ticker, start=None, retries=3):
    csv_path = os.path.join(DATA_DIR, f"{ticker}.csv")
    last_date = get_last_date(csv_path)
    if last_date:
        start = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    data = None
    for i in range(retries):
        data = yf.download(ticker, start=start, auto_adjust=False, progress=False)
        if data is not None and not data.empty:
            break
        time.sleep(1 + i)
    if data is None or data.empty:
        return False
    data.reset_index(inplace=True)
    data.rename(columns={
        'Date': 'Date',
        'Open': 'Open',
        'High': 'High',
        'Low': 'Low',
        'Close': 'Close',
        'Adj Close': 'AdjClose',
        'Volume': 'Volume'
    }, inplace=True)
    if os.path.exists(csv_path):
        old = pd.read_csv(csv_path)
        merged = pd.concat([old, data], ignore_index=True)
        merged.drop_duplicates(subset=['Date'], keep='last', inplace=True)
        merged.to_csv(csv_path, index=False)
    else:
        data.to_csv(csv_path, index=False)
    return True


if __name__ == "__main__":
    ensure_dir(DATA_DIR)

    try:
        sp500 = fetch_sp500_list()
        tickers = sp500['Symbol'].tolist()
    except Exception as e:
        append_pipeline_event(
            source="fetch_us_ohlcv",
            status="FAILED",
            count=0,
            errors=[str(e)],
            note="S&P500 ticker list fetch failed",
        )
        raise

    ok, fail = 0, 0
    errors = []
    for i, t in enumerate(tickers, 1):
        try:
            success = fetch_and_append(t)
            if success:
                ok += 1
            else:
                fail += 1
                errors.append(f"{t}: empty data")
        except Exception as e:
            fail += 1
            errors.append(f"{t}: {e}")
        if i % 50 == 0:
            print(f"Progress: {i}/{len(tickers)} | ok={ok} fail={fail}")

    status = "OK" if fail == 0 else "WARN"
    append_pipeline_event(
        source="fetch_us_ohlcv",
        status=status,
        count=ok,
        errors=errors[:20],
        note=f"Done. total={len(tickers)} ok={ok} fail={fail}",
    )
    print(f"Done. ok={ok} fail={fail}")
