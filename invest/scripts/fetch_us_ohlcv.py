import os
import time
import signal

import pandas as pd
import yfinance as yf

from fetch_us_sp500 import fetch_sp500_list
from pipeline_logger import append_pipeline_event

DATA_DIR = "invest/data/raw/us/ohlcv"
BASE_START_DATE = os.environ.get('US_OHLCV_BASE_START_DATE', '2016-01-01')
PER_TICKER_TIMEOUT_SEC = int(os.environ.get('US_OHLCV_PER_TICKER_TIMEOUT_SEC', '25'))
DOWNLOAD_RETRIES = int(os.environ.get('US_OHLCV_RETRIES', '3'))
MAX_TICKERS_PER_RUN = int(os.environ.get('US_OHLCV_MAX_TICKERS_PER_RUN', '80'))
CURSOR_PATH = os.environ.get('US_OHLCV_CURSOR_PATH', 'invest/data/raw/us/ohlcv/_cursor.txt')


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def get_last_date(csv_path):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    if df.empty:
        return None
    return pd.to_datetime(df['Date']).max().date()


class _Timeout:
    def __init__(self, sec):
        self.sec = max(1, int(sec))
        self.prev = None

    def _handler(self, signum, frame):
        raise TimeoutError(f"timeout after {self.sec}s")

    def __enter__(self):
        self.prev = signal.signal(signal.SIGALRM, self._handler)
        signal.alarm(self.sec)

    def __exit__(self, exc_type, exc, tb):
        signal.alarm(0)
        if self.prev is not None:
            signal.signal(signal.SIGALRM, self.prev)


def _load_cursor(default=0):
    try:
        if os.path.exists(CURSOR_PATH):
            with open(CURSOR_PATH, 'r', encoding='utf-8') as f:
                return int((f.read() or '0').strip())
    except Exception:
        pass
    return default


def _save_cursor(i):
    os.makedirs(os.path.dirname(CURSOR_PATH), exist_ok=True)
    with open(CURSOR_PATH, 'w', encoding='utf-8') as f:
        f.write(str(int(i)))


def fetch_and_append(ticker, start=None, retries=DOWNLOAD_RETRIES, full_collection=False):
    csv_path = os.path.join(DATA_DIR, f"{ticker}.csv")
    if full_collection:
        start = BASE_START_DATE
    else:
        last_date = get_last_date(csv_path)
        if last_date:
            start = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        elif not start:
            start = BASE_START_DATE
    data = None
    for i in range(retries):
        try:
            with _Timeout(PER_TICKER_TIMEOUT_SEC):
                data = yf.download(ticker, start=start, auto_adjust=False, progress=False, timeout=PER_TICKER_TIMEOUT_SEC)
        except Exception as e:
            print(f"{ticker} retry {i+1}/{retries} failed: {e}")
            data = None
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
    if os.path.exists(csv_path) and not full_collection:
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

    full_collection = os.environ.get('FULL_COLLECTION', '0').strip().lower() in ('1', 'true', 'yes')

    ok, fail = 0, 0
    errors = []

    n = len(tickers)
    start_idx = _load_cursor(0) % max(1, n)
    run_limit = max(1, min(MAX_TICKERS_PER_RUN, n))

    print(f"US OHLCV chunk run: start_idx={start_idx} limit={run_limit} total={n}")

    for step in range(run_limit):
        i = (start_idx + step) % n
        t = tickers[i]
        try:
            success = fetch_and_append(t, full_collection=full_collection)
            if success:
                ok += 1
            else:
                fail += 1
                errors.append(f"{t}: empty data")
        except Exception as e:
            fail += 1
            errors.append(f"{t}: {e}")

        if (step + 1) % 20 == 0:
            print(f"Progress(chunk): {step+1}/{run_limit} | ok={ok} fail={fail}")

    next_idx = (start_idx + run_limit) % n
    _save_cursor(next_idx)

    status = "OK" if fail == 0 else "WARN"
    append_pipeline_event(
        source="fetch_us_ohlcv",
        status=status,
        count=ok,
        errors=errors[:20],
        note=f"Chunk done. processed={run_limit}/{n} start={start_idx} next={next_idx} ok={ok} fail={fail}",
    )
    print(f"Chunk done. processed={run_limit}/{n} next={next_idx} ok={ok} fail={fail}")
