#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd

from pipeline_logger import append_pipeline_event

INCLUDED_MARKETS = ("KOSPI", "KOSDAQ", "KOSDAQ GLOBAL")
INCLUDED_MARKET_IDS = ("STK", "KSQ")
DEFAULT_FALLBACK_CACHE_TTL_HOURS = 6

ROOT = Path(__file__).resolve().parents[4]
OUTPUT_PATH = ROOT / "invest/stages/stage1/outputs/master/kr_stock_list.csv"


def _resolve_fallback_cache_ttl_hours() -> int:
    raw = os.getenv("KR_STOCK_LIST_FALLBACK_TTL_HOURS", str(DEFAULT_FALLBACK_CACHE_TTL_HOURS)).strip()
    try:
        ttl = int(raw)
    except ValueError:
        ttl = DEFAULT_FALLBACK_CACHE_TTL_HOURS
    return ttl if ttl > 0 else DEFAULT_FALLBACK_CACHE_TTL_HOURS


FALLBACK_CACHE_TTL_HOURS = _resolve_fallback_cache_ttl_hours()
FALLBACK_CACHE_TTL_SECONDS = FALLBACK_CACHE_TTL_HOURS * 3600


def _looks_like_krx_json_response_error(exc: Exception) -> bool:
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


def _fetch_krx_listing_with_retry(max_retries: int = 4, base_backoff_sec: float = 1.0) -> pd.DataFrame:
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            df_krx = fdr.StockListing("KRX")
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
                    f"{type(exc).__name__}: {exc}. retry in {sleep_sec:.1f}s"
                )
                time.sleep(sleep_sec)
                continue
            break

    print("[warn] KRX unified listing failed repeatedly. fallback to KOSPI/KOSDAQ merge")
    try:
        parts: list[pd.DataFrame] = []
        for market in ("KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"):
            try:
                df = fdr.StockListing(market)
                if df is not None and not df.empty:
                    parts.append(df)
            except Exception as exc:
                print(f"[warn] fallback market listing failed ({market}): {type(exc).__name__}: {exc}")

        if not parts:
            raise RuntimeError("fallback returned empty frames for all target markets")

        merged = pd.concat(parts, ignore_index=True)
        dedup_cols = [c for c in ("Code", "Name", "Symbol") if c in merged.columns]
        if dedup_cols:
            merged = merged.drop_duplicates(subset=[dedup_cols[0]], keep="first")
        else:
            merged = merged.drop_duplicates(keep="first")
        return merged
    except Exception as fallback_exc:
        raise RuntimeError(
            "Failed to fetch stock list via both KRX and market fallback. "
            f"krx_error_type={type(last_exc).__name__ if last_exc else 'unknown'}, "
            f"krx_error={last_exc}, "
            f"fallback_error_type={type(fallback_exc).__name__}, fallback_error={fallback_exc}"
        ) from fallback_exc


def fetch_kr_stock_list() -> int:
    print("Fetching KRX stock list...")
    try:
        df_krx = _fetch_krx_listing_with_retry()
        df_universe = _normalize_and_filter_universe(df_krx)
        if df_universe.empty:
            raise RuntimeError("Filtered universe is empty after market policy")

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_universe.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

        market_counts = (
            df_universe["Market"].value_counts(dropna=False).to_dict()
            if "Market" in df_universe.columns
            else {}
        )
        print(f"Saved {len(df_universe)} stocks to {OUTPUT_PATH}")
        print(f"Universe policy include={INCLUDED_MARKETS}, exclude=others (e.g., KONEX)")
        print(f"Market breakdown: {market_counts}")

        append_pipeline_event(
            source="fetch_stock_list",
            status="OK",
            count=len(df_universe),
            errors=[],
            note=f"market_breakdown={market_counts}",
        )
        return 0

    except Exception as exc:
        if OUTPUT_PATH.exists():
            try:
                cache_mtime = OUTPUT_PATH.stat().st_mtime
            except OSError as stat_exc:
                append_pipeline_event(
                    source="fetch_stock_list",
                    status="FAIL",
                    count=0,
                    errors=[f"cache_stat_failed:{stat_exc}", f"krx_error:{exc}"],
                    note="fail-close",
                )
                print(f"[error] Cached stock list stat failed: {stat_exc}", file=sys.stderr)
                return 1

            cache_age_seconds = time.time() - cache_mtime
            if cache_age_seconds < 0:
                append_pipeline_event(
                    source="fetch_stock_list",
                    status="FAIL",
                    count=0,
                    errors=[f"future_cache_mtime cache_age_seconds={cache_age_seconds}"],
                    note="fail-close",
                )
                print("[error] Cached stock list has future mtime; fallback denied", file=sys.stderr)
                return 1

            if cache_age_seconds > FALLBACK_CACHE_TTL_SECONDS:
                cache_age_hours = cache_age_seconds / 3600
                append_pipeline_event(
                    source="fetch_stock_list",
                    status="FAIL",
                    count=0,
                    errors=[
                        f"stale_cache cache_age_hours={cache_age_hours:.2f} ttl_hours={FALLBACK_CACHE_TTL_HOURS}",
                        f"krx_error:{exc}",
                    ],
                    note="fail-close",
                )
                print(
                    "[error] Live KRX fetch failed and cache is stale; fallback denied "
                    f"(age={cache_age_hours:.2f}h, ttl={FALLBACK_CACHE_TTL_HOURS}h)",
                    file=sys.stderr,
                )
                return 1

            cached = pd.read_csv(OUTPUT_PATH)
            cached_filtered = _normalize_and_filter_universe(cached)
            if not cached_filtered.empty:
                cached_filtered.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
                append_pipeline_event(
                    source="fetch_stock_list",
                    status="WARN",
                    count=len(cached_filtered),
                    errors=[f"live_fetch_failed:{exc}"],
                    note=(
                        f"fallback_cache_used age_hours={cache_age_seconds / 3600:.2f} "
                        f"ttl_hours={FALLBACK_CACHE_TTL_HOURS}"
                    ),
                )
                print(
                    f"[warn] Live fetch failed ({type(exc).__name__}: {exc}); "
                    f"using cached list within TTL ({cache_age_seconds / 3600:.2f}h)"
                )
                return 0

            append_pipeline_event(
                source="fetch_stock_list",
                status="FAIL",
                count=0,
                errors=["cached_stock_list_empty_after_filter", f"krx_error:{exc}"],
                note="fail-close",
            )
            print("[error] Cached stock list exists but is empty after filtering", file=sys.stderr)
            return 1

        append_pipeline_event(
            source="fetch_stock_list",
            status="FAIL",
            count=0,
            errors=[str(exc)],
            note="no_cache",
        )
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(fetch_kr_stock_list())
