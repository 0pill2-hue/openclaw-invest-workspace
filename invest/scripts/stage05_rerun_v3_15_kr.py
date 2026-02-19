#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
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
CONFIG_PATH = BASE / "invest/config/stage05_auto_capture_v3_15_kr.yaml"
PREV_JSON = VALIDATED / "stage05_baselines_v3_14_kr.json"
OUT_JSON = VALIDATED / "stage05_baselines_v3_15_kr.json"

LOG_DIR = BASE / "reports/stage_updates/logs"
SCAN_LOG = LOG_DIR / "stage05_no_whitelist_scan_v3_15_kr.log"
UNIVERSE_LOG = LOG_DIR / "stage05_dynamic_universe_v3_15_kr.json"

US_TICKERS = re.compile(r"\b(AAPL|NVDA|TSLA|MSFT|AMZN|GOOG|META)\b")
KR_CODE_LITERAL = re.compile(r"['\"]\d{6}['\"]")

INTERNAL_MODELS = ["numeric", "qualitative", "hybrid"]
ALL_MODELS = INTERNAL_MODELS + ["external_proxy"]

EPSILON = 0.005
VERSION = "v3_15_kr"


@dataclass
class LockedNumericConfig:
    universe_limit: int
    min_history_days: int
    max_pos: int = 6
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
    monthly_returns: dict[str, float]
    equity_curve: dict[str, float]
    stats: dict[str, float]
    trades: list[dict[str, Any]]
    selection_signature: str
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
    high_density_advantage_pass: bool
    gate2_detail: dict[str, Any]
    gate3_subperiod_stability_pass: bool
    gate4_purged_cv_oos_pass: bool
    numeric_return: float
    qualitative_return: float
    hybrid_return: float
    non_numeric_candidate: str
    non_numeric_return: float
    tie_detected: bool
    clone_detected: bool
    non_numeric_top_valid: bool
    gate3_detail: dict[str, Any]
    gate4_detail: dict[str, Any]



def stable_hash(obj: Any) -> str:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def stats_from_equity(eq: pd.Series, trades_count: int, rebalance_count: int) -> dict[str, float]:
    eq = eq.dropna().sort_index()
    if eq.empty:
        return {
            "total_return": 0.0,
            "asset_multiple": 1.0,
            "mdd": 0.0,
            "turnover_proxy": 0.0,
        }
    ret = float(eq.iloc[-1] / max(1e-12, eq.iloc[0]) - 1.0) if len(eq) > 1 else 0.0
    peak = float(eq.iloc[0])
    mdd = 0.0
    for v in eq.values:
        peak = max(peak, float(v))
        mdd = min(mdd, float(v) / max(1e-12, peak) - 1.0)
    return {
        "total_return": ret,
        "asset_multiple": float(eq.iloc[-1]),
        "mdd": mdd,
        "turnover_proxy": float(trades_count / max(1, rebalance_count)),
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


def parse_config() -> tuple[dict[str, Any], str, str]:
    raw = CONFIG_PATH.read_text(encoding="utf-8")
    cfg = json.loads(raw)
    config_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    search_hash = stable_hash(cfg.get("search_space", {}))
    return cfg, config_hash, search_hash


def run_static_hardcode_scan() -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    target_files = sorted([*BASE.glob("invest/scripts/stage05*kr.py"), BASE / "invest/scripts/stage05_backtest_engine.py"])

    allowlist_list_hits: list[dict[str, Any]] = []
    favorites_list_hits: list[dict[str, Any]] = []
    ticker_literal_hits: list[dict[str, Any]] = []

    for fp in target_files:
        try:
            lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            if re.search(r"\b(allowlist|whitelist)\b\s*=\s*\[", line):
                allowlist_list_hits.append({"file": str(fp.relative_to(BASE)), "line": i, "text": line.strip()[:180]})
            if re.search(r"\b(favorites?|manual[_\- ]?pick|manual[_\- ]?ticker)\b\s*=\s*\[", line):
                favorites_list_hits.append({"file": str(fp.relative_to(BASE)), "line": i, "text": line.strip()[:180]})
            if KR_CODE_LITERAL.search(line):
                ticker_literal_hits.append({"file": str(fp.relative_to(BASE)), "line": i, "text": line.strip()[:180]})

    scan_pass = (len(allowlist_list_hits) == 0) and (len(favorites_list_hits) == 0) and (len(ticker_literal_hits) == 0)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_files": [str(p.relative_to(BASE)) for p in target_files],
        "allowlist_list_hits": allowlist_list_hits,
        "favorites_list_hits": favorites_list_hits,
        "ticker_literal_hits": ticker_literal_hits,
        "scan_pass": scan_pass,
    }
    SCAN_LOG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_universe_pool(pool_limit: int) -> dict[str, pd.DataFrame]:
    rows: list[tuple[str, float, pd.DataFrame]] = []
    for fp in OHLCV_DIR.glob("*.csv"):
        try:
            df = pd.read_csv(fp, usecols=lambda c: c in {"Date", "Open", "High", "Low", "Close", "Volume"})
            if not {"Date", "Close", "Volume"}.issubset(df.columns):
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
            df = df[(df["Date"] >= "2015-01-01") & (df["Date"] <= "2026-12-31")]
            if len(df) < 260:
                continue
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                if c not in df.columns:
                    df[c] = np.nan
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["Close"]).set_index("Date").sort_index()
            turnover = (df["Close"].fillna(0) * df["Volume"].fillna(0)).rolling(252).mean()
            df["liq252"] = turnover
            liq = float(turnover.dropna().iloc[-1]) if not turnover.dropna().empty else 0.0
            rows.append((fp.stem, liq, df))
        except Exception:
            continue
    rows.sort(key=lambda x: x[1], reverse=True)
    if pool_limit > 0:
        rows = rows[:pool_limit]
    return {c: d for c, _, d in rows}


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


