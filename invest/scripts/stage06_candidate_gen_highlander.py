#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from pykrx import stock

BASE = Path(__file__).resolve().parents[1]
KR_OHLCV = BASE / "invest/data/clean/production/kr/ohlcv"
KR_SUPPLY = BASE / "invest/data/clean/production/kr/supply"
OUT_DIR = BASE / "invest/results/validated"
CACHE_DIR = BASE / "invest/results/test"

START = pd.Timestamp("2016-01-01")
END = pd.Timestamp("2026-02-18")
TRADE_COST = 0.0035  # 35bp
MAX_HOLDINGS = 6


@dataclass
class Params:
    mom_lb: int
    breakout: float
    stop_loss: float
    top_n: int
    min_hold_months: int  # 너무 빠른 익절 억제


@dataclass
class WindowResult:
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    best_params: dict
    train_return: float
    train_mdd: float
    val_return: float
    val_mdd: float


def load_liquid_universe(max_symbols: int = 100) -> list[str]:
    rows: list[tuple[str, float, int]] = []
    cutoff = pd.Timestamp("2024-01-01")
    for fp in KR_OHLCV.glob("*.csv"):
        code = fp.stem
        try:
            df = pd.read_csv(fp, usecols=["Date", "Close", "Volume"])
            if len(df) < 1500:
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close", "Volume"])
            dfr = df[df["Date"] >= cutoff]
            if dfr.empty:
                continue
            turnover = float((dfr["Close"] * dfr["Volume"]).median())
            rows.append((code, turnover, len(df)))
        except Exception:
            continue
    rows.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in rows[:max_symbols]]


def load_symbol_panel(code: str) -> pd.DataFrame | None:
    ohlcv_path = KR_OHLCV / f"{code}.csv"
    supply_path = KR_SUPPLY / f"{code}_supply.csv"
    if not ohlcv_path.exists() or not supply_path.exists():
        return None
    try:
        px = pd.read_csv(ohlcv_path)
        sp = pd.read_csv(supply_path)
    except Exception:
        return None

    if "Date" not in px.columns or "Close" not in px.columns or "Volume" not in px.columns:
        return None
    if "Date" not in sp.columns:
        return None

    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    sp["Date"] = pd.to_datetime(sp["Date"], errors="coerce")
    px = px.dropna(subset=["Date", "Close", "Volume"]).sort_values("Date")
    sp = sp.dropna(subset=["Date"]).sort_values("Date")

    if len(px) < 1200:
        return None

    inst = pd.to_numeric(sp["Inst"], errors="coerce").fillna(0.0) if "Inst" in sp.columns else 0.0
    foreign = pd.to_numeric(sp["Foreign"], errors="coerce").fillna(0.0) if "Foreign" in sp.columns else 0.0
    sp["flow"] = inst + foreign

    df = px[["Date", "Close", "Volume"]].merge(sp[["Date", "flow"]], on="Date", how="left")
    df["flow"] = df["flow"].fillna(0.0)
    df = df[(df["Date"] >= START) & (df["Date"] <= END)].copy()
    if df.empty:
        return None

    df["ret1"] = df["Close"].pct_change().fillna(0.0)
    df["mom20"] = df["Close"].pct_change(20)
    df["mom40"] = df["Close"].pct_change(40)
    df["mom60"] = df["Close"].pct_change(60)
    df["break20"] = df["Close"] / df["Close"].rolling(20).max() - 1
    df["turnover20"] = (df["Close"] * df["Volume"]).rolling(20).mean()
    df["flow20"] = df["flow"].rolling(20).sum()
    df["ma120"] = df["Close"].rolling(120).mean()
    return df


