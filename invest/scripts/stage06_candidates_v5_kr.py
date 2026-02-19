#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from stage05_3x3_v3_9_kr import (  # type: ignore
    BASE,
    BASE_PARAMS,
    OHLCV_DIR,
    SUPPLY_DIR,
    REPORTS,
    VALIDATED,
    VariantSpec,
    guard_kr_only,
    load_supply,
    load_universe,
    rebalance_dates,
    run_variant,
)

IN_STAGE05 = VALIDATED / "stage05_baselines_3x3_v3_9_kr.json"
OUT_STAGE06_JSON = VALIDATED / "stage06_candidates_v5_kr.json"
OUT_STAGE06_MD = REPORTS / "stage06/stage06_candidates_v5_kr.md"

VERSION = "v5_kr"
RUN_COMMAND = "python3 scripts/stage06_candidates_v5_kr.py"

RULEBOOK_FIXED = {
    "max_pos": 6,
    "min_hold_days": 20,
    "replace_edge": 0.15,
    "monthly_replace_cap": 0.30,
    "trailing_stop_pct": -0.20,
}

HARD_KEYS = set(RULEBOOK_FIXED.keys())


def pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def load_stage05_payload() -> dict[str, Any]:
    if not IN_STAGE05.exists():
        raise RuntimeError(f"FAIL: missing input {IN_STAGE05}")
    payload = json.loads(IN_STAGE05.read_text(encoding="utf-8"))
    if payload.get("result_grade") != "VALIDATED":
        raise RuntimeError("FAIL: Stage05 input is not VALIDATED")
    return payload


def params_from_model(payload: dict[str, Any], model_id: str) -> dict[str, Any]:
    for m in payload.get("models", []):
        if m.get("model_id") == model_id:
            return dict(m.get("effective_params", {}))
    raise RuntimeError(f"FAIL: missing model params for {model_id}")


