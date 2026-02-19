#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW_KR = BASE / "data/raw/kr"
OHLCV_DIR = RAW_KR / "ohlcv"
SUPPLY_DIR = RAW_KR / "supply"
VALIDATED = BASE / "results/validated"
REPORTS = BASE / "reports/stage_updates"
STAGE05_REPORTS = REPORTS / "stage05"

OUT_JSON = VALIDATED / "stage05_baselines_3x3_v3_9_kr.json"
DESIGN_MD = STAGE05_REPORTS / "stage05_3x3_design_v3_9_kr.md"
RESULT_MD = STAGE05_REPORTS / "stage05_3x3_result_v3_9_kr.md"

VERSION = "v3_9_kr"
INTERNAL_TRACKS = ("numeric", "qualitative", "hybrid")
US_TICKERS = re.compile(r"\b(AAPL|NVDA|TSLA|MSFT|AMZN|GOOG|META)\b")

BASE_PARAMS: dict[str, Any] = {
    "universe_limit": 120,
    "max_pos": 6,  # RULEBOOK: 1~6
    "ret_short": 10,
    "ret_mid": 40,
    "trend_fast": 8,
    "trend_slow": 36,
    "flow_scale": 120_000_000.0,
    "quant_trend_w": 0.70,
    "quant_flow_w": 0.30,
    "qual_buzz_w": 0.72,
    "qual_ret_w": 0.18,
    "qual_up_w": 0.10,
    "buzz_window": 60,
    "up_window": 20,
    "hybrid_quant_w": 0.58,
    "hybrid_qual_w": 0.32,
    "hybrid_agree_w": 0.10,
    "min_hold_days": 20,
    "replace_edge": 0.15,
    "monthly_replace_cap": 0.30,
    "trailing_stop_pct": -0.20,
    "fee": 0.003,
}


@dataclass
class VariantSpec:
    model_id: str
    track: str
    score_model: str
    changed_params: dict[str, Any]
    why: str
    expected_risk: str


VARIANTS: list[VariantSpec] = [
    VariantSpec(
        model_id="numeric_n1_horizon_fast",
        track="numeric",
        score_model="numeric",
        changed_params={"ret_short": 8, "ret_mid": 32, "trend_fast": 6, "trend_slow": 28},
        why="단기/중기 모멘텀 및 추세 span 단축으로 가격 반응 민감도 측정",
        expected_risk="횡보 구간에서 신호 과민 반응(whipsaw) 가능",
    ),
    VariantSpec(
        model_id="numeric_n2_flow_tilt",
        track="numeric",
        score_model="numeric",
        changed_params={"flow_scale": 80_000_000.0, "quant_trend_w": 0.55, "quant_flow_w": 0.45},
        why="수급(flow) 영향도 확대 시 성과 변화 확인",
        expected_risk="수급 데이터 노이즈에 의한 과적합 가능",
    ),
    VariantSpec(
        model_id="numeric_n3_fee_stress",
        track="numeric",
        score_model="numeric",
        changed_params={"fee": 0.0045},
        why="거래비용 민감도(수수료+슬리피지 스트레스) 측정",
        expected_risk="고회전 구간에서 수익 급감 가능",
    ),
    VariantSpec(
        model_id="qual_q1_buzz_heavy",
        track="qualitative",
        score_model="qualitative",
        changed_params={"qual_buzz_w": 0.84, "qual_ret_w": 0.12, "qual_up_w": 0.04, "buzz_window": 40},
        why="buzz 중심 정성 점수 강화 시 성과/변동성 영향 확인",
        expected_risk="이슈 급등주 쏠림으로 drawdown 확대 가능",
    ),
    VariantSpec(
        model_id="qual_q2_ret_up_mix",
        track="qualitative",
        score_model="qualitative",
        changed_params={"qual_buzz_w": 0.56, "qual_ret_w": 0.24, "qual_up_w": 0.20, "up_window": 15},
        why="ret_short + 상승일 비율(up_ratio) 혼합 시 지속성 측정",
        expected_risk="모멘텀 둔화 시 급격한 성과 저하 가능",
    ),
    VariantSpec(
        model_id="qual_q3_fee_stress",
        track="qualitative",
        score_model="qualitative",
        changed_params={"fee": 0.0045},
        why="정성 트랙의 거래비용 내구성 측정",
        expected_risk="정성 신호 고빈도 구간에서 turnover 비용 증가",
    ),
    VariantSpec(
        model_id="hybrid_h1_quant_tilt",
        track="hybrid",
        score_model="hybrid",
        changed_params={"hybrid_quant_w": 0.70, "hybrid_qual_w": 0.20, "hybrid_agree_w": 0.10},
        why="hybrid 내 정량 비중 확대로 수익/리스크 변화 확인",
        expected_risk="정성 이벤트 반응 둔화 가능",
    ),
    VariantSpec(
        model_id="hybrid_h2_consensus_tilt",
        track="hybrid",
        score_model="hybrid",
        changed_params={"hybrid_quant_w": 0.50, "hybrid_agree_w": 0.26},
        why="합의항(min term) 비중 증가 + 정량축 완만 조정으로 보수적 합의형 효과 측정",
        expected_risk="신호 엄격화로 기회 손실 가능",
    ),
    VariantSpec(
        model_id="hybrid_h3_fee_stress",
        track="hybrid",
        score_model="hybrid",
        changed_params={"fee": 0.0045},
        why="하이브리드 트랙 거래비용 민감도 측정",
        expected_risk="혼합신호 고회전 시 비용 누적",
    ),
]


def pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def guard_kr_only() -> None:
    if not OHLCV_DIR.exists() or not SUPPLY_DIR.exists():
        raise RuntimeError("FAIL: required KRX raw path missing")

    bad = []
    for fp in list(OHLCV_DIR.glob("*.csv"))[:4000]:
        if US_TICKERS.search(fp.stem.upper()):
            bad.append(fp.name)
    if bad:
        raise RuntimeError(f"FAIL: US ticker pattern detected: {bad[:5]}")


def annual_stats_from_curve(eq: pd.Series) -> tuple[dict[int, float], dict[str, float]]:
    eq = eq.sort_index()
    running_peak = eq.cummax()
    mdd = float((eq / running_peak - 1.0).min()) if len(eq) else 0.0

    annual: dict[int, float] = {}
    for y, ys in eq.groupby(eq.index.year):
        if y < 2016:
            continue
        annual[int(y)] = float(ys.iloc[-1] / ys.iloc[0] - 1.0) if len(ys) > 1 else 0.0

    if len(eq) >= 2 and eq.iloc[0] > 0:
        total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
        years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
        cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
        asset_multiple = float(eq.iloc[-1] / eq.iloc[0])
    else:
        total_return, cagr, asset_multiple = 0.0, 0.0, 1.0

    return annual, {
        "total_return": total_return,
        "asset_multiple": asset_multiple,
        "mdd": mdd,
        "cagr": cagr,
    }


def normalize_weights(score_map: dict[str, float]) -> dict[str, float]:
    if not score_map:
        return {}
    values = np.array(list(score_map.values()), dtype=float)
    min_v = float(values.min())
    # 강제 epsilon(+1e-6)으로 모든 종목에 극소 비중이 배정되는 현상 제거
    shifted = {k: max(float(v - min_v), 0.0) for k, v in score_map.items()}
    total = sum(shifted.values())
    if total <= 0:
        n = len(score_map)
        return {k: 1.0 / n for k in score_map}
    return {k: v / total for k, v in shifted.items() if v > 0}


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


