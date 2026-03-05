#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = [
    "execution_id",
    "order_id",
    "timestamp",
    "symbol",
    "side",
    "qty",
    "fill_price",
    "fee",
    "tax",
]

DEFAULT_EXPECTED = Path("invest/stages/stage6/inputs/execution_ledger/model_trade_orders.csv")
DEFAULT_LEDGER = Path("invest/stages/stage6/inputs/execution_ledger/broker_execution_ledger.csv")
DEFAULT_OUTPUT = Path("invest/stages/stage6/outputs/reports/stage06_real_execution_parity_latest.json")
DEFAULT_MISMATCH_CSV = Path("invest/stages/stage6/outputs/reports/stage06_real_execution_mismatches_latest.csv")
PARITY_LABEL = "실거래 일치 보장"


@dataclass
class Tol:
    qty: float
    price: float
    fee: float
    tax: float


def _resolve_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "invest").exists():
            return p
    raise RuntimeError("FAIL: cannot resolve workspace root")


def _to_side(v: Any) -> str:
    raw = str(v or "").strip().upper()
    if raw in {"BUY", "B", "매수"}:
        return "BUY"
    if raw in {"SELL", "S", "매도"}:
        return "SELL"
    return raw


def _read_csv_required(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def _ensure_columns(df: pd.DataFrame, cols: list[str], label: str) -> list[str]:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"FAIL: {label} missing required columns: {missing}")
    return missing


def _normalize(df: pd.DataFrame, label: str) -> pd.DataFrame:
    _ensure_columns(df, REQUIRED_COLUMNS, label)
    ndf = df.copy().reset_index().rename(columns={"index": "_row_no"})

    ndf["execution_id"] = ndf["execution_id"].astype(str).str.strip()
    ndf["order_id"] = ndf["order_id"].astype(str).str.strip()
    ndf["symbol"] = ndf["symbol"].astype(str).str.strip().str.upper()
    ndf["side"] = ndf["side"].map(_to_side)

    ndf["ts"] = pd.to_datetime(ndf["timestamp"], errors="coerce")
    ndf["date"] = ndf["ts"].dt.strftime("%Y-%m-%d")

    for col in ["qty", "fill_price", "fee", "tax"]:
        ndf[col] = pd.to_numeric(ndf[col], errors="coerce")

    return ndf


def _pair_by_key(expected: pd.DataFrame, ledger: pd.DataFrame, key_col: str, matched_exp: set[int], matched_led: set[int]) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []

    em = expected[(~expected["_row_no"].isin(matched_exp)) & (expected[key_col].astype(str).str.len() > 0)]
    lm = ledger[(~ledger["_row_no"].isin(matched_led)) & (ledger[key_col].astype(str).str.len() > 0)]
    if em.empty or lm.empty:
        return pairs

    for k, eg in em.groupby(key_col):
        lg = lm[lm[key_col] == k]
        if lg.empty:
            continue
        es = eg.sort_values(["ts", "_row_no"])
        ls = lg.sort_values(["ts", "_row_no"])
        n = min(len(es), len(ls))
        for eidx, lidx in zip(es["_row_no"].tolist()[:n], ls["_row_no"].tolist()[:n]):
            matched_exp.add(int(eidx))
            matched_led.add(int(lidx))
            pairs.append((int(eidx), int(lidx), key_col))
    return pairs


def _pair_by_composite(expected: pd.DataFrame, ledger: pd.DataFrame, matched_exp: set[int], matched_led: set[int]) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    em = expected[~expected["_row_no"].isin(matched_exp)].copy()
    lm = ledger[~ledger["_row_no"].isin(matched_led)].copy()
    if em.empty or lm.empty:
        return pairs

    em["_ckey"] = em["date"].astype(str) + "|" + em["symbol"].astype(str) + "|" + em["side"].astype(str)
    lm["_ckey"] = lm["date"].astype(str) + "|" + lm["symbol"].astype(str) + "|" + lm["side"].astype(str)

    for k, eg in em.groupby("_ckey"):
        lg = lm[lm["_ckey"] == k]
        if lg.empty:
            continue
        es = eg.sort_values(["ts", "_row_no"])
        ls = lg.sort_values(["ts", "_row_no"])
        n = min(len(es), len(ls))
        for eidx, lidx in zip(es["_row_no"].tolist()[:n], ls["_row_no"].tolist()[:n]):
            matched_exp.add(int(eidx))
            matched_led.add(int(lidx))
            pairs.append((int(eidx), int(lidx), "date+symbol+side"))
    return pairs


def _field_diff(a: float, b: float) -> float:
    return abs(float(a) - float(b))