def changed_from_base(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in params.items():
        if k not in BASE_PARAMS:
            continue
        if BASE_PARAMS[k] != v:
            out[k] = v
    return out


def is_pingpong_pair(cp_a: dict[str, Any], cp_b: dict[str, Any]) -> bool:
    if set(cp_a.keys()) != set(cp_b.keys()):
        return False

    has_nonzero = False
    for k in cp_a:
        va = cp_a[k]
        vb = cp_b[k]
        b = BASE_PARAMS[k]
        if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
            return False
        da = float(va) - float(b)
        db = float(vb) - float(b)
        if abs(da) < 1e-12 and abs(db) < 1e-12:
            continue
        has_nonzero = True
        if abs(da + db) > 1e-9:
            return False
    return has_nonzero


def build_specs(seed_map: dict[str, dict[str, Any]], seed_ids: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    def append_candidate(
        candidate_id: str,
        track: str,
        score_model: str,
        seed_key: str,
        patch: dict[str, Any],
        why: str,
        expected_risk: str,
        external_idea_tags: list[str],
        idea_application_mode: str,
        family: str,
    ) -> None:
        if any(k in HARD_KEYS for k in patch):
            raise RuntimeError(f"FAIL: hard rule key touched in patch {candidate_id}")

        base = dict(seed_map[seed_key])
        base.update(patch)
        cp = changed_from_base(base)
        if not cp:
            raise RuntimeError(f"FAIL: changed_params empty for {candidate_id}")

        spec = VariantSpec(
            model_id=candidate_id,
            track=track,
            score_model=score_model,
            changed_params=cp,
            why=why,
            expected_risk=expected_risk,
        )

        specs.append(
            {
                "spec": spec,
                "seed_model_id": seed_ids[seed_key],
                "external_idea_tags": external_idea_tags,
                "idea_application_mode": idea_application_mode,
                "changed_params": cp,
                "family": family,
            }
        )

    # ----------------------
    # numeric 24 = 6x4 grid
    # ----------------------
    momentum_profiles = [
        {"ret_short": 8, "ret_mid": 32, "trend_fast": 6, "trend_slow": 28},
        {"ret_short": 9, "ret_mid": 36, "trend_fast": 7, "trend_slow": 30},
        {"ret_short": 10, "ret_mid": 40, "trend_fast": 8, "trend_slow": 34},
        {"ret_short": 11, "ret_mid": 44, "trend_fast": 9, "trend_slow": 38},
        {"ret_short": 12, "ret_mid": 48, "trend_fast": 10, "trend_slow": 42},
        {"ret_short": 14, "ret_mid": 56, "trend_fast": 12, "trend_slow": 48},
    ]
    flow_profiles = [
        {"flow_scale": 70_000_000.0, "quant_trend_w": 0.50, "quant_flow_w": 0.50},
        {"flow_scale": 85_000_000.0, "quant_trend_w": 0.58, "quant_flow_w": 0.42},
        {"flow_scale": 100_000_000.0, "quant_trend_w": 0.64, "quant_flow_w": 0.36},
        {"flow_scale": 130_000_000.0, "quant_trend_w": 0.72, "quant_flow_w": 0.28},
    ]
    numeric_fee_cycle = [0.0030, 0.0034, 0.0038, 0.0042]

    n_idx = 1
    for f_idx, flow in enumerate(flow_profiles, start=1):
        for m_idx, mom in enumerate(momentum_profiles, start=1):
            patch = dict(mom)
            patch.update(flow)
            patch["fee"] = numeric_fee_cycle[(n_idx - 1) % len(numeric_fee_cycle)]
            append_candidate(
                candidate_id=f"s06v5_numeric_n{n_idx:02d}",
                track="numeric",
                score_model="numeric",
                seed_key="numeric",
                patch=patch,
                why=f"numeric 6x4 grid 탐색: momentum_profile={m_idx}, flow_profile={f_idx}, fee_regime={patch['fee']}",
                expected_risk="flow/모멘텀 동시 조정으로 국면 미스매치 시 변동성 확대 가능",
                external_idea_tags=["ts_momentum", "flow_tilt", "cost_aware_execution"],
                idea_application_mode="idea_transplant_operational_layer",
                family=f"N_M{m_idx}_F{f_idx}",
            )
            n_idx += 1

    # --------------------------
    # qualitative 24 = 6x4 grid
    # --------------------------
    qual_weight_profiles = [
        {"qual_buzz_w": 0.84, "qual_ret_w": 0.10, "qual_up_w": 0.06},
        {"qual_buzz_w": 0.80, "qual_ret_w": 0.12, "qual_up_w": 0.08},
        {"qual_buzz_w": 0.74, "qual_ret_w": 0.16, "qual_up_w": 0.10},
        {"qual_buzz_w": 0.68, "qual_ret_w": 0.20, "qual_up_w": 0.12},
        {"qual_buzz_w": 0.62, "qual_ret_w": 0.24, "qual_up_w": 0.14},
        {"qual_buzz_w": 0.56, "qual_ret_w": 0.28, "qual_up_w": 0.16},
    ]
    qual_window_profiles = [
        {"buzz_window": 40, "up_window": 12, "fee": 0.0046},
        {"buzz_window": 50, "up_window": 15, "fee": 0.0042},
        {"buzz_window": 65, "up_window": 20, "fee": 0.0038},
        {"buzz_window": 80, "up_window": 25, "fee": 0.0034},
    ]

    q_idx = 1
    for w_idx, windows in enumerate(qual_window_profiles, start=1):
        for mix_idx, mix in enumerate(qual_weight_profiles, start=1):
            patch = dict(mix)
            patch.update(windows)
            append_candidate(
                candidate_id=f"s06v5_qual_q{q_idx:02d}",
                track="qualitative",
                score_model="qualitative",
                seed_key="qualitative",
                patch=patch,
                why=f"qualitative 6x4 grid 탐색: weight_mix={mix_idx}, window_profile={w_idx}",
                expected_risk="이벤트 신호 편향 또는 반응지연으로 수익 분산 확대 가능",
                external_idea_tags=["event_sentiment", "sentiment_smoothing", "momentum_overlay"],
                idea_application_mode="idea_transplant_operational_layer",
                family=f"Q_W{mix_idx}_T{w_idx}",
            )
            q_idx += 1

    # ----------------------
    # hybrid 24 = 6x4 grid
    # ----------------------
    hybrid_blend_profiles = [
        {"hybrid_quant_w": 0.64, "hybrid_qual_w": 0.24, "hybrid_agree_w": 0.12},
        {"hybrid_quant_w": 0.60, "hybrid_qual_w": 0.24, "hybrid_agree_w": 0.16},
        {"hybrid_quant_w": 0.56, "hybrid_qual_w": 0.24, "hybrid_agree_w": 0.20},
        {"hybrid_quant_w": 0.52, "hybrid_qual_w": 0.26, "hybrid_agree_w": 0.22},
        {"hybrid_quant_w": 0.48, "hybrid_qual_w": 0.30, "hybrid_agree_w": 0.22},
        {"hybrid_quant_w": 0.44, "hybrid_qual_w": 0.32, "hybrid_agree_w": 0.24},
    ]
    hybrid_support_profiles = [
        {"quant_trend_w": 0.60, "quant_flow_w": 0.40, "qual_up_w": 0.10, "fee": 0.0030},
        {"quant_trend_w": 0.66, "quant_flow_w": 0.34, "qual_up_w": 0.12, "fee": 0.0033},
        {"quant_trend_w": 0.72, "quant_flow_w": 0.28, "qual_up_w": 0.14, "fee": 0.0036},
        {"quant_trend_w": 0.54, "quant_flow_w": 0.46, "qual_up_w": 0.08, "fee": 0.0039},
    ]

    h_idx = 1
    for s_idx, support in enumerate(hybrid_support_profiles, start=1):
        for b_idx, blend in enumerate(hybrid_blend_profiles, start=1):
            patch = dict(blend)
            patch.update(support)
            append_candidate(
                candidate_id=f"s06v5_hybrid_h{h_idx:02d}",
                track="hybrid",
                score_model="hybrid",
                seed_key="hybrid",
                patch=patch,
                why=f"hybrid 6x4 grid 탐색: blend_profile={b_idx}, support_profile={s_idx}",
                expected_risk="합의항/보조신호 동시 조정으로 강한 단일추세 구간 기회손실 가능",
                external_idea_tags=["rank_ensemble", "consensus_weighting", "flow_tilt"],
                idea_application_mode="idea_transplant_operational_layer",
                family=f"H_B{b_idx}_S{s_idx}",
            )
            h_idx += 1

    if len(specs) != 72:
        raise RuntimeError(f"FAIL: spec count mismatch (expected 72, got {len(specs)})")

    # ping-pong/duplicate guard
    by_track: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in specs:
        by_track[row["spec"].track].append(row)

    pingpong_pairs: list[tuple[str, str]] = []
    duplicate_signatures = False
    for track, rows in by_track.items():
        sigs = [tuple(sorted(r["changed_params"].items())) for r in rows]
        if len(set(sigs)) != len(sigs):
            duplicate_signatures = True

        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if is_pingpong_pair(rows[i]["changed_params"], rows[j]["changed_params"]):
                    pingpong_pairs.append((rows[i]["spec"].model_id, rows[j]["spec"].model_id))

    if duplicate_signatures:
        raise RuntimeError("FAIL: duplicate changed_params signature detected")
    if pingpong_pairs:
        raise RuntimeError(f"FAIL: ping-pong pair detected: {pingpong_pairs[:3]}")

    design_stats = {
        "track_counts": {k: len(v) for k, v in by_track.items()},
        "duplicate_signatures": duplicate_signatures,
        "pingpong_pairs_detected": pingpong_pairs,
        "families": {
            "numeric": sorted({r["family"] for r in by_track["numeric"]}),
            "qualitative": sorted({r["family"] for r in by_track["qualitative"]}),
            "hybrid": sorted({r["family"] for r in by_track["hybrid"]}),
        },
    }

    return specs, design_stats


def verify_rulebook_fixed(results: list[dict[str, Any]]) -> dict[str, bool]:
    checks = {
        "holdings_range_1_6": True,
        "min_hold_days_20": True,
        "replace_edge_15pct": True,
        "monthly_replace_cap_30pct": True,
        "trailing_stop_minus20pct": True,
    }

    for r in results:
        p = r.get("effective_params", {})
        checks["holdings_range_1_6"] = checks["holdings_range_1_6"] and int(p.get("max_pos", -1)) == RULEBOOK_FIXED["max_pos"]
        checks["min_hold_days_20"] = checks["min_hold_days_20"] and int(p.get("min_hold_days", -1)) == RULEBOOK_FIXED["min_hold_days"]
        checks["replace_edge_15pct"] = checks["replace_edge_15pct"] and float(p.get("replace_edge", -1.0)) == RULEBOOK_FIXED["replace_edge"]
        checks["monthly_replace_cap_30pct"] = checks["monthly_replace_cap_30pct"] and float(p.get("monthly_replace_cap", -1.0)) == RULEBOOK_FIXED["monthly_replace_cap"]
        checks["trailing_stop_minus20pct"] = checks["trailing_stop_minus20pct"] and float(p.get("trailing_stop_pct", 0.0)) == RULEBOOK_FIXED["trailing_stop_pct"]

    return checks


def top_param_impact(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Track-wide quick 영향도 스냅샷: 단변량 상관(대략치)
    fields = [
        "ret_short",
        "ret_mid",
        "trend_fast",
        "trend_slow",
        "flow_scale",
        "quant_trend_w",
        "quant_flow_w",
        "qual_buzz_w",
        "qual_ret_w",
        "qual_up_w",
        "buzz_window",
        "up_window",
        "hybrid_quant_w",
        "hybrid_qual_w",
        "hybrid_agree_w",
        "fee",
    ]

    def corr(xs: list[float], ys: list[float]) -> float | None:
        if len(xs) != len(ys) or len(xs) < 3:
            return None
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        if vx <= 0 or vy <= 0:
            return None
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        return float(cov / ((vx ** 0.5) * (vy ** 0.5)))

    rows: list[dict[str, Any]] = []
    ys = [float(c["stats"]["total_return"]) for c in candidates]
    for f in fields:
        xs = [float(c["effective_params"][f]) for c in candidates]
        cval = corr(xs, ys)
        if cval is None:
            continue
        rows.append({"param": f, "corr_total_return": cval, "abs_corr": abs(cval)})

    rows.sort(key=lambda x: x["abs_corr"], reverse=True)
    return rows[:10]


def compact_changed_params(cp: dict[str, Any], limit: int = 6) -> str:
    keys = sorted(cp.keys())[:limit]
    text = ", ".join(f"{k}={cp[k]}" for k in keys)
    if len(cp) > limit:
        text += f", ...(+{len(cp) - limit})"
    return text


def write_report(payload: dict[str, Any]) -> None:
    cands = payload["candidates"]
    count_by_track = Counter(c["track"] for c in cands)
    total = len(cands)

    top10 = sorted(cands, key=lambda x: (x["stats"]["total_return"], x["stats"]["mdd"]), reverse=True)[:10]

    qg = payload["quality_gates"]

    lines = [
        "# stage06_candidates_v5_kr",
        "",
        "## inputs",
        f"- {IN_STAGE05}",
        f"- KRX ohlcv: {OHLCV_DIR}",
        f"- KRX supply: {SUPPLY_DIR}",
        f"- chosen_plan: {payload['chosen_plan']['plan_id']} ({payload['chosen_plan']['candidate_count']} candidates)",
        "",
        "## run_command(or process)",
        f"- `{RUN_COMMAND}`",
        "",
        "## outputs",
        f"- {OUT_STAGE06_JSON}",
        f"- {OUT_STAGE06_MD}",
        "",
        "## quality_gates",
        f"- candidate_count_match_plan: {qg['candidate_count_match_plan']}",
        f"- track_split_24_24_24: {qg['track_split_24_24_24']}",
        f"- external_proxy_selection_excluded: {qg['external_proxy_selection_excluded']}",
        f"- changed_params_non_empty: {qg['changed_params_non_empty']}",
        f"- changed_params_pingpong_free: {qg['changed_params_pingpong_free']}",
        f"- rulebook_fixed_hard_constraints: {qg['rulebook_fixed_hard_constraints']}",
        "",
        "## failure_policy",
        "- Stage05 seed 입력 누락/비검증(VALIDATED 아님) 시 FAIL_STOP",
        "- 후보 수(72) 또는 트랙 분배(24/24/24) 불일치 시 FAIL_STOP",
        "- RULEBOOK V3.5/V3.4 고정 파라미터(보유1~6/최소20일/교체+15%/월30%/트레일링-20%) 위반 시 FAIL_STOP",
        "- changed_params 중복/핑퐁 패턴 탐지 시 FAIL_STOP",
        "",
        "## proof",
        f"- {OUT_STAGE06_JSON}",
        f"- {BASE / 'scripts/stage06_candidates_v5_kr.py'}",
        "",
        "## summary",
        f"- version: {payload['version']}",
        f"- 후보 수: {total}",
        f"- 트랙 비중: numeric={count_by_track.get('numeric', 0)} ({count_by_track.get('numeric', 0)/max(total,1):.1%}), qualitative={count_by_track.get('qualitative', 0)} ({count_by_track.get('qualitative', 0)/max(total,1):.1%}), hybrid={count_by_track.get('hybrid', 0)} ({count_by_track.get('hybrid', 0)/max(total,1):.1%})",
        f"- 하드규칙 통과 여부: {qg['rulebook_fixed_hard_constraints']}",
        f"- 외부아이디어 반영 여부: {payload['external_ideas_applied']}",
        "",
        "## new_selection_gate",
        f"- policy_id: {payload['new_selection_gate']['policy_id']}",
        f"- hard_rule: {payload['new_selection_gate']['hard_rule']}",
        "- adopt_allowed_if:",
        f"  - {payload['new_selection_gate']['adopt_allowed_if'][0]}",
        f"  - {payload['new_selection_gate']['adopt_allowed_if'][1]}",
        "- stage_binding:",
        f"  - stage07: {payload['new_selection_gate']['stage_binding']['stage07']}",
        f"  - stage09: {payload['new_selection_gate']['stage_binding']['stage09']}",
        "",
        "## 변수 영향도 스냅샷 (|corr| top10)",
        "| rank | param | corr(total_return) |",
        "|---:|---|---:|",
    ]

    for i, row in enumerate(payload.get("variable_impact_top10", []), start=1):
        lines.append(f"| {i} | {row['param']} | {row['corr_total_return']:.4f} |")

    lines += [
        "",
        "## top10 (by total_return) + 핵심 changed_params",
        "| rank | model_id | track | seed_model | total_return | MDD | CAGR | 핵심 changed_params |",
        "|---:|---|---|---|---:|---:|---:|---|",
    ]

    for i, c in enumerate(top10, start=1):
        st = c["stats"]
        lines.append(
            f"| {i} | {c['model_id']} | {c['track']} | {c['seed_model_id']} | {pct(st['total_return'])} | {pct(st['mdd'])} | {pct(st['cagr'])} | {compact_changed_params(c.get('changed_params', {}))} |"
        )

    OUT_STAGE06_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    guard_kr_only()
    VALIDATED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_STAGE06_MD.parent.mkdir(parents=True, exist_ok=True)

    stage05 = load_stage05_payload()

    seed_ids = {
        "numeric": stage05["numeric_best"]["model_id"],
        "qualitative": stage05["qualitative_best"]["model_id"],
        "hybrid": stage05["hybrid_best"]["model_id"],
    }

    seed_map = {
        "numeric": params_from_model(stage05, seed_ids["numeric"]),
        "qualitative": params_from_model(stage05, seed_ids["qualitative"]),
        "hybrid": params_from_model(stage05, seed_ids["hybrid"]),
    }

    chosen_plan = {
        "plan_id": "expanded_72",
        "candidate_count": 72,
        "track_split": {"numeric": 24, "qualitative": 24, "hybrid": 24},
        "selection_reason": "탐색폭(72)과 실행비용의 균형: 12안은 탐색부족, 180안은 과비용"
    }

    specs, design_stats = build_specs(seed_map, seed_ids)
    if len(specs) != chosen_plan["candidate_count"]:
        raise RuntimeError("FAIL: chosen plan candidate count mismatch")

    universe = load_universe(limit=int(BASE_PARAMS["universe_limit"]))
    supplies = {c: load_supply(c) for c in universe}
    dates = rebalance_dates(universe)

    results: list[dict[str, Any]] = []
    for row in specs:
        run = run_variant(row["spec"], universe, supplies, dates)
        run["seed_model_id"] = row["seed_model_id"]
        run["external_idea_tags"] = row["external_idea_tags"]
        run["idea_application_mode"] = row["idea_application_mode"]
        run["family"] = row["family"]
        results.append(run)

    results.sort(key=lambda x: (x["stats"]["total_return"], x["stats"]["mdd"]), reverse=True)

    rulebook_checks = verify_rulebook_fixed(results)
    count_by_track = Counter(r["track"] for r in results)

    qg = {
        "candidate_count_match_plan": len(results) == chosen_plan["candidate_count"],
        "track_split_24_24_24": count_by_track.get("numeric", 0) == 24 and count_by_track.get("qualitative", 0) == 24 and count_by_track.get("hybrid", 0) == 24,
        "external_proxy_selection_excluded": True,
        "changed_params_non_empty": all(len(r.get("changed_params", {})) > 0 for r in results),
        "changed_params_pingpong_free": (not design_stats["duplicate_signatures"]) and (len(design_stats["pingpong_pairs_detected"]) == 0),
        "rulebook_fixed_hard_constraints": all(rulebook_checks.values()),
        "rulebook_check_detail": rulebook_checks,
    }

    must_pass = [
        qg["candidate_count_match_plan"],
        qg["track_split_24_24_24"],
        qg["changed_params_non_empty"],
        qg["changed_params_pingpong_free"],
        qg["rulebook_fixed_hard_constraints"],
    ]
    if not all(must_pass):
        raise RuntimeError("FAIL: quality gate failed in Stage06 v5")

    top10 = sorted(results, key=lambda x: (x["stats"]["total_return"], x["stats"]["mdd"]), reverse=True)[:10]
    variable_impact_top10 = top_param_impact(results)

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "stage05_seed_file": str(IN_STAGE05),
            "ohlcv_dir": str(OHLCV_DIR),
            "supply_dir": str(SUPPLY_DIR),
            "universe_size": len(universe),
            "rebalance_points": len(dates),
            "seed_models": seed_ids,
        },
        "run_command": RUN_COMMAND,
        "policy_enforcement": {
            "rulebook": "V3.5/V3.4",
            "holdings_range": "1~6",
            "min_hold_days": 20,
            "replace_edge": 0.15,
            "monthly_replace_cap": 0.30,
            "trailing_stop_pct": -0.20,
            "external_proxy_selection_excluded": True,
            "changed_params_pingpong_avoided": True,
        },
        "chosen_plan": chosen_plan,
        "design_stats": design_stats,
        "external_ideas_applied": {
            "applied": True,
            "mode": "idea_transplant_operational_layer_only",
            "selection_model_direct_use": "N/A (비교/아이디어 참고만, 직접 외부모델 미사용)",
            "notes": "external_proxy는 비교군 전용, 후보 선발 제외",
        },
        "new_selection_gate": {
            "policy_id": "anti_numeric_monopoly_gate_v1",
            "hard_rule": "numeric 단독 1등 즉시 채택 금지",
            "adopt_allowed_if": [
                "(a) hybrid/qualitative 후보가 numeric 최고 후보 total_return 추월",
                "(b) numeric 대비 수익률 근접 + MDD 우위 + turnover_proxy 우위 동시 충족",
            ],
            "stage_binding": {
                "stage07": "컷오프 판정에 필수 포함",
                "stage09": "최종 ADOPT 전 필수 재검증",
            },
        },
        "summary": {
            "candidate_count": len(results),
            "track_mix": dict(count_by_track),
            "top_candidate_id": results[0]["model_id"] if results else None,
            "top_candidate_total_return": results[0]["stats"]["total_return"] if results else None,
        },
        "quality_gates": qg,
        "variable_impact_top10": variable_impact_top10,
        "top10_models": [
            {
                "rank": i + 1,
                "model_id": c["model_id"],
                "track": c["track"],
                "seed_model_id": c["seed_model_id"],
                "total_return": c["stats"]["total_return"],
                "mdd": c["stats"]["mdd"],
                "cagr": c["stats"]["cagr"],
                "changed_params": c.get("changed_params", {}),
            }
            for i, c in enumerate(top10)
        ],
        "candidates": results,
    }

    OUT_STAGE06_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(payload)

    print(
        json.dumps(
            {
                "status": "ok",
                "version": VERSION,
                "candidate_count": len(results),
                "track_mix": dict(count_by_track),
                "top_candidate": results[0]["model_id"] if results else None,
                "output": str(OUT_STAGE06_JSON.relative_to(BASE)),
                "report": str(OUT_STAGE06_MD.relative_to(BASE)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
