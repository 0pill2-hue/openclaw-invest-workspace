#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW_KR = BASE / "invest/data/raw/kr"
OHLCV_DIR = RAW_KR / "ohlcv"
SUPPLY_DIR = RAW_KR / "supply"
VALIDATED = BASE / "invest/results/validated"
US_TICKERS = re.compile(r"\b(AAPL|NVDA|TSLA|MSFT|AMZN|GOOG|META)\b")

INTERNAL_MODELS = ["numeric", "qualitative", "hybrid"]
ALL_MODELS = INTERNAL_MODELS + ["external_proxy"]
TARGET_RETURN = 30.0  # 3000%


@dataclass
class LockedNumericConfig:
    universe_limit: int = 180
    max_pos: int = 5
    min_hold_days: int = 20
    replace_edge: float = 0.15
    monthly_replace_cap: float = 0.30
    trend_span_fast: int = 8
    trend_span_slow: int = 36
    ret_short: int = 10
    ret_mid: int = 40
    flow_scale: float = 120_000_000.0
    fee: float = 0.003


@dataclass
class QualHybridConfig:
    round_id: str
    qual_buzz_w: float
    qual_ret_w: float
    qual_up_w: float
    hybrid_quant_w: float
    hybrid_qual_w: float
    hybrid_agree_w: float
    rationale: str


@dataclass
class ModelRun:
    model: str
    annual_returns: dict[int, float]
    stats: dict[str, float]
    trades: list[dict[str, Any]]
    notes: str


@dataclass
class RoundEval:
    round_id: str
    rationale: str
    numeric_locked: bool
    numeric_return: float
    numeric_guard_floor: float
    numeric_guard_pass: bool
    qualitative_return: float
    hybrid_return: float
    changed_params: dict[str, dict[str, float]]
    objective: float



def annual_stats(annual: dict[int, float]) -> dict[str, float]:
    years = sorted(annual)
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for y in years:
        eq *= 1.0 + float(annual[y])
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    total = eq - 1.0
    n = len(years)
    cagr = (eq ** (1 / n) - 1.0) if n > 0 and eq > 0 else -1.0
    return {"total_return": total, "asset_multiple": eq, "mdd": mdd, "cagr": cagr}



def guard_kr_only() -> None:
    if not OHLCV_DIR.exists() or not SUPPLY_DIR.exists():
        raise RuntimeError("FAIL: required KRX raw path missing")
    for p in [OHLCV_DIR, SUPPLY_DIR]:
        if "us" in str(p).lower().split("/"):
            raise RuntimeError("FAIL: us/ path detected")
    bad = []
    for fp in list(OHLCV_DIR.glob("*.csv"))[:4000]:
        if US_TICKERS.search(fp.stem.upper()):
            bad.append(fp.name)
    if bad:
        raise RuntimeError(f"FAIL: US ticker pattern detected: {bad[:5]}")



def load_universe(limit: int) -> dict[str, pd.DataFrame]:
    rows: list[tuple[str, float, pd.DataFrame]] = []
    for fp in OHLCV_DIR.glob("*.csv"):
        try:
            df = pd.read_csv(fp)
            if not {"Date", "Close", "Volume"}.issubset(df.columns):
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
            df = df[(df["Date"] >= "2015-01-01") & (df["Date"] <= "2026-12-31")]
            if len(df) < 700:
                continue
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                if c not in df.columns:
                    df[c] = np.nan
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["Close"]).set_index("Date").sort_index()
            liq = float((df["Close"].fillna(0) * df["Volume"].fillna(0)).tail(252).mean())
            rows.append((fp.stem, liq, df))
        except Exception:
            continue
    rows.sort(key=lambda x: x[1], reverse=True)
    return {c: d for c, _, d in rows[:limit]}



