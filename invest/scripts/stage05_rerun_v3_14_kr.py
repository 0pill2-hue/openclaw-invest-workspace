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

EPSILON = 0.005
VERSION = "v3_14_kr"
PREV_JSON = VALIDATED / "stage05_baselines_v3_12_kr.json"
OUT_JSON = VALIDATED / "stage05_baselines_v3_14_kr.json"


@dataclass
class LockedNumericConfig:
    universe_limit: int = 180
    max_pos: int = 6  # RULEBOOK hard: holdings 1~6
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
class RoundConfig:
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
    changed_params: dict[str, dict[str, Any]]
    hybrid_qual_mix_ratio: float
    regime: str
    regime_band: dict[str, float]
    gate1_pass: bool
    gate1_recommended_pass: bool
    gate1_fail_reason: str | None
    gate2_pass: bool
    gate2_reason: str
    gate2_condition_i: bool
    gate2_condition_ii: bool
    numeric_return: float
    qualitative_return: float
    hybrid_return: float
    non_numeric_candidate: str
    non_numeric_return: float
    tie_detected: bool
    clone_detected: bool
    non_numeric_top_valid: bool


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


def year_density_map(density_base: dict[str, dict[int, float]], cfg: RoundConfig) -> dict[int, float]:
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
    cfg: RoundConfig,
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
    cfg: RoundConfig,
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
            "RULEBOOK hard 유지: min_hold=20d, replace_edge=+15%, monthly_replace_cap=30%, "
            "holdings=1~6 / numeric fixed baseline"
        ),
    )


def changed_params(prev: RoundConfig | None, cur: RoundConfig) -> dict[str, dict[str, Any]]:
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


def load_prev_repeat_final() -> int:
    if not PREV_JSON.exists():
        return 0
    try:
        payload = json.loads(PREV_JSON.read_text(encoding="utf-8"))
        return int(payload.get("policy_enforcement", {}).get("repeat_counter_final", 0))
    except Exception:
        return 0


def make_rounds(start_repeat: int) -> list[RoundConfig]:
    specs = [
        dict(
            round_id="rA_blog_boost_low_noise",
            why="강완화 시작: blog 우선 가중 공격 상향 + 저노이즈 + quant-anchor 보강",
            qual_buzz_w=0.86,
            qual_ret_w=0.10,
            qual_up_w=0.04,
            qual_quant_anchor=0.45,
            hybrid_quant_w=1.00,
            hybrid_qual_w=0.20,
            hybrid_agree_w=0.15,
            hybrid_pos_boost=0.10,
            signal_lag_days=2,
            density_pow=0.45,
            blog_weight=0.92,
            telegram_weight=0.08,
            noise_w=0.05,
            noise_buzz_cut=0.86,
            low_density_threshold=0.30,
            low_density_scale=0.82,
        ),
        dict(
            round_id="rB_blog_boost_mid_noise",
            why="밀도 완화 확대: 저밀도 스케일 상향 + 중간 노이즈 컷",
            qual_buzz_w=0.83,
            qual_ret_w=0.11,
            qual_up_w=0.06,
            qual_quant_anchor=0.50,
            hybrid_quant_w=0.94,
            hybrid_qual_w=0.22,
            hybrid_agree_w=0.16,
            hybrid_pos_boost=0.10,
            signal_lag_days=3,
            density_pow=0.60,
            blog_weight=0.94,
            telegram_weight=0.06,
            noise_w=0.08,
            noise_buzz_cut=0.82,
            low_density_threshold=0.34,
            low_density_scale=0.78,
        ),
        dict(
            round_id="rC_density_noise_balance",
            why="density/lag/noise 축 확장: lag 증가 + density_pow 중립 영역 탐색",
            qual_buzz_w=0.80,
            qual_ret_w=0.12,
            qual_up_w=0.08,
            qual_quant_anchor=0.55,
            hybrid_quant_w=0.86,
            hybrid_qual_w=0.25,
            hybrid_agree_w=0.17,
            hybrid_pos_boost=0.09,
            signal_lag_days=4,
            density_pow=0.80,
            blog_weight=0.95,
            telegram_weight=0.05,
            noise_w=0.10,
            noise_buzz_cut=0.78,
            low_density_threshold=0.40,
            low_density_scale=0.72,
        ),
        dict(
            round_id="rD_high_density_pref",
            why="고밀도/저노이즈 구간 상단 권장(>=0.50) 검증 라운드",
            qual_buzz_w=0.76,
            qual_ret_w=0.14,
            qual_up_w=0.10,
            qual_quant_anchor=0.60,
            hybrid_quant_w=0.80,
            hybrid_qual_w=0.30,
            hybrid_agree_w=0.20,
            hybrid_pos_boost=0.08,
            signal_lag_days=5,
            density_pow=1.00,
            blog_weight=0.96,
            telegram_weight=0.04,
            noise_w=0.10,
            noise_buzz_cut=0.76,
            low_density_threshold=0.45,
            low_density_scale=0.68,
        ),
        dict(
            round_id="rE_high_density_upper_band",
            why="정성 상단밴드 강화(qual mix 0.55) + blog 우선 극대화",
            qual_buzz_w=0.72,
            qual_ret_w=0.16,
            qual_up_w=0.12,
            qual_quant_anchor=0.65,
            hybrid_quant_w=0.72,
            hybrid_qual_w=0.34,
            hybrid_agree_w=0.21,
            hybrid_pos_boost=0.07,
            signal_lag_days=6,
            density_pow=1.15,
            blog_weight=0.97,
            telegram_weight=0.03,
            noise_w=0.12,
            noise_buzz_cut=0.74,
            low_density_threshold=0.50,
            low_density_scale=0.64,
        ),
        dict(
            round_id="rF_upper_band_stress",
            why="상단밴드 스트레스: 정성 0.60 경계 + 고lag/high-noise 내구성 확인",
            qual_buzz_w=0.68,
            qual_ret_w=0.18,
            qual_up_w=0.14,
            qual_quant_anchor=0.68,
            hybrid_quant_w=0.66,
            hybrid_qual_w=0.36,
            hybrid_agree_w=0.24,
            hybrid_pos_boost=0.06,
            signal_lag_days=7,
            density_pow=1.30,
            blog_weight=0.98,
            telegram_weight=0.02,
            noise_w=0.16,
            noise_buzz_cut=0.70,
            low_density_threshold=0.56,
            low_density_scale=0.60,
        ),
    ]

    rounds: list[RoundConfig] = []
    for i, s in enumerate(specs, start=1):
        rounds.append(RoundConfig(repeat_counter=start_repeat + i, **s))
    return rounds


