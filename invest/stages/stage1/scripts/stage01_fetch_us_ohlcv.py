import ast
import json
import os
import signal
import time
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pandas as pd
import yfinance as yf

from fetch_us_sp500 import fetch_sp500_list
from pipeline_logger import append_pipeline_event

DATA_DIR = "invest/stages/stage1/outputs/raw/signal/us/ohlcv"
STATUS_PATH = os.environ.get("US_OHLCV_STATUS_PATH", "invest/stages/stage1/outputs/runtime/us_ohlcv_status.json")
BASE_START_DATE = os.environ.get("US_OHLCV_BASE_START_DATE", "2016-01-01")
PER_TICKER_TIMEOUT_SEC = int(os.environ.get("US_OHLCV_PER_TICKER_TIMEOUT_SEC", "25"))
DOWNLOAD_RETRIES = int(os.environ.get("US_OHLCV_RETRIES", "3"))
MAX_TICKERS_PER_RUN = int(os.environ.get("US_OHLCV_MAX_TICKERS_PER_RUN", "0"))
SP500_FETCH_RETRIES = int(os.environ.get("US_OHLCV_SP500_FETCH_RETRIES", "3"))
SP500_FETCH_RETRY_SLEEP_SEC = int(os.environ.get("US_OHLCV_SP500_FETCH_RETRY_SLEEP_SEC", "3"))
STALE_LAG_DAYS = int(os.environ.get("US_OHLCV_STALE_LAG_DAYS", "7"))


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class _Timeout:
    def __init__(self, sec: int):
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


def _save_status(payload: dict) -> None:
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


STANDARD_COLUMNS = ["Date", "Open", "High", "Low", "Close", "AdjClose", "Volume"]


def _flatten_col_name(col) -> str:
    if isinstance(col, tuple):
        col = next((str(part).strip() for part in col if str(part).strip()), col[0] if col else "")
    if isinstance(col, str):
        raw = col.strip()
        if raw.startswith("(") and raw.endswith(")"):
            try:
                parsed = ast.literal_eval(raw)
                if isinstance(parsed, tuple) and parsed:
                    raw = next((str(part).strip() for part in parsed if str(part).strip()), raw)
            except Exception:
                pass
        col = raw
    text = str(col).strip()
    if text == "Adj Close":
        return "AdjClose"
    return text



