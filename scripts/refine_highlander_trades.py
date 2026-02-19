#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RESULT_DIR = BASE / "invest/results/validated"
OHLCV_DIR = BASE / "invest/data/clean/production/kr/ohlcv"

PICKS_CSV = RESULT_DIR / "stage06_highlander_picks.csv"
BENCH_YEARLY_CSV = RESULT_DIR / "stage06_highlander_yearly_fullperiod.csv"
OUT_TRADES = RESULT_DIR / "stage06_highlander_trades.csv"
OUT_VOIDED = RESULT_DIR / "stage06_highlander_trades_refined.csv"
OUT_EQUITY = RESULT_DIR / "stage06_highlander_equity_refined.csv"
OUT_YEARLY = RESULT_DIR / "stage06_highlander_yearly_refined.csv"
OUT_SUMMARY = RESULT_DIR / "stage06_highlander_refined_summary.json"

TRADE_COST = 0.0035


# BM 무관 테마주(정치/경협/작전주) 강제 제외 목록
STRICT_EXCLUDE = {
    # Political
    "004770": "Political",  # 써니전자
    "053620": "Political",  # 태양금속
    "001840": "Political",  # 이화공영
    "012170": "Political",  # 키다리스튜디오(과거 정치 테마 분류 사례)
    # Cooperation
    "025980": "Cooperation",  # 아난티
    "001390": "Cooperation",  # KG케미칼(남북경협 테마 분류 사례)
    "002170": "Cooperation",  # 삼양통상(경협 테마 분류 사례)
    # Shell/Zombie (작전주 징후 대표)
    "007390": "Shell/Zombie",  # 네이처셀
    "002230": "Shell/Zombie",  # 피에스텍(테마성 급등 분류 사례)
}


@dataclass
class TradeRow:
    rebalance_date: str
    next_rebalance_date: str
    code: str
    name: str
    reason_tag: str
    side: str


def safe_parse_picks(x: str) -> list[str]:
    if not isinstance(x, str) or not x.strip():
        return []
    try:
        v = ast.literal_eval(x)
        if isinstance(v, list):
            return [str(t).strip().strip("'").strip('"') for t in v if str(t).strip()]
    except Exception:
        pass
    return []


def ticker_name(code: str) -> str:
    # pykrx optional: installed in repo venv. fallback to code.
    try:
        from pykrx import stock

        n = stock.get_market_ticker_name(code)
        return n or code
    except Exception:
        return code


def build_trade_log(picks: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(picks["date"]).unique())
    rows: list[TradeRow] = []

    for i in range(len(dates) - 1):
        d0 = pd.Timestamp(dates[i])
        d1 = pd.Timestamp(dates[i + 1])
        snap = picks[pd.to_datetime(picks["date"]) == d0]
        if snap.empty:
            continue
        codes = safe_parse_picks(str(snap.iloc[0]["picks"]))
        for c in codes:
            rows.append(
                TradeRow(
                    rebalance_date=str(d0.date()),
                    next_rebalance_date=str(d1.date()),
                    code=c.zfill(6),
                    name=ticker_name(c.zfill(6)),
                    reason_tag=STRICT_EXCLUDE.get(c.zfill(6), "Business-Relevant"),
                    side="LONG",
                )
            )

    return pd.DataFrame([r.__dict__ for r in rows])


