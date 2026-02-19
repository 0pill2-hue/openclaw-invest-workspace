#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
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
OUT_STAGE06_JSON = VALIDATED / "stage06_candidates_v4_kr.json"
OUT_STAGE06_MD = REPORTS / "stage06/stage06_candidates_v4_kr.md"

VERSION = "v4_kr"
RUN_COMMAND = "python3 scripts/stage06_candidates_v4_kr.py"

RULEBOOK_FIXED = {
    "max_pos": 6,
    "min_hold_days": 20,
    "replace_edge": 0.15,
    "monthly_replace_cap": 0.30,
    "trailing_stop_pct": -0.20,
}


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


def build_specs(seed_map: dict[str, dict[str, Any]], seed_ids: dict[str, str]) -> list[dict[str, Any]]:
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
    ) -> None:
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
            }
        )

    # numeric track (4)
    append_candidate(
        candidate_id="s06v4_numeric_n4_tsmom_fast",
        track="numeric",
        score_model="numeric",
        seed_key="numeric",
        patch={"ret_short": 8, "ret_mid": 32, "trend_fast": 6, "trend_slow": 28},
        why="시계열 모멘텀(lookback 단축) 아이디어 이식으로 반응속도 개선 테스트",
        expected_risk="횡보장 과민반응으로 whipsaw 증가 가능",
        external_idea_tags=["ts_momentum", "dynamic_lookback"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_numeric_n5_flow_balance",
        track="numeric",
        score_model="numeric",
        seed_key="numeric",
        patch={"flow_scale": 100_000_000.0, "quant_trend_w": 0.62, "quant_flow_w": 0.38},
        why="flow 신호 과민도를 낮추는 리스크 관리형 밸런스 테스트",
        expected_risk="급격한 수급장세에서 추세 추종 반응 지연 가능",
        external_idea_tags=["cross_sectional_flow", "risk_balance"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_numeric_n6_flow_aggressive",
        track="numeric",
        score_model="numeric",
        seed_key="numeric",
        patch={"flow_scale": 70_000_000.0, "quant_trend_w": 0.50, "quant_flow_w": 0.50},
        why="대회 상위권 계열의 flow tilt 아이디어를 공격적으로 반영",
        expected_risk="수급 노이즈 구간에서 변동성 확대 가능",
        external_idea_tags=["flow_tilt", "ensemble_weight_shift"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_numeric_n7_cost_guard",
        track="numeric",
        score_model="numeric",
        seed_key="numeric",
        patch={"fee": 0.0038, "ret_mid": 45},
        why="실전형 비용 보수화 + 중기모멘텀 안정화 조합",
        expected_risk="강한 상승장에서는 상대 성과 둔화 가능",
        external_idea_tags=["cost_aware_execution", "ts_momentum"],
        idea_application_mode="idea_transplant_operational_layer",
    )

    # qualitative track (4)
    append_candidate(
        candidate_id="s06v4_qual_q4_event_balanced",
        track="qualitative",
        score_model="qualitative",
        seed_key="qualitative",
        patch={"qual_buzz_w": 0.68, "qual_ret_w": 0.20, "qual_up_w": 0.12, "buzz_window": 50, "fee": 0.0042},
        why="이벤트(buzz) 편향 완화 + 수익률/상승비율 보강",
        expected_risk="테마 급등 구간에서 초과성과 놓칠 수 있음",
        external_idea_tags=["event_sentiment", "meta_labeling_idea"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_qual_q5_persistence",
        track="qualitative",
        score_model="qualitative",
        seed_key="qualitative",
        patch={"qual_buzz_w": 0.60, "qual_ret_w": 0.24, "qual_up_w": 0.16, "up_window": 15},
        why="상승 지속성(up ratio) 강화로 추세 지속 구간 포착 시도",
        expected_risk="추세 반전 시 회전율 증가 가능",
        external_idea_tags=["trend_persistence", "time_series_signal"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_qual_q6_noise_filter",
        track="qualitative",
        score_model="qualitative",
        seed_key="qualitative",
        patch={"qual_buzz_w": 0.78, "qual_ret_w": 0.14, "qual_up_w": 0.08, "buzz_window": 70, "fee": 0.0040},
        why="긴 buzz window로 단기 테마 노이즈 억제",
        expected_risk="신규 이슈 반영 지연 가능",
        external_idea_tags=["sentiment_smoothing", "risk_management_filter"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_qual_q7_cost_relief",
        track="qualitative",
        score_model="qualitative",
        seed_key="qualitative",
        patch={"fee": 0.0038, "qual_ret_w": 0.22, "qual_up_w": 0.12},
        why="정성 트랙 비용 스트레스 완화 + 모멘텀 반영도 상향",
        expected_risk="거래비용 추정이 과소일 경우 실전괴리 가능",
        external_idea_tags=["cost_aware_execution", "momentum_overlay"],
        idea_application_mode="idea_transplant_operational_layer",
    )

    # hybrid track (4)
    append_candidate(
        candidate_id="s06v4_hybrid_h4_consensus_plus",
        track="hybrid",
        score_model="hybrid",
        seed_key="hybrid",
        patch={"hybrid_quant_w": 0.46, "hybrid_qual_w": 0.30, "hybrid_agree_w": 0.28},
        why="앙상블 합의항(agree) 강화로 one-sided 신호 완화",
        expected_risk="강추세 단일 신호 구간에서 기회손실 가능",
        external_idea_tags=["rank_ensemble", "consensus_weighting"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_hybrid_h5_quant_rebound",
        track="hybrid",
        score_model="hybrid",
        seed_key="hybrid",
        patch={"hybrid_quant_w": 0.56, "hybrid_qual_w": 0.26, "hybrid_agree_w": 0.18},
        why="정량 비중 회복으로 수급/추세 리더십 구간 대응",
        expected_risk="정성 이벤트 반응력 저하 가능",
        external_idea_tags=["ensemble_reweighting", "flow_tilt"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_hybrid_h6_qual_event",
        track="hybrid",
        score_model="hybrid",
        seed_key="hybrid",
        patch={"hybrid_quant_w": 0.42, "hybrid_qual_w": 0.40, "hybrid_agree_w": 0.18, "qual_up_w": 0.14},
        why="정성 이벤트 반응과 합의항을 동시에 유지하는 혼합형",
        expected_risk="qual 신호 노이즈에 민감해질 수 있음",
        external_idea_tags=["event_overlay", "ensemble_weighting"],
        idea_application_mode="idea_transplant_operational_layer",
    )
    append_candidate(
        candidate_id="s06v4_hybrid_h7_balanced_cost",
        track="hybrid",
        score_model="hybrid",
        seed_key="hybrid",
        patch={"hybrid_quant_w": 0.50, "hybrid_qual_w": 0.30, "hybrid_agree_w": 0.22, "fee": 0.0038},
        why="합의형 하이브리드에 비용보수화 결합",
        expected_risk="비용 가정과 실제 체결비용 괴리 리스크",
        external_idea_tags=["cost_aware_execution", "consensus_weighting"],
        idea_application_mode="idea_transplant_operational_layer",
    )

    return specs


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


def write_report(payload: dict[str, Any]) -> None:
    cands = payload["candidates"]
    count_by_track = Counter(c["track"] for c in cands)
    total = len(cands)

    top = sorted(cands, key=lambda x: (x["stats"]["total_return"], x["stats"]["mdd"]), reverse=True)[:5]

    qg = payload["quality_gates"]

    lines = [
        "# stage06_candidates_v4_kr",
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
        f"- external_proxy_selection_excluded: {qg['external_proxy_selection_excluded']}",
        f"- changed_params_non_empty: {qg['changed_params_non_empty']}",
        f"- rulebook_fixed_hard_constraints: {qg['rulebook_fixed_hard_constraints']}",
        "",
        "## failure_policy",
        "- Stage05 seed 입력 누락/비검증(VALIDATED 아님) 시 FAIL_STOP",
        "- 후보 수가 chosen_plan과 불일치하면 FAIL_STOP",
        "- RULEBOOK V3.4 고정 파라미터(보유1~6/최소20일/교체+15%/월30%/트레일링-20%) 위반 시 FAIL_STOP",
        "",
        "## proof",
        f"- {OUT_STAGE06_JSON}",
        f"- {BASE / 'scripts/stage06_candidates_v4_kr.py'}",
        "",
        "## summary",
        f"- version: {payload['version']}",
        f"- 후보 수: {total}",
        f"- 트랙 비중: numeric={count_by_track.get('numeric', 0)} ({count_by_track.get('numeric', 0)/max(total,1):.1%}), qualitative={count_by_track.get('qualitative', 0)} ({count_by_track.get('qualitative', 0)/max(total,1):.1%}), hybrid={count_by_track.get('hybrid', 0)} ({count_by_track.get('hybrid', 0)/max(total,1):.1%})",
        f"- 외부아이디어 반영 여부: {payload['external_ideas_applied']}",
        "",
        "## top5 (by total_return)",
        "| rank | candidate_id | track | seed_model | total_return | MDD | CAGR | external_ideas |",
        "|---:|---|---|---|---:|---:|---:|---|",
    ]

    for i, c in enumerate(top, start=1):
        st = c["stats"]
        ideas = ", ".join(c.get("external_idea_tags", []))
        lines.append(
            f"| {i} | {c['model_id']} | {c['track']} | {c['seed_model_id']} | {pct(st['total_return'])} | {pct(st['mdd'])} | {pct(st['cagr'])} | {ideas} |"
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
        "plan_id": "medium_12",
        "candidate_count": 12,
        "track_split": {"numeric": 4, "qualitative": 4, "hybrid": 4},
        "selection_reason": "연산비용과 탐색다양성 균형(3x3 seed 확장)"
    }

    specs = build_specs(seed_map, seed_ids)
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
        results.append(run)

    results.sort(key=lambda x: (x["stats"]["total_return"], x["stats"]["mdd"]), reverse=True)

    rulebook_checks = verify_rulebook_fixed(results)
    qg = {
        "candidate_count_match_plan": len(results) == chosen_plan["candidate_count"],
        "external_proxy_selection_excluded": True,
        "changed_params_non_empty": all(len(r.get("changed_params", {})) > 0 for r in results),
        "rulebook_fixed_hard_constraints": all(rulebook_checks.values()),
        "rulebook_check_detail": rulebook_checks,
    }

    if not all([qg["candidate_count_match_plan"], qg["changed_params_non_empty"], qg["rulebook_fixed_hard_constraints"]]):
        raise RuntimeError("FAIL: quality gate failed in Stage06 v4")

    count_by_track = Counter(r["track"] for r in results)

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
            "rulebook": "V3.4",
            "holdings_range": "1~6",
            "min_hold_days": 20,
            "replace_edge": 0.15,
            "monthly_replace_cap": 0.30,
            "external_proxy_selection_excluded": True,
            "changed_params_pingpong_avoided": True,
        },
        "chosen_plan": chosen_plan,
        "external_ideas_applied": {
            "applied": True,
            "mode": "idea_transplant_operational_layer_only",
            "selection_model_direct_use": "N/A (비교/아이디어 참고만, 직접 외부모델 미사용)",
            "notes": "external_proxy는 비교군 전용, 후보 선발 제외",
        },
        "summary": {
            "candidate_count": len(results),
            "track_mix": dict(count_by_track),
            "top_candidate_id": results[0]["model_id"] if results else None,
            "top_candidate_total_return": results[0]["stats"]["total_return"] if results else None,
        },
        "quality_gates": qg,
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