def calc_scores(
    d: pd.Timestamp,
    px: pd.DataFrame,
    sp: pd.DataFrame | None,
    p: dict[str, Any],
) -> dict[str, float] | None:
    h = px.loc[:d]
    min_hist = max(
        130,
        int(p["trend_slow"]) + 5,
        int(p["ret_mid"]) + 5,
        int(p["buzz_window"]) + 5,
        int(p["up_window"]) + 5,
    )
    if len(h) < min_hist:
        return None

    c = h["Close"]
    v = h["Volume"].fillna(0)

    ret_s = float(c.pct_change(int(p["ret_short"])).iloc[-1])
    ret_m = float(c.pct_change(int(p["ret_mid"])).iloc[-1])

    ma_f = float(c.ewm(span=int(p["trend_fast"])).mean().iloc[-1])
    ma_s = float(c.ewm(span=int(p["trend_slow"])).mean().iloc[-1])
    ma120 = float(c.rolling(120).mean().iloc[-1])

    trend = 0.6 * float(ma_f > ma_s) + 0.4 * float(ma_s > ma120)
    trend += 0.5 * (0.0 if math.isnan(ret_m) else ret_m)

    flow = 0.0
    if sp is not None:
        sh = sp.loc[:d]
        if len(sh) > 20:
            val = (
                sh["기관합계"].rolling(20).mean().iloc[-1]
                + sh["외국인합계"].rolling(20).mean().iloc[-1]
            ) / float(p["flow_scale"])
            flow = float(np.tanh(val))

    quant = float(p["quant_trend_w"]) * trend + float(p["quant_flow_w"]) * flow

    buzz = float(v.iloc[-1] / (v.rolling(int(p["buzz_window"])).mean().iloc[-1] + 1e-9))
    up_ratio = float(c.pct_change().tail(int(p["up_window"])).gt(0.02).mean())
    qual = (
        float(p["qual_buzz_w"]) * np.tanh(buzz - 1.0)
        + float(p["qual_ret_w"]) * (0.0 if math.isnan(ret_s) else ret_s)
        + float(p["qual_up_w"]) * up_ratio
    )

    agree = min(quant, qual)
    hybrid = (
        float(p["hybrid_quant_w"]) * quant
        + float(p["hybrid_qual_w"]) * qual
        + float(p["hybrid_agree_w"]) * agree
    )

    external_proxy = 0.6 * (ma_f / (ma_s + 1e-9) - 1.0) + 0.4 * (0.0 if math.isnan(ret_s) else ret_s)

    return {
        "numeric": float(quant),
        "qualitative": float(qual),
        "hybrid": float(hybrid),
        "external_proxy": float(external_proxy),
    }