def load_supply(code: str) -> pd.DataFrame | None:
    p = SUPPLY_DIR / f"{code}_supply.csv"
    if not p.exists():
        return None
    try:
        s = pd.read_csv(p)
        if "날짜" not in s.columns:
            return None
        s["날짜"] = pd.to_datetime(s["날짜"], errors="coerce")
        s = s.dropna(subset=["날짜"]).set_index("날짜").sort_index()
        for c in ["기관합계", "외국인합계", "전체"]:
            if c not in s.columns:
                s[c] = 0.0
            s[c] = pd.to_numeric(s[c], errors="coerce").fillna(0.0)
        return s
    except Exception:
        return None



def rebalance_dates(universe: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    all_idx = sorted(set().union(*[set(df.index) for df in universe.values()]))
    s = pd.Series(all_idx, index=all_idx)
    return [d for d in s.groupby(pd.Grouper(freq="ME")).last().dropna().tolist() if d >= pd.Timestamp("2016-01-01")]



def score_for_model(
    model: str,
    d: pd.Timestamp,
    px: pd.DataFrame,
    sp: pd.DataFrame | None,
    lock: LockedNumericConfig,
    qh: QualHybridConfig,
) -> float:
    h = px.loc[:d]
    if len(h) < max(130, lock.trend_span_slow + 5, lock.ret_mid + 5):
        return -999

    c = h["Close"]
    v = h["Volume"].fillna(0)

    ret_s = float(c.pct_change(lock.ret_short).iloc[-1])
    ret_m = float(c.pct_change(lock.ret_mid).iloc[-1])
    ma_f = float(c.ewm(span=lock.trend_span_fast).mean().iloc[-1])
    ma_s = float(c.ewm(span=lock.trend_span_slow).mean().iloc[-1])
    ma120 = float(c.rolling(120).mean().iloc[-1])

    trend = 0.6 * float(ma_f > ma_s) + 0.4 * float(ma_s > ma120)
    trend += 0.5 * (0.0 if math.isnan(ret_m) else ret_m)

    flow = 0.0
    if sp is not None:
        sh = sp.loc[:d]
        if len(sh) > 20:
            val = (sh["기관합계"].rolling(20).mean().iloc[-1] + sh["외국인합계"].rolling(20).mean().iloc[-1]) / lock.flow_scale
            flow = float(np.tanh(val))

    # numeric formula is intentionally frozen by lock config
    quant = 0.7 * trend + 0.3 * flow

    buzz = float(v.iloc[-1] / (v.rolling(60).mean().iloc[-1] + 1e-9))
    up_ratio = float(c.pct_change().tail(20).gt(0.02).mean())
    qual = qh.qual_buzz_w * np.tanh(buzz - 1.0) + qh.qual_ret_w * (0.0 if math.isnan(ret_s) else ret_s) + qh.qual_up_w * up_ratio

    agree = min(quant, qual)
    hybrid = qh.hybrid_quant_w * quant + qh.hybrid_qual_w * qual + qh.hybrid_agree_w * agree

    external_proxy = 0.6 * (ma_f / (ma_s + 1e-9) - 1.0) + 0.4 * (0.0 if math.isnan(ret_s) else ret_s)

    if model == "numeric":
        return quant
    if model == "qualitative":
        return qual
    if model == "hybrid":
        return hybrid
    if model == "external_proxy":
        return external_proxy
    return -999



def run_model(
    model: str,
    universe: dict[str, pd.DataFrame],
    supplies: dict[str, pd.DataFrame | None],
    dates: list[pd.Timestamp],
    lock: LockedNumericConfig,
    qh: QualHybridConfig,
) -> ModelRun:
    cash = 1.0
    holdings: dict[str, dict[str, Any]] = {}
    eq_curve: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict[str, Any]] = []

    for d in dates:
        px_now: dict[str, float] = {}
        scores: dict[str, float] = {}

        for code, df in universe.items():
            h = df.loc[:d]
            if h.empty:
                continue
            px_now[code] = float(h["Close"].iloc[-1])
            s = score_for_model(model, h.index[-1], df, supplies.get(code), lock, qh)
            if s > -900:
                scores[code] = s

        if not scores:
            total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
            eq_curve.append((d, total))
            continue

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = ranked[: lock.max_pos]
        target_set = {c for c, _ in top}

        replacements: list[str] = []
        n_hold = len(holdings)
        replace_cap = int(math.floor(n_hold * lock.monthly_replace_cap)) if n_hold > 0 else 0

        for c in list(holdings.keys()):
            if c not in px_now or c in target_set:
                continue
            held_days = int((d - holdings[c]["buy_date"]).days)
            if held_days < lock.min_hold_days:
                continue
            incumbent_score = scores.get(c, -999.0)
            challenger_scores = [s for cc, s in top if cc not in holdings]
            best_challenger = max(challenger_scores) if challenger_scores else -999.0
            if best_challenger < incumbent_score + lock.replace_edge:
                continue
            replacements.append(c)

        replacements = replacements[:replace_cap]

        for c in replacements:
            pos = holdings.pop(c)
            sell_p = px_now[c]
            gross = pos["shares"] * sell_p
            fee = gross * lock.fee
            cash += gross - fee
            trades.append(
                {
                    "code": c,
                    "buy_date": pos["buy_date"].strftime("%Y-%m-%d"),
                    "sell_date": d.strftime("%Y-%m-%d"),
                    "buy_price": float(pos["buy_price"]),
                    "sell_price": float(sell_p),
                    "pnl": float((sell_p / pos["buy_price"]) - 1.0),
                }
            )

        slots = max(1, min(lock.max_pos, len(target_set)))
        target_val = (cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())) / slots

        for c, _ in top:
            if c in holdings or c not in px_now:
                continue
            if len(holdings) >= lock.max_pos:
                break
            p = px_now[c]
            buy_cash = min(cash, target_val)
            if buy_cash <= 0:
                continue
            fee = buy_cash * lock.fee
            net = buy_cash - fee
            sh = net / p
            cash -= buy_cash
            holdings[c] = {"shares": sh, "buy_price": p, "buy_date": d}

        total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
        eq_curve.append((d, total))

    if eq_curve:
        d = eq_curve[-1][0]
        px_now = {c: float(df.loc[:d]["Close"].iloc[-1]) for c, df in universe.items() if not df.loc[:d].empty}
        for c in list(holdings.keys()):
            pos = holdings.pop(c)
            if c not in px_now:
                continue
            sell_p = px_now[c]
            gross = pos["shares"] * sell_p
            fee = gross * lock.fee
            cash += gross - fee
            trades.append(
                {
                    "code": c,
                    "buy_date": pos["buy_date"].strftime("%Y-%m-%d"),
                    "sell_date": d.strftime("%Y-%m-%d"),
                    "buy_price": float(pos["buy_price"]),
                    "sell_price": float(sell_p),
                    "pnl": float((sell_p / pos["buy_price"]) - 1.0),
                }
            )

    eq = pd.Series({d: v for d, v in eq_curve}).sort_index()
    annual: dict[int, float] = {}
    for y, ys in eq.groupby(eq.index.year):
        if y < 2016:
            continue
        annual[int(y)] = float(ys.iloc[-1] / ys.iloc[0] - 1.0) if len(ys) > 1 else 0.0

    stats = annual_stats(annual)
    return ModelRun(
        model=model,
        annual_returns=annual,
        stats=stats,
        trades=trades,
        notes="RULEBOOK V3.5 + numeric freeze: min_hold=20d, replace_edge=+15%, monthly_replace_cap=30%, holdings=1~6",
    )



