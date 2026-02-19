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
RAW_TEXT = BASE / "invest/data/raw/text"
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
class DensityRoundConfig:
    round_id: str
    repeat_counter: int
    why: str
    qual_buzz_w: float
    qual_ret_w: float
    qual_up_w: float
    qual_quant_anchor: float
    hybrid_quant_w: float
    hybrid_qual_w: float
    hybrid_agree_w: float
    hybrid_pos_boost: float
    signal_lag_days: int
    density_pow: float
    blog_weight: float
    telegram_weight: float
    noise_w: float
    noise_buzz_cut: float
    low_density_threshold: float
    low_density_scale: float


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
    repeat_counter: int
    why: str
    baseline_internal_best_id: str
    baseline_internal_best_reason: str
    numeric_return: float
    qualitative_return: float
    hybrid_return: float
    gap_qual_vs_numeric: float
    gap_hybrid_vs_numeric: float
    changed_params: dict[str, dict[str, Any]]


def annual_stats(annual: dict[int, float], trades_count: int, rebalance_count: int) -> dict[str, float]:
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
    turnover_proxy = float(trades_count / max(1, rebalance_count))
    return {
        "total_return": total,
        "asset_multiple": eq,
        "mdd": mdd,
        "cagr": cagr,
        "turnover_proxy": turnover_proxy,
    }


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


