#!/usr/bin/env python3
from __future__ import annotations

import math
from typing import Any

SCORE_V4_6_WEIGHTS = {
    # legacy key(문서/하위호환 참조)
    "return_2021_plus": 0.70,
    "return_2023_2025": 0.20,
    "return_2025_plus": 0.08,
    "total_return": 0.02,
    "mdd_2021_plus_penalty": 0.02,
    "mdd_full_penalty": 0.01,
    "mdd_2023_2025_penalty": 0.01,
    # duplication-guard axis cap
    "axis_value_cap": 0.25,
    "axis_momentum_cap": 0.25,
    "axis_risk_cap": 0.25,
    "axis_theme_cap": 0.25,
    "corr_threshold": 0.70,
}

TURNOVER_PENALTY_START = 2.8
TURNOVER_PENALTY_WEIGHT = 0.03
SECTOR_BONUS = 0.08
SECTOR_BONUS_KEYWORDS = (
    "momentum",
    "trend",
    "factor_rotation",
    "theme_sector",
    "institutional_flow",
    "earnings_surprise",
)

AXES = ("value", "momentum", "risk", "theme")
AXIS_BASE_WEIGHTS = {
    "value": 0.25,
    "momentum": 0.25,
    "risk": 0.25,
    "theme": 0.25,
}
AXIS_PRIORITY = {
    "value": 4,
    "risk": 3,
    "momentum": 2,
    "theme": 1,
}
AXIS_CORR_THRESHOLD = 0.70
AXIS_WEIGHT_CAP = 0.25

# 단일 공식(문서화): winner는 아래 final_score의 argmax로만 확정한다.
#
# 1) 축별 대표지표 1개 생성
#    value_axis    = 0.80*return_2021_plus + 0.20*total_return
#    momentum_axis = 0.70*return_2023_2025 + 0.30*return_2025_plus
#    risk_axis     = -(0.50*|mdd_2021_plus| + 0.30*|mdd_2023_2025| + 0.20*|mdd_full| + 0.10*turnover_excess)
#    theme_axis    = sector_keyword_flag(1 or 0)
# 2) 같은 축 내부 지표는 composite 1개로 축약
# 3) 축간 |rho|>0.7이면 우선순위 낮은 축 제거
# 4) 단일축 기여도 cap 25%
# final_score = weighted_mean(z(value, momentum, risk, theme), effective_axis_weights)
SCORE_V4_6_FORMULA_TEXT = (
    "final_score = weighted_mean(z(axis_representatives), axis_cap<=0.25, corr_guard(|rho|<=0.7)); "
    "axes={value,momentum,risk,theme}"
)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _legacy_score_v4_6(stats: dict, model_id: str) -> dict:
    weighted = (
        _safe_float(stats.get("return_2021_plus"), 0.0) * SCORE_V4_6_WEIGHTS["return_2021_plus"]
        + _safe_float(stats.get("return_2023_2025"), 0.0) * SCORE_V4_6_WEIGHTS["return_2023_2025"]
        + _safe_float(stats.get("return_2025_plus"), 0.0) * SCORE_V4_6_WEIGHTS["return_2025_plus"]
        + _safe_float(stats.get("total_return"), 0.0) * SCORE_V4_6_WEIGHTS["total_return"]
    )
    mdd_penalty = (
        abs(_safe_float(stats.get("mdd_2021_plus"), 0.0)) * SCORE_V4_6_WEIGHTS["mdd_2021_plus_penalty"]
        + abs(_safe_float(stats.get("mdd_full"), 0.0)) * SCORE_V4_6_WEIGHTS["mdd_full_penalty"]
        + abs(_safe_float(stats.get("mdd_2023_2025"), 0.0)) * SCORE_V4_6_WEIGHTS["mdd_2023_2025_penalty"]
    )
    turnover_penalty = max(0.0, _safe_float(stats.get("turnover"), 0.0) - TURNOVER_PENALTY_START) * TURNOVER_PENALTY_WEIGHT
    sector_adjustment = SECTOR_BONUS if any(k in model_id for k in SECTOR_BONUS_KEYWORDS) else 0.0
    score_base = weighted - mdd_penalty - turnover_penalty
    final_score = score_base + sector_adjustment
    return {
        "final_score": float(final_score),
        "score_base": float(score_base),
        "score_sector_adjustment": float(sector_adjustment),
        "axis_representatives": {},
        "axis_zscores": {},
        "axis_contributions": {},
        "axis_weights": {},
        "dup_guard": {"enabled": False, "mode": "legacy_formula"},
    }


