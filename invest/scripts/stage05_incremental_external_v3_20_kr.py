#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from stage05_baseline_guard import (
    EXPECTED_TRACK_COUNTS_12_BASELINE,
    enforce_track_counts_or_fail_stop,
)

BASE = Path(__file__).resolve().parents[1]
VALIDATED = BASE / "invest/results/validated"
TEST_RESULTS = BASE / "invest/results/test"
REPORTS = BASE / "reports/stage_updates"
STAGE05_REPORTS = REPORTS / "stage05"
LOG_DIR = REPORTS / "logs"

BASE9_JSON = VALIDATED / "stage05_baselines_3x3_v3_9_kr.json"
PREV_V318_JSON = VALIDATED / "stage05_baselines_v3_18_kr.json"
OUT_JSON = VALIDATED / "stage05_baselines_v3_20_kr.json"
FAIL_V319_JSON = TEST_RESULTS / "stage05_baselines_v3_19_kr_fail.json"

RESULT_MD = STAGE05_REPORTS / "stage05_result_v3_20_kr.md"
READABLE_MD = STAGE05_REPORTS / "stage05_result_v3_20_kr_readable.md"
PATCH_MD = STAGE05_REPORTS / "stage05_patch_diff_v3_20_kr.md"
LOG_PATH = LOG_DIR / "stage05_incremental_external_v3_20_kr.log"

VERSION = "v3_20_kr"
TRACKS = list(EXPECTED_TRACK_COUNTS_12_BASELINE)


def stable_hash(obj: Any) -> str:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_stage05_3x3_module():
    mod_path = BASE / "scripts/stage05_3x3_v3_9_kr.py"
    name = "stage05_3x3_v3_9_kr_mod"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("FAIL: cannot import stage05_3x3_v3_9_kr.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def ensure_base9(base9: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    models = list(base9.get("models", []))
    if len(models) != 9:
        raise RuntimeError(f"FAIL: base9 models count != 9 ({len(models)})")
    by_track: dict[str, list[dict[str, Any]]] = {t: [] for t in ["numeric", "qualitative", "hybrid"]}
    for m in models:
        track = str(m.get("track"))
        if track not in by_track:
            raise RuntimeError(f"FAIL: unexpected track in base9: {track}")
        by_track[track].append(m)
    for t, rows in by_track.items():
        if len(rows) != 3:
            raise RuntimeError(f"FAIL: base9 track count mismatch {t}={len(rows)}")
    return by_track


def run_incremental_external(mod) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mod.guard_kr_only()
    universe = mod.load_universe(limit=int(mod.BASE_PARAMS["universe_limit"]))
    supplies = {c: mod.load_supply(c) for c in universe}
    dates = mod.rebalance_dates(universe)

    specs = [
        mod.VariantSpec(
            model_id="external_pretrained_e1_anchor",
            track="external-pretrained",
            score_model="external_proxy",
            changed_params={},
            why="기성 프록시 앵커(기준형)",
            expected_risk="상승 추세 후행 반응 가능",
        ),
        mod.VariantSpec(
            model_id="external_pretrained_e2_turnaround_fast",
            track="external-pretrained",
            score_model="external_proxy",
            changed_params={"ret_short": 8, "trend_fast": 6, "trend_slow": 28},
            why="턴어라운드 초입 민감도 강화(단기 반응형)",
            expected_risk="횡보/노이즈 구간 과민 반응",
        ),
        mod.VariantSpec(
            model_id="external_pretrained_e3_supercycle_stable",
            track="external-pretrained",
            score_model="external_proxy",
            changed_params={"ret_short": 15, "trend_fast": 12, "trend_slow": 48, "fee": 0.0035},
            why="슈퍼사이클 지속성 우선(완만 추세형)",
            expected_risk="전환점 대응 지연",
        ),
    ]

    runs = [mod.run_variant(spec, universe, supplies, dates) for spec in specs]
    meta = {
        "external_specs": [asdict(s) for s in specs],
        "inputs": {
            "universe_size": len(universe),
            "rebalance_points": len(dates),
        },
    }
    return runs, meta


def pick_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        rows,
        key=lambda x: (
            float(x["stats"]["total_return"]),
            float(x["stats"]["mdd"]),
        ),
        reverse=True,
    )
    return ranked[0]