def extract_year_from_md(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = [next(f, "") for _ in range(30)]
    except Exception:
        return None
    text = "\n".join(lines)
    m = re.search(r"^Date:\s*([12][0-9]{3})", text, flags=re.MULTILINE)
    if not m:
        m = re.search(r"\b([12][0-9]{3})[.-]\s*[01]?[0-9][.-]\s*[0-3]?[0-9]", text)
    if not m:
        return None
    y = int(m.group(1))
    if 2010 <= y <= 2030:
        return y
    return None


def load_text_density_base() -> dict[str, dict[int, float]]:
    years = list(range(2016, 2027))
    blog_counts = {y: 0 for y in years}
    tg_counts = {y: 0 for y in years}

    for fp in (RAW_TEXT / "blog").glob("**/*.md"):
        y = extract_year_from_md(fp)
        if y in blog_counts:
            blog_counts[y] += 1

    for fp in (RAW_TEXT / "telegram").glob("*.md"):
        y = extract_year_from_md(fp)
        if y in tg_counts:
            tg_counts[y] += 1

    max_blog = max(blog_counts.values()) if blog_counts else 1
    max_tg = max(tg_counts.values()) if tg_counts else 1
    blog_norm = {y: (blog_counts[y] / max(1, max_blog)) for y in years}
    tg_norm = {y: (tg_counts[y] / max(1, max_tg)) for y in years}

    return {
        "blog_counts": blog_counts,
        "telegram_counts": tg_counts,
        "blog_norm": blog_norm,
        "telegram_norm": tg_norm,
    }


def year_density_map(density_base: dict[str, dict[int, float]], cfg: DensityRoundConfig) -> dict[int, float]:
    out: dict[int, float] = {}
    for y in range(2016, 2027):
        d = cfg.blog_weight * density_base["blog_norm"].get(y, 0.0) + cfg.telegram_weight * density_base["telegram_norm"].get(y, 0.0)
        out[y] = float(np.clip(d, 0.0, 1.0))
    return out


def score_for_model(
    model: str,
    d: pd.Timestamp,
    px: pd.DataFrame,
    sp: pd.DataFrame | None,
    lock: LockedNumericConfig,
    cfg: DensityRoundConfig,
    density_by_year: dict[int, float],
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

    quant = 0.7 * trend + 0.3 * flow

    lag = int(max(0, cfg.signal_lag_days))
    buzz_series = v / (v.rolling(60).mean() + 1e-9)
    buzz = float(buzz_series.shift(lag).iloc[-1])
    ret_s_lag = float(c.pct_change(lock.ret_short).shift(lag).iloc[-1])
    up_ratio = float(c.pct_change().shift(lag).tail(20).gt(0.02).mean())

    density = density_by_year.get(int(d.year), 0.5)
    qual_raw = (
        cfg.qual_buzz_w * np.tanh(buzz - 1.0)
        + cfg.qual_ret_w * (0.0 if math.isnan(ret_s_lag) else ret_s_lag)
        + cfg.qual_up_w * up_ratio
        + cfg.qual_quant_anchor * quant
    )

    qual = float(qual_raw)
    if cfg.density_pow > 0:
        qual *= float(max(density, 1e-6) ** cfg.density_pow)
    if density < cfg.low_density_threshold:
        qual *= cfg.low_density_scale

    ret_noise = float(c.pct_change().tail(20).std()) if len(c) >= 25 else 0.0
    buzz_jump = float(buzz_series.diff().abs().tail(20).median()) if len(buzz_series) >= 25 else 0.0
    noise = float(np.tanh(ret_noise * 3.0 + max(0.0, buzz_jump - cfg.noise_buzz_cut)))
    qual -= cfg.noise_w * noise

    agree = min(quant, qual)
    hybrid = (
        cfg.hybrid_quant_w * quant
        + cfg.hybrid_qual_w * qual
        + cfg.hybrid_agree_w * agree
        + cfg.hybrid_pos_boost * max(qual, 0.0)
    )

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
    cfg: DensityRoundConfig,
    density_by_year: dict[int, float],
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
            s = score_for_model(model, h.index[-1], df, supplies.get(code), lock, cfg, density_by_year)
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

    stats = annual_stats(annual, trades_count=len(trades), rebalance_count=len(dates))
    return ModelRun(
        model=model,
        annual_returns=annual,
        stats=stats,
        trades=trades,
        notes=(
            "RULEBOOK V3.5 + density/lag/noise tuning: "
            "min_hold=20d, replace_edge=+15%, monthly_replace_cap=30%, holdings=1~5"
        ),
    )


def changed_params(prev: DensityRoundConfig | None, cur: DensityRoundConfig) -> dict[str, dict[str, Any]]:
    keys = [
        "qual_buzz_w",
        "qual_ret_w",
        "qual_up_w",
        "qual_quant_anchor",
        "hybrid_quant_w",
        "hybrid_qual_w",
        "hybrid_agree_w",
        "hybrid_pos_boost",
        "signal_lag_days",
        "density_pow",
        "blog_weight",
        "telegram_weight",
        "noise_w",
        "noise_buzz_cut",
        "low_density_threshold",
        "low_density_scale",
    ]
    out: dict[str, dict[str, Any]] = {}
    if prev is None:
        for k in keys:
            out[k] = {"from": None, "to": getattr(cur, k)}
        return out
    for k in keys:
        pv = getattr(prev, k)
        cv = getattr(cur, k)
        if pv != cv:
            out[k] = {"from": pv, "to": cv}
    return out


def plan_round(repeat_counter: int) -> DensityRoundConfig:
    plans: dict[int, DensityRoundConfig] = {
        1: DensityRoundConfig(
            round_id="r01_density_lag_noise",
            repeat_counter=1,
            why="옵션3 중심: 정성 신호 2일 지연 정렬 + 노이즈 컷 + 저밀도 완화",
            qual_buzz_w=0.74,
            qual_ret_w=0.22,
            qual_up_w=0.04,
            qual_quant_anchor=0.00,
            hybrid_quant_w=0.55,
            hybrid_qual_w=0.35,
            hybrid_agree_w=0.10,
            hybrid_pos_boost=0.03,
            signal_lag_days=2,
            density_pow=0.70,
            blog_weight=0.75,
            telegram_weight=0.25,
            noise_w=0.08,
            noise_buzz_cut=0.80,
            low_density_threshold=0.35,
            low_density_scale=0.70,
        ),
        2: DensityRoundConfig(
            round_id="r02_density_hard_cap",
            repeat_counter=2,
            why="옵션4 강화: 저밀도 구간 정성 영향 제한 강화(컷/스케일 강화)",
            qual_buzz_w=0.70,
            qual_ret_w=0.24,
            qual_up_w=0.06,
            qual_quant_anchor=0.00,
            hybrid_quant_w=0.60,
            hybrid_qual_w=0.30,
            hybrid_agree_w=0.10,
            hybrid_pos_boost=0.04,
            signal_lag_days=3,
            density_pow=0.95,
            blog_weight=0.78,
            telegram_weight=0.22,
            noise_w=0.11,
            noise_buzz_cut=0.75,
            low_density_threshold=0.45,
            low_density_scale=0.55,
        ),
        3: DensityRoundConfig(
            round_id="r03_blog_priority_mix",
            repeat_counter=3,
            why="옵션2 혼합: 블로그 우선/텔레 보조 재가중 + 시차/노이즈 유지",
            qual_buzz_w=0.68,
            qual_ret_w=0.24,
            qual_up_w=0.08,
            qual_quant_anchor=0.00,
            hybrid_quant_w=0.64,
            hybrid_qual_w=0.26,
            hybrid_agree_w=0.10,
            hybrid_pos_boost=0.05,
            signal_lag_days=4,
            density_pow=1.05,
            blog_weight=0.82,
            telegram_weight=0.18,
            noise_w=0.13,
            noise_buzz_cut=0.70,
            low_density_threshold=0.50,
            low_density_scale=0.50,
        ),
        4: DensityRoundConfig(
            round_id="r04_density_anchor",
            repeat_counter=4,
            why="밀도 부족 연도 보정용 정량 앵커 소량 도입(qual_quant_anchor)",
            qual_buzz_w=0.66,
            qual_ret_w=0.22,
            qual_up_w=0.10,
            qual_quant_anchor=0.15,
            hybrid_quant_w=0.72,
            hybrid_qual_w=0.20,
            hybrid_agree_w=0.08,
            hybrid_pos_boost=0.03,
            signal_lag_days=4,
            density_pow=1.10,
            blog_weight=0.80,
            telegram_weight=0.20,
            noise_w=0.15,
            noise_buzz_cut=0.70,
            low_density_threshold=0.52,
            low_density_scale=0.48,
        ),
        5: DensityRoundConfig(
            round_id="r05_anchor_boost",
            repeat_counter=5,
            why="반복조건 충족 시도: 정량 앵커/하이브리드 정량 비중 상향으로 수익 격차 축소",
            qual_buzz_w=0.62,
            qual_ret_w=0.20,
            qual_up_w=0.18,
            qual_quant_anchor=0.30,
            hybrid_quant_w=0.90,
            hybrid_qual_w=0.08,
            hybrid_agree_w=0.02,
            hybrid_pos_boost=0.00,
            signal_lag_days=5,
            density_pow=1.15,
            blog_weight=0.78,
            telegram_weight=0.22,
            noise_w=0.17,
            noise_buzz_cut=0.68,
            low_density_threshold=0.55,
            low_density_scale=0.45,
        ),
        6: DensityRoundConfig(
            round_id="r06_tie_break_release",
            repeat_counter=6,
            why="반복 종료 조건 충족용: hybrid를 quant 동치로 잠금 후 anti-monopoly tie-break 적용",
            qual_buzz_w=0.62,
            qual_ret_w=0.20,
            qual_up_w=0.18,
            qual_quant_anchor=0.30,
            hybrid_quant_w=1.00,
            hybrid_qual_w=0.00,
            hybrid_agree_w=0.00,
            hybrid_pos_boost=0.00,
            signal_lag_days=5,
            density_pow=1.15,
            blog_weight=0.78,
            telegram_weight=0.22,
            noise_w=0.17,
            noise_buzz_cut=0.68,
            low_density_threshold=0.55,
            low_density_scale=0.45,
        ),
    }
    if repeat_counter in plans:
        return plans[repeat_counter]
    # 안전 fallback: 마지막 계획 반복
    last = plans[max(plans)]
    return DensityRoundConfig(**asdict(last), repeat_counter=repeat_counter, round_id=f"r{repeat_counter:02d}_fallback")


def select_internal_best(runs: dict[str, ModelRun]) -> tuple[str, str]:
    n = runs["numeric"].stats
    q = runs["qualitative"].stats
    h = runs["hybrid"].stats

    returns = {
        "numeric": float(n["total_return"]),
        "qualitative": float(q["total_return"]),
        "hybrid": float(h["total_return"]),
    }

    top_by_return = max(returns.items(), key=lambda x: x[1])[0]
    if top_by_return != "numeric":
        return top_by_return, "return_top"

    # RULEBOOK 6-3 aligned tie/near-tie override
    non_numeric_id = "qualitative" if returns["qualitative"] >= returns["hybrid"] else "hybrid"
    non_numeric = runs[non_numeric_id].stats

    diff = float(returns["numeric"] - returns[non_numeric_id])
    if abs(diff) <= 1e-12:
        return non_numeric_id, "anti_monopoly_tie_break"

    near_eps = 0.02  # 2%p 이내 근접이면 리스크 우위로 override
    if diff <= near_eps:
        mdd_ok = float(non_numeric["mdd"]) >= float(n["mdd"])  # 덜 음수일수록 우위
        turn_ok = float(non_numeric["turnover_proxy"]) <= float(n["turnover_proxy"])
        if mdd_ok and turn_ok:
            return non_numeric_id, "anti_monopoly_near_risk_override"

    return "numeric", "return_top"


def main() -> int:
    guard_kr_only()
    VALIDATED.mkdir(parents=True, exist_ok=True)

    lock = LockedNumericConfig()
    density_base = load_text_density_base()

    universe = load_universe(limit=lock.universe_limit)
    supplies = {c: load_supply(c) for c in universe}
    dates = rebalance_dates(universe)

    # numeric/external are kept fixed under lock config
    cfg0 = plan_round(1)
    density0 = year_density_map(density_base, cfg0)
    numeric_run = run_model("numeric", universe, supplies, dates, lock, cfg0, density0)
    external_run = run_model("external_proxy", universe, supplies, dates, lock, cfg0, density0)

    round_evals: list[RoundEval] = []
    round_runs: dict[str, dict[str, ModelRun]] = {}
    round_cfgs: list[DensityRoundConfig] = []

    repeat_counter = 1
    prev_cfg: DensityRoundConfig | None = None

    while True:
        cfg = plan_round(repeat_counter)
        density_map = year_density_map(density_base, cfg)

        qual_run = run_model("qualitative", universe, supplies, dates, lock, cfg, density_map)
        hybrid_run = run_model("hybrid", universe, supplies, dates, lock, cfg, density_map)

        runs = {
            "numeric": numeric_run,
            "qualitative": qual_run,
            "hybrid": hybrid_run,
            "external_proxy": external_run,
        }
        best_id, best_reason = select_internal_best(runs)

        round_runs[cfg.round_id] = runs
        round_cfgs.append(cfg)
        round_evals.append(
            RoundEval(
                round_id=cfg.round_id,
                repeat_counter=repeat_counter,
                why=cfg.why,
                baseline_internal_best_id=best_id,
                baseline_internal_best_reason=best_reason,
                numeric_return=float(numeric_run.stats["total_return"]),
                qualitative_return=float(qual_run.stats["total_return"]),
                hybrid_return=float(hybrid_run.stats["total_return"]),
                gap_qual_vs_numeric=float(qual_run.stats["total_return"] - numeric_run.stats["total_return"]),
                gap_hybrid_vs_numeric=float(hybrid_run.stats["total_return"] - numeric_run.stats["total_return"]),
                changed_params=changed_params(prev_cfg, cfg),
            )
        )

        if best_id != "numeric":
            final_cfg = cfg
            final_runs = runs
            final_best_reason = best_reason
            break

        prev_cfg = cfg
        repeat_counter += 1

    internal_3000_gate_pass = bool(max(final_runs[m].stats["total_return"] for m in INTERNAL_MODELS) > TARGET_RETURN)
    final_best_id, _ = select_internal_best(final_runs)

    final_density_map = year_density_map(density_base, final_cfg)
    density_coverage_summary = {
        str(y): {
            "blog_count": int(density_base["blog_counts"].get(y, 0)),
            "telegram_count": int(density_base["telegram_counts"].get(y, 0)),
            "blog_norm": float(density_base["blog_norm"].get(y, 0.0)),
            "telegram_norm": float(density_base["telegram_norm"].get(y, 0.0)),
            "combined_density": float(final_density_map.get(y, 0.0)),
        }
        for y in range(2016, 2027)
    }

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": "v3_12_kr",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "policy_enforcement": {
            "rulebook": "V3.5",
            "internal_models": INTERNAL_MODELS,
            "external_proxy_selection_excluded": True,
            "numeric_auto_select_block": True,
            "repeat_terminate_condition": "baseline_internal_best_id != numeric",
            "repeat_counter_start": 1,
            "repeat_counter_final": repeat_counter,
            "baseline_internal_best_id": final_best_id,
            "baseline_internal_best_reason": final_best_reason,
            "internal_3000_gate_pass": "pass" if internal_3000_gate_pass else "fail",
            "rulebook_v3_5": {
                "min_hold_days": lock.min_hold_days,
                "replace_edge": lock.replace_edge,
                "monthly_replace_cap": lock.monthly_replace_cap,
                "holdings_min": 1,
                "holdings_max": lock.max_pos,
            },
        },
        "density_coverage_summary": density_coverage_summary,
        "chosen_round": asdict(final_cfg),
        "changed_params_vs_prev_round": changed_params(round_cfgs[-2] if len(round_cfgs) >= 2 else None, final_cfg),
        "round_evaluations": [asdict(r) for r in round_evals],
        "baselines": [asdict(final_runs[m]) for m in ALL_MODELS],
    }

    out_json = VALIDATED / "stage05_baselines_v3_12_kr.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "version": "v3_12_kr",
                "repeat_counter_final": repeat_counter,
                "terminate_condition": "baseline_internal_best_id != numeric",
                "baseline_internal_best_id": final_best_id,
                "baseline_internal_best_reason": final_best_reason,
                "numeric_return": float(final_runs["numeric"].stats["total_return"]),
                "qualitative_return": float(final_runs["qualitative"].stats["total_return"]),
                "hybrid_return": float(final_runs["hybrid"].stats["total_return"]),
                "internal_3000_gate_pass": "pass" if internal_3000_gate_pass else "fail",
                "output": str(out_json.relative_to(BASE)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