def load_fundamentals_quarterly() -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / "highlander_fund_quarterly_cache.csv"
    if cache.exists():
        df = pd.read_csv(cache)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        return df

    q_dates = pd.date_range(START, END, freq="Q")
    rows = []
    for d in q_dates:
        ds = d.strftime("%Y%m%d")
        try:
            f = stock.get_market_fundamental_by_ticker(ds, market="ALL")
            if f is None or f.empty:
                continue
            x = f.reset_index().rename(columns={"티커": "code"})
            x["Date"] = pd.Timestamp(d)
            rows.append(x[["Date", "code", "PER", "PBR", "DIV"]])
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(columns=["Date", "code", "PER", "PBR", "DIV"])
    out = pd.concat(rows, ignore_index=True)
    for c in ["PER", "PBR", "DIV"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out.to_csv(cache, index=False, encoding="utf-8-sig")
    return out


def build_rebalance_table(universe: list[str]) -> pd.DataFrame:
    panels = []
    for code in universe:
        df = load_symbol_panel(code)
        if df is None or df.empty:
            continue
        month_end = df.set_index("Date").resample("ME").last().reset_index()
        month_end["code"] = code
        panels.append(month_end)
    if not panels:
        raise RuntimeError("No panel data built")
    panel = pd.concat(panels, ignore_index=True)
    panel = panel[(panel["Date"] >= START) & (panel["Date"] <= END)]

    fund = load_fundamentals_quarterly()
    if not fund.empty:
        merged_parts = []
        for code, g in panel.groupby("code", sort=False):
            gf = fund[fund["code"] == code].sort_values("Date")
            gg = g.sort_values("Date")
            if gf.empty:
                gg["PER"] = np.nan
                gg["PBR"] = np.nan
                gg["DIV"] = np.nan
                merged_parts.append(gg)
                continue
            m = pd.merge_asof(
                gg,
                gf[["Date", "PER", "PBR", "DIV"]],
                on="Date",
                direction="backward",
                tolerance=pd.Timedelta(days=120),
            )
            merged_parts.append(m)
        panel = pd.concat(merged_parts, ignore_index=True)
    else:
        panel["PER"] = np.nan
        panel["PBR"] = np.nan
        panel["DIV"] = np.nan

    panel["fin_score"] = (
        (panel["PER"].between(0, 30, inclusive="both")).astype(float)
        + (panel["PBR"].between(0, 3, inclusive="both")).astype(float)
        + (panel["DIV"].fillna(0) > 0).astype(float)
    ).fillna(0.0)

    return panel.sort_values(["Date", "code"]).reset_index(drop=True)


def simulate(panel: pd.DataFrame, params: Params, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Series, pd.DataFrame]:
    p = panel[(panel["Date"] >= start) & (panel["Date"] <= end)].copy()
    if p.empty:
        return pd.Series(dtype=float), pd.DataFrame()

    mom_col = {20: "mom20", 40: "mom40", 60: "mom60"}[params.mom_lb]
    p["score"] = (
        p[mom_col].fillna(-9)
        + 0.35 * p["flow20"].fillna(0).rank(pct=True)
        + 0.15 * p["fin_score"].fillna(0)
    )
    p["eligible"] = (
        (p[mom_col] > 0)
        & (p["break20"] >= -params.breakout)
        & (p["Close"] > p["ma120"])
        & (p["turnover20"] > 1e8)
    )

    months = sorted(p["Date"].unique())
    daily_returns = []
    picks_log = []
    prev_weights: dict[str, float] = {}
    entry_price: dict[str, float] = {}
    held_months: dict[str, int] = {}

    close_map: dict[str, pd.Series] = {}
    for code, g in p.groupby("code"):
        close_map[code] = g.set_index("Date")["Close"].sort_index()

    for i in range(len(months) - 1):
        d0, d1 = pd.Timestamp(months[i]), pd.Timestamp(months[i + 1])
        snap = p[p["Date"] == d0]
        candidates = snap[snap["eligible"]].sort_values("score", ascending=False)
        raw_picks = candidates["code"].tolist()

        # 너무 빠른 익절 억제: min_hold_months 전까지 기존 보유 우선 유지
        forced_keep = [c for c, hm in held_months.items() if hm < params.min_hold_months and c in snap["code"].values]
        picks = forced_keep[:MAX_HOLDINGS]
        for c in raw_picks:
            if len(picks) >= min(MAX_HOLDINGS, params.top_n):
                break
            if c not in picks:
                picks.append(c)

        k = int(max(1, min(MAX_HOLDINGS, params.top_n, len(picks))))
        picks = picks[:k]
        weights = {c: 1.0 / k for c in picks} if k > 0 else {}

        turnover = 0.0
        all_codes = set(prev_weights.keys()) | set(weights.keys())
        for c in all_codes:
            turnover += abs(weights.get(c, 0.0) - prev_weights.get(c, 0.0))

        month_days = pd.date_range(d0 + pd.Timedelta(days=1), d1, freq="B")
        mrets = []
        for day in month_days:
            r = 0.0
            for c, w in weights.items():
                s = close_map.get(c)
                if s is None or day not in s.index:
                    continue
                loc = s.index.get_loc(day)
                if loc == 0:
                    continue
                prev_day = s.index[loc - 1]
                pr, cr = s.loc[prev_day], s.loc[day]
                if pr <= 0:
                    continue
                dr = cr / pr - 1
                ep = entry_price.get(c, pr)
                if ep > 0 and (cr / ep - 1) <= -params.stop_loss:
                    dr = 0.0
                r += w * dr
            mrets.append(r)

        if mrets:
            mrets[0] -= turnover * TRADE_COST
            daily_returns.extend([(day, rr) for day, rr in zip(month_days, mrets)])

        # holding month 업데이트
        new_held = {}
        for c in picks:
            if c in held_months:
                new_held[c] = held_months[c] + 1
            else:
                new_held[c] = 1
        held_months = new_held

        entry_price = {}
        for c in picks:
            s = close_map.get(c)
            if s is not None and d0 in s.index:
                entry_price[c] = float(s.loc[d0])

        prev_weights = weights
        picks_log.append({"date": str(d0.date()), "n_holdings": k, "picks": picks})

    if not daily_returns:
        return pd.Series(dtype=float), pd.DataFrame(picks_log)
    rs = pd.Series({pd.Timestamp(d): r for d, r in daily_returns}).sort_index()
    return rs, pd.DataFrame(picks_log)


def perf_stats(r: pd.Series) -> tuple[float, float]:
    if r.empty:
        return 0.0, 0.0
    eq = (1 + r.fillna(0)).cumprod()
    total = float(eq.iloc[-1] - 1)
    mdd = float((eq / eq.cummax() - 1).min())
    return total, mdd


def make_windows() -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    windows = []
    t0 = pd.Timestamp("2016-01-01")
    while True:
        tr_s = t0
        tr_e = tr_s + pd.DateOffset(years=3) - pd.Timedelta(days=1)
        va_s = tr_e + pd.Timedelta(days=1)
        va_e = va_s + pd.DateOffset(years=1) - pd.Timedelta(days=1)
        if va_e > END:
            break
        windows.append((tr_s, tr_e, va_s, va_e))
        t0 = t0 + pd.DateOffset(years=1)
    return windows


def objective(total_ret: float, mdd: float) -> float:
    penalty = 0.0
    if mdd < -0.40:
        penalty = abs(mdd + 0.40) * 3.0
    return total_ret - penalty


def run_walk_forward(panel: pd.DataFrame) -> tuple[pd.Series, list[WindowResult], pd.DataFrame, Params]:
    param_grid = [
        Params(m, b, s, n, h)
        for m, b, s, n, h in product([20, 40, 60], [0.0, 0.03, 0.06], [0.08, 0.12, 0.16], [1, 2, 3, 4, 5, 6], [0, 2, 4])
    ]

    stitched = []
    window_rows: list[WindowResult] = []
    picks_all = []
    last_best = param_grid[0]

    for tr_s, tr_e, va_s, va_e in make_windows():
        best = None
        best_score = -1e9
        best_train_ret, best_train_mdd = 0.0, 0.0

        for p in param_grid:
            tr_r, _ = simulate(panel, p, tr_s, tr_e)
            tr_ret, tr_mdd = perf_stats(tr_r)
            sc = objective(tr_ret, tr_mdd)
            if sc > best_score:
                best_score = sc
                best = p
                best_train_ret, best_train_mdd = tr_ret, tr_mdd

        assert best is not None
        last_best = best
        va_r, va_pick = simulate(panel, best, va_s, va_e)
        va_ret, va_mdd = perf_stats(va_r)
        stitched.append(va_r)
        if not va_pick.empty:
            va_pick["window_val_start"] = str(va_s.date())
            va_pick["min_hold_months"] = best.min_hold_months
            picks_all.append(va_pick)

        window_rows.append(
            WindowResult(
                train_start=str(tr_s.date()),
                train_end=str(tr_e.date()),
                val_start=str(va_s.date()),
                val_end=str(va_e.date()),
                best_params=asdict(best),
                train_return=best_train_ret,
                train_mdd=best_train_mdd,
                val_return=va_ret,
                val_mdd=va_mdd,
            )
        )

    oos = pd.concat(stitched).sort_index() if stitched else pd.Series(dtype=float)
    picks_df = pd.concat(picks_all, ignore_index=True) if picks_all else pd.DataFrame()
    return oos, window_rows, picks_df, last_best


def load_benchmarks() -> pd.DataFrame:
    s = START.strftime("%Y%m%d")
    e = END.strftime("%Y%m%d")
    kospi = stock.get_index_ohlcv_by_date(s, e, "1001")
    kosdaq = stock.get_index_ohlcv_by_date(s, e, "2001")

    out = pd.DataFrame(index=pd.to_datetime(kospi.index))
    out["KOSPI"] = kospi["종가"].astype(float)
    out = out.join(pd.DataFrame({"KOSDAQ": kosdaq["종가"].astype(float)}, index=pd.to_datetime(kosdaq.index)), how="outer")
    out = out.sort_index().ffill().dropna()
    out["ret_kospi"] = out["KOSPI"].pct_change().fillna(0.0)
    out["ret_kosdaq"] = out["KOSDAQ"].pct_change().fillna(0.0)
    return out


def yearly_table(model_r: pd.Series, bench: pd.DataFrame) -> pd.DataFrame:
    if model_r.empty:
        return pd.DataFrame(columns=["year", "model_return", "model_mdd", "kospi_return", "kospi_mdd", "kosdaq_return", "kosdaq_mdd"])

    idx = sorted(set(model_r.index.year))
    rows = []
    for y in idx:
        mr = model_r[model_r.index.year == y]
        kr = bench.loc[bench.index.year == y, "ret_kospi"]
        dr = bench.loc[bench.index.year == y, "ret_kosdaq"]

        def yr(x: pd.Series) -> tuple[float, float]:
            if x.empty:
                return 0.0, 0.0
            eq = (1 + x.fillna(0)).cumprod()
            return float(eq.iloc[-1] - 1), float((eq / eq.cummax() - 1).min())

        mret, mmdd = yr(mr)
        kret, kmdd = yr(kr)
        dret, dmdd = yr(dr)
        rows.append({
            "year": int(y),
            "model_return": mret,
            "model_mdd": mmdd,
            "kospi_return": kret,
            "kospi_mdd": kmdd,
            "kosdaq_return": dret,
            "kosdaq_mdd": dmdd,
        })
    return pd.DataFrame(rows)


def top_boom_crisis(y: pd.DataFrame) -> tuple[int, int]:
    if y.empty:
        return 0, 0
    boom = int(y.sort_values("model_return", ascending=False).iloc[0]["year"])
    crisis = int(y.sort_values("model_mdd", ascending=True).iloc[0]["year"])
    return boom, crisis


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/5] Build universe...")
    universe = load_liquid_universe(100)
    print(f"universe={len(universe)}")

    print("[2/5] Build panel + fundamentals(quarterly real)...")
    panel = build_rebalance_table(universe)
    print(f"panel_rows={len(panel):,}")

    print("[3/5] Walk-forward optimize/validate...")
    oos_r, windows, picks, last_best = run_walk_forward(panel)

    print("[4/5] Benchmark compare (KOSPI/KOSDAQ)...")
    bench = load_benchmarks()
    oos_r = oos_r[oos_r.index.isin(bench.index)]

    total_ret, total_mdd = perf_stats(oos_r)
    ytbl = yearly_table(oos_r, bench)
    boom, crisis = top_boom_crisis(ytbl)

    eq = (1 + oos_r.fillna(0)).cumprod()
    eq_df = pd.DataFrame({"Date": eq.index, "equity": eq.values, "ret": oos_r.values})

    out_json = OUT_DIR / "stage06_highlander_result.json"
    out_yearly = OUT_DIR / "stage06_highlander_yearly.csv"
    out_equity = OUT_DIR / "stage06_highlander_equity.csv"
    out_picks = OUT_DIR / "stage06_highlander_picks.csv"

    payload = {
        "stage": 6,
        "model_name": "Highlander_Aggressive_Momentum_WFO",
        "result_grade": "VALIDATED",
        "test_only": False,
        "constraints": {
            "holdings_dynamic": "1~6",
            "leverage": 1.0,
            "trade_cost": TRADE_COST,
            "data": "real OHLCV + real supply + real fundamentals(pykrx quarterly PER/PBR/DIV)",
            "fast_profit_taking_suppression_experiment": [0, 2, 4],
        },
        "period": {"start": str(START.date()), "end": str(END.date())},
        "total_return_10y": total_ret,
        "total_mdd_10y": total_mdd,
        "target_2000pct_hit": bool(total_ret >= 20.0 and total_mdd >= -0.40),
        "selected_last_window_params": asdict(last_best),
        "windows": [asdict(w) for w in windows],
        "boom_year": boom,
        "crisis_year": crisis,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ytbl.to_csv(out_yearly, index=False, encoding="utf-8-sig")
    eq_df.to_csv(out_equity, index=False, encoding="utf-8-sig")
    if not picks.empty:
        picks.to_csv(out_picks, index=False, encoding="utf-8-sig")

    print("[5/5] done")
    print(json.dumps({
        "total_return_10y": total_ret,
        "total_mdd_10y": total_mdd,
        "target_2000pct_hit": payload["target_2000pct_hit"],
        "boom_year": boom,
        "crisis_year": crisis,
        "selected_last_window_params": asdict(last_best),
    }, ensure_ascii=False, indent=2))
    print(f"OUT: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
