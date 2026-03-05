import FinanceDataReader as fdr
import pandas as pd
import os
import sys
import time
import json

INCLUDED_MARKETS = ("KOSPI", "KOSDAQ", "KOSDAQ GLOBAL")
INCLUDED_MARKET_IDS = ("STK", "KSQ")
DEFAULT_FALLBACK_CACHE_TTL_HOURS = 6


def _resolve_fallback_cache_ttl_hours() -> int:
    raw = os.getenv("KR_STOCK_LIST_FALLBACK_TTL_HOURS", str(DEFAULT_FALLBACK_CACHE_TTL_HOURS)).strip()
    try:
        ttl = int(raw)
    except ValueError:
        print(
            f"[warn] Invalid KR_STOCK_LIST_FALLBACK_TTL_HOURS='{raw}'. "
            f"Using default {DEFAULT_FALLBACK_CACHE_TTL_HOURS}h."
        )
        ttl = DEFAULT_FALLBACK_CACHE_TTL_HOURS

    if ttl <= 0:
        print(
            f"[warn] Non-positive KR_STOCK_LIST_FALLBACK_TTL_HOURS={ttl}. "
            f"Using default {DEFAULT_FALLBACK_CACHE_TTL_HOURS}h."
        )
        ttl = DEFAULT_FALLBACK_CACHE_TTL_HOURS
    return ttl


FALLBACK_CACHE_TTL_HOURS = _resolve_fallback_cache_ttl_hours()
FALLBACK_CACHE_TTL_SECONDS = FALLBACK_CACHE_TTL_HOURS * 3600


def _looks_like_krx_json_response_error(exc):
    """
    KRX endpoint occasionally returns an empty/non-JSON payload.
    FinanceDataReader then surfaces JSONDecodeError (or similar ValueError text).
    """
    if isinstance(exc, json.JSONDecodeError):
        return True
    message = str(exc).strip().lower()
    return (
        "jsondecodeerror" in message
        or "expecting value" in message
        or "no json object could be decoded" in message
        or "cannot access local variable 'r'" in message
    )


def _normalize_and_filter_universe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    x = df.copy()

    if "Code" in x.columns:
        x["Code"] = x["Code"].astype(str).str.zfill(6)

    if "Market" in x.columns:
        x["Market"] = x["Market"].astype(str).str.upper().str.strip()
        x = x[x["Market"].isin(INCLUDED_MARKETS)].copy()
    elif "MarketId" in x.columns:
        x["MarketId"] = x["MarketId"].astype(str).str.upper().str.strip()
        x = x[x["MarketId"].isin(INCLUDED_MARKET_IDS)].copy()
        if "Market" not in x.columns:
            x["Market"] = x["MarketId"].map({"STK": "KOSPI", "KSQ": "KOSDAQ"}).fillna("UNKNOWN")

    if "Code" in x.columns:
        x = x.drop_duplicates(subset=["Code"], keep="first")
    else:
        x = x.drop_duplicates(keep="first")

    return x


def _fetch_krx_listing_with_retry(max_retries=4, base_backoff_sec=1.0):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            df_krx = fdr.StockListing('KRX')
            if df_krx is None or (isinstance(df_krx, pd.DataFrame) and df_krx.empty):
                raise ValueError("KRX listing response is empty")
            return df_krx
        except Exception as exc:
            last_exc = exc
            retryable = _looks_like_krx_json_response_error(exc) or "response is empty" in str(exc).lower()
            if retryable and attempt < max_retries:
                sleep_sec = base_backoff_sec * (2 ** (attempt - 1))
                print(
                    f"[warn] KRX listing fetch failed (attempt {attempt}/{max_retries}) "
                    f"with transient response issue: {type(exc).__name__}: {exc}. "
                    f"retrying in {sleep_sec:.1f}s..."
                )
                time.sleep(sleep_sec)
                continue

            break

    print(
        "[warn] KRX unified listing endpoint failed repeatedly. "
        "falling back to KOSPI/KOSDAQ merge."
    )
    try:
        parts = []
        for market in ("KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"):
            try:
                df = fdr.StockListing(market)
                if df is not None and not df.empty:
                    parts.append(df)
            except Exception as e:
                print(f"[warn] fallback market listing failed ({market}): {type(e).__name__}: {e}")

        if not parts:
            raise RuntimeError("fallback returned empty frames for all target markets")

        merged = pd.concat(parts, ignore_index=True)
        dedup_cols = [c for c in ("Code", "Name", "Symbol") if c in merged.columns]
        if dedup_cols:
            merged = merged.drop_duplicates(subset=dedup_cols[0], keep="first")
        else:
            merged = merged.drop_duplicates(keep="first")
        return merged
    except Exception as fallback_exc:
        raise RuntimeError(
            "Failed to fetch stock list via both KRX and market fallback. "
            f"krx_error_type={type(last_exc).__name__ if last_exc else 'unknown'}, "
            f"krx_error={last_exc}, "
            f"fallback_error_type={type(fallback_exc).__name__}, "
            f"fallback_error={fallback_exc}"
        ) from fallback_exc