def _axis_representatives(stats: dict, model_id: str) -> dict[str, float]:
    turnover_excess = max(0.0, _safe_float(stats.get("turnover"), 0.0) - TURNOVER_PENALTY_START)
    theme_flag = 1.0 if any(k in model_id for k in SECTOR_BONUS_KEYWORDS) else 0.0

    value_axis = (
        0.80 * _safe_float(stats.get("return_2021_plus"), 0.0)
        + 0.20 * _safe_float(stats.get("total_return"), 0.0)
    )
    momentum_axis = (
        0.70 * _safe_float(stats.get("return_2023_2025"), 0.0)
        + 0.30 * _safe_float(stats.get("return_2025_plus"), 0.0)
    )
    risk_axis = -(
        0.50 * abs(_safe_float(stats.get("mdd_2021_plus"), 0.0))
        + 0.30 * abs(_safe_float(stats.get("mdd_2023_2025"), 0.0))
        + 0.20 * abs(_safe_float(stats.get("mdd_full"), 0.0))
        + 0.10 * turnover_excess
    )

    return {
        "value": float(value_axis),
        "momentum": float(momentum_axis),
        "risk": float(risk_axis),
        "theme": float(theme_flag),
    }


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0
    x = [float(v) for v in xs[:n]]
    y = [float(v) for v in ys[:n]]
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx <= 1e-15 or vy <= 1e-15:
        return 0.0
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    return float(cov / math.sqrt(vx * vy))


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / max(n, 1)
    std = math.sqrt(var)
    if std <= 1e-12:
        std = 1.0
    return float(mean), float(std)


def _zscore(value: float, mean: float, std: float) -> float:
    if std <= 1e-12:
        return 0.0
    z = (float(value) - float(mean)) / float(std)
    return float(max(-3.0, min(3.0, z)))


def build_dup_guard_context_v4_6(candidates: list[dict]) -> dict:
    reps_by_model: dict[str, dict[str, float]] = {}
    axis_series: dict[str, list[float]] = {a: [] for a in AXES}

    for row in candidates:
        model_id = str(row.get("model_id", "") or "")
        stats = row.get("stats", {}) or {}
        reps = _axis_representatives(stats, model_id)
        reps_by_model[model_id] = reps
        for a in AXES:
            axis_series[a].append(float(reps[a]))

    axis_stats = {}
    for a in AXES:
        m, s = _mean_std(axis_series[a])
        axis_stats[a] = {"mean": m, "std": s}

    corr_matrix = {a: {b: 0.0 for b in AXES} for a in AXES}
    pre_pairs: list[dict] = []
    for i in range(len(AXES)):
        for j in range(i + 1, len(AXES)):
            a, b = AXES[i], AXES[j]
            rho = _pearson(axis_series[a], axis_series[b])
            corr_matrix[a][b] = rho
            corr_matrix[b][a] = rho
            if abs(rho) > AXIS_CORR_THRESHOLD:
                pre_pairs.append({"axis_a": a, "axis_b": b, "rho": float(rho)})
    pre_pairs.sort(key=lambda x: abs(float(x["rho"])), reverse=True)

    effective_weights = dict(AXIS_BASE_WEIGHTS)
    actions: list[dict] = []
    dropped: set[str] = set()
    for pair in pre_pairs:
        a = str(pair["axis_a"])
        b = str(pair["axis_b"])
        loser = a if AXIS_PRIORITY.get(a, 0) < AXIS_PRIORITY.get(b, 0) else b
        if loser in dropped:
            continue
        effective_weights[loser] = 0.0
        dropped.add(loser)
        actions.append({"action": "drop_axis", "axis": loser, "reason": pair})

    for a in AXES:
        effective_weights[a] = float(max(0.0, min(AXIS_WEIGHT_CAP, effective_weights[a])))

    if sum(effective_weights.values()) <= 1e-12:
        effective_weights = dict(AXIS_BASE_WEIGHTS)

    active_axes = [a for a in AXES if effective_weights.get(a, 0.0) > 0.0]
    post_pairs: list[dict] = []
    if len(active_axes) >= 2:
        for i in range(len(active_axes)):
            for j in range(i + 1, len(active_axes)):
                a, b = active_axes[i], active_axes[j]
                rho = corr_matrix.get(a, {}).get(b, 0.0)
                if abs(rho) > AXIS_CORR_THRESHOLD:
                    post_pairs.append({"axis_a": a, "axis_b": b, "rho": float(rho)})
        post_pairs.sort(key=lambda x: abs(float(x["rho"])), reverse=True)

    return {
        "enabled": True,
        "rules_enabled": [
            "axis_representative_one",
            "same_axis_composite_one",
            "cross_axis_corr_drop_if_abs_rho_gt_0_7",
            "single_axis_contribution_cap_0_25",
        ],
        "corr_threshold": AXIS_CORR_THRESHOLD,
        "axis_cap": AXIS_WEIGHT_CAP,
        "axis_base_weights": dict(AXIS_BASE_WEIGHTS),
        "axis_effective_weights": dict(effective_weights),
        "axis_priority": dict(AXIS_PRIORITY),
        "axis_stats": axis_stats,
        "axis_corr_pre": corr_matrix,
        "pre_high_corr_pairs": pre_pairs,
        "post_high_corr_pairs": post_pairs,
        "pre_high_corr_pair_count": int(len(pre_pairs)),
        "post_high_corr_pair_count": int(len(post_pairs)),
        "actions": actions,
        "reps_by_model": reps_by_model,
    }