def changed_params(prev: QualHybridConfig, cur: QualHybridConfig) -> dict[str, dict[str, float]]:
    keys = [
        "qual_buzz_w",
        "qual_ret_w",
        "qual_up_w",
        "hybrid_quant_w",
        "hybrid_qual_w",
        "hybrid_agree_w",
    ]
    out: dict[str, dict[str, float]] = {}
    for k in keys:
        pv = float(getattr(prev, k))
        cv = float(getattr(cur, k))
        if abs(cv - pv) > 1e-12:
            out[k] = {"from": pv, "to": cv}
    return out



def distribution_metrics(model_runs: dict[str, ModelRun]) -> dict[str, Any]:
    vals = {m: float(model_runs[m].stats["total_return"]) for m in INTERNAL_MODELS}
    sorted_vals = sorted(vals.values())
    best = sorted_vals[-1]
    second = sorted_vals[-2] if len(sorted_vals) >= 2 else 0.0
    skew_ratio = float(best / (second + 1e-9)) if second > 0 else float("inf")
    return {
        "internal_returns": vals,
        "best_to_second_ratio": skew_ratio,
        "one_sided_skew_flag": bool(skew_ratio > 2.5),
    }



def main() -> int:
    guard_kr_only()
    VALIDATED.mkdir(parents=True, exist_ok=True)

    lock = LockedNumericConfig()

    qh_lock_base = QualHybridConfig(
        round_id="r00_lock_base",
        qual_buzz_w=0.80,
        qual_ret_w=0.20,
        qual_up_w=0.00,
        hybrid_quant_w=0.50,
        hybrid_qual_w=0.50,
        hybrid_agree_w=0.00,
        rationale="numeric best run(v3_6_kr_r03) 재현용 잠금 기준",
    )

    qh_rounds = [
        QualHybridConfig(
            round_id="r01_qh_tune",
            qual_buzz_w=0.82,
            qual_ret_w=0.18,
            qual_up_w=0.00,
            hybrid_quant_w=0.50,
            hybrid_qual_w=0.50,
            hybrid_agree_w=0.00,
            rationale="수익 극대화 관점: qual 반응도를 높여 급등 포착 강화",
        ),
        QualHybridConfig(
            round_id="r02_qh_tune",
            qual_buzz_w=0.78,
            qual_ret_w=0.21,
            qual_up_w=0.00,
            hybrid_quant_w=0.50,
            hybrid_qual_w=0.50,
            hybrid_agree_w=0.00,
            rationale="정성결합 관점: qual 노이즈를 줄여 hybrid 안정 개선",
        ),
        QualHybridConfig(
            round_id="r03_qh_tune",
            qual_buzz_w=0.76,
            qual_ret_w=0.20,
            qual_up_w=0.00,
            hybrid_quant_w=0.50,
            hybrid_qual_w=0.50,
            hybrid_agree_w=0.00,
            rationale="안정성 관점: turnover 충격 완화형 qual 가중 조합",
        ),
    ]

    universe = load_universe(limit=lock.universe_limit)
    supplies = {c: load_supply(c) for c in universe}
    dates = rebalance_dates(universe)

    lock_runs = {m: run_model(m, universe, supplies, dates, lock, qh_lock_base) for m in ALL_MODELS}
    numeric_locked_return = float(lock_runs["numeric"].stats["total_return"])
    numeric_guard_floor = numeric_locked_return * 0.95

    round_evals: list[RoundEval] = []
    round_payloads: dict[str, dict[str, ModelRun]] = {}

    prev_cfg = qh_lock_base
    base_qual = float(lock_runs["qualitative"].stats["total_return"])
    base_hybrid = float(lock_runs["hybrid"].stats["total_return"])

    for qh in qh_rounds:
        runs = {m: run_model(m, universe, supplies, dates, lock, qh) for m in ALL_MODELS}
        round_payloads[qh.round_id] = runs

        numeric_ret = float(runs["numeric"].stats["total_return"])
        guard_pass = bool(numeric_ret >= numeric_guard_floor)
        qual_ret = float(runs["qualitative"].stats["total_return"])
        hybrid_ret = float(runs["hybrid"].stats["total_return"])

        # balanced objective: both qual/hybrid uplift while avoiding one-side dominance
        uplift = (qual_ret - base_qual) + (hybrid_ret - base_hybrid)
        objective = (min(qual_ret, hybrid_ret) * 0.70) + ((qual_ret + hybrid_ret) * 0.15) + (uplift * 0.15)

        eval_row = RoundEval(
            round_id=qh.round_id,
            rationale=qh.rationale,
            numeric_locked=True,
            numeric_return=numeric_ret,
            numeric_guard_floor=numeric_guard_floor,
            numeric_guard_pass=guard_pass,
            qualitative_return=qual_ret,
            hybrid_return=hybrid_ret,
            changed_params=changed_params(prev_cfg, qh),
            objective=float(objective),
        )
        round_evals.append(eval_row)
        prev_cfg = qh

    passed = [r for r in round_evals if r.numeric_guard_pass and len(r.changed_params) > 0]
    if not passed:
        raise RuntimeError("FAIL: no valid round after numeric guard / changed_params checks")

    passed_sorted = sorted(passed, key=lambda x: x.objective, reverse=True)
    adopted_eval = passed_sorted[0]
    backup_eval = passed_sorted[1] if len(passed_sorted) > 1 else passed_sorted[0]

    adopted_qh = next(q for q in qh_rounds if q.round_id == adopted_eval.round_id)
    backup_qh = next(q for q in qh_rounds if q.round_id == backup_eval.round_id)

    final_runs = round_payloads[adopted_qh.round_id]
    internal = [final_runs[m] for m in INTERNAL_MODELS]
    best_internal = max(internal, key=lambda x: x.stats["total_return"])
    internal_3000_gate_pass = bool(best_internal.stats["total_return"] > TARGET_RETURN)

    dist = distribution_metrics(final_runs)

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": "v3_7_kr",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "policy_enforcement": {
            "internal_models": INTERNAL_MODELS,
            "external_proxy_selection_excluded": True,
            "numeric_locked": True,
            "numeric_locked_reference": "v3_6_kr_r03",
            "numeric_locked_return": numeric_locked_return,
            "numeric_guard_floor_return": numeric_guard_floor,
            "numeric_guard_rule": "current_numeric >= locked_numeric * 0.95",
            "numeric_guard_pass": bool(adopted_eval.numeric_guard_pass),
            "baseline_internal_best_id": best_internal.model,
            "baseline_internal_best_return": best_internal.stats["total_return"],
            "internal_3000_gate_pass": "pass" if internal_3000_gate_pass else "fail",
            "internal_distribution": dist,
            "rulebook_v3_5": {
                "min_hold_days": lock.min_hold_days,
                "replace_edge": lock.replace_edge,
                "monthly_replace_cap": lock.monthly_replace_cap,
                "holdings_min": 1,
                "holdings_max": lock.max_pos,
                "numeric_freeze": True,
            },
        },
        "tuning_config": {
            "locked_numeric_params": asdict(lock),
            "lock_base_qh_params": asdict(qh_lock_base),
            "adopted_qh_params": asdict(adopted_qh),
            "backup_qh_params": asdict(backup_qh),
            "changed_params_vs_v3_6_r03": changed_params(qh_lock_base, adopted_qh),
        },
        "round_evaluations": [asdict(r) for r in round_evals],
        "baselines": [asdict(final_runs[m]) for m in ALL_MODELS],
    }

    out_json = VALIDATED / "stage05_baselines_v3_7_kr.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "version": "v3_7_kr",
                "adopted_round": adopted_qh.round_id,
                "backup_round": backup_qh.round_id,
                "numeric_locked_return": numeric_locked_return,
                "numeric_guard_floor": numeric_guard_floor,
                "numeric_guard_pass": adopted_eval.numeric_guard_pass,
                "qualitative_return": final_runs["qualitative"].stats["total_return"],
                "hybrid_return": final_runs["hybrid"].stats["total_return"],
                "baseline_internal_best_id": best_internal.model,
                "baseline_internal_best_return": best_internal.stats["total_return"],
                "internal_3000_gate_pass": "pass" if internal_3000_gate_pass else "fail",
                "distribution_best_to_second": dist["best_to_second_ratio"],
                "one_sided_skew_flag": dist["one_sided_skew_flag"],
                "output": str(out_json.relative_to(BASE)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