def evaluate_gate1(cfg: RoundConfig, density_map: dict[int, float]) -> tuple[bool, bool, str | None, str, dict[str, float], float]:
    mix_ratio = float(cfg.hybrid_qual_w + cfg.hybrid_agree_w)
    avg_density = float(np.mean(list(density_map.values()))) if density_map else 0.0

    high_density_low_noise = avg_density >= 0.55 and cfg.noise_w <= 0.11
    if high_density_low_noise:
        regime = "HIGH_DENSITY_LOW_NOISE"
        recommended_min = 0.50
    else:
        regime = "LOW_DENSITY_OR_HIGH_NOISE"
        recommended_min = 0.35

    fail_reason = None
    hard_pass = True

    if mix_ratio < 0.35:
        hard_pass = False
        fail_reason = "hybrid_qual_mix_ratio < 0.35"
    elif mix_ratio > 0.60:
        hard_pass = False
        fail_reason = "hybrid_qual_mix_ratio > 0.60"
    elif cfg.hybrid_qual_w < 0.10:
        hard_pass = False
        fail_reason = "hybrid_qual_w < 0.10"
    elif cfg.hybrid_agree_w < 0.05:
        hard_pass = False
        fail_reason = "hybrid_agree_w < 0.05"

    recommended_pass = bool(mix_ratio >= recommended_min)
    band = {
        "min": 0.35,
        "max": 0.60,
        "recommended_min": recommended_min,
    }
    return hard_pass, recommended_pass, fail_reason, regime, band, mix_ratio


def detect_clone(numeric_run: ModelRun, hybrid_run: ModelRun) -> bool:
    years = sorted(set(numeric_run.annual_returns.keys()) | set(hybrid_run.annual_returns.keys()))
    annual_clone = all(
        abs(float(numeric_run.annual_returns.get(y, 0.0)) - float(hybrid_run.annual_returns.get(y, 0.0))) <= 1e-12
        for y in years
    )
    if not annual_clone:
        return False

    n_tr = numeric_run.trades
    h_tr = hybrid_run.trades
    if len(n_tr) != len(h_tr):
        return False

    for i in range(min(len(n_tr), 50)):
        a = n_tr[i]
        b = h_tr[i]
        if not (
            a.get("code") == b.get("code")
            and a.get("buy_date") == b.get("buy_date")
            and a.get("sell_date") == b.get("sell_date")
        ):
            return False
    return True