def _recalculate_from_ledger(ledger: pd.DataFrame, initial_capital: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ldf = ledger.sort_values(["ts", "_row_no"]).copy()
    positions: dict[str, list[dict[str, float]]] = defaultdict(list)
    last_price: dict[str, float] = {}

    cash = float(initial_capital)
    realized_pnl = 0.0
    total_fee = 0.0
    total_tax = 0.0
    total_notional_buy = 0.0
    total_notional_sell = 0.0

    underflow_rows: list[dict[str, Any]] = []

    for r in ldf.itertuples(index=False):
        symbol = str(r.symbol)
        side = str(r.side)
        qty = float(r.qty)
        price = float(r.fill_price)
        fee = float(r.fee)
        tax = float(r.tax)

        notional = qty * price
        total_fee += fee
        total_tax += tax
        last_price[symbol] = price

        if side == "BUY":
            total_notional_buy += notional
            cash -= (notional + fee + tax)
            positions[symbol].append({"qty": qty, "unit_cost": (notional + fee + tax) / qty})
            continue

        if side == "SELL":
            total_notional_sell += notional
            proceeds = notional - fee - tax
            cash += proceeds

            remain = qty
            cost_out = 0.0
            lots = positions[symbol]
            while remain > 1e-12 and lots:
                lot = lots[0]
                take = min(float(lot["qty"]), remain)
                cost_out += take * float(lot["unit_cost"])
                lot["qty"] = float(lot["qty"]) - take
                remain -= take
                if lot["qty"] <= 1e-12:
                    lots.pop(0)

            if remain > 1e-12:
                underflow_rows.append(
                    {
                        "mismatch_type": "position_underflow",
                        "symbol": symbol,
                        "timestamp": str(r.timestamp),
                        "requested_sell_qty": qty,
                        "uncovered_qty": remain,
                    }
                )

            realized_pnl += (proceeds - cost_out)
            continue

        underflow_rows.append(
            {
                "mismatch_type": "invalid_side",
                "symbol": symbol,
                "timestamp": str(r.timestamp),
                "side": side,
            }
        )

    open_positions = []
    inventory_cost = 0.0
    inventory_mark = 0.0
    for symbol, lots in positions.items():
        qty = sum(float(x["qty"]) for x in lots)
        if qty <= 1e-12:
            continue
        cost = sum(float(x["qty"]) * float(x["unit_cost"]) for x in lots)
        mark_price = float(last_price.get(symbol, 0.0))
        mark_value = qty * mark_price
        inventory_cost += cost
        inventory_mark += mark_value
        open_positions.append(
            {
                "symbol": symbol,
                "qty": qty,
                "cost_value": cost,
                "mark_price_last_fill": mark_price,
                "mark_value_last_fill": mark_value,
            }
        )

    equity_cost_basis = cash + inventory_cost
    equity_mark_to_last_fill = cash + inventory_mark

    def _ret(equity: float) -> float | None:
        if initial_capital == 0:
            return None
        return (equity / initial_capital) - 1.0

    summary = {
        "initial_capital": initial_capital,
        "cash": cash,
        "realized_pnl": realized_pnl,
        "total_fee": total_fee,
        "total_tax": total_tax,
        "total_notional_buy": total_notional_buy,
        "total_notional_sell": total_notional_sell,
        "equity_cost_basis": equity_cost_basis,
        "equity_mark_to_last_fill": equity_mark_to_last_fill,
        "return_cost_basis": _ret(equity_cost_basis),
        "return_mark_to_last_fill": _ret(equity_mark_to_last_fill),
        "open_positions": open_positions,
    }
    return summary, underflow_rows


def _build_fail_result(reason: str, expected_path: Path, ledger_path: Path) -> dict[str, Any]:
    return {
        "verdict": "FAIL",
        "fail_close": True,
        "stop_reason": reason,
        "reconciliation": {
            "status": "FAIL",
            "mismatch_count": None,
            "mismatch_threshold": None,
        },
        "required_inputs": {
            "expected_trades": str(expected_path),
            "execution_ledger": str(ledger_path),
            "required_schema": REQUIRED_COLUMNS,
            "schema_file": "invest/stages/stage6/inputs/config/schemas/execution_ledger.schema.json",
        },
        "label_policy": {
            "label": PARITY_LABEL,
            "allowed": False,
        },
    }


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any], pd.DataFrame]:
    expected_path: Path = args.expected_trades
    ledger_path: Path = args.execution_ledger

    if not ledger_path.exists():
        return 2, _build_fail_result("FAIL_CLOSE_LEDGER_MISSING", expected_path, ledger_path), pd.DataFrame()
    if not expected_path.exists():
        return 2, _build_fail_result("FAIL_CLOSE_EXPECTED_TRADES_MISSING", expected_path, ledger_path), pd.DataFrame()

    try:
        expected_raw = _read_csv_required(expected_path)
        ledger_raw = _read_csv_required(ledger_path)
        expected = _normalize(expected_raw, "expected_trades")
        ledger = _normalize(ledger_raw, "execution_ledger")
    except Exception as exc:
        fail = _build_fail_result("FAIL_CLOSE_SCHEMA_OR_PARSE_ERROR", expected_path, ledger_path)
        fail["error"] = str(exc)
        return 2, fail, pd.DataFrame()

    parse_issues = []
    for label, df in (("expected", expected), ("ledger", ledger)):
        bad_ts = int(df["date"].isna().sum())
        bad_side = int((~df["side"].isin(["BUY", "SELL"])).sum())
        bad_qty = int(df["qty"].isna().sum())
        bad_price = int(df["fill_price"].isna().sum())
        bad_fee = int(df["fee"].isna().sum())
        bad_tax = int(df["tax"].isna().sum())
        if any(x > 0 for x in [bad_ts, bad_side, bad_qty, bad_price, bad_fee, bad_tax]):
            parse_issues.append(
                {
                    "source": label,
                    "invalid_timestamp": bad_ts,
                    "invalid_side": bad_side,
                    "invalid_qty": bad_qty,
                    "invalid_fill_price": bad_price,
                    "invalid_fee": bad_fee,
                    "invalid_tax": bad_tax,
                }
            )

    mismatch_rows: list[dict[str, Any]] = []

    matched_exp: set[int] = set()
    matched_led: set[int] = set()
    pairs: list[tuple[int, int, str]] = []

    pairs.extend(_pair_by_key(expected, ledger, "execution_id", matched_exp, matched_led))
    pairs.extend(_pair_by_key(expected, ledger, "order_id", matched_exp, matched_led))
    pairs.extend(_pair_by_composite(expected, ledger, matched_exp, matched_led))

    exp_by_row = expected.set_index("_row_no")
    led_by_row = ledger.set_index("_row_no")

    tol = Tol(qty=args.qty_tol, price=args.price_tol, fee=args.fee_tol, tax=args.tax_tol)

    for eidx, lidx, match_key in pairs:
        er = exp_by_row.loc[eidx]
        lr = led_by_row.loc[lidx]

        if str(er["symbol"]) != str(lr["symbol"]):
            mismatch_rows.append(
                {
                    "mismatch_type": "symbol_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_symbol": str(er["symbol"]),
                    "ledger_symbol": str(lr["symbol"]),
                }
            )
        if str(er["side"]) != str(lr["side"]):
            mismatch_rows.append(
                {
                    "mismatch_type": "side_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_side": str(er["side"]),
                    "ledger_side": str(lr["side"]),
                }
            )
        if str(er["date"]) != str(lr["date"]):
            mismatch_rows.append(
                {
                    "mismatch_type": "date_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_date": str(er["date"]),
                    "ledger_date": str(lr["date"]),
                }
            )

        qty_diff = _field_diff(er["qty"], lr["qty"])
        if qty_diff > tol.qty:
            mismatch_rows.append(
                {
                    "mismatch_type": "qty_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_qty": float(er["qty"]),
                    "ledger_qty": float(lr["qty"]),
                    "abs_diff": qty_diff,
                    "tolerance": tol.qty,
                }
            )

        price_diff = _field_diff(er["fill_price"], lr["fill_price"])
        if price_diff > tol.price:
            mismatch_rows.append(
                {
                    "mismatch_type": "price_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_fill_price": float(er["fill_price"]),
                    "ledger_fill_price": float(lr["fill_price"]),
                    "abs_diff": price_diff,
                    "tolerance": tol.price,
                }
            )

        fee_diff = _field_diff(er["fee"], lr["fee"])
        if fee_diff > tol.fee:
            mismatch_rows.append(
                {
                    "mismatch_type": "fee_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_fee": float(er["fee"]),
                    "ledger_fee": float(lr["fee"]),
                    "abs_diff": fee_diff,
                    "tolerance": tol.fee,
                }
            )

        tax_diff = _field_diff(er["tax"], lr["tax"])
        if tax_diff > tol.tax:
            mismatch_rows.append(
                {
                    "mismatch_type": "tax_mismatch",
                    "match_key": match_key,
                    "expected_row": int(eidx),
                    "ledger_row": int(lidx),
                    "expected_tax": float(er["tax"]),
                    "ledger_tax": float(lr["tax"]),
                    "abs_diff": tax_diff,
                    "tolerance": tol.tax,
                }
            )

    unmatched_exp = expected[~expected["_row_no"].isin(matched_exp)]
    unmatched_led = ledger[~ledger["_row_no"].isin(matched_led)]

    for r in unmatched_exp.itertuples(index=False):
        mismatch_rows.append(
            {
                "mismatch_type": "missing_in_ledger",
                "expected_row": int(r._row_no),
                "ledger_row": None,
                "date": str(r.date),
                "symbol": str(r.symbol),
                "side": str(r.side),
                "qty": None if pd.isna(r.qty) else float(r.qty),
            }
        )

    for r in unmatched_led.itertuples(index=False):
        mismatch_rows.append(
            {
                "mismatch_type": "unexpected_in_ledger",
                "expected_row": None,
                "ledger_row": int(r._row_no),
                "date": str(r.date),
                "symbol": str(r.symbol),
                "side": str(r.side),
                "qty": None if pd.isna(r.qty) else float(r.qty),
            }
        )

    recalc, recalc_issues = _recalculate_from_ledger(ledger, float(args.initial_capital))
    mismatch_rows.extend(recalc_issues)

    mismatch_count = len(mismatch_rows)
    mismatch_threshold = int(args.mismatch_threshold)
    threshold_breached = mismatch_count > mismatch_threshold

    parse_issue_count = sum(
        int(x[k])
        for x in parse_issues
        for k in ["invalid_timestamp", "invalid_side", "invalid_qty", "invalid_fill_price", "invalid_fee", "invalid_tax"]
    )

    is_pass = (not threshold_breached) and (parse_issue_count == 0)

    mismatch_counter = Counter(str(r.get("mismatch_type", "unknown")) for r in mismatch_rows)

    result = {
        "verdict": "PASS" if is_pass else "FAIL",
        "fail_close": not is_pass,
        "stop_reason": "PASS" if is_pass else "FAIL_CLOSE_RECONCILIATION_MISMATCH",
        "required_inputs": {
            "expected_trades": str(expected_path),
            "execution_ledger": str(ledger_path),
            "required_schema": REQUIRED_COLUMNS,
            "schema_file": "invest/stages/stage6/inputs/config/schemas/execution_ledger.schema.json",
        },
        "matching_policy": {
            "priority": ["execution_id", "order_id", "date+symbol+side"],
            "strict_1to1": True,
        },
        "tolerance": {
            "qty": tol.qty,
            "fill_price": tol.price,
            "fee": tol.fee,
            "tax": tol.tax,
        },
        "counts": {
            "expected_rows": int(len(expected)),
            "ledger_rows": int(len(ledger)),
            "paired_rows": int(len(pairs)),
            "unmatched_expected_rows": int(len(unmatched_exp)),
            "unmatched_ledger_rows": int(len(unmatched_led)),
            "parse_issue_count": int(parse_issue_count),
            "mismatch_count": int(mismatch_count),
            "mismatch_threshold": int(mismatch_threshold),
            "threshold_breached": bool(threshold_breached),
        },
        "parse_issues": parse_issues,
        "mismatch_type_counts": dict(mismatch_counter),
        "mismatch_preview": mismatch_rows[:200],
        "recalculated_performance": {
            "method": "execution-ledger fifo with fee/tax included",
            "summary": recalc,
        },
        "label_policy": {
            "label": PARITY_LABEL,
            "allowed": bool(is_pass),
            "granted": PARITY_LABEL if is_pass else "",
        },
    }

    mismatch_df = pd.DataFrame(mismatch_rows)
    return (0 if is_pass else 2), result, mismatch_df