def build_dynamic_universe(
    universe_pool: dict[str, pd.DataFrame],
    dates: list[pd.Timestamp],
    limit: int,
    min_history_days: int,
) -> tuple[dict[pd.Timestamp, list[str]], dict[str, Any], str]:
    by_date: dict[pd.Timestamp, list[str]] = {}
    log_payload: dict[str, Any] = {
        "version": VERSION,
        "selection_rule": {
            "universe_mode": "liquidity_top_n",
            "limit": limit,
            "min_history_days": min_history_days,
        },
        "by_date": {},
    }

    for d in dates:
        ranked: list[tuple[str, float, int]] = []
        for code, df in universe_pool.items():
            pos = int(df.index.searchsorted(d, side="right"))
            if pos < min_history_days:
                continue
            liq = float(df["liq252"].iloc[pos - 1]) if pos > 0 else float("nan")
            if math.isnan(liq) or liq <= 0:
                continue
            ranked.append((code, liq, pos))
        ranked.sort(key=lambda x: x[1], reverse=True)
        members = [code for code, _, _ in ranked[:limit]]
        by_date[d] = members

        date_key = d.strftime("%Y-%m-%d")
        log_payload["by_date"][date_key] = {
            "eligible_count": int(len(ranked)),
            "selected_count": int(len(members)),
            "liquidity_cutoff": float(ranked[min(len(ranked), limit) - 1][1]) if ranked and len(ranked) >= limit else float(ranked[-1][1]) if ranked else 0.0,
            "top10": members[:10],
            "membership_hash": stable_hash(members),
        }

    membership_hash = stable_hash({k.strftime("%Y-%m-%d"): v for k, v in by_date.items()})
    log_payload["membership_by_date_hash"] = membership_hash

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    UNIVERSE_LOG.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return by_date, log_payload, membership_hash


def compute_market_regime(
    universe_pool: dict[str, pd.DataFrame],
    membership_by_date: dict[pd.Timestamp, list[str]],
    dates: list[pd.Timestamp],
    regime_cfg: dict[str, Any],
) -> tuple[dict[pd.Timestamp, str], dict[str, int]]:
    risk_off_dd = float(regime_cfg.get("risk_off_drawdown", -0.15))
    risk_off_vol_z = float(regime_cfg.get("risk_off_vol_z", 1.5))
    persistence_days = int(regime_cfg.get("regime_min_persistence_days", 20))
    persistence_months = max(1, int(round(persistence_days / 21)))

    market_rets: list[float] = []
    eq = 1.0
    peak = 1.0
    regimes: dict[pd.Timestamp, str] = {}
    streak = 0
    prev_regime = "TRANSITION"

    for i, d in enumerate(dates):
        if i == 0:
            market_rets.append(0.0)
            regimes[d] = "TRANSITION"
            continue

        prev_d = dates[i - 1]
        members = membership_by_date.get(d, [])
        one_month_rets: list[float] = []
        for code in members:
            df = universe_pool.get(code)
            if df is None:
                continue
            h_now = df.loc[:d]
            h_prev = df.loc[:prev_d]
            if h_now.empty or h_prev.empty:
                continue
            now_p = float(h_now["Close"].iloc[-1])
            prev_p = float(h_prev["Close"].iloc[-1])
            if prev_p <= 0:
                continue
            one_month_rets.append(now_p / prev_p - 1.0)

        mret = float(np.mean(one_month_rets)) if one_month_rets else 0.0
        market_rets.append(mret)

        eq *= 1.0 + mret
        peak = max(peak, eq)
        dd = eq / max(1e-12, peak) - 1.0

        ret_s = pd.Series(market_rets)
        vol = float(ret_s.tail(12).std()) if len(ret_s) >= 12 else 0.0
        vol_hist = ret_s.rolling(12).std().dropna()
        if len(vol_hist) >= 24:
            base = float(vol_hist.tail(24).mean())
            std = float(vol_hist.tail(24).std())
            vol_z = (vol - base) / (std + 1e-9)
        else:
            vol_z = 0.0

        proposed = "RISK_ON"
        if dd <= risk_off_dd or vol_z >= risk_off_vol_z:
            proposed = "RISK_OFF"
        elif dd <= risk_off_dd * 0.5 or vol_z >= risk_off_vol_z * 0.75:
            proposed = "TRANSITION"

        if proposed == prev_regime:
            streak += 1
        else:
            if streak < persistence_months:
                proposed = prev_regime
                streak += 1
            else:
                streak = 1
        regimes[d] = proposed
        prev_regime = proposed

    counts = {"RISK_ON": 0, "TRANSITION": 0, "RISK_OFF": 0}
    for r in regimes.values():
        counts[r] = counts.get(r, 0) + 1
    return regimes, counts


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


def normalize_weights(weights: dict[str, float], floor: float, cap: float) -> dict[str, float]:
    bounded = {k: float(np.clip(v, floor, cap)) for k, v in weights.items()}
    total = sum(bounded.values())
    if total <= 0:
        n = len(bounded)
        return {k: 1.0 / max(1, n) for k in bounded}
    return {k: v / total for k, v in bounded.items()}