def fetch_kr_stock_list():
    """
    Role: fetch_kr_stock_list 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-03-04
    """
    output_path = 'invest/stages/stage1/outputs/master/kr_stock_list.csv'
    print("Fetching KRX stock list...")
    # Universe policy: include only KOSPI + KOSDAQ family (KOSDAQ GLOBAL included), exclude KONEX.
    try:
        df_krx = _fetch_krx_listing_with_retry()
        df_universe = _normalize_and_filter_universe(df_krx)
        if df_universe.empty:
            raise RuntimeError("Filtered universe is empty after applying market policy")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_universe.to_csv(output_path, index=False, encoding='utf-8-sig')

        if "Market" in df_universe.columns:
            market_counts = df_universe["Market"].value_counts(dropna=False).to_dict()
        else:
            market_counts = {}

        print(f"Saved {len(df_universe)} stocks to {output_path}")
        print(f"Universe policy: include={INCLUDED_MARKETS}, exclude=others (e.g., KONEX)")
        print(f"Market breakdown: {market_counts}")
        return
    except Exception as exc:
        if os.path.exists(output_path):
            try:
                cache_mtime = os.path.getmtime(output_path)
            except OSError as stat_exc:
                print(
                    f"[warn] Live KRX fetch failed ({type(exc).__name__}: {exc}) and "
                    f"cache stat failed ({type(stat_exc).__name__}: {stat_exc})."
                )
                raise RuntimeError("Cached stock list stat failed; fallback not allowed.") from stat_exc

            cache_age_seconds = time.time() - cache_mtime
            if cache_age_seconds < 0:
                raise RuntimeError(
                    "Cached stock list has future mtime; fallback not allowed. "
                    f"cache_age_seconds={cache_age_seconds:.1f}"
                )

            if cache_age_seconds > FALLBACK_CACHE_TTL_SECONDS:
                cache_age_hours = cache_age_seconds / 3600
                print(
                    f"[warn] Live KRX fetch failed ({type(exc).__name__}: {exc}) but cache is stale. "
                    f"cache_age_hours={cache_age_hours:.2f}, ttl_hours={FALLBACK_CACHE_TTL_HOURS}. "
                    "Fallback denied (fail-close)."
                )
                raise RuntimeError(
                    "Cached stock list is older than fallback TTL; refusing stale fallback. "
                    f"cache_age_hours={cache_age_hours:.2f}, ttl_hours={FALLBACK_CACHE_TTL_HOURS}"
                )

            cached = pd.read_csv(output_path)
            cached_filtered = _normalize_and_filter_universe(cached)
            if not cached_filtered.empty:
                cached_filtered.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(
                    f"[warn] Live KRX fetch failed ({type(exc).__name__}: {exc}). "
                    f"Using cached+filtered stock list within TTL: {output_path} "
                    f"({len(cached_filtered)} rows, age_hours={cache_age_seconds / 3600:.2f}, "
                    f"ttl_hours={FALLBACK_CACHE_TTL_HOURS})."
                )
                return

            raise RuntimeError("Cached stock list exists but is empty after market filtering.")
        raise


if __name__ == "__main__":
    try:
        fetch_kr_stock_list()
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        raise SystemExit(1)