def parse_args() -> argparse.Namespace:
    root = _resolve_root(Path(__file__).resolve())
    p = argparse.ArgumentParser(description="실거래체결 strict reconciliation + fail-close gate")
    p.add_argument("--expected-trades", type=Path, default=root / DEFAULT_EXPECTED)
    p.add_argument("--execution-ledger", type=Path, default=root / DEFAULT_LEDGER)
    p.add_argument("--output-json", type=Path, default=root / DEFAULT_OUTPUT)
    p.add_argument("--output-mismatch-csv", type=Path, default=root / DEFAULT_MISMATCH_CSV)
    p.add_argument("--initial-capital", type=float, required=True)
    p.add_argument("--qty-tol", type=float, default=1e-9)
    p.add_argument("--price-tol", type=float, default=1e-6)
    p.add_argument("--fee-tol", type=float, default=1e-6)
    p.add_argument("--tax-tol", type=float, default=1e-6)
    p.add_argument("--mismatch-threshold", type=int, default=0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    code, result, mismatch_df = run(args)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    args.output_mismatch_csv.parent.mkdir(parents=True, exist_ok=True)
    if mismatch_df.empty:
        pd.DataFrame(columns=["mismatch_type"]).to_csv(args.output_mismatch_csv, index=False)
    else:
        mismatch_df.to_csv(args.output_mismatch_csv, index=False)

    print(
        json.dumps(
            {
                "verdict": result.get("verdict"),
                "fail_close": result.get("fail_close"),
                "stop_reason": result.get("stop_reason"),
                "output_json": str(args.output_json),
                "output_mismatch_csv": str(args.output_mismatch_csv),
                "label_allowed": ((result.get("label_policy") or {}).get("allowed")),
            },
            ensure_ascii=False,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