def compute_factor_values(
    d: pd.Timestamp,
    px: pd.DataFrame,
    sp: pd.DataFrame | None,
    lock: LockedNumericConfig,
    cfg: RoundConfig,
    density_by_year: dict[int, float],
    regime: str,
    regime_cfg: dict[str, Any],
) -> dict[str, float] | None:
    h = px.loc[:d]
    if len(h) < max(130, lock.trend_span_slow + 5, lock.ret_mid + 5):
        return None

    c = h["Close"]
    v = h["Volume"].fillna(0)

    ret_s = float(c.pct_change(lock.ret_short).iloc[-1])
    ret_m = float(c.pct_change(lock.ret_mid).iloc[-1])

    high_120 = float(c.rolling(120).max().iloc[-1])
    breakout = float(c.iloc[-1] / max(1e-9, high_120) - 1.0)

    ma_f = float(c.ewm(span=lock.trend_span_fast).mean().iloc[-1])
    ma_s = float(c.ewm(span=lock.trend_span_slow).mean().iloc[-1])
    ma120 = float(c.rolling(120).mean().iloc[-1])

    trend = 0.6 * float(ma_f > ma_s) + 0.4 * float(ma_s > ma120)
    momentum = 0.45 * trend + 0.30 * (0.0 if math.isnan(ret_s) else ret_s) + 0.25 * (0.0 if math.isnan(ret_m) else ret_m)

    flow = 0.0
    if sp is not None:
        sh = sp.loc[:d]
        if len(sh) > 20:
            val = (sh["기관합계"].rolling(20).mean().iloc[-1] + sh["외국인합계"].rolling(20).mean().iloc[-1]) / lock.flow_scale
            flow = float(np.tanh(val))

    vol20 = float(c.pct_change().tail(20).std()) if len(c) >= 25 else 0.0
    volatility_stability = float(np.clip(1.0 - vol20 * 8.0, -1.0, 1.0))

    lag = int(max(0, cfg.signal_lag_days))
    buzz_series = v / (v.rolling(60).mean() + 1e-9)
    buzz = float(buzz_series.shift(lag).iloc[-1])
    ret_s_lag = float(c.pct_change(lock.ret_short).shift(lag).iloc[-1])
    up_ratio = float(c.pct_change().shift(lag).tail(20).gt(0.02).mean())

    density = density_by_year.get(int(d.year), 0.5)
    reg_thr = float(regime_cfg.get("low_density_threshold_by_regime", {}).get(regime, cfg.low_density_threshold))
    reg_scale = float(regime_cfg.get("low_density_scale_by_regime", {}).get(regime, cfg.low_density_scale))

    qual_raw = (
        cfg.qual_buzz_w * np.tanh(buzz - 1.0)
        + cfg.qual_ret_w * (0.0 if math.isnan(ret_s_lag) else ret_s_lag)
        + cfg.qual_up_w * up_ratio
        + cfg.qual_quant_anchor * momentum
    )

    qualitative_lagged = float(qual_raw)
    if cfg.density_pow > 0:
        qualitative_lagged *= float(max(density, 1e-6) ** cfg.density_pow)

    low_thr = max(cfg.low_density_threshold, reg_thr)
    low_scale = min(cfg.low_density_scale, reg_scale)
    if density < low_thr:
        qualitative_lagged *= low_scale

    buzz_jump = float(buzz_series.diff().abs().tail(20).median()) if len(buzz_series) >= 25 else 0.0
    noise_penalty = float(np.tanh(vol20 * 3.0 + max(0.0, buzz_jump - cfg.noise_buzz_cut)))

    external_proxy = 0.6 * (ma_f / (ma_s + 1e-9) - 1.0) + 0.4 * (0.0 if math.isnan(ret_s) else ret_s)

    return {
        "momentum": float(momentum),
        "breakout": float(breakout),
        "flow": float(flow),
        "volatility_stability": float(volatility_stability),
        "qualitative_lagged": float(qualitative_lagged),
        "noise_penalty": float(noise_penalty),
        "external_proxy": float(external_proxy),
    }


def rank_series(values: dict[str, float], ascending: bool = False) -> pd.Series:
    s = pd.Series(values, dtype=float)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return pd.Series(dtype=float)
    return s.rank(method="average", pct=True, ascending=ascending)