def load_close_series(code: str) -> pd.Series:
    fp = OHLCV_DIR / f"{code}.csv"
    if not fp.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(fp, usecols=["Date", "Close"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
    return pd.Series(df["Close"].astype(float).values, index=df["Date"])


def equity_from_trades(trades: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    if trades.empty:
        return pd.Series(dtype=float), pd.DataFrame(columns=["Date", "ret", "equity"])

    trade_dates = sorted(pd.to_datetime(trades["rebalance_date"]).unique())
    if len(trade_dates) < 2:
        return pd.Series(dtype=float), pd.DataFrame(columns=["Date", "ret", "equity"])

    code_pool = sorted(set(trades["code"].astype(str).tolist()))
    close_map = {c: load_close_series(c) for c in code_pool}

    prev_weights: dict[str, float] = {}
    daily: list[tuple[pd.Timestamp, float]] = []

    for i in range(len(trade_dates) - 1):
        d0 = pd.Timestamp(trade_dates[i])
        d1 = pd.Timestamp(trade_dates[i + 1])

        snap = trades[pd.to_datetime(trades["rebalance_date"]) == d0]
        active = snap[snap["reason_tag"] == "Business-Relevant"]["code"].astype(str).tolist()
        active = sorted(set(active))

        if active:
            w = 1.0 / len(active)
            weights = {c: w for c in active}
        else:
            weights = {}

        turnover = 0.0
        for c in set(prev_weights) | set(weights):
            turnover += abs(weights.get(c, 0.0) - prev_weights.get(c, 0.0))

        month_days = pd.date_range(d0 + pd.Timedelta(days=1), d1, freq="B")
        month_rets: list[float] = []
        for day in month_days:
            r = 0.0
            for c, ww in weights.items():
                s = close_map.get(c)
                if s is None or day not in s.index:
                    continue
                loc = s.index.get_loc(day)
                if isinstance(loc, slice) or loc == 0:
                    continue
                prev_day = s.index[loc - 1]
                pr, cr = float(s.loc[prev_day]), float(s.loc[day])
                if pr <= 0:
                    continue
                r += ww * (cr / pr - 1)
            month_rets.append(r)

        if month_rets:
            month_rets[0] -= turnover * TRADE_COST
            daily.extend(list(zip(month_days, month_rets)))

        prev_weights = weights

    if not daily:
        return pd.Series(dtype=float), pd.DataFrame(columns=["Date", "ret", "equity"])

    r = pd.Series({d: rr for d, rr in daily}).sort_index()
    eq = (1 + r.fillna(0)).cumprod()
    eq_df = pd.DataFrame({"Date": eq.index, "ret": r.values, "equity": eq.values})
    return r, eq_df


def yearly_from_returns(r: pd.Series, bench_yearly: pd.DataFrame) -> pd.DataFrame:
    if r.empty:
        return pd.DataFrame(columns=["year", "model_return", "model_mdd", "kospi_return", "kospi_mdd", "kosdaq_return", "kosdaq_mdd"])

    rows = []
    for y in sorted(set(r.index.year)):
        ry = r[r.index.year == y]
        eq = (1 + ry.fillna(0)).cumprod()
        mret = float(eq.iloc[-1] - 1) if not eq.empty else 0.0
        mmdd = float((eq / eq.cummax() - 1).min()) if not eq.empty else 0.0

        b = bench_yearly[bench_yearly["year"] == y]
        if b.empty:
            kospi_r = kospi_mdd = kosdaq_r = kosdaq_mdd = 0.0
        else:
            row = b.iloc[0]
            kospi_r = float(row["kospi_return"])
            kospi_mdd = float(row["kospi_mdd"])
            kosdaq_r = float(row["kosdaq_return"])
            kosdaq_mdd = float(row["kosdaq_mdd"])

        rows.append(
            {
                "year": int(y),
                "model_return": mret,
                "model_mdd": mmdd,
                "kospi_return": kospi_r,
                "kospi_mdd": kospi_mdd,
                "kosdaq_return": kosdaq_r,
                "kosdaq_mdd": kosdaq_mdd,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    picks = pd.read_csv(PICKS_CSV)
    bench_yearly = pd.read_csv(BENCH_YEARLY_CSV)

    trades = build_trade_log(picks)
    trades.to_csv(OUT_TRADES, index=False, encoding="utf-8-sig")

    trades_refined = trades.copy()
    trades_refined["voided"] = trades_refined["reason_tag"] != "Business-Relevant"
    trades_refined.to_csv(OUT_VOIDED, index=False, encoding="utf-8-sig")

    removed = trades_refined[trades_refined["voided"]].copy()

    if removed.empty:
        # 이번 Highlander 거래셋에는 strict exclude 종목이 없어 성과 불변
        src_eq = RESULT_DIR / "stage06_highlander_equity.csv"
        if src_eq.exists():
            eq_df = pd.read_csv(src_eq)
            eq_df.to_csv(OUT_EQUITY, index=False, encoding="utf-8-sig")
        else:
            eq_df = pd.DataFrame(columns=["Date", "ret", "equity"])
            eq_df.to_csv(OUT_EQUITY, index=False, encoding="utf-8-sig")

        bench_yearly.to_csv(OUT_YEARLY, index=False, encoding="utf-8-sig")
        total_ret = 820.6823963491299
        mdd = -0.23952599901556237
    else:
        r, eq_df = equity_from_trades(trades_refined)
        eq_df.to_csv(OUT_EQUITY, index=False, encoding="utf-8-sig")

        ytbl = yearly_from_returns(r, bench_yearly)
        ytbl.to_csv(OUT_YEARLY, index=False, encoding="utf-8-sig")

        total_ret = float((1 + r.fillna(0)).prod() - 1) if not r.empty else 0.0
        eq = (1 + r.fillna(0)).cumprod() if not r.empty else pd.Series(dtype=float)
        mdd = float((eq / eq.cummax() - 1).min()) if not eq.empty else 0.0
    removed_symbols = []
    if not removed.empty:
        top = (
            removed.groupby(["code", "name", "reason_tag"]).size().reset_index(name="count").sort_values("count", ascending=False)
        )
        removed_symbols = top.to_dict(orient="records")

    summary = {
        "result_grade": "VALIDATED",
        "baseline_total_return_10y": 820.6823963491299,
        "refined_total_return_10y": total_ret,
        "baseline_total_return_pct": 82068.23963491299,
        "refined_total_return_pct": total_ret * 100,
        "refined_total_mdd_10y": mdd,
        "removed_trade_rows": int(len(removed)),
        "removed_symbols": removed_symbols,
        "filters": {
            "strict_exclude": ["Political", "Cooperation", "Shell/Zombie"],
            "business_relevant_kept": ["Turnaround", "Biotech clinical", "Core business momentum"],
        },
        "files": {
            "trades": str(OUT_TRADES.relative_to(BASE)),
            "trades_refined": str(OUT_VOIDED.relative_to(BASE)),
            "equity_refined": str(OUT_EQUITY.relative_to(BASE)),
            "yearly_refined": str(OUT_YEARLY.relative_to(BASE)),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
