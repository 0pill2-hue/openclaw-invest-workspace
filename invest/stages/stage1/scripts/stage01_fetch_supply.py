#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from pykrx import stock

from pipeline_logger import append_pipeline_event
from stage01_atomic_io import append_report_rows, atomic_write_csv, merge_dedup_sort

ROOT = Path(__file__).resolve().parents[4]
STOCK_LIST_PATH = ROOT / "invest/stages/stage1/outputs/master/kr_stock_list.csv"
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/signal/kr/supply"
ANOMALY_REPORT_PATH = ROOT / "invest/stages/stage1/outputs/reports/data_quality/stage01_supply_anomalies.csv"


def _to_standard(df_new: pd.DataFrame) -> pd.DataFrame:
    x = df_new.copy().reset_index().rename(columns={"index": "Date", "날짜": "Date"})
    cols = list(x.columns)
    if len(cols) >= 6:
        x = x.iloc[:, :6]
        x.columns = ["Date", "Inst", "Corp", "Indiv", "Foreign", "Total"]
    else:
        for c in ["Inst", "Corp", "Indiv", "Foreign", "Total"]:
            if c not in x.columns:
                x[c] = None
    x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
    for c in ["Inst", "Corp", "Indiv", "Foreign", "Total"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    return x[["Date", "Inst", "Corp", "Indiv", "Foreign", "Total"]]


def _build_anomaly_rows(code: str, x: pd.DataFrame) -> pd.DataFrame:
    if x.empty:
        return pd.DataFrame()
    records = []

    invalid_date = x["Date"].isna()
    if invalid_date.any():
        for _, _r in x[invalid_date].iterrows():
            records.append({"code": code, "date": "", "reason": "invalid_date", "detail": "Date parse failed"})

    non_numeric = x[["Inst", "Corp", "Indiv", "Foreign", "Total"]].isna().any(axis=1)
    if non_numeric.any():
        for _, r in x[non_numeric].iterrows():
            records.append(
                {
                    "code": code,
                    "date": r["Date"].strftime("%Y-%m-%d") if pd.notna(r["Date"]) else "",
                    "reason": "non_numeric_supply_value",
                    "detail": "one_or_more_columns_nan",
                }
            )

    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)


def _load_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    prev = pd.read_csv(path)
    if "Date" not in prev.columns and len(prev.columns) >= 1:
        prev = prev.rename(columns={prev.columns[0]: "Date"})
    for c in ["Inst", "Corp", "Indiv", "Foreign", "Total"]:
        if c not in prev.columns:
            prev[c] = None
    return prev[["Date", "Inst", "Corp", "Indiv", "Foreign", "Total"]]


def fetch_supply_data() -> int:
    full_collection = os.environ.get("FULL_COLLECTION", "0").strip().lower() in ("1", "true", "yes")

    if not STOCK_LIST_PATH.exists():
        msg = f"Stock list not found: {STOCK_LIST_PATH}"
        append_pipeline_event("fetch_supply", "FAIL", 0, [msg], "missing stock list")
        print(msg)
        return 1

    df_stocks = pd.read_csv(STOCK_LIST_PATH)
    df_stocks["Code"] = df_stocks["Code"].astype(str).str.zfill(6)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    end_date = datetime.now().strftime("%Y%m%d")
    base_start = (datetime.now() - timedelta(days=365 * 10)).strftime("%Y%m%d")

    ok_count = 0
    fail_count = 0
    skip_count = 0
    errors: list[str] = []

    for idx, row in df_stocks.iterrows():
        code = row["Code"]
        name = row.get("Name", "")
        file_path = OUT_DIR / f"{code}_supply.csv"

        try:
            existing = _load_existing(file_path)
        except Exception as exc:
            fail_count += 1
            errors.append(f"{code}: existing_parse_failed:{exc}")
            continue

        start_date = base_start
        if not full_collection and existing is not None and not existing.empty:
            try:
                last_date = pd.to_datetime(existing["Date"], errors="coerce").max()
                if pd.notna(last_date):
                    next_date = (last_date + timedelta(days=1)).strftime("%Y%m%d")
                    if next_date > end_date:
                        skip_count += 1
                        continue
                    start_date = next_date
            except Exception:
                start_date = base_start

        try:
            fetched = stock.get_market_trading_value_by_date(start_date, end_date, code, on="순매수")
            if fetched is None or fetched.empty:
                skip_count += 1
                continue

            x = _to_standard(fetched)
            anomaly_rows = _build_anomaly_rows(code, x)
            append_report_rows(ANOMALY_REPORT_PATH, anomaly_rows)

            # Stage1 raw 원칙: invalid_date만 제외하고 값은 보존한다.
            x = x[x["Date"].notna()].copy()
            x["Date"] = x["Date"].dt.strftime("%Y-%m-%d")

            merged = merge_dedup_sort(existing, x, key_columns=["Date"])
            atomic_write_csv(merged, file_path, index=False)
            ok_count += 1

            if (ok_count + fail_count + skip_count) % 50 == 0:
                print(
                    f"Progress: {idx+1}/{len(df_stocks)} "
                    f"(ok={ok_count}, fail={fail_count}, skip={skip_count})"
                )
            time.sleep(0.03)
        except Exception as exc:
            fail_count += 1
            errors.append(f"{code}({name}): {exc}")
            time.sleep(0.2)

    status = "OK" if fail_count == 0 else "FAIL"
    append_pipeline_event(
        source="fetch_supply",
        status=status,
        count=ok_count,
        errors=errors,
        note=f"total={len(df_stocks)} ok={ok_count} fail={fail_count} skip={skip_count}",
    )

    print(f"KR supply done: ok={ok_count} fail={fail_count} skip={skip_count}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(fetch_supply_data())