def evaluate_gate2(runs: dict[str, ModelRun]) -> dict[str, Any]:
    numeric = runs["numeric"].stats
    qual = runs["qualitative"].stats
    hybrid = runs["hybrid"].stats

    numeric_ret = float(numeric["total_return"])
    qual_ret = float(qual["total_return"])
    hybrid_ret = float(hybrid["total_return"])

    non_numeric_id = "qualitative" if qual_ret >= hybrid_ret else "hybrid"
    non_numeric_stats = runs[non_numeric_id].stats
    non_numeric_ret = float(non_numeric_stats["total_return"])

    cond_i = bool(non_numeric_ret >= numeric_ret + EPSILON)
    near = bool(abs(non_numeric_ret - numeric_ret) <= EPSILON)
    risk_superior = bool(
        float(non_numeric_stats["mdd"]) >= float(numeric["mdd"]) and float(non_numeric_stats["turnover_proxy"]) <= float(numeric["turnover_proxy"])
    )
    cond_ii = bool(near and risk_superior)
    gate2_pass = bool(cond_i or cond_ii)

    if cond_i:
        reason = "(i) return_excess_over_numeric"
    elif cond_ii:
        reason = "(ii) near_tie_with_mdd_turnover_superiority"
    else:
        reason = "gate2_fail"

    return {
        "gate2_pass": gate2_pass,
        "gate2_reason": reason,
        "gate2_condition_i": cond_i,
        "gate2_condition_ii": cond_ii,
        "non_numeric_candidate": non_numeric_id,
        "non_numeric_return": non_numeric_ret,
        "numeric_return": numeric_ret,
        "qualitative_return": qual_ret,
        "hybrid_return": hybrid_ret,
        "tie_detected": near,
    }


def density_summary(density_base: dict[str, dict[int, float]], density_map: dict[int, float]) -> dict[str, Any]:
    return {
        str(y): {
            "blog_count": int(density_base["blog_counts"].get(y, 0)),
            "telegram_count": int(density_base["telegram_counts"].get(y, 0)),
            "blog_norm": float(density_base["blog_norm"].get(y, 0.0)),
            "telegram_norm": float(density_base["telegram_norm"].get(y, 0.0)),
            "combined_density": float(density_map.get(y, 0.0)),
        }
        for y in range(2016, 2027)
    }


