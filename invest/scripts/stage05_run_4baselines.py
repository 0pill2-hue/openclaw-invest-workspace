#!/usr/bin/env python3
"""
Stage05: 4 Baseline Engines (Quant / Qual / Hybrid / External)
- Common Rulebook V3 applied via BacktestEngine
  * is_delisting_risk (survival)
  * is_blacklist
  * max_pos=6
  * no_tp (take-profit rule not used)
- Backtest window: 2016-01 ~ 2026-12 (available data range dependent)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from invest.scripts.stage05_backtest_engine import BacktestEngine
except ModuleNotFoundError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / "invest" / "scripts"))
    from stage05_backtest_engine import BacktestEngine

BASE = Path(__file__).resolve().parent.parent
OHLCV_DIR = BASE / "invest/data/clean/production/kr/ohlcv"
SUPPLY_DIR = BASE / "invest/data/clean/production/kr/supply"
NAME_PATH = BASE / "invest/data/master/kr_stock_list.csv"

OUT_JSON = BASE / "invest/reports/stage_updates/STAGE05_4BASELINES_20260219.json"
OUT_MD = BASE / "invest/reports/stage_updates/STAGE05_4BASELINES_20260219.md"

START = pd.Timestamp("2016-01-01")
END = pd.Timestamp("2026-12-31")


@dataclass
class ModelResult:
    model: str
    total_return: float
    mdd: float
    feature: str


def load_names() -> dict[str, str]:
    if not NAME_PATH.exists():
        return {}
    df = pd.read_csv(NAME_PATH, dtype={"Code": str})
    df["Code"] = df["Code"].str.zfill(6)
    return dict(zip(df["Code"], df["Name"].astype(str)))


def load_universe(limit: int = 180) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    ohlcv_map: dict[str, pd.DataFrame] = {}
    supply_map: dict[str, pd.DataFrame] = {}

    files = sorted(OHLCV_DIR.glob("*.csv"))
    liquidity_rank: list[tuple[str, float]] = []

    for fp in files:
        code = fp.stem
        try:
            df = pd.read_csv(fp)
            if "Date" not in df.columns or "Close" not in df.columns:
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
            df = df[(df["Date"] >= START) & (df["Date"] <= END)].copy()
            if len(df) < 400:
                continue
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                if c not in df.columns:
                    df[c] = np.nan
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["Close"]).set_index("Date").sort_index()
            if df.empty:
                continue
            liq = float((df["Close"].fillna(0) * df["Volume"].fillna(0)).tail(252).mean())
            liquidity_rank.append((code, liq))
            ohlcv_map[code] = df
        except Exception:
            continue

    top_codes = {c for c, _ in sorted(liquidity_rank, key=lambda x: x[1], reverse=True)[:limit]}
    ohlcv_map = {c: d for c, d in ohlcv_map.items() if c in top_codes}

    for code in list(ohlcv_map.keys()):
        sp = SUPPLY_DIR / f"{code}_supply.csv"
        if not sp.exists():
            continue
        try:
            s = pd.read_csv(sp)
            if "Date" not in s.columns:
                continue
            s["Date"] = pd.to_datetime(s["Date"], errors="coerce")
            s = s.dropna(subset=["Date"]).set_index("Date").sort_index()
            for c in ["Inst", "Foreign", "Total"]:
                if c in s.columns:
                    s[c] = pd.to_numeric(s[c], errors="coerce")
                else:
                    s[c] = 0.0
            supply_map[code] = s
        except Exception:
            continue

    return ohlcv_map, supply_map


def _z(x: pd.Series) -> pd.Series:
    m, sd = x.mean(), x.std()
    if pd.isna(sd) or sd == 0:
        return pd.Series(0.0, index=x.index)
    return (x - m) / (sd + 1e-12)


def score_for_date(code: str, d: pd.Timestamp, px: pd.DataFrame, supply: pd.DataFrame | None) -> dict[str, float]:
    hist = px.loc[:d]
    if len(hist) < 130:
        return {"quant": -999, "qual": -999, "external": -999}

    c = hist["Close"]
    v = hist["Volume"].fillna(0)

    ma20 = c.rolling(20).mean().iloc[-1]
    ma60 = c.rolling(60).mean().iloc[-1]
    ma120 = c.rolling(120).mean().iloc[-1]
    ret20 = c.pct_change(20).iloc[-1]
    ret60 = c.pct_change(60).iloc[-1]

    trend_score = float((ma20 > ma60) + (ma60 > ma120)) + float(np.nan_to_num(ret60, nan=0.0))

    flow_score = 0.0
    if supply is not None and d in supply.index:
        sh = supply.loc[:d]
        if len(sh) > 20:
            flow = (sh["Foreign"].fillna(0) + sh["Inst"].fillna(0)).rolling(20).mean().iloc[-1]
            flow_score = float(np.tanh(flow / 1e8))

    turnaround_score = float(np.nan_to_num(ret20 - ret60, nan=0.0))
    quant = 0.45 * trend_score + 0.35 * flow_score + 0.20 * turnaround_score

    vol60 = v.rolling(60).mean().iloc[-1]
    buzz = float(v.iloc[-1] / (vol60 + 1e-9)) if vol60 and not pd.isna(vol60) else 0.0
    pos_days = float(c.pct_change().tail(20).gt(0.03).mean())
    qual = 0.6 * np.tanh(buzz - 1.0) + 0.4 * pos_days

    chronos_proxy = 0.5 * float(np.nan_to_num(c.ewm(span=10).mean().iloc[-1] / (c.ewm(span=40).mean().iloc[-1] + 1e-9) - 1.0, nan=0.0)) + 0.5 * float(np.nan_to_num(ret20, nan=0.0))

    return {"quant": quant, "qual": qual, "external": chronos_proxy}


def delisting_info_for_date(px: pd.DataFrame, d: pd.Timestamp) -> dict:
    hist = px.loc[:d]
    if len(hist) < 252:
        return {}
    c = hist["Close"]
    dd_1y = c.iloc[-1] / (c.tail(252).max() + 1e-9) - 1.0
    tiny_price = c.iloc[-1] < 700
    risk = bool(dd_1y < -0.85 and tiny_price)
    return {
        "admin_issue": risk,
        "capital_erosion": False,
        "audit_opinion": False,
    }


def calc_mdd(equity: pd.Series) -> float:
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


def run_model(model: str, ohlcv_map: dict[str, pd.DataFrame], supply_map: dict[str, pd.DataFrame], names: dict[str, str]) -> ModelResult:
    engine = BacktestEngine(initial_capital=100_000_000, round_trip_penalty=0.003)
    engine.max_pos = 6

    all_dates = sorted(set().union(*[set(df.index) for df in ohlcv_map.values()]))
    all_dates = [d for d in all_dates if START <= d <= END]
    month_ends = pd.Series(all_dates, index=all_dates).groupby(pd.Grouper(freq="ME")).last().dropna().tolist()

    equity_points = []

    for d in month_ends:
        scores = {}
        prices = {}
        info = {}

        for code, px in ohlcv_map.items():
            if d not in px.index:
                p = px.loc[:d]
                if p.empty:
                    continue
                d_eff = p.index[-1]
            else:
                d_eff = d

            feat = score_for_date(code, d_eff, px, supply_map.get(code))
            if feat["quant"] <= -900:
                continue

            if model == "Quant":
                s = feat["quant"]
            elif model == "Qual":
                s = feat["qual"]
            elif model == "Hybrid":
                s = 0.5 * feat["quant"] + 0.5 * feat["qual"]
            elif model == "External":
                s = feat["external"]
            else:
                raise ValueError(model)

            scores[code] = s
            prices[code] = float(px.loc[d_eff, "Close"])
            info[code] = delisting_info_for_date(px, d_eff)

        if not scores:
            cur_prices = {c: float(df.loc[:d]["Close"].iloc[-1]) for c, df in ohlcv_map.items() if not df.loc[:d].empty}
            equity_points.append((d, engine.get_total_value(cur_prices)))
            continue

        s_ser = pd.Series(scores)
        s_ser = _z(s_ser)
        selected = s_ser.nlargest(6)

        selected_codes = set(selected.index.tolist())
        cur_prices = {c: float(df.loc[:d]["Close"].iloc[-1]) for c, df in ohlcv_map.items() if not df.loc[:d].empty}
        engine.update_trailing_stop(d, cur_prices)

        for held in list(engine.portfolio.keys()):
            if held not in selected_codes and held in cur_prices:
                engine.execute_trade(date=d, code=held, action="SELL", price=cur_prices[held], signal_reason="rebalance_out")

        score_map = {c: float(max(selected[c], 0.0)) for c in selected.index}
        w = engine.get_dynamic_weights(score_map)

        for c in selected.index:
            engine.execute_trade(
                date=d,
                code=c,
                action="BUY",
                price=prices[c],
                weight=w.get(c, 0.0),
                name=names.get(c, c),
                delisting_info=info[c],
            )

        equity_points.append((d, engine.get_total_value(cur_prices)))

    eq = pd.Series({d: v for d, v in equity_points}).sort_index()
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0) if len(eq) > 1 else 0.0
    mdd = calc_mdd(eq) if len(eq) > 1 else 0.0

    feature = {
        "Quant": "수급(외인/기관)+이평 정배열+턴어라운드 프록시",
        "Qual": "거래량 Buzz + 급등 키워드(호재) 프록시",
        "Hybrid": "Quant/Qual 50:50 가중합",
        "External": "Chronos 대체 시계열 예측 프록시(EMA 추세+모멘텀)",
    }[model]

    return ModelResult(model=model, total_return=total_return, mdd=mdd, feature=feature)


def main():
    names = load_names()
    ohlcv_map, supply_map = load_universe(limit=180)

    models = ["Quant", "Qual", "Hybrid", "External"]
    results: list[ModelResult] = [run_model(m, ohlcv_map, supply_map, names) for m in models]

    winners = [r.model for r in results if r.total_return >= 20.0]  # 2000% == 20x profit == 21x equity

    payload = {
        "grade": "DRAFT",
        "watermark": "TEST ONLY",
        "period": {"start": str(START.date()), "end": str(END.date())},
        "rulebook_v3": {
            "is_delisting_risk": True,
            "is_blacklist": True,
            "max_pos": 6,
            "no_tp": True,
        },
        "comparison": [
            {
                "model": r.model,
                "return_10y": r.total_return,
                "return_10y_pct": r.total_return * 100,
                "mdd": r.mdd,
                "feature": r.feature,
            }
            for r in results
        ],
        "winner_over_2000pct": winners,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Stage05 4대 베이스라인 엔진 비교 (2016~2026)\n\n",
        "- 등급: DRAFT (TEST ONLY)\n",
        "- 공통 Rulebook V3 적용: `is_delisting_risk`, `is_blacklist`, `max_pos=6`, `no_tp`\n",
        "- External 모델은 Chronos API/가중치 부재로 **Chronos-style 시계열 프록시**로 대체 실행\n\n",
        "| 모델명 | 10년 수익률 | MDD | 주요 특징 |\n",
        "|---|---:|---:|---|\n",
    ]
    for r in results:
        lines.append(f"| {r.model} | {r.total_return*100:.2f}% | {r.mdd:.2%} | {r.feature} |\n")

    if winners:
        lines.append("\n## 승자 판정 (2000% 초과)\n")
        for w in winners:
            lines.append(f"- {w}\n")
    else:
        lines.append("\n## 승자 판정 (2000% 초과)\n- 없음\n")

    OUT_MD.write_text("".join(lines), encoding="utf-8")

    print(f"WROTE {OUT_JSON}")
    print(f"WROTE {OUT_MD}")
    print(json.dumps(payload["comparison"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