def _normalize_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [_flatten_col_name(col) for col in normalized.columns]

    result = pd.DataFrame(index=normalized.index)
    for name in STANDARD_COLUMNS:
        matching = [col for col in normalized.columns if col == name]
        if not matching:
            result[name] = pd.Series([pd.NA] * len(normalized), index=normalized.index)
            continue
        merged = normalized[matching[0]].copy()
        if isinstance(merged, pd.DataFrame):
            merged = merged.iloc[:, 0]
        for extra in matching[1:]:
            candidate = normalized[extra]
            if isinstance(candidate, pd.DataFrame):
                candidate = candidate.iloc[:, 0]
            merged = merged.combine_first(candidate)
        result[name] = merged

    if "Date" in result.columns:
        result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
        result = result[result["Date"].notna()].copy()
        result["Date"] = result["Date"].dt.strftime("%Y-%m-%d")

    for col in ["Open", "High", "Low", "Close", "AdjClose", "Volume"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    return result



def get_last_date(csv_path: str) -> Optional[pd.Timestamp]:
    if not os.path.exists(csv_path):
        return None
    try:
        df = _normalize_ohlcv_frame(pd.read_csv(csv_path))
    except Exception:
        return None
    if df.empty or "Date" not in df.columns:
        return None
    try:
        dt = pd.to_datetime(df["Date"]).max()
    except Exception:
        return None
    return dt if pd.notna(dt) else None


def _last_date_iso(csv_path: str) -> str:
    dt = get_last_date(csv_path)
    if dt is None:
        return ""
    return dt.date().isoformat()


def _load_cached_us_tickers(limit: int = 0) -> List[str]:
    tickers: List[str] = []
    if not os.path.isdir(DATA_DIR):
        return tickers
    for name in os.listdir(DATA_DIR):
        if not name.endswith(".csv"):
            continue
        if name.startswith("_"):
            continue
        tickers.append(name[:-4])
    tickers = sorted(set(tickers))
    if limit > 0:
        tickers = tickers[:limit]
    return tickers


def _get_tickers_with_auto_bypass() -> Tuple[List[str], str, List[str]]:
    errors: List[str] = []
    for i in range(SP500_FETCH_RETRIES):
        try:
            sp500 = fetch_sp500_list()
            tickers = sp500["Symbol"].dropna().astype(str).tolist()
            tickers = sorted(set(tickers))
            if tickers:
                return tickers, "remote_sp500_ok", errors
            errors.append("remote_sp500_empty")
        except Exception as e:
            errors.append(f"remote_sp500_try{i+1}: {e}")
        if i < SP500_FETCH_RETRIES - 1:
            time.sleep(SP500_FETCH_RETRY_SLEEP_SEC * (i + 1))

    cached = _load_cached_us_tickers()
    if cached:
        errors.append(f"fallback_cache_used:{len(cached)}")
        return cached, "fallback_cached_universe", errors

    raise RuntimeError("S&P500 fetch failed and local fallback cache is empty: " + " | ".join(errors))


def _build_universe_rows(tickers: List[str]) -> List[dict]:
    rows: List[dict] = []
    for ticker in sorted(set(tickers)):
        csv_path = os.path.join(DATA_DIR, f"{ticker}.csv")
        last_date = _last_date_iso(csv_path)
        rows.append({
            "ticker": ticker,
            "csv_path": csv_path,
            "last_date": last_date,
        })
    rows.sort(key=lambda x: (x["last_date"] or "0000-00-00", x["ticker"]))
    return rows


def _compute_stale(rows: List[dict]) -> Tuple[str, int, List[str], dict]:
    last_dates = [str(r.get("last_date") or "") for r in rows if str(r.get("last_date") or "")]
    if not last_dates:
        return "", len(rows), [str(r.get("ticker")) for r in rows[:20]], {}
    latest = max(last_dates)
    latest_dt = datetime.fromisoformat(latest).date()
    stale: List[str] = []
    distribution = Counter(last_dates)
    for row in rows:
        raw = str(row.get("last_date") or "")
        if not raw:
            stale.append(str(row.get("ticker")))
            continue
        try:
            lag_days = (latest_dt - datetime.fromisoformat(raw).date()).days
        except Exception:
            stale.append(str(row.get("ticker")))
            continue
        if lag_days > STALE_LAG_DAYS:
            stale.append(str(row.get("ticker")))
    return latest, len(stale), stale[:20], {k: distribution[k] for k in sorted(distribution.keys())}


def fetch_and_append(ticker: str, start: Optional[str] = None, retries: int = DOWNLOAD_RETRIES, full_collection: bool = False) -> Tuple[str, str]:
    csv_path = os.path.join(DATA_DIR, f"{ticker}.csv")
    if full_collection:
        start = BASE_START_DATE
        has_existing = os.path.exists(csv_path)
    else:
        last_date = get_last_date(csv_path)
        has_existing = last_date is not None
        if last_date is not None:
            start = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        elif not start:
            start = BASE_START_DATE

    data = None
    last_err = ""
    for i in range(retries):
        try:
            with _Timeout(PER_TICKER_TIMEOUT_SEC):
                data = yf.download(ticker, start=start, auto_adjust=False, progress=False, timeout=PER_TICKER_TIMEOUT_SEC)
        except Exception as e:
            last_err = str(e)
            print(f"{ticker} retry {i+1}/{retries} failed: {e}")
            data = None
        if data is not None and not data.empty:
            break
        time.sleep(1 + i)

    if data is None or data.empty:
        if has_existing and not full_collection:
            return "up_to_date", ""
        return "failed", (last_err or "empty data")

    data.reset_index(inplace=True)
    data = _normalize_ohlcv_frame(data)
    if data.empty:
        if has_existing and not full_collection:
            return "up_to_date", ""
        return "failed", "normalized_data_empty"

    if os.path.exists(csv_path) and not full_collection:
        old = _normalize_ohlcv_frame(pd.read_csv(csv_path))
        merged = pd.concat([old, data], ignore_index=True)
        merged.drop_duplicates(subset=["Date"], keep="last", inplace=True)
        merged.sort_values("Date", inplace=True)
        merged.to_csv(csv_path, index=False)
    else:
        data.sort_values("Date", inplace=True)
        data.to_csv(csv_path, index=False)
    return "updated", ""


if __name__ == "__main__":
    ensure_dir(DATA_DIR)

    started_at = datetime.now(timezone.utc)
    try:
        tickers, ticker_source, ticker_fetch_errors = _get_tickers_with_auto_bypass()
    except Exception as e:
        append_pipeline_event(
            source="fetch_us_ohlcv",
            status="FAILED",
            count=0,
            errors=[str(e)],
            note="S&P500 ticker list fetch failed (no fallback available)",
        )
        raise

    full_collection = os.environ.get("FULL_COLLECTION", "0").strip().lower() in ("1", "true", "yes")
    universe_before = _build_universe_rows(tickers)
    latest_before, stale_before, stale_samples_before, dist_before = _compute_stale(universe_before)

    n = len(universe_before)
    run_limit = n if MAX_TICKERS_PER_RUN <= 0 else max(1, min(MAX_TICKERS_PER_RUN, n))
    targets = universe_before[:run_limit]

    print(
        f"US OHLCV run: source={ticker_source} total={n} limit={run_limit} full_collection={int(full_collection)} "
        f"stale_before={stale_before} latest_before={latest_before or '미확인'}",
        flush=True,
    )

    ok_updated = 0
    ok_uptodate = 0
    fail = 0
    errors: List[str] = []
    processed_tickers: List[str] = []

    for idx, row in enumerate(targets, start=1):
        ticker = str(row["ticker"])
        processed_tickers.append(ticker)
        try:
            result, err = fetch_and_append(ticker, full_collection=full_collection)
            if result == "updated":
                ok_updated += 1
            elif result == "up_to_date":
                ok_uptodate += 1
            else:
                fail += 1
                errors.append(f"{ticker}: {err or 'failed'}")
        except Exception as e:
            fail += 1
            errors.append(f"{ticker}: {e}")

        if idx % 20 == 0 or idx == run_limit:
            print(
                f"Progress(us_ohlcv): {idx}/{run_limit} | updated={ok_updated} uptodate={ok_uptodate} fail={fail}",
                flush=True,
            )

    universe_after = _build_universe_rows(tickers)
    latest_after, stale_after, stale_samples_after, dist_after = _compute_stale(universe_after)

    status_payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started_at.isoformat(),
        "ticker_source": ticker_source,
        "ticker_fetch_errors": ticker_fetch_errors,
        "full_collection": full_collection,
        "universe_total": n,
        "processed_count": run_limit,
        "processed_tickers_sample": processed_tickers[:50],
        "updated_count": ok_updated,
        "up_to_date_count": ok_uptodate,
        "failed_count": fail,
        "errors": errors[:200],
        "latest_date_before": latest_before,
        "latest_date_after": latest_after,
        "stale_lag_days": STALE_LAG_DAYS,
        "stale_ticker_count_before": stale_before,
        "stale_ticker_count_after": stale_after,
        "stale_ticker_samples_before": stale_samples_before,
        "stale_ticker_samples_after": stale_samples_after,
        "last_date_distribution_before": dist_before,
        "last_date_distribution_after": dist_after,
        "all_tickers_fresh": stale_after == 0,
        "auto_expands_on_universe_update": True,
    }
    _save_status(status_payload)

    status = "OK" if fail == 0 and stale_after == 0 and ticker_source == "remote_sp500_ok" else "WARN"
    merged_errors = ticker_fetch_errors + errors
    append_pipeline_event(
        source="fetch_us_ohlcv",
        status=status,
        count=ok_updated + ok_uptodate,
        errors=merged_errors[:20],
        note=(
            f"source={ticker_source} processed={run_limit}/{n} updated={ok_updated} uptodate={ok_uptodate} fail={fail} "
            f"stale_before={stale_before} stale_after={stale_after} latest_after={latest_after or '미확인'}"
        ),
    )
    print(
        f"US OHLCV done. source={ticker_source} processed={run_limit}/{n} updated={ok_updated} uptodate={ok_uptodate} fail={fail} "
        f"stale_before={stale_before} stale_after={stale_after} latest_after={latest_after or '미확인'}",
        flush=True,
    )