def run_variant(
    spec: VariantSpec,
    universe: dict[str, pd.DataFrame],
    supplies: dict[str, pd.DataFrame | None],
    dates: list[pd.Timestamp],
) -> dict[str, Any]:
    p = dict(BASE_PARAMS)
    p.update(spec.changed_params)

    cash = 1.0
    holdings: dict[str, dict[str, Any]] = {}
    eq_curve: list[tuple[pd.Timestamp, float]] = []

    trade_count = 0
    replacement_count = 0
    trailing_stop_count = 0
    buy_notional = 0.0
    sell_notional = 0.0

    reasons = {"replacement": 0, "trailing_stop": 0, "final_liquidation": 0}

    def sell_position(code: str, date: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal cash, trade_count, sell_notional
        if code not in holdings:
            return
        pos = holdings.pop(code)
        gross = pos["shares"] * price
        fee = gross * float(p["fee"])
        cash += gross - fee
        sell_notional += gross
        trade_count += 1
        reasons[reason] = reasons.get(reason, 0) + 1

    for d in dates:
        px_now: dict[str, float] = {}
        score_by_code: dict[str, float] = {}

        for code, df in universe.items():
            h = df.loc[:d]
            if h.empty:
                continue
            px_now[code] = float(h["Close"].iloc[-1])
            score_pack = calc_scores(d, df, supplies.get(code), p)
            if score_pack is None:
                continue
            score_by_code[code] = float(score_pack[spec.score_model])

        if not score_by_code:
            total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
            eq_curve.append((d, total))
            continue

        # Rulebook Trend-Trailing: -20%
        for code in list(holdings.keys()):
            if code not in px_now:
                continue
            current_price = float(px_now[code])
            holdings[code]["peak_price"] = max(float(holdings[code]["peak_price"]), current_price)
            peak = float(holdings[code]["peak_price"])
            drawdown = (current_price / peak) - 1.0 if peak > 0 else 0.0
            if drawdown <= float(p["trailing_stop_pct"]):
                sell_position(code, d, current_price, reason="trailing_stop")
                trailing_stop_count += 1

        ranked = sorted(score_by_code.items(), key=lambda x: x[1], reverse=True)
        top = ranked[: int(p["max_pos"])]
        top_set = {c for c, _ in top}

        # Rulebook Low-turnover replacement guard
        n_hold = len(holdings)
        replace_cap = int(math.floor(n_hold * float(p["monthly_replace_cap"]))) if n_hold > 0 else 0

        challengers = [(c, s) for c, s in top if c not in holdings]
        chosen_challengers: set[str] = set()
        to_replace: list[tuple[str, str]] = []

        for code in sorted([c for c in holdings.keys() if c not in top_set], key=lambda x: score_by_code.get(x, -999.0)):
            if len(to_replace) >= replace_cap:
                break
            held_days = int((d - holdings[code]["buy_date"]).days)
            if held_days < int(p["min_hold_days"]):
                continue

            incumbent = score_by_code.get(code, -999.0)
            eligible = [
                (cc, ss)
                for cc, ss in challengers
                if cc not in chosen_challengers and ss >= incumbent + float(p["replace_edge"])
            ]
            if not eligible:
                continue
            challenger = sorted(eligible, key=lambda x: x[1], reverse=True)[0][0]
            chosen_challengers.add(challenger)
            to_replace.append((code, challenger))

        for old_code, _ in to_replace:
            if old_code in px_now:
                sell_position(old_code, d, float(px_now[old_code]), reason="replacement")
                replacement_count += 1

        # Buy new positions with score-proportional weights (no equal weight)
        slots_left = max(int(p["max_pos"]) - len(holdings), 0)
        buy_candidates = [c for c, _ in top if c not in holdings][:slots_left]

        buy_scores = {c: score_by_code[c] for c in buy_candidates}
        weights = normalize_weights(buy_scores)

        start_cash = cash
        for c in buy_candidates:
            if c not in px_now:
                continue
            buy_cash = start_cash * weights.get(c, 0.0)
            buy_cash = min(buy_cash, cash)
            if buy_cash <= 0:
                continue
            price = float(px_now[c])
            fee = buy_cash * float(p["fee"])
            net = buy_cash - fee
            shares = net / price if price > 0 else 0.0
            if shares <= 0:
                continue

            cash -= buy_cash
            holdings[c] = {
                "shares": shares,
                "buy_price": price,
                "buy_date": d,
                "peak_price": price,
            }
            buy_notional += buy_cash
            trade_count += 1

        total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
        eq_curve.append((d, total))

    if eq_curve:
        d = eq_curve[-1][0]
        px_now = {c: float(df.loc[:d]["Close"].iloc[-1]) for c, df in universe.items() if not df.loc[:d].empty}
        for c in list(holdings.keys()):
            if c in px_now:
                sell_position(c, d, float(px_now[c]), reason="final_liquidation")

    eq = pd.Series({d: v for d, v in eq_curve}).sort_index()
    annual, stats = annual_stats_from_curve(eq)

    avg_eq = float(eq.mean()) if len(eq) else 1.0
    years = max(len(annual), 1)
    turnover_proxy = float((buy_notional + sell_notional) / (avg_eq * years + 1e-9))

    return {
        "model_id": spec.model_id,
        "track": spec.track,
        "score_model": spec.score_model,
        "changed_params": spec.changed_params,
        "why": spec.why,
        "expected_risk": spec.expected_risk,
        "effective_params": p,
        "annual_returns": annual,
        "stats": {
            **stats,
            "turnover_proxy": turnover_proxy,
            "trade_count": trade_count,
            "replacement_count": replacement_count,
            "trailing_stop_count": trailing_stop_count,
        },
        "reason_counts": reasons,
    }


def run_external_proxy(
    universe: dict[str, pd.DataFrame],
    supplies: dict[str, pd.DataFrame | None],
    dates: list[pd.Timestamp],
) -> dict[str, Any]:
    spec = VariantSpec(
        model_id="external_proxy_ref",
        track="comparison",
        score_model="external_proxy",
        changed_params={},
        why="external proxy comparison only",
        expected_risk="selection exclusion model",
    )
    return run_variant(spec, universe, supplies, dates)


def pick_best(models: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        models,
        key=lambda x: (
            float(x["stats"]["total_return"]),
            float(x["stats"]["mdd"]),
        ),
        reverse=True,
    )
    return ranked[0]


def sensitivity_summary(internal_models: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for m in internal_models:
        r = {
            "model_id": m["model_id"],
            "track": m["track"],
            "ret_short": float(m["effective_params"]["ret_short"]),
            "ret_mid": float(m["effective_params"]["ret_mid"]),
            "flow_scale": float(m["effective_params"]["flow_scale"]),
            "trend_fast": float(m["effective_params"]["trend_fast"]),
            "trend_slow": float(m["effective_params"]["trend_slow"]),
            "qual_buzz_w": float(m["effective_params"]["qual_buzz_w"]),
            "fee": float(m["effective_params"]["fee"]),
            "total_return": float(m["stats"]["total_return"]),
        }
        rows.append(r)
    df = pd.DataFrame(rows)

    def corr_of(col: str) -> float | None:
        if col not in df.columns:
            return None
        if df[col].nunique() <= 1:
            return None
        return float(df[[col, "total_return"]].corr().iloc[0, 1])

    fee_grp = df.groupby("fee")["total_return"].mean().to_dict()
    fee_impact = None
    if len(fee_grp) >= 2:
        vals = sorted((float(k), float(v)) for k, v in fee_grp.items())
        fee_impact = {
            "low_fee": {"fee": vals[0][0], "avg_return": vals[0][1]},
            "high_fee": {"fee": vals[-1][0], "avg_return": vals[-1][1]},
            "delta_high_minus_low": vals[-1][1] - vals[0][1],
        }

    return {
        "measurement_points": [
            "ret_short/ret_mid",
            "qual_buzz_w",
            "flow_scale",
            "trend_fast/trend_slow",
            "fee",
        ],
        "correlations": {
            "ret_short": corr_of("ret_short"),
            "ret_mid": corr_of("ret_mid"),
            "qual_buzz_w": corr_of("qual_buzz_w"),
            "flow_scale": corr_of("flow_scale"),
            "trend_fast": corr_of("trend_fast"),
            "trend_slow": corr_of("trend_slow"),
            "fee": corr_of("fee"),
        },
        "fee_sensitivity": fee_impact,
    }


def ensure_variant_distinctness() -> None:
    by_track: dict[str, list[VariantSpec]] = {}
    for v in VARIANTS:
        by_track.setdefault(v.track, []).append(v)

    for track, variants in by_track.items():
        if len(variants) != 3:
            raise RuntimeError(f"FAIL: {track} variant count != 3")
        sigs = [tuple(sorted(v.changed_params.keys())) for v in variants]
        if len(set(sigs)) != len(sigs):
            raise RuntimeError(f"FAIL: ping-pong detected in {track}, changed_params keys overlap identically")


def write_design_report() -> None:
    lines = [
        "# stage05_3x3_design_v3_9_kr",
        "",
        "## inputs",
        "- RULEBOOK V3.4 고정 제약: 보유1~6, 최소보유20일, 교체+15%, 월교체30%",
        "- KRX raw data: invest/data/raw/kr/ohlcv/*.csv, invest/data/raw/kr/supply/*_supply.csv",
        "- 내부 모델 9개(3x3) + external_proxy 비교군 1개",
        "",
        "## run_command(or process)",
        "- `python3 invest/scripts/stage05_3x3_v3_9_kr.py`",
        "",
        "## outputs",
        f"- {OUT_JSON}",
        f"- {DESIGN_MD}",
        f"- {RESULT_MD}",
        "",
        "## quality_gates",
        "- KRX only guard pass (US ticker/path reject)",
        "- RULEBOOK V3.4 핵심 가드 고정 (보유1~6, 최소보유20일, 교체+15%, 월교체30%)",
        "- external_proxy는 비교군 전용(선발 제외)",
        "- track별 3개 changed_params 명확 구분(핑퐁 금지)",
        "",
        "## failure_policy",
        "- KRX guard fail 또는 track별 3개 구성 위반 시 즉시 FAIL_STOP",
        "- internal 3000% gate 미충족 시 Stage06 진입 금지",
        "",
        "## proof",
        f"- {BASE / 'invest/scripts/stage05_3x3_v3_9_kr.py'}",
        "",
        "## Stage05-3x3 모델 설계",
        "| track | model_id | changed_params | why | expected_risk |",
        "|---|---|---|---|---|",
    ]

    for v in VARIANTS:
        cp = ", ".join(f"{k}={v.changed_params[k]}" for k in sorted(v.changed_params))
        lines.append(f"| {v.track} | {v.model_id} | {cp} | {v.why} | {v.expected_risk} |")

    lines += [
        "",
        "## 변수 민감도 측정 포인트",
        "- ret_short / ret_mid",
        "- qual_buzz_w",
        "- flow_scale",
        "- trend_fast / trend_slow",
        "- fee sensitivity",
    ]

    DESIGN_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_result_report(payload: dict[str, Any]) -> None:
    internal_models = payload["models"]
    by_track = {t: [m for m in internal_models if m["track"] == t] for t in INTERNAL_TRACKS}

    lines = [
        "# stage05_3x3_result_v3_9_kr",
        "",
        "## inputs",
        "- KRX OHLCV + supply",
        "- model_matrix: numeric3 / qualitative3 / hybrid3",
        "",
        "## run_command(or process)",
        "- `python3 invest/scripts/stage05_3x3_v3_9_kr.py`",
        "",
        "## outputs",
        f"- {OUT_JSON}",
        f"- {RESULT_MD}",
        "",
        "## quality_gates",
        f"- result_grade=VALIDATED: {payload['result_grade']}",
        f"- scope=KRX_ONLY: {payload['scope']}",
        f"- external_proxy_selection_excluded: {payload['policy_enforcement']['external_proxy_selection_excluded']}",
        f"- track_variant_3x3_distinct: {payload['policy_enforcement']['track_variant_3x3_distinct']}",
        f"- internal_3000_gate_pass: {payload['internal_3000_gate_pass']}",
        "",
        "## failure_policy",
        "- internal_3000_gate_pass=false -> Stage06 진입 금지",
        "- 비교군(external_proxy) 성과는 선발 기준에서 제외",
        "",
        "## proof",
        f"- {OUT_JSON}",
        f"- {BASE / 'invest/scripts/stage05_3x3_v3_9_kr.py'}",
        "",
        "## 모델별 성과표",
        "| model_id | track | cumulative_return | MDD | CAGR | turnover_proxy |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for m in internal_models:
        st = m["stats"]
        lines.append(
            f"| {m['model_id']} | {m['track']} | {pct(st['total_return'])} | {pct(st['mdd'])} | {pct(st['cagr'])} | {st['turnover_proxy']:.3f} |"
        )

    lines += [
        "",
        "## track별 best",
        f"- numeric_best: {payload['numeric_best']['model_id']} ({pct(payload['numeric_best']['stats']['total_return'])})",
        f"- qualitative_best: {payload['qualitative_best']['model_id']} ({pct(payload['qualitative_best']['stats']['total_return'])})",
        f"- hybrid_best: {payload['hybrid_best']['model_id']} ({pct(payload['hybrid_best']['stats']['total_return'])})",
        f"- overall_best: {payload['overall_best']['model_id']} ({pct(payload['overall_best']['stats']['total_return'])})",
        "",
        "## 변수 영향도 요약",
    ]

    sens = payload["sensitivity_summary"]
    corrs = sens["correlations"]
    for k in ["ret_short", "ret_mid", "qual_buzz_w", "flow_scale", "trend_fast", "trend_slow", "fee"]:
        v = corrs.get(k)
        lines.append(f"- corr({k}, total_return): {'N/A' if v is None else f'{v:.4f}'}")

    fee_sens = sens.get("fee_sensitivity")
    if fee_sens:
        lines.append(
            f"- fee sensitivity: high_fee({fee_sens['high_fee']['fee']}) - low_fee({fee_sens['low_fee']['fee']}) = {pct(fee_sens['delta_high_minus_low'])}"
        )

    ext = payload["comparison_model_external_proxy"]
    lines += [
        "",
        "## external_proxy (비교군 전용)",
        f"- model_id: {ext['model_id']}",
        f"- cumulative_return: {pct(ext['stats']['total_return'])}",
        f"- selection_used: false",
        "",
        "## required fields",
        f"- numeric_best: {payload['numeric_best']['model_id']}",
        f"- qualitative_best: {payload['qualitative_best']['model_id']}",
        f"- hybrid_best: {payload['hybrid_best']['model_id']}",
        f"- overall_best: {payload['overall_best']['model_id']}",
        f"- internal_3000_gate_pass: {payload['internal_3000_gate_pass']}",
        "",
        "## next (Stage06 진입안)",
        "- 3x3 결과의 track별 best 3개를 seed로 사용",
        "- seed별로 ret_horizon / flow / fee 3축 조합 후보를 생성",
        "- external_proxy는 여전히 비교군으로만 유지하고 내부 모델만 컷오프",
    ]

    RESULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    guard_kr_only()
    ensure_variant_distinctness()

    VALIDATED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    STAGE05_REPORTS.mkdir(parents=True, exist_ok=True)

    write_design_report()

    universe = load_universe(limit=int(BASE_PARAMS["universe_limit"]))
    supplies = {c: load_supply(c) for c in universe}
    dates = rebalance_dates(universe)

    model_runs = [run_variant(v, universe, supplies, dates) for v in VARIANTS]
    external = run_external_proxy(universe, supplies, dates)

    by_track = {t: [m for m in model_runs if m["track"] == t] for t in INTERNAL_TRACKS}

    numeric_best = pick_best(by_track["numeric"])
    qualitative_best = pick_best(by_track["qualitative"])
    hybrid_best = pick_best(by_track["hybrid"])
    overall_best = pick_best(model_runs)

    internal_3000_gate_pass = bool(float(overall_best["stats"]["total_return"]) > 30.0)

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "policy_enforcement": {
            "rulebook": "V3.4",
            "holdings_range": "1~6",
            "min_hold_days": int(BASE_PARAMS["min_hold_days"]),
            "replace_edge": float(BASE_PARAMS["replace_edge"]),
            "monthly_replace_cap": float(BASE_PARAMS["monthly_replace_cap"]),
            "external_proxy_selection_excluded": True,
            "track_variant_3x3_distinct": True,
        },
        "inputs": {
            "ohlcv_dir": str(OHLCV_DIR),
            "supply_dir": str(SUPPLY_DIR),
            "universe_size": len(universe),
            "rebalance_points": len(dates),
        },
        "models": model_runs,
        "comparison_model_external_proxy": external,
        "numeric_best": numeric_best,
        "qualitative_best": qualitative_best,
        "hybrid_best": hybrid_best,
        "overall_best": overall_best,
        "internal_3000_gate_pass": internal_3000_gate_pass,
        "sensitivity_summary": sensitivity_summary(model_runs),
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_result_report(payload)

    print(
        json.dumps(
            {
                "status": "ok",
                "version": VERSION,
                "universe_size": len(universe),
                "rebalance_points": len(dates),
                "numeric_best": numeric_best["model_id"],
                "qualitative_best": qualitative_best["model_id"],
                "hybrid_best": hybrid_best["model_id"],
                "overall_best": overall_best["model_id"],
                "internal_3000_gate_pass": internal_3000_gate_pass,
                "output": str(OUT_JSON.relative_to(BASE)),
                "design_report": str(DESIGN_MD.relative_to(BASE)),
                "result_report": str(RESULT_MD.relative_to(BASE)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