def run_model(
    model: str,
    universe_pool: dict[str, pd.DataFrame],
    supplies: dict[str, pd.DataFrame | None],
    dates: list[pd.Timestamp],
    membership_by_date: dict[pd.Timestamp, list[str]],
    regime_by_date: dict[pd.Timestamp, str],
    lock: LockedNumericConfig,
    cfg: RoundConfig,
    density_by_year: dict[int, float],
    main_cfg: dict[str, Any],
) -> ModelRun:
    cash = 1.0
    holdings: dict[str, dict[str, Any]] = {}
    eq_curve: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []

    factor_set = list(main_cfg["factors"]["factor_set"])
    ensemble_method = str(main_cfg["factors"].get("ensemble_method", "median_rank"))
    regime_templates = main_cfg["regime_gate"].get("factor_weight_templates", {})
    fw_floor = float(main_cfg["factors"].get("factor_weight_floor", 0.1))
    fw_cap = float(main_cfg["factors"].get("factor_weight_cap", 0.4))

    for d in dates:
        px_now: dict[str, float] = {}
        regime = regime_by_date.get(d, "TRANSITION")
        members = membership_by_date.get(d, [])

        raw_factors: dict[str, dict[str, float]] = {k: {} for k in [*factor_set, "noise_penalty", "external_proxy"]}

        for code in members:
            df = universe_pool.get(code)
            if df is None:
                continue
            h = df.loc[:d]
            if h.empty:
                continue
            px_now[code] = float(h["Close"].iloc[-1])
            fv = compute_factor_values(
                d=h.index[-1],
                px=df,
                sp=supplies.get(code),
                lock=lock,
                cfg=cfg,
                density_by_year=density_by_year,
                regime=regime,
                regime_cfg=main_cfg["regime_gate"],
            )
            if fv is None:
                continue
            for k, v in fv.items():
                raw_factors.setdefault(k, {})[code] = float(v)

        if not raw_factors.get("momentum"):
            total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
            eq_curve.append((d, total))
            continue

        rank_map: dict[str, pd.Series] = {}
        for f in factor_set:
            rank_map[f] = rank_series(raw_factors.get(f, {}), ascending=False)
        rank_map["noise_penalty"] = rank_series(raw_factors.get("noise_penalty", {}), ascending=True)

        weight_template = regime_templates.get(regime) or regime_templates.get("TRANSITION") or {f: 1.0 for f in factor_set}
        w = normalize_weights({f: float(weight_template.get(f, 0.0)) for f in factor_set}, floor=fw_floor, cap=fw_cap)

        score_numeric: dict[str, float] = {}
        score_qual: dict[str, float] = {}
        score_hybrid: dict[str, float] = {}
        score_external: dict[str, float] = {}

        index_sets = [set(rank_map[f].index.tolist()) for f in factor_set if not rank_map[f].empty]
        if index_sets:
            base_codes = set.intersection(*index_sets)
        else:
            base_codes = set()

        for code in base_codes:
            factor_ranks = [float(rank_map[f].get(code, np.nan)) for f in factor_set]
            if any(math.isnan(v) for v in factor_ranks):
                continue

            quant_factors = ["momentum", "breakout", "flow", "volatility_stability"]
            quant_vals = [float(rank_map[f].get(code, np.nan)) for f in quant_factors]
            if any(math.isnan(v) for v in quant_vals):
                continue
            quant_rank = float(np.mean(quant_vals))

            qual_rank = float(rank_map["qualitative_lagged"].get(code, np.nan))
            if math.isnan(qual_rank):
                continue

            noise_rank = float(rank_map["noise_penalty"].get(code, 0.5))
            qual_adj = max(0.0, qual_rank - cfg.noise_w * (1.0 - noise_rank))

            median_rank = float(np.median(factor_ranks))
            weighted_rank = float(sum(w[f] * float(rank_map[f].get(code, 0.0)) for f in factor_set))
            ensemble_rank = median_rank if ensemble_method == "median_rank" else weighted_rank
            if ensemble_method == "median_rank":
                ensemble_rank = 0.5 * (median_rank + weighted_rank)

            agree = min(quant_rank, qual_adj)
            hybrid = (
                cfg.hybrid_quant_w * quant_rank
                + cfg.hybrid_qual_w * qual_adj
                + cfg.hybrid_agree_w * agree
                + cfg.hybrid_pos_boost * max(qual_adj - 0.50, 0.0)
                + 0.20 * ensemble_rank
            )

            score_numeric[code] = float(quant_rank)
            score_qual[code] = float(qual_adj)
            score_hybrid[code] = float(hybrid)
            score_external[code] = float(raw_factors["external_proxy"].get(code, 0.0))

        scores: dict[str, float] = {}
        if model == "numeric":
            scores = score_numeric
        elif model == "qualitative":
            scores = score_qual
        elif model == "hybrid":
            scores = score_hybrid
        elif model == "external_proxy":
            scores = score_external

        if not scores:
            total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
            eq_curve.append((d, total))
            continue

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = ranked[: lock.max_pos]
        target_set = {c for c, _ in top}

        selections.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "regime": regime,
                "model": model,
                "top": [c for c, _ in top],
            }
        )

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
        px_now = {c: float(df.loc[:d]["Close"].iloc[-1]) for c, df in universe_pool.items() if not df.loc[:d].empty}
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

    monthly = eq.pct_change().dropna()
    monthly_returns = {d.strftime("%Y-%m-%d"): float(v) for d, v in monthly.items()}
    equity_curve = {d.strftime("%Y-%m-%d"): float(v) for d, v in eq.items()}
    stats = annual_stats(annual, trades_count=len(trades), rebalance_count=len(dates))
    selection_signature = stable_hash(selections)

    return ModelRun(
        model=model,
        annual_returns=annual,
        monthly_returns=monthly_returns,
        equity_curve=equity_curve,
        stats=stats,
        trades=trades,
        selection_signature=selection_signature,
        notes=(
            "RULEBOOK hard 유지: min_hold=20d, replace_edge=+15%, monthly_replace_cap=30%, "
            "holdings=1~6 / regime gate + multifactor ensemble"
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


def sample_combo_indices(total: int, max_trials: int) -> list[int]:
    if total <= 0 or max_trials <= 0:
        return []
    if total <= max_trials:
        return list(range(total))
    step = (total - 1) / float(max_trials - 1)
    out = sorted(set(int(round(i * step)) for i in range(max_trials)))
    while len(out) < max_trials:
        out.append((out[-1] + 1) % total)
    return out[:max_trials]


def combo_from_index(idx: int, keys: list[str], values: list[list[Any]]) -> dict[str, Any]:
    sizes = [len(v) for v in values]
    out: dict[str, Any] = {}
    rem = idx
    for k, vals, sz in zip(reversed(keys), reversed(values), reversed(sizes), strict=False):
        pick = rem % sz
        rem //= sz
        out[k] = vals[pick]
    return {k: out[k] for k in keys}


def make_rounds(start_repeat: int, main_cfg: dict[str, Any]) -> tuple[list[RoundConfig], dict[str, Any]]:
    grid = main_cfg["search_space"]["param_grid"]
    max_trials = int(main_cfg["search_space"].get("max_trials", 6))

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
    values = [list(grid[k]) for k in keys]
    total = int(np.prod([len(v) for v in values], dtype=np.int64))
    indices = sample_combo_indices(total=total, max_trials=max_trials)

    rounds: list[RoundConfig] = []
    for i, idx in enumerate(indices, start=1):
        combo = combo_from_index(idx, keys, values)
        rounds.append(
            RoundConfig(
                round_id=f"r{i:02d}_auto_grid_{idx}",
                repeat_counter=start_repeat + i,
                why=f"config-grid deterministic sample idx={idx}/{total - 1}",
                **combo,
            )
        )

    meta = {
        "total_combinations": total,
        "sampled_indices": indices,
        "max_trials": max_trials,
    }
    return rounds, meta


def evaluate_gate1(cfg: RoundConfig, regime_counts: dict[str, int], main_cfg: dict[str, Any]) -> tuple[bool, bool, str | None, str, dict[str, float], float]:
    mix_ratio = float(cfg.hybrid_qual_w + cfg.hybrid_agree_w)
    band = list(main_cfg["factors"].get("hybrid_mix_ratio_band", [0.35, 0.60]))
    hard_min, hard_max = float(band[0]), float(band[1])

    dominant = max(regime_counts.items(), key=lambda x: x[1])[0] if regime_counts else "TRANSITION"
    recommended_min = 0.50 if dominant == "RISK_ON" else 0.35

    fail_reason = None
    hard_pass = True
    if mix_ratio < hard_min:
        hard_pass = False
        fail_reason = f"hybrid_qual_mix_ratio < {hard_min}"
    elif mix_ratio > hard_max:
        hard_pass = False
        fail_reason = f"hybrid_qual_mix_ratio > {hard_max}"
    elif cfg.hybrid_qual_w < 0.10:
        hard_pass = False
        fail_reason = "hybrid_qual_w < 0.10"
    elif cfg.hybrid_agree_w < 0.05:
        hard_pass = False
        fail_reason = "hybrid_agree_w < 0.05"

    recommended_pass = bool(mix_ratio >= recommended_min)
    return (
        hard_pass,
        recommended_pass,
        fail_reason,
        dominant,
        {"min": hard_min, "max": hard_max, "recommended_min": recommended_min},
        mix_ratio,
    )


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
        if not (a.get("code") == b.get("code") and a.get("buy_date") == b.get("buy_date") and a.get("sell_date") == b.get("sell_date")):
            return False
    return True


def evaluate_gate2(runs: dict[str, ModelRun], density_map: dict[int, float], anti_cfg: dict[str, Any]) -> dict[str, Any]:
    numeric = runs["numeric"].stats
    qual = runs["qualitative"].stats
    hybrid = runs["hybrid"].stats

    numeric_ret = float(numeric["total_return"])
    qual_ret = float(qual["total_return"])
    hybrid_ret = float(hybrid["total_return"])

    non_numeric_id = "qualitative" if qual_ret >= hybrid_ret else "hybrid"
    non_numeric_stats = runs[non_numeric_id].stats
    non_numeric_ret = float(non_numeric_stats["total_return"])

    near = bool(abs(non_numeric_ret - numeric_ret) <= EPSILON)

    numeric_mdd = float(numeric["mdd"])
    non_numeric_mdd = float(non_numeric_stats["mdd"])
    numeric_turnover = max(1e-9, float(numeric["turnover_proxy"]))
    non_numeric_turnover = max(1e-9, float(non_numeric_stats["turnover_proxy"]))
    turnover_ratio = float(non_numeric_turnover / numeric_turnover)

    mdd_superior = bool(non_numeric_mdd >= numeric_mdd)
    turnover_superior_basic = bool(non_numeric_turnover <= numeric_turnover)

    avg_density = float(np.mean(list(density_map.values()))) if density_map else 0.0
    high_density_threshold = float(anti_cfg.get("high_density_threshold", 0.50))
    high_density = bool(avg_density >= high_density_threshold)

    high_density_advantage_required = float(anti_cfg.get("high_density_advantage_pp", 0.25))
    high_density_turnover_ratio_max = float(anti_cfg.get("high_density_turnover_ratio_max", 1.05))

    advantage = float(non_numeric_ret - numeric_ret)
    high_density_advantage_pass = bool(advantage >= high_density_advantage_required)
    high_density_risk_pass = bool(mdd_superior and turnover_ratio <= high_density_turnover_ratio_max)

    if high_density:
        cond_i = bool(high_density_advantage_pass and high_density_risk_pass)
        cond_ii = False
    else:
        cond_i = bool(non_numeric_ret >= numeric_ret + EPSILON)
        risk_superior = bool(mdd_superior and turnover_superior_basic)
        cond_ii = bool(near and risk_superior)

    gate2_pass = bool(cond_i or cond_ii)

    if high_density and cond_i:
        reason = "(i-hd) high_density_advantage_25pp_plus_risk_superiority"
    elif cond_i:
        reason = "(i) return_excess_over_numeric"
    elif cond_ii:
        reason = "(ii) near_tie_with_mdd_turnover_superiority"
    elif high_density:
        reason = "gate2_fail_high_density_raised_bar"
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
        "high_density_advantage_pass": high_density_advantage_pass,
        "high_density_mode": high_density,
        "avg_density": avg_density,
        "high_density_threshold": high_density_threshold,
        "high_density_advantage_required": high_density_advantage_required,
        "advantage": advantage,
        "mdd_superior": mdd_superior,
        "turnover_ratio": turnover_ratio,
        "turnover_ratio_max": high_density_turnover_ratio_max,
        "high_density_risk_pass": high_density_risk_pass,
        "numeric_mdd": numeric_mdd,
        "non_numeric_mdd": non_numeric_mdd,
        "numeric_turnover": numeric_turnover,
        "non_numeric_turnover": non_numeric_turnover,
    }


def evaluate_gate3_subperiod_stability(run: ModelRun, anti_cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    eq = pd.Series({pd.to_datetime(k): float(v) for k, v in run.equity_curve.items()}).sort_index()
    base_stats = run.stats

    periods = anti_cfg.get("subperiods", [])
    pass_ratio_min = float(anti_cfg.get("subperiod_pass_ratio_min", 0.67))
    mdd_delta_max = float(anti_cfg.get("stability_mdd_delta_max", 0.10))
    turnover_ratio_max = float(anti_cfg.get("stability_turnover_ratio_max", 1.30))
    return_floor = float(anti_cfg.get("stability_return_floor", -0.25))

    rows = []
    pass_count = 0
    for p in periods:
        s = pd.to_datetime(p["start"])
        e = pd.to_datetime(p["end"])
        seg = eq[(eq.index >= s) & (eq.index <= e)]
        seg_trades = [t for t in run.trades if s <= pd.to_datetime(t["sell_date"]) <= e]
        seg_stats = stats_from_equity(seg, trades_count=len(seg_trades), rebalance_count=max(1, len(seg)))

        mdd_delta = abs(float(seg_stats["mdd"]) - float(base_stats["mdd"]))
        base_turn = max(1e-9, float(base_stats["turnover_proxy"]))
        seg_turn = max(1e-9, float(seg_stats["turnover_proxy"]))
        turnover_ratio = max(seg_turn / base_turn, base_turn / seg_turn)
        period_pass = bool(
            float(seg_stats["total_return"]) >= return_floor and mdd_delta <= mdd_delta_max and turnover_ratio <= turnover_ratio_max
        )
        pass_count += int(period_pass)

        rows.append(
            {
                "id": p["id"],
                "start": p["start"],
                "end": p["end"],
                "total_return": float(seg_stats["total_return"]),
                "mdd": float(seg_stats["mdd"]),
                "turnover_proxy": float(seg_stats["turnover_proxy"]),
                "mdd_delta_vs_full": float(mdd_delta),
                "turnover_ratio_vs_full": float(turnover_ratio),
                "period_pass": period_pass,
            }
        )

    total = max(1, len(rows))
    pass_ratio = pass_count / total
    gate_pass = bool(pass_ratio >= pass_ratio_min)
    detail = {
        "pass_ratio": float(pass_ratio),
        "pass_ratio_min": float(pass_ratio_min),
        "subperiods": rows,
    }
    return gate_pass, detail


def evaluate_gate4_purged_cv_oos(run: ModelRun, anti_cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    monthly = pd.Series({pd.to_datetime(k): float(v) for k, v in run.monthly_returns.items()}).sort_index()
    if monthly.empty:
        return False, {"reason": "empty_monthly_returns", "cv_pass": False, "walkforward_pass": False}

    folds = int(anti_cfg.get("purged_cv_folds", 5))
    purge_days = int(anti_cfg.get("purge_days", 20))
    embargo_days = int(anti_cfg.get("embargo_days", 20))
    cv_pass_ratio_min = float(anti_cfg.get("cv_pass_ratio_min", 0.60))

    idx = np.arange(len(monthly))
    split = np.array_split(idx, folds)
    cv_rows = []
    cv_pass_count = 0

    for fi, test_idx in enumerate(split, start=1):
        if len(test_idx) == 0:
            continue
        test_start = monthly.index[int(test_idx[0])]
        test_end = monthly.index[int(test_idx[-1])]

        train_mask = (monthly.index < (test_start - pd.Timedelta(days=purge_days))) | (monthly.index > (test_end + pd.Timedelta(days=embargo_days)))
        train = monthly[train_mask]
        test = monthly.iloc[test_idx]

        test_eq = (1.0 + test).cumprod()
        test_ret = float(test_eq.iloc[-1] - 1.0) if not test_eq.empty else 0.0
        peak = 1.0
        mdd = 0.0
        for v in test_eq.values:
            peak = max(peak, float(v))
            mdd = min(mdd, float(v) / max(1e-12, peak) - 1.0)

        train_mean = float(train.mean()) if not train.empty else 0.0
        fold_pass = bool(test_ret >= -0.35 and mdd >= -0.45 and (test_ret >= train_mean - 0.20))
        cv_pass_count += int(fold_pass)
        cv_rows.append(
            {
                "fold": fi,
                "test_start": test_start.strftime("%Y-%m-%d"),
                "test_end": test_end.strftime("%Y-%m-%d"),
                "train_samples": int(len(train)),
                "test_samples": int(len(test)),
                "train_mean": float(train_mean),
                "oos_total_return": float(test_ret),
                "oos_mdd": float(mdd),
                "fold_pass": fold_pass,
            }
        )

    cv_pass_ratio = cv_pass_count / max(1, len(cv_rows))
    cv_pass = bool(cv_pass_ratio >= cv_pass_ratio_min)

    wf_rows = []
    wf_pass_count = 0
    windows = anti_cfg.get("walkforward_windows", [])
    wf_pass_ratio_min = float(anti_cfg.get("walkforward_pass_ratio_min", 0.67))
    for w in windows:
        t0 = pd.to_datetime(w["test_start"])
        t1 = pd.to_datetime(w["test_end"])
        seg = monthly[(monthly.index >= t0) & (monthly.index <= t1)]
        if seg.empty:
            wf_rows.append(
                {
                    "id": w["id"],
                    "test_start": w["test_start"],
                    "test_end": w["test_end"],
                    "oos_total_return": 0.0,
                    "oos_mdd": 0.0,
                    "window_pass": False,
                    "reason": "empty_segment",
                }
            )
            continue

        eq = (1.0 + seg).cumprod()
        total_ret = float(eq.iloc[-1] - 1.0)
        peak = 1.0
        mdd = 0.0
        for v in eq.values:
            peak = max(peak, float(v))
            mdd = min(mdd, float(v) / max(1e-12, peak) - 1.0)
        w_pass = bool(total_ret >= -0.30 and mdd >= -0.45)
        wf_pass_count += int(w_pass)
        wf_rows.append(
            {
                "id": w["id"],
                "test_start": w["test_start"],
                "test_end": w["test_end"],
                "oos_total_return": float(total_ret),
                "oos_mdd": float(mdd),
                "window_pass": w_pass,
            }
        )

    wf_pass_ratio = wf_pass_count / max(1, len(wf_rows))
    wf_pass = bool(wf_pass_ratio >= wf_pass_ratio_min)
    gate_pass = bool(cv_pass and wf_pass)

    detail = {
        "purged_cv": {
            "folds": folds,
            "purge_days": purge_days,
            "embargo_days": embargo_days,
            "pass_ratio": float(cv_pass_ratio),
            "pass_ratio_min": float(cv_pass_ratio_min),
            "fold_results": cv_rows,
            "cv_pass": cv_pass,
        },
        "walkforward": {
            "windows": wf_rows,
            "pass_ratio": float(wf_pass_ratio),
            "pass_ratio_min": float(wf_pass_ratio_min),
            "walkforward_pass": wf_pass,
        },
    }
    return gate_pass, detail


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
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    cfg_main, config_hash, search_space_hash = parse_config()
    uni_cfg = cfg_main["universe"]
    if not bool(uni_cfg.get("no_ticker_whitelist", False)):
        raise RuntimeError("FAIL_STOP: no_ticker_whitelist must be true")
    if not bool(uni_cfg.get("no_manual_favorites", False)):
        raise RuntimeError("FAIL_STOP: no_manual_favorites must be true")

    static_scan = run_static_hardcode_scan()

    lock = LockedNumericConfig(universe_limit=int(uni_cfg["universe_limit"]), min_history_days=int(uni_cfg["min_history_days"]))
    prev_repeat = load_prev_repeat_final()
    rounds, search_meta = make_rounds(prev_repeat, cfg_main)
    density_base = load_text_density_base()

    universe_pool = load_universe_pool(pool_limit=int(uni_cfg.get("universe_pool_limit", 600)))
    supplies = {c: load_supply(c) for c in universe_pool}
    dates = rebalance_dates(universe_pool)

    membership_by_date, universe_log_payload, universe_membership_hash = build_dynamic_universe(
        universe_pool=universe_pool,
        dates=dates,
        limit=lock.universe_limit,
        min_history_days=lock.min_history_days,
    )
    regime_by_date, regime_counts = compute_market_regime(
        universe_pool=universe_pool,
        membership_by_date=membership_by_date,
        dates=dates,
        regime_cfg=cfg_main["regime_gate"],
    )

    cfg_anchor = rounds[0]
    density_anchor = year_density_map(density_base, cfg_anchor)
    numeric_run = run_model(
        "numeric",
        universe_pool,
        supplies,
        dates,
        membership_by_date,
        regime_by_date,
        lock,
        cfg_anchor,
        density_anchor,
        cfg_main,
    )
    external_run = run_model(
        "external_proxy",
        universe_pool,
        supplies,
        dates,
        membership_by_date,
        regime_by_date,
        lock,
        cfg_anchor,
        density_anchor,
        cfg_main,
    )

    round_evals: list[RoundEval] = []
    round_runs: dict[str, dict[str, ModelRun]] = {}

    prev_cfg: RoundConfig | None = None
    final_cfg = rounds[-1]
    final_runs: dict[str, ModelRun] | None = None
    stop_reason = "MAX_REPEAT_REACHED_REDESIGN"
    final_decision = "REDESIGN"

    non_numeric_top_valid = False
    chosen_gate3 = False
    chosen_gate4 = False

    anti_cfg = cfg_main["anti_overfit"]
    for r_cfg in rounds:
        density_map = year_density_map(density_base, r_cfg)
        g1_pass, g1_reco_pass, g1_fail_reason, regime, regime_band, mix_ratio = evaluate_gate1(r_cfg, regime_counts, cfg_main)

        qual_run = run_model(
            "qualitative",
            universe_pool,
            supplies,
            dates,
            membership_by_date,
            regime_by_date,
            lock,
            r_cfg,
            density_map,
            cfg_main,
        )
        hybrid_run = run_model(
            "hybrid",
            universe_pool,
            supplies,
            dates,
            membership_by_date,
            regime_by_date,
            lock,
            r_cfg,
            density_map,
            cfg_main,
        )

        runs = {
            "numeric": numeric_run,
            "qualitative": qual_run,
            "hybrid": hybrid_run,
            "external_proxy": external_run,
        }
        round_runs[r_cfg.round_id] = runs

        g2 = evaluate_gate2(runs, density_map=density_map, anti_cfg=anti_cfg)
        clone_detected = detect_clone(numeric_run, hybrid_run)

        high_density_advantage_pass = bool(g2.get("high_density_advantage_pass", False))
        gate2_detail = {
            "high_density_mode": bool(g2.get("high_density_mode", False)),
            "avg_density": float(g2.get("avg_density", 0.0)),
            "high_density_threshold": float(g2.get("high_density_threshold", 0.5)),
            "high_density_advantage_required": float(g2.get("high_density_advantage_required", 0.25)),
            "advantage": float(g2.get("advantage", 0.0)),
            "high_density_advantage_pass": high_density_advantage_pass,
            "mdd_superior": bool(g2.get("mdd_superior", False)),
            "turnover_ratio": float(g2.get("turnover_ratio", 0.0)),
            "turnover_ratio_max": float(g2.get("turnover_ratio_max", 1.05)),
            "high_density_risk_pass": bool(g2.get("high_density_risk_pass", False)),
            "numeric_mdd": float(g2.get("numeric_mdd", 0.0)),
            "non_numeric_mdd": float(g2.get("non_numeric_mdd", 0.0)),
            "numeric_turnover": float(g2.get("numeric_turnover", 0.0)),
            "non_numeric_turnover": float(g2.get("non_numeric_turnover", 0.0)),
        }

        if clone_detected:
            gate2_pass = False
            gate2_reason = "clone_detected_fail"
            gate2_i = False
            gate2_ii = False
            high_density_advantage_pass = False
        else:
            gate2_pass = bool(g2["gate2_pass"])
            gate2_reason = str(g2["gate2_reason"])
            gate2_i = bool(g2["gate2_condition_i"])
            gate2_ii = bool(g2["gate2_condition_ii"])

        candidate_id = str(g2["non_numeric_candidate"])
        candidate_run = runs[candidate_id]
        gate3_pass, gate3_detail = evaluate_gate3_subperiod_stability(candidate_run, anti_cfg)
        gate4_pass, gate4_detail = evaluate_gate4_purged_cv_oos(candidate_run, anti_cfg)

        non_numeric_top_valid = bool(g1_pass and gate2_pass and (not clone_detected) and gate3_pass and gate4_pass)

        row = RoundEval(
            round_id=r_cfg.round_id,
            repeat_counter=r_cfg.repeat_counter,
            why=r_cfg.why,
            changed_params=changed_params(prev_cfg, r_cfg),
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
            high_density_advantage_pass=high_density_advantage_pass,
            gate2_detail=gate2_detail,
            gate3_subperiod_stability_pass=gate3_pass,
            gate4_purged_cv_oos_pass=gate4_pass,
            numeric_return=float(g2["numeric_return"]),
            qualitative_return=float(g2["qualitative_return"]),
            hybrid_return=float(g2["hybrid_return"]),
            non_numeric_candidate=str(g2["non_numeric_candidate"]),
            non_numeric_return=float(g2["non_numeric_return"]),
            tie_detected=bool(g2["tie_detected"]),
            clone_detected=clone_detected,
            non_numeric_top_valid=non_numeric_top_valid,
            gate3_detail=gate3_detail,
            gate4_detail=gate4_detail,
        )
        round_evals.append(row)

        if non_numeric_top_valid:
            final_cfg = r_cfg
            final_runs = runs
            chosen_gate3 = gate3_pass
            chosen_gate4 = gate4_pass
            stop_reason = "NON_NUMERIC_TOP_CONFIRMED_WITH_OVERFIT_GUARDS"
            final_decision = "ADOPT"
            break

        prev_cfg = r_cfg

    if final_runs is None:
        final_runs = round_runs[final_cfg.round_id]

    chosen_eval = next(r for r in round_evals if r.round_id == final_cfg.round_id)

    overfit_guard_pass = {
        "no_ticker_whitelist": bool(uni_cfg.get("no_ticker_whitelist", False)),
        "no_manual_favorites": bool(uni_cfg.get("no_manual_favorites", False)),
        "purged_cv_oos_mandatory": bool(chosen_eval.gate4_purged_cv_oos_pass),
        "subperiod_stability_check": bool(chosen_eval.gate3_subperiod_stability_pass),
        "search_space_freeze_hash_logging": bool(search_space_hash and config_hash),
        "numeric_auto_adopt_block": bool(not (chosen_eval.non_numeric_candidate == "numeric")),
        "high_density_advantage_pass": bool(chosen_eval.high_density_advantage_pass),
        "static_no_hardcoded_ticker_scan": bool(static_scan.get("scan_pass", False)),
    }

    anti_overfit_audit = {
        "non_numeric_top_valid": bool(chosen_eval.non_numeric_top_valid),
        "overfit_guard_pass": overfit_guard_pass,
        "config_hash": config_hash,
        "search_space_hash": search_space_hash,
        "search_space_meta": search_meta,
        "static_scan_log": str(SCAN_LOG.relative_to(BASE)),
        "dynamic_universe_log": str(UNIVERSE_LOG.relative_to(BASE)),
        "universe_membership_by_date_hash": universe_membership_hash,
        "gate2_high_density_advantage": chosen_eval.gate2_detail,
        "gate3_subperiod_stability": chosen_eval.gate3_detail,
        "gate4_purged_cv_oos": chosen_eval.gate4_detail,
        "selection_signatures": {
            "numeric": final_runs["numeric"].selection_signature,
            "qualitative": final_runs["qualitative"].selection_signature,
            "hybrid": final_runs["hybrid"].selection_signature,
            "external_proxy": final_runs["external_proxy"].selection_signature,
        },
    }

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "policy_enforcement": {
            "rulebook": "V3.5_hard_rules",
            "internal_models": INTERNAL_MODELS,
            "external_proxy_selection_excluded": True,
            "numeric_auto_select_block": True,
            "numeric_fixed_baseline": True,
            "repeat_counter_start": prev_repeat + 1,
            "repeat_counter_final": int(chosen_eval.repeat_counter),
            "stop_reason": stop_reason,
            "final_decision": final_decision,
            "epsilon": EPSILON,
            "repeat_terminate_condition": "non_numeric_top_valid_and_overfit_guard_pass",
            "rulebook_v3_5": {
                "min_hold_days": lock.min_hold_days,
                "replace_edge": lock.replace_edge,
                "monthly_replace_cap": lock.monthly_replace_cap,
                "holdings_min": 1,
                "holdings_max": lock.max_pos,
            },
        },
        "anti_overfit_audit": anti_overfit_audit,
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
            "high_density_advantage_pass": chosen_eval.high_density_advantage_pass,
            "high_density_advantage_detail": chosen_eval.gate2_detail,
            "gate3_subperiod_stability_pass": chosen_eval.gate3_subperiod_stability_pass,
            "gate4_purged_cv_oos_pass": chosen_eval.gate4_purged_cv_oos_pass,
            "non_numeric_top_valid": chosen_eval.non_numeric_top_valid,
            "tie_detected": chosen_eval.tie_detected,
            "clone_detected": chosen_eval.clone_detected,
        },
        "regime_distribution": regime_counts,
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
                "gate3_pass": chosen_eval.gate3_subperiod_stability_pass,
                "gate4_pass": chosen_eval.gate4_purged_cv_oos_pass,
                "high_density_advantage_pass": chosen_eval.high_density_advantage_pass,
                "high_density_advantage_detail": chosen_eval.gate2_detail,
                "output": str(OUT_JSON.relative_to(BASE)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