def compute_winner_score_v4_6(stats: dict, model_id: str, guard_context: dict | None = None) -> dict:
    if not guard_context:
        return _legacy_score_v4_6(stats, model_id)

    reps = _axis_representatives(stats, model_id)
    axis_stats = guard_context.get("axis_stats", {}) or {}
    axis_weights = guard_context.get("axis_effective_weights", {}) or {}

    axis_zscores: dict[str, float] = {}
    axis_contrib: dict[str, float] = {}
    for a in AXES:
        mean = float((axis_stats.get(a, {}) or {}).get("mean", 0.0))
        std = float((axis_stats.get(a, {}) or {}).get("std", 1.0))
        z = _zscore(reps.get(a, 0.0), mean, std)
        w = float(axis_weights.get(a, 0.0))
        axis_zscores[a] = z
        axis_contrib[a] = w * z

    sum_w = float(sum(float(axis_weights.get(a, 0.0)) for a in AXES))
    if sum_w <= 1e-12:
        sum_w = 1.0

    final_score = float(sum(axis_contrib.values()) / sum_w)
    theme_contrib = float(axis_contrib.get("theme", 0.0) / sum_w)
    score_base = float(final_score - theme_contrib)

    return {
        "final_score": float(final_score),
        "score_base": float(score_base),
        "score_sector_adjustment": float(theme_contrib),
        "axis_representatives": reps,
        "axis_zscores": axis_zscores,
        "axis_contributions": axis_contrib,
        "axis_weights": dict(axis_weights),
        "dup_guard": {
            k: v
            for k, v in guard_context.items()
            if k
            not in {
                "reps_by_model",
            }
        },
    }


def rank_candidates_v4_6(candidates: list[dict]) -> list[dict]:
    ranked: list[dict] = []
    guard_context = build_dup_guard_context_v4_6(candidates)

    for row in candidates:
        model_id = str(row.get("model_id", "") or "")
        stats = row.get("stats", {}) or {}
        score = compute_winner_score_v4_6(stats, model_id, guard_context=guard_context)
        ranked.append(
            {
                "model_id": model_id,
                "track": str(row.get("track", "") or ""),
                "stats": stats,
                "final_score": score["final_score"],
                "score_base": score["score_base"],
                "score_sector_adjustment": score["score_sector_adjustment"],
                "axis_representatives": score.get("axis_representatives", {}),
                "axis_zscores": score.get("axis_zscores", {}),
                "axis_contributions": score.get("axis_contributions", {}),
                "axis_weights": score.get("axis_weights", {}),
                "dup_guard": score.get("dup_guard", {}),
            }
        )

    ranked.sort(key=lambda x: (-float(x.get("final_score", 0.0)), str(x.get("model_id", ""))))
    return ranked


def score_leaderboard_v4_6(ranked: list[dict], top_n: int = 10) -> list[dict]:
    out: list[dict] = []
    for idx, row in enumerate(ranked[: max(0, int(top_n))], start=1):
        out.append(
            {
                "rank": idx,
                "model_id": row["model_id"],
                "track": row.get("track"),
                "final_score": float(row.get("final_score", 0.0)),
                "score_base": float(row.get("score_base", 0.0)),
                "score_sector_adjustment": float(row.get("score_sector_adjustment", 0.0)),
                "axis_weights": row.get("axis_weights", {}),
            }
        )
    return out