def main() -> int:
    guard_kr_only()
    VALIDATED.mkdir(parents=True, exist_ok=True)

    lock = LockedNumericConfig()
    prev_repeat = load_prev_repeat_final()
    rounds = make_rounds(prev_repeat)
    density_base = load_text_density_base()

    universe = load_universe(limit=lock.universe_limit)
    supplies = {c: load_supply(c) for c in universe}
    dates = rebalance_dates(universe)

    # numeric/external fixed once (numeric baseline freeze)
    cfg_anchor = rounds[0]
    density_anchor = year_density_map(density_base, cfg_anchor)
    numeric_run = run_model("numeric", universe, supplies, dates, lock, cfg_anchor, density_anchor)
    external_run = run_model("external_proxy", universe, supplies, dates, lock, cfg_anchor, density_anchor)

    round_evals: list[RoundEval] = []
    round_runs: dict[str, dict[str, ModelRun]] = {}

    prev_cfg: RoundConfig | None = None
    final_cfg = rounds[-1]
    final_runs: dict[str, ModelRun] | None = None
    stop_reason = "MAX_REPEAT_REACHED_REDESIGN"
    final_decision = "REDESIGN"

    for cfg in rounds:
        density_map = year_density_map(density_base, cfg)
        g1_pass, g1_reco_pass, g1_fail_reason, regime, regime_band, mix_ratio = evaluate_gate1(cfg, density_map)

        qual_run = run_model("qualitative", universe, supplies, dates, lock, cfg, density_map)
        hybrid_run = run_model("hybrid", universe, supplies, dates, lock, cfg, density_map)

        runs = {
            "numeric": numeric_run,
            "qualitative": qual_run,
            "hybrid": hybrid_run,
            "external_proxy": external_run,
        }
        round_runs[cfg.round_id] = runs

        g2 = evaluate_gate2(runs)
        clone_detected = detect_clone(numeric_run, hybrid_run)
        non_numeric_top_valid = bool(g1_pass and g2["gate2_pass"] and (not clone_detected))

        if clone_detected:
            gate2_pass = False
            gate2_reason = "clone_detected_fail"
            gate2_i = False
            gate2_ii = False
        else:
            gate2_pass = bool(g2["gate2_pass"])
            gate2_reason = str(g2["gate2_reason"])
            gate2_i = bool(g2["gate2_condition_i"])
            gate2_ii = bool(g2["gate2_condition_ii"])

        row = RoundEval(
            round_id=cfg.round_id,
            repeat_counter=cfg.repeat_counter,
            why=cfg.why,
            changed_params=changed_params(prev_cfg, cfg),
            hybrid_qual_mix_ratio=mix_ratio,
            regime=regime,
            regime_band=regime_band,
            gate1_pass=g1_pass,
            gate1_recommended_pass=g1_reco_pass,
            gate1_fail_reason=g1_fail_reason,
            gate2_pass=gate2_pass,
            gate2_reason=gate2_reason,
            gate2_condition_i=gate2_i,
            gate2_condition_ii=gate2_ii,
            numeric_return=float(g2["numeric_return"]),
            qualitative_return=float(g2["qualitative_return"]),
            hybrid_return=float(g2["hybrid_return"]),
            non_numeric_candidate=str(g2["non_numeric_candidate"]),
            non_numeric_return=float(g2["non_numeric_return"]),
            tie_detected=bool(g2["tie_detected"]),
            clone_detected=clone_detected,
            non_numeric_top_valid=non_numeric_top_valid,
        )
        round_evals.append(row)

        if non_numeric_top_valid:
            final_cfg = cfg
            final_runs = runs
            stop_reason = "NON_NUMERIC_TOP_CONFIRMED"
            final_decision = "ADOPT"
            break

        prev_cfg = cfg

    if final_runs is None:
        final_runs = round_runs[final_cfg.round_id]

    chosen_eval = next(r for r in round_evals if r.round_id == final_cfg.round_id)

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "policy_enforcement": {
            "rulebook": "V3.5_hard_rules",
            "internal_models": INTERNAL_MODELS,
            "external_proxy_selection_excluded": True,
            "numeric_fixed_baseline": True,
            "repeat_counter_start": prev_repeat + 1,
            "repeat_counter_final": int(chosen_eval.repeat_counter),
            "stop_reason": stop_reason,
            "final_decision": final_decision,
            "epsilon": EPSILON,
            "gate1_dynamic_band": {
                "mix_ratio_hard_min": 0.35,
                "mix_ratio_hard_max": 0.60,
                "high_density_low_noise_recommended_min": 0.50,
                "hard_fail_if_mix_ratio_below": 0.35,
                "per_component_floor": {
                    "hybrid_qual_w_min": 0.10,
                    "hybrid_agree_w_min": 0.05,
                },
            },
            "gate2_non_numeric_adopt": {
                "condition_i": "non_numeric_return >= numeric_return + epsilon",
                "condition_ii": "abs(non_numeric_return - numeric_return) <= epsilon and mdd/turnover both superior",
            },
            "rulebook_v3_5": {
                "min_hold_days": lock.min_hold_days,
                "replace_edge": lock.replace_edge,
                "monthly_replace_cap": lock.monthly_replace_cap,
                "holdings_min": 1,
                "holdings_max": lock.max_pos,
            },
        },
        "chosen_round": asdict(final_cfg),
        "chosen_round_gate": {
            "hybrid_qual_mix_ratio": chosen_eval.hybrid_qual_mix_ratio,
            "regime": chosen_eval.regime,
            "regime_band": chosen_eval.regime_band,
            "gate1_pass": chosen_eval.gate1_pass,
            "gate1_recommended_pass": chosen_eval.gate1_recommended_pass,
            "gate2_pass": chosen_eval.gate2_pass,
            "gate2_reason": chosen_eval.gate2_reason,
            "gate2_condition_i": chosen_eval.gate2_condition_i,
            "gate2_condition_ii": chosen_eval.gate2_condition_ii,
            "non_numeric_top_valid": chosen_eval.non_numeric_top_valid,
            "tie_detected": chosen_eval.tie_detected,
            "clone_detected": chosen_eval.clone_detected,
        },
        "density_coverage_summary": density_summary(density_base, year_density_map(density_base, final_cfg)),
        "round_evaluations": [asdict(r) for r in round_evals],
        "baselines": [asdict(final_runs[m]) for m in ALL_MODELS],
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "version": VERSION,
                "repeat_counter_start": prev_repeat + 1,
                "repeat_counter_final": int(chosen_eval.repeat_counter),
                "stop_reason": stop_reason,
                "final_decision": final_decision,
                "numeric_return": chosen_eval.numeric_return,
                "qualitative_return": chosen_eval.qualitative_return,
                "hybrid_return": chosen_eval.hybrid_return,
                "non_numeric_top_valid": chosen_eval.non_numeric_top_valid,
                "gate1_pass": chosen_eval.gate1_pass,
                "gate2_pass": chosen_eval.gate2_pass,
                "tie_detected": chosen_eval.tie_detected,
                "clone_detected": chosen_eval.clone_detected,
                "output": str(OUT_JSON.relative_to(BASE)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