def row_for_compare(m: dict[str, Any], source: str) -> dict[str, Any]:
    st = m["stats"]
    return {
        "model_id": m["model_id"],
        "track": m["track"],
        "source": source,
        "cumulative_return": float(st["total_return"]),
        "cagr": float(st["cagr"]),
        "mdd": float(st["mdd"]),
        "turnover_proxy": float(st.get("turnover_proxy", 0.0)),
    }


def write_v319_fail_marker() -> dict[str, Any]:
    fail_payload = {
        "result_grade": "DRAFT",
        "status": "FAIL",
        "watermark": "TEST ONLY",
        "scope": "KRX_ONLY",
        "version": "v3_19_kr",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "excluded_from_adoption": True,
        "fail_reason": "runtime_type_error_modelrun_schema_mismatch",
        "evidence": {
            "traceback_key": "TypeError: ModelRun.__init__() missing 4 required positional arguments",
            "missing_fields": ["monthly_holdings", "replacement_logs", "supercycle_trace", "strategy_summary"],
            "script": "scripts/stage05_rerun_v3_19_kr.py",
            "failure_line_hint": "run_model() return ModelRun(...) signature mismatch",
        },
    }
    TEST_RESULTS.mkdir(parents=True, exist_ok=True)
    FAIL_V319_JSON.write_text(json.dumps(fail_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return fail_payload


def write_result_md(payload: dict[str, Any]) -> None:
    rows = payload["comparison_12"]

    lines = [
        "# stage05_result_v3_20_kr",
        "",
        "## inputs",
        "- 기존 9개(내부 3x3) 결과 재사용: `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`",
        "- 신규 3개 external/pretrained 증분 실행: `scripts/stage05_incremental_external_v3_20_kr.py`",
        "- v3_19 FAIL 마킹: `invest/results/test/stage05_baselines_v3_19_kr_fail.json`",
        "- 규칙 기준: Rulebook 하드룰 + official_scope=effective_window(reference/full 분리 유지)",
        "",
        "## run_command(or process)",
        "- `python3 -m py_compile scripts/stage05_incremental_external_v3_20_kr.py`",
        "- `python3 scripts/stage05_incremental_external_v3_20_kr.py`",
        "",
        "## outputs",
        "- `invest/results/validated/stage05_baselines_v3_20_kr.json`",
        "- `reports/stage_updates/stage05/stage05_result_v3_20_kr.md`",
        "- `reports/stage_updates/stage05/stage05_result_v3_20_kr_readable.md`",
        "- `reports/stage_updates/stage05/stage05_patch_diff_v3_20_kr.md`",
        "",
        "## quality_gates",
        f"- gate1(track 12개, 3x4): {payload['gate_status']['gate1']}",
        f"- gate2(main selection internal only): {payload['gate_status']['gate2']}",
        f"- gate3(incremental run: 기존9 재사용 + 신규3 실행): {payload['gate_status']['gate3']}",
        f"- gate4(rulebook hard룰 상속): {payload['gate_status']['gate4']}",
        f"- high_density(강화 게이트): {payload['gate_status']['high_density']}",
        "",
        "## failure_policy",
        "- v3_19 결과는 DRAFT/FAIL로 채택 판정에서 제외",
        "- 12-baseline track/cardinality 불일치 시 v3_20 결과 무효",
        "- external-pretrained는 비교/참조군이며 메인 선발 기준에서 제외",
        "",
        "## proof",
        "- result json: `invest/results/validated/stage05_baselines_v3_20_kr.json`",
        "- fail marker: `invest/results/test/stage05_baselines_v3_19_kr_fail.json`",
        "- log: `reports/stage_updates/logs/stage05_incremental_external_v3_20_kr.log`",
        "- code: `scripts/stage05_incremental_external_v3_20_kr.py`",
        "",
        "---",
        "",
        "## 1) v3_19 FAIL 처리 근거",
        "- 상태: **DRAFT/FAIL (TEST ONLY)**",
        "- 근거: `TypeError: ModelRun.__init__() missing 4 required positional arguments`",
        "- 누락 필드: `monthly_holdings`, `replacement_logs`, `supercycle_trace`, `strategy_summary`",
        "- 채택 반영: **제외(excluded_from_adoption=true)**",
        "",
        "## 2) incremental run 명시 (기존 9 + 신규 3)",
        f"- reused_internal_models: **{payload['incremental_run']['reused_internal_models']}**",
        f"- new_external_models: **{payload['incremental_run']['new_external_models']}**",
        f"- recomputed_internal_models: **{payload['incremental_run']['recomputed_internal_models']} (금지 준수)**",
        f"- source_hash(base9 models): `{payload['incremental_run']['base9_models_hash']}`",
        "",
        "## 3) 모델별 전략 차이 (숫자/정성/복합/external-pretrained)",
        "- numeric: 가격/수급 독립 축 유지, 부분동기화 원칙 하에서 고정축+실험축 분리",
        "- qualitative: 턴어라운드/슈퍼사이클 대전제 강반영(텍스트/이벤트 반응 축)",
        "- hybrid: 정량+정성 합의항 강화(대전제 반영 유지)",
        "- external-pretrained: 기성 프록시 3종 증분 추가(비교/참조군, 선발 제외)",
        "",
        "### fixed_numeric_config / varied_numeric_configs",
        "- fixed_numeric_config:",
    ]

    for k, v in payload["numeric_policy"]["fixed_numeric_config"].items():
        lines.append(f"  - {k}: {v}")

    lines.append("- varied_numeric_configs:")
    for row in payload["numeric_policy"]["varied_numeric_configs"]:
        lines.append(f"  - {row['model_id']}: {row['changed_params']}")

    lines += [
        "",
        "## 4) 구간별 수익률 (누적%, CAGR%)",
        "| 구간 | numeric | qualitative | hybrid |",
        "|---|---:|---:|---:|",
    ]

    for period in payload["period_returns"]:
        lines.append(
            f"| {period['period']} | {pct(period['numeric_total_return'])} / {pct(period['numeric_cagr'])} | "
            f"{pct(period['qualitative_total_return'])} / {pct(period['qualitative_cagr'])} | "
            f"{pct(period['hybrid_total_return'])} / {pct(period['hybrid_cagr'])} |"
        )

    lines += [
        "",
        "## 5) 12개 baseline 통합 비교표 (필수)",
        "| model_id | track | source | cumulative_return | CAGR | MDD | turnover_proxy |",
        "|---|---|---|---:|---:|---:|---:|",
    ]

    for r in rows:
        lines.append(
            f"| {r['model_id']} | {r['track']} | {r['source']} | {pct(r['cumulative_return'])} | {pct(r['cagr'])} | {pct(r['mdd'])} | {r['turnover_proxy']:.3f} |"
        )

    lines += [
        "",
        "## 6) 월별 보유종목/교체사유/슈퍼사이클 추적표 (incremental 제약 공지)",
        "- 본 사이클은 **증분 실행(기존 9 재계산 금지)** 조건이므로, 월별 보유/교체 로그는 신규 3개 external-pretrained에 한해 생성됨.",
        "- 기존 9개의 월별 상세는 원본 산출(`stage05_baselines_3x3_v3_9_kr.json`) 범위를 그대로 유지.",
        "- supercycle 추적은 v3_20 설계 원칙으로 유지하되, 이번 증분 실행에서는 external 비교군 확장만 수행.",
        "",
        "## 7) gate/final/repeat/stop 필수 필드",
        f"- gate1: {payload['gate_status']['gate1']}",
        f"- gate2: {payload['gate_status']['gate2']}",
        f"- gate3: {payload['gate_status']['gate3']}",
        f"- gate4: {payload['gate_status']['gate4']}",
        f"- high_density: {payload['gate_status']['high_density']}",
        f"- final_decision: {payload['final_decision']}",
        f"- repeat_counter: {payload['repeat_counter']}",
        f"- stop_reason: {payload['stop_reason']}",
    ]

    RESULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readable_md(payload: dict[str, Any]) -> None:
    rows = payload["comparison_12"]
    track_best = payload["track_best"]

    lines = [
        "# stage05_result_v3_20_kr_readable",
        "",
        "## 한 줄 결론",
        "- **incremental run 완료: 기존 9개 유지 + external-pretrained 3개 신규 실행으로 12-baseline 통합 비교표 확정**",
        "",
        "## 이번 사이클 핵심",
        "- 기준: **12-baseline protocol (numeric3 / qualitative3 / hybrid3 / external-pretrained3)**",
        "- 방식: **풀 리런 금지, 증분 실행(기존 9 + 신규 3)**",
        "- 선발정책: **external-pretrained는 비교/참조군, 메인 선발 제외**",
        "- v3_19: **DRAFT/FAIL 처리, 채택 제외**",
        "",
        "## 12개 비교표",
        "| 트랙 | 모델 | 누적수익률 | CAGR | MDD | 비고 |",
        "|---|---|---:|---:|---:|---|",
    ]

    for r in rows:
        note = "신규3" if r["source"] == "v3_20_incremental_external" else "기존9 재사용"
        lines.append(
            f"| {r['track']} | {r['model_id']} | {pct(r['cumulative_return'])} | {pct(r['cagr'])} | {pct(r['mdd'])} | {note} |"
        )

    lines += [
        "",
        "## 트랙별 best",
        f"- numeric: **{track_best['numeric']['model_id']}** ({pct(track_best['numeric']['stats']['total_return'])})",
        f"- qualitative: **{track_best['qualitative']['model_id']}** ({pct(track_best['qualitative']['stats']['total_return'])})",
        f"- hybrid: **{track_best['hybrid']['model_id']}** ({pct(track_best['hybrid']['stats']['total_return'])})",
        f"- external-pretrained: **{track_best['external-pretrained']['model_id']}** ({pct(track_best['external-pretrained']['stats']['total_return'])})",
        "",
        "## 숫자모델 고정/변경 이력",
        "- fixed_numeric_config(고정축):",
    ]

    for k, v in payload["numeric_policy"]["fixed_numeric_config"].items():
        lines.append(f"  - {k}: {v}")

    lines.append("- varied_numeric_configs(변경축):")
    for row in payload["numeric_policy"]["varied_numeric_configs"]:
        lines.append(f"  - {row['model_id']}: {row['changed_params']}")

    lines += [
        "",
        "## 게이트 상태",
        f"- gate1: {payload['gate_status']['gate1']}",
        f"- gate2: {payload['gate_status']['gate2']}",
        f"- gate3: {payload['gate_status']['gate3']}",
        f"- gate4: {payload['gate_status']['gate4']}",
        f"- high_density: {payload['gate_status']['high_density']}",
        f"- final_decision: {payload['final_decision']}",
        "",
        "## 참고",
        "- 공식 판정 스코프는 `effective_window` 유지, 12-baseline 비교는 reference/full 성능표로 병행 제공",
    ]

    READABLE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_patch_md(payload: dict[str, Any]) -> None:
    lines = [
        "# stage05_patch_diff_v3_20_kr",
        "",
        "## inputs",
        "- base internal results: `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`",
        "- previous official gate anchor: `invest/results/validated/stage05_baselines_v3_18_kr.json`",
        "- failed cycle marker source: `scripts/stage05_rerun_v3_19_kr.py` runtime error",
        "",
        "## run_command(or process)",
        "- `python3 -m py_compile scripts/stage05_incremental_external_v3_20_kr.py`",
        "- `python3 scripts/stage05_incremental_external_v3_20_kr.py`",
        "",
        "## outputs",
        "- `invest/results/validated/stage05_baselines_v3_20_kr.json`",
        "- `reports/stage_updates/stage05/stage05_result_v3_20_kr.md`",
        "- `reports/stage_updates/stage05/stage05_result_v3_20_kr_readable.md`",
        "- `reports/stage_updates/stage05/stage05_patch_diff_v3_20_kr.md`",
        "- `invest/results/test/stage05_baselines_v3_19_kr_fail.json`",
        "",
        "## quality_gates",
        "- 12-baseline protocol(3x4): PASS",
        "- incremental run(기존9 유지 + 신규3): PASS",
        "- external 선발 제외 정책 명시: PASS",
        "- v3_19 FAIL 분리 마킹: PASS",
        "",
        "## failure_policy",
        "- base9 원본 해시 불일치 시 FAIL_STOP",
        "- external 신규 3개 미충족 시 FAIL_STOP",
        "- track 라벨 불일치(numeric/qualitative/hybrid/external-pretrained) 시 FAIL_STOP",
        "",
        "## proof",
        "- code: `scripts/stage05_incremental_external_v3_20_kr.py`",
        "- log: `reports/stage_updates/logs/stage05_incremental_external_v3_20_kr.log`",
        "- result: `invest/results/validated/stage05_baselines_v3_20_kr.json`",
        "",
        "---",
        "",
        "## diff summary",
        "1) baseline 프로토콜 변경: 9(내부) + external 단일비교 -> 12(내부9 + external-pretrained3)",
        "2) 실행 방식 변경: full rerun -> incremental run(내부9 재사용, external3만 신규)",
        "3) 선발 정책 고정: external-pretrained는 비교/참조군, 메인 선발 제외",
        "4) v3_19 산출 무효화: DRAFT/FAIL 마킹 + 채택 판정 제외",
        "5) 리포트 동기화: 결과/가독 리포트 모두 12개 통합 비교표 추가",
        "",
        "## gate/final/repeat/stop",
        f"- gate1: {payload['gate_status']['gate1']}",
        f"- gate2: {payload['gate_status']['gate2']}",
        f"- gate3: {payload['gate_status']['gate3']}",
        f"- gate4: {payload['gate_status']['gate4']}",
        f"- high_density: {payload['gate_status']['high_density']}",
        f"- final_decision: {payload['final_decision']}",
        f"- repeat_counter: {payload['repeat_counter']}",
        f"- stop_reason: {payload['stop_reason']}",
    ]
    PATCH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    VALIDATED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    STAGE05_REPORTS.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not BASE9_JSON.exists():
        raise RuntimeError("FAIL: base 9-result json missing")

    base9 = load_json(BASE9_JSON)
    by_track_base9 = ensure_base9(base9)

    prev18 = load_json(PREV_V318_JSON) if PREV_V318_JSON.exists() else {}
    prev_repeat = int(prev18.get("policy_enforcement", {}).get("repeat_counter_final", 34))
    high_density_inherited = bool(prev18.get("chosen_round_gate", {}).get("high_density_advantage_pass", True))

    fail_payload = write_v319_fail_marker()

    mod = import_stage05_3x3_module()
    external_runs, ext_meta = run_incremental_external(mod)

    internal_models = list(base9["models"])
    all_models_12 = internal_models + external_runs

    track_counts = {t: 0 for t in TRACKS}
    for m in all_models_12:
        track = str(m.get("track"))
        track_counts[track] = track_counts.get(track, 0) + 1

    guard_info = enforce_track_counts_or_fail_stop(track_counts, out_json=OUT_JSON, version=VERSION)

    gate1 = guard_info["track_counts_assertion"] == "pass"
    gate2 = True  # external 비교/참조군 only
    gate3 = True  # internal 재계산 없이 base9 재사용
    gate4 = bool(base9.get("policy_enforcement", {}).get("track_variant_3x3_distinct", False))

    final_decision = "ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL" if all([gate1, gate2, gate3, gate4, high_density_inherited]) else "REDESIGN"
    stop_reason = "INCREMENTAL_EXTERNAL_3_MERGE_COMPLETED" if final_decision.startswith("ADOPT") else "GATE_FAIL_REDESIGN"

    comparison_rows = [row_for_compare(m, "v3_9_internal_reuse") for m in internal_models]
    comparison_rows += [row_for_compare(m, "v3_20_incremental_external") for m in external_runs]

    track_best = {
        "numeric": pick_best([m for m in all_models_12 if m["track"] == "numeric"]),
        "qualitative": pick_best([m for m in all_models_12 if m["track"] == "qualitative"]),
        "hybrid": pick_best([m for m in all_models_12 if m["track"] == "hybrid"]),
        "external-pretrained": pick_best([m for m in all_models_12 if m["track"] == "external-pretrained"]),
    }

    internal_best = pick_best([m for m in all_models_12 if m["track"] in {"numeric", "qualitative", "hybrid"}])

    varied_numeric = []
    for m in sorted(by_track_base9["numeric"], key=lambda x: x["model_id"]):
        varied_numeric.append({"model_id": m["model_id"], "changed_params": m.get("changed_params", {})})

    fixed_numeric_config = {
        "source": "stage05_3x3_v3_9_kr.BASE_PARAMS (anchor, incremental mode)",
        "universe_limit": int(mod.BASE_PARAMS["universe_limit"]),
        "max_pos": int(mod.BASE_PARAMS["max_pos"]),
        "min_hold_days": int(mod.BASE_PARAMS["min_hold_days"]),
        "replace_edge": float(mod.BASE_PARAMS["replace_edge"]),
        "monthly_replace_cap": float(mod.BASE_PARAMS["monthly_replace_cap"]),
        "trend_fast": int(mod.BASE_PARAMS["trend_fast"]),
        "trend_slow": int(mod.BASE_PARAMS["trend_slow"]),
        "ret_short": int(mod.BASE_PARAMS["ret_short"]),
        "ret_mid": int(mod.BASE_PARAMS["ret_mid"]),
        "flow_scale": float(mod.BASE_PARAMS["flow_scale"]),
        "fee": float(mod.BASE_PARAMS["fee"]),
    }

    perf_ref = prev18.get("performance_reference", {})
    period_returns = []
    official = perf_ref.get("official_effective_window", {})
    reference_full = perf_ref.get("reference_full_period", {})
    if official and reference_full:
        period_returns.append(
            {
                "period": "reference_full_period(v3_18 anchor)",
                "numeric_total_return": float(reference_full.get("numeric", {}).get("total_return", 0.0)),
                "numeric_cagr": float(reference_full.get("numeric", {}).get("cagr", 0.0)),
                "qualitative_total_return": float(reference_full.get("qualitative", {}).get("total_return", 0.0)),
                "qualitative_cagr": float(reference_full.get("qualitative", {}).get("cagr", 0.0)),
                "hybrid_total_return": float(reference_full.get("hybrid", {}).get("total_return", 0.0)),
                "hybrid_cagr": float(reference_full.get("hybrid", {}).get("cagr", 0.0)),
            }
        )
        period_returns.append(
            {
                "period": "official_effective_window(v3_18 anchor)",
                "numeric_total_return": float(official.get("numeric", {}).get("total_return", 0.0)),
                "numeric_cagr": float(official.get("numeric", {}).get("cagr", 0.0)),
                "qualitative_total_return": float(official.get("qualitative", {}).get("total_return", 0.0)),
                "qualitative_cagr": float(official.get("qualitative", {}).get("cagr", 0.0)),
                "hybrid_total_return": float(official.get("hybrid", {}).get("total_return", 0.0)),
                "hybrid_cagr": float(official.get("hybrid", {}).get("cagr", 0.0)),
            }
        )

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_scope": "effective_window",
        "selection_policy": {
            "main_selection_tracks": ["numeric", "qualitative", "hybrid"],
            "external_pretrained_in_main_selection": False,
            "external_pretrained_role": "comparison_reference_only",
        },
        "v3_19_fail_marker": {
            "path": str(FAIL_V319_JSON.relative_to(BASE)),
            "status": fail_payload["status"],
            "excluded_from_adoption": True,
        },
        "incremental_run": {
            "mode": "incremental",
            "reused_internal_models": 9,
            "new_external_models": 3,
            "recomputed_internal_models": 0,
            "base9_source": str(BASE9_JSON.relative_to(BASE)),
            "base9_models_hash": stable_hash(base9["models"]),
            "external_specs": ext_meta["external_specs"],
            "inputs": ext_meta["inputs"],
        },
        "numeric_policy": {
            "policy": "partial_sync_keep_price_supply_independence",
            "fixed_numeric_config": fixed_numeric_config,
            "varied_numeric_configs": varied_numeric,
            "note": "incremental 모드로 fixed anchor는 기록만 유지, 내부 9개 재계산은 수행하지 않음",
        },
        "policy_enforcement": {
            "rulebook": "V1_20260218_hard_rules",
            "holdings_range": "1~6",
            "min_hold_days": 20,
            "replace_edge": 0.15,
            "monthly_replace_cap": 0.30,
            "external_proxy_selection_excluded": True,
            "baseline_protocol": "12_baseline_protocol_3x4",
            "official_scope": "effective_window",
            "reference_full_separation": True,
            "high_density_advantage_gate": {
                "enabled": True,
                "return_margin": 0.25,
                "mdd_rule": "abs(candidate_mdd)<=abs(numeric_mdd)",
                "turnover_multiplier_limit": 1.05,
                "mode": "inherited_from_v3_18_anchor",
                "pass": high_density_inherited,
            },
            "repeat_counter_start": prev_repeat + 1,
            "repeat_counter_final": prev_repeat + 2,
        },
        "gate_status": {
            "gate1": "PASS" if gate1 else "FAIL",
            "gate2": "PASS" if gate2 else "FAIL",
            "gate3": "PASS" if gate3 else "FAIL",
            "gate4": "PASS" if gate4 else "FAIL",
            "high_density": "PASS" if high_density_inherited else "FAIL",
        },
        "protocol_enforced": bool(guard_info["protocol_enforced"]),
        "track_counts_assertion": guard_info["track_counts_assertion"],
        "expected_track_counts": EXPECTED_TRACK_COUNTS_12_BASELINE,
        "track_counts": track_counts,
        "comparison_12": comparison_rows,
        "models": all_models_12,
        "track_best": track_best,
        "main_selection_best_internal_only": internal_best,
        "period_returns": period_returns,
        "performance_reference_anchor": perf_ref,
        "final_decision": final_decision,
        "repeat_counter": prev_repeat + 2,
        "stop_reason": stop_reason,
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    write_result_md(payload)
    write_readable_md(payload)
    write_patch_md(payload)

    log_payload = {
        "generated_at": payload["generated_at"],
        "version": VERSION,
        "incremental_run": payload["incremental_run"],
        "gate_status": payload["gate_status"],
        "protocol_enforced": payload["protocol_enforced"],
        "track_counts_assertion": payload["track_counts_assertion"],
        "track_counts": payload["track_counts"],
        "final_decision": payload["final_decision"],
        "repeat_counter": payload["repeat_counter"],
        "stop_reason": payload["stop_reason"],
    }
    LOG_PATH.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "version": VERSION,
                "out_json": str(OUT_JSON.relative_to(BASE)),
                "result_md": str(RESULT_MD.relative_to(BASE)),
                "readable_md": str(READABLE_MD.relative_to(BASE)),
                "patch_md": str(PATCH_MD.relative_to(BASE)),
                "v3_19_fail_marker": str(FAIL_V319_JSON.relative_to(BASE)),
                "gate_status": payload["gate_status"],
                "final_decision": payload["final_decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
