#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
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
RAW_TEXT = BASE / "invest/data/raw/text"

BASE9_JSON = VALIDATED / "stage05_baselines_3x3_v3_9_kr.json"
PREV_V320_JSON = VALIDATED / "stage05_baselines_v3_20_kr.json"
OUT_JSON = VALIDATED / "stage05_baselines_v3_21_kr.json"
FAIL_V319_JSON = TEST_RESULTS / "stage05_baselines_v3_19_kr_fail.json"

RESULT_MD = STAGE05_REPORTS / "stage05_result_v3_21_kr.md"
READABLE_MD = STAGE05_REPORTS / "stage05_result_v3_21_kr_readable.md"
PATCH_MD = STAGE05_REPORTS / "stage05_patch_diff_v3_21_kr.md"
LOG_PATH = LOG_DIR / "stage05_incremental_external_v3_21_kr.log"

VERSION = "v3_21_kr"
TRACKS = list(EXPECTED_TRACK_COUNTS_12_BASELINE)
INTERNAL_TRACKS = ["numeric", "qualitative", "hybrid"]

OFFICIAL_START_YEAR = 2021
CORE_START_YEAR = 2023
CORE_END_YEAR = 2025
REFERENCE_START_YEAR = 2016
LEGACY_END_YEAR = 2020

EPSILON = 0.005
CORE_WEIGHT = 0.55
OFFICIAL_WEIGHT = 0.40
LEGACY_LOW_WEIGHT = 0.05

YEAR_RE = re.compile(r"^Date:\s*([12][0-9]{3})", flags=re.MULTILINE)
DATE_FALLBACK_RE = re.compile(r"\b([12][0-9]{3})[.-]\s*[01]?[0-9][.-]\s*[0-3]?[0-9]")


def stable_hash(obj: Any) -> str:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_stage05_3x3_module():
    mod_path = BASE / "invest/scripts/stage05_3x3_v3_9_kr.py"
    name = "stage05_3x3_v3_9_kr_mod_v321"
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
    by_track: dict[str, list[dict[str, Any]]] = {t: [] for t in INTERNAL_TRACKS}
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


def extract_year_from_md(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = [next(f, "") for _ in range(30)]
    except Exception:
        return None
    text = "\n".join(lines)

    m = YEAR_RE.search(text)
    if not m:
        m = DATE_FALLBACK_RE.search(text)
    if not m:
        return None
    y = int(m.group(1))
    if 2010 <= y <= 2030:
        return y
    return None


def load_text_filter_pass_counts() -> dict[str, Any]:
    years = list(range(REFERENCE_START_YEAR, datetime.now().year + 1))
    blog = {y: 0 for y in years}
    telegram = {y: 0 for y in years}

    for fp in (RAW_TEXT / "blog").glob("**/*.md"):
        y = extract_year_from_md(fp)
        if y in blog:
            blog[y] += 1

    for fp in (RAW_TEXT / "telegram").glob("*.md"):
        y = extract_year_from_md(fp)
        if y in telegram:
            telegram[y] += 1

    combined = {
        str(y): {
            "blog_filter_pass_count": int(blog.get(y, 0)),
            "telegram_filter_pass_count": int(telegram.get(y, 0)),
            "combined_filter_pass_count": int(blog.get(y, 0) + telegram.get(y, 0)),
        }
        for y in years
    }
    return {
        "range": {"start": years[0] if years else REFERENCE_START_YEAR, "end": years[-1] if years else REFERENCE_START_YEAR},
        "counts_by_year": combined,
    }


def normalize_annual_map(annual_returns: dict[Any, Any]) -> dict[int, float]:
    out: dict[int, float] = {}
    for k, v in annual_returns.items():
        try:
            out[int(k)] = float(v)
        except Exception:
            continue
    return out


def period_metrics_from_annual(
    annual_returns: dict[Any, Any],
    start_year: int,
    end_year: int | None = None,
) -> dict[str, Any]:
    annual = normalize_annual_map(annual_returns)
    years = sorted(y for y in annual if y >= start_year and (end_year is None or y <= end_year))
    if not years:
        return {
            "start_year": start_year,
            "end_year": end_year,
            "years": [],
            "samples": 0,
            "total_return": 0.0,
            "cagr": 0.0,
            "asset_multiple": 1.0,
            "mdd": 0.0,
        }

    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for y in years:
        eq *= 1.0 + float(annual[y])
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)

    samples = len(years)
    cagr = float(eq ** (1.0 / samples) - 1.0) if samples > 0 and eq > 0 else -1.0
    return {
        "start_year": start_year,
        "end_year": end_year,
        "years": years,
        "samples": samples,
        "total_return": float(eq - 1.0),
        "cagr": cagr,
        "asset_multiple": float(eq),
        "mdd": float(mdd),
    }


def build_track_period_metrics(track_best_internal: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for track, model in track_best_internal.items():
        annual = model.get("annual_returns", {})
        out[track] = {
            "core_2023_2025": period_metrics_from_annual(annual, CORE_START_YEAR, CORE_END_YEAR),
            "official_2021_plus": period_metrics_from_annual(annual, OFFICIAL_START_YEAR, None),
            "reference_2016_plus": period_metrics_from_annual(annual, REFERENCE_START_YEAR, None),
            "legacy_2016_2020_low_weight": period_metrics_from_annual(annual, REFERENCE_START_YEAR, LEGACY_END_YEAR),
        }
    return out


def weighted_score(periods: dict[str, Any]) -> float:
    core = float(periods["core_2023_2025"]["total_return"])
    official = float(periods["official_2021_plus"]["total_return"])
    legacy = float(periods["legacy_2016_2020_low_weight"]["total_return"])
    return CORE_WEIGHT * core + OFFICIAL_WEIGHT * official + LEGACY_LOW_WEIGHT * legacy


def write_result_md(payload: dict[str, Any]) -> None:
    rows = payload["comparison_12"]
    gate = payload["gate_status"]
    track_periods = payload["track_period_metrics"]
    text_counts = payload["text_filter_pass_counts_by_year"]["counts_by_year"]

    lines = [
        "# stage05_result_v3_21_kr",
        "",
        "## inputs",
        "- 기존 9개(내부 3x3) 결과 재사용: `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`",
        "- 신규 3개 external/pretrained 증분 실행: `invest/scripts/stage05_incremental_external_v3_21_kr.py`",
        "- v3_19 FAIL 마킹 재확인: `invest/results/test/stage05_baselines_v3_19_kr_fail.json`",
        "- 정책 반영: official_scope=2021~현재, core_high_density=2023~2025(가중), legacy(2016~2020)=reference/low-weight",
        "",
        "## run_command(or process)",
        "- `python3 -m py_compile invest/scripts/stage05_incremental_external_v3_21_kr.py`",
        "- `python3 invest/scripts/stage05_incremental_external_v3_21_kr.py`",
        "",
        "## outputs",
        "- `invest/results/validated/stage05_baselines_v3_21_kr.json`",
        "- `reports/stage_updates/stage05/stage05_result_v3_21_kr.md`",
        "- `reports/stage_updates/stage05/stage05_result_v3_21_kr_readable.md`",
        "- `reports/stage_updates/stage05/stage05_patch_diff_v3_21_kr.md`",
        "",
        "## quality_gates",
        f"- gate1(track 12개, 3x4): {gate['gate1']}",
        f"- gate2(official+core weighted internal selection): {gate['gate2']}",
        f"- gate3(official/core sample coverage): {gate['gate3']}",
        f"- gate4(rulebook hard룰 고정): {gate['gate4']}",
        f"- high_density(+25%p/MDD/turnover): {gate['high_density']}",
        "",
        "## failure_policy",
        "- gate1~4/high_density 중 1개라도 FAIL이면 최종결정은 REDESIGN",
        "- external-pretrained는 비교/참조군이며 메인 선발 기준에서 제외",
        "- v3_19 결과(DRAFT/FAIL)는 채택 판정에서 제외",
        "",
        "## proof",
        "- result json: `invest/results/validated/stage05_baselines_v3_21_kr.json`",
        "- log: `reports/stage_updates/logs/stage05_incremental_external_v3_21_kr.log`",
        "- code: `invest/scripts/stage05_incremental_external_v3_21_kr.py`",
        "",
        "---",
        "",
        "## 1) 필수 구간 성과 (누적/CAGR)",
        "| 구간 | numeric | qualitative | hybrid |",
        "|---|---:|---:|---:|",
    ]

    for key, label in [
        ("core_2023_2025", "3년 core(2023~2025)"),
        ("official_2021_plus", "공식 official(2021~현재)"),
        ("reference_2016_plus", "참고 reference(2016~현재)"),
    ]:
        n = track_periods["numeric"][key]
        q = track_periods["qualitative"][key]
        h = track_periods["hybrid"][key]
        lines.append(
            f"| {label} | {pct(float(n['total_return']))} / {pct(float(n['cagr']))} | "
            f"{pct(float(q['total_return']))} / {pct(float(q['cagr']))} | "
            f"{pct(float(h['total_return']))} / {pct(float(h['cagr']))} |"
        )

    lines += [
        "",
        "## 2) gate/final/repeat/stop 필수 필드",
        f"- gate1: {gate['gate1']}",
        f"- gate2: {gate['gate2']}",
        f"- gate3: {gate['gate3']}",
        f"- gate4: {gate['gate4']}",
        f"- high_density: {gate['high_density']}",
        f"- final_decision: {payload['final_decision']}",
        f"- repeat_counter: {payload['repeat_counter']}",
        f"- stop_reason: {payload['stop_reason']}",
        "",
        "## 3) 연도별 텔레그램/블로그 필터통과 데이터 카운트",
        "| 연도 | telegram_filter_pass | blog_filter_pass | combined |",
        "|---:|---:|---:|---:|",
    ]

    for y in sorted(text_counts.keys()):
        row = text_counts[y]
        lines.append(
            f"| {y} | {int(row['telegram_filter_pass_count'])} | {int(row['blog_filter_pass_count'])} | {int(row['combined_filter_pass_count'])} |"
        )

    lines += [
        "",
        "## 4) 12개 baseline 통합 비교표",
        "| model_id | track | source | cumulative_return | CAGR | MDD | turnover_proxy |",
        "|---|---|---|---:|---:|---:|---:|",
    ]

    for r in rows:
        lines.append(
            f"| {r['model_id']} | {r['track']} | {r['source']} | {pct(r['cumulative_return'])} | {pct(r['cagr'])} | {pct(r['mdd'])} | {r['turnover_proxy']:.3f} |"
        )

    lines += [
        "",
        "## 5) 핵심 가중(2023~) 반영 상세",
        f"- weighted_score = core*{CORE_WEIGHT:.2f} + official*{OFFICIAL_WEIGHT:.2f} + legacy*{LEGACY_LOW_WEIGHT:.2f}",
        f"- gate2_non_numeric_candidate: {payload['gate_detail']['gate2']['non_numeric_candidate']}",
        f"- gate2_reason: {payload['gate_detail']['gate2']['reason']}",
        f"- high_density_candidate: {payload['gate_detail']['high_density']['winner_candidate']}",
    ]

    RESULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readable_md(payload: dict[str, Any]) -> None:
    gate = payload["gate_status"]
    track_periods = payload["track_period_metrics"]

    lines = [
        "# stage05_result_v3_21_kr_readable",
        "",
        "## 한 줄 결론",
        f"- **{payload['final_decision']}** (official=2021~, core=2023~2025 가중 평가 반영)",
        "",
        "## 이번 변경 포인트",
        "- v3_20 체계/12-baseline 유지 + 증분 실행(기존9 재사용, external3 신규)",
        "- 공식 평가구간을 2021~현재로 상향",
        "- 2023~2025 core band를 가중(필수) 반영",
        "- 2016~2020은 reference/저가중으로 분리",
        "",
        "## 필수 수익률 요약 (누적/CAGR)",
        "| 구간 | numeric | qualitative | hybrid |",
        "|---|---:|---:|---:|",
    ]

    for key, label in [
        ("core_2023_2025", "3년 core(2023~2025)"),
        ("official_2021_plus", "공식 official(2021~현재)"),
        ("reference_2016_plus", "참고 reference(2016~현재)"),
    ]:
        n = track_periods["numeric"][key]
        q = track_periods["qualitative"][key]
        h = track_periods["hybrid"][key]
        lines.append(
            f"| {label} | {pct(float(n['total_return']))} / {pct(float(n['cagr']))} | "
            f"{pct(float(q['total_return']))} / {pct(float(q['cagr']))} | "
            f"{pct(float(h['total_return']))} / {pct(float(h['cagr']))} |"
        )

    lines += [
        "",
        "## gate 상태",
        f"- gate1: {gate['gate1']}",
        f"- gate2: {gate['gate2']}",
        f"- gate3: {gate['gate3']}",
        f"- gate4: {gate['gate4']}",
        f"- high_density: {gate['high_density']}",
        f"- final_decision: {payload['final_decision']}",
        f"- repeat_counter: {payload['repeat_counter']}",
        f"- stop_reason: {payload['stop_reason']}",
    ]

    READABLE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_patch_md(payload: dict[str, Any]) -> None:
    gate = payload["gate_status"]
    lines = [
        "# stage05_patch_diff_v3_21_kr",
        "",
        "## 변경 요약",
        "1) official_scope를 `effective_window` -> `official_2021_plus`로 상향",
        "2) core high-density 구간을 `2023~2025`로 명시하고 가중 평가 반영",
        "3) 2016~2020 구간은 reference/저가중으로 분리",
        "4) v3_20 incremental 12-baseline 실행 구조 유지(기존9 재사용 + 신규3 실행)",
        "",
        "## 입력/출력",
        "- input(base9): `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`",
        "- output(result): `invest/results/validated/stage05_baselines_v3_21_kr.json`",
        "- output(report): `reports/stage_updates/stage05/stage05_result_v3_21_kr.md`",
        "- output(readable): `reports/stage_updates/stage05/stage05_result_v3_21_kr_readable.md`",
        "- output(patch): `reports/stage_updates/stage05/stage05_patch_diff_v3_21_kr.md`",
        "",
        "## hard-rule 유지 확인",
        "- KRX only: 유지",
        "- 보유1~6: 유지",
        "- 최소보유20일: 유지",
        "- 교체+15%: 유지",
        "- 월교체30%: 유지",
        "- high-density gate(+25%p/MDD/turnover): 유지",
        "",
        "## gate/final/repeat/stop",
        f"- gate1: {gate['gate1']}",
        f"- gate2: {gate['gate2']}",
        f"- gate3: {gate['gate3']}",
        f"- gate4: {gate['gate4']}",
        f"- high_density: {gate['high_density']}",
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

    prev = load_json(PREV_V320_JSON) if PREV_V320_JSON.exists() else {}
    prev_repeat = int(prev.get("repeat_counter", prev.get("policy_enforcement", {}).get("repeat_counter_final", 36)))

    mod = import_stage05_3x3_module()
    external_runs, ext_meta = run_incremental_external(mod)

    internal_models = list(base9["models"])
    all_models_12 = internal_models + external_runs

    track_counts = {t: 0 for t in TRACKS}
    for m in all_models_12:
        t = str(m.get("track"))
        track_counts[t] = track_counts.get(t, 0) + 1

    guard_info = enforce_track_counts_or_fail_stop(track_counts, out_json=OUT_JSON, version=VERSION)

    track_best = {
        "numeric": pick_best([m for m in all_models_12 if m["track"] == "numeric"]),
        "qualitative": pick_best([m for m in all_models_12 if m["track"] == "qualitative"]),
        "hybrid": pick_best([m for m in all_models_12 if m["track"] == "hybrid"]),
        "external-pretrained": pick_best([m for m in all_models_12 if m["track"] == "external-pretrained"]),
    }

    track_best_internal = {k: track_best[k] for k in INTERNAL_TRACKS}
    track_period_metrics = build_track_period_metrics(track_best_internal)

    weighted_scores = {k: weighted_score(v) for k, v in track_period_metrics.items()}

    gate1 = guard_info["track_counts_assertion"] == "pass"

    non_numeric_candidate = "qualitative" if weighted_scores["qualitative"] >= weighted_scores["hybrid"] else "hybrid"
    non_numeric_score = float(weighted_scores[non_numeric_candidate])
    numeric_score = float(weighted_scores["numeric"])

    non_numeric_official = track_period_metrics[non_numeric_candidate]["official_2021_plus"]
    numeric_official = track_period_metrics["numeric"]["official_2021_plus"]

    cond_i = bool(non_numeric_score >= numeric_score + EPSILON)
    near = bool(abs(non_numeric_score - numeric_score) <= EPSILON)
    risk_superior = bool(
        abs(float(non_numeric_official["mdd"])) <= abs(float(numeric_official["mdd"]))
        and float(track_best_internal[non_numeric_candidate]["stats"].get("turnover_proxy", 0.0))
        <= float(track_best_internal["numeric"]["stats"].get("turnover_proxy", 0.0))
    )
    cond_ii = bool(near and risk_superior)
    gate2 = bool(cond_i or cond_ii)
    gate2_reason = "(i) weighted_return_excess_over_numeric" if cond_i else "(ii) near_tie_with_mdd_turnover_superiority" if cond_ii else "gate2_fail"

    official_samples_ok = all(track_period_metrics[t]["official_2021_plus"]["samples"] >= 5 for t in INTERNAL_TRACKS)
    core_samples_ok = all(track_period_metrics[t]["core_2023_2025"]["samples"] >= 3 for t in INTERNAL_TRACKS)
    gate3 = bool(official_samples_ok and core_samples_ok)

    gate4 = bool(
        int(mod.BASE_PARAMS["max_pos"]) <= 6
        and int(mod.BASE_PARAMS["min_hold_days"]) >= 20
        and float(mod.BASE_PARAMS["replace_edge"]) >= 0.15
        and float(mod.BASE_PARAMS["monthly_replace_cap"]) <= 0.30
    )

    core_numeric = track_period_metrics["numeric"]["core_2023_2025"]
    high_density_checks: dict[str, Any] = {}
    winner_candidate = "none"
    high_density_pass = False

    for candidate in ["qualitative", "hybrid"]:
        core_cand = track_period_metrics[candidate]["core_2023_2025"]
        return_pass = bool(float(core_cand["total_return"]) >= float(core_numeric["total_return"]) + 0.25)
        mdd_pass = bool(abs(float(core_cand["mdd"])) <= abs(float(core_numeric["mdd"])))
        turnover_pass = bool(
            float(track_best_internal[candidate]["stats"].get("turnover_proxy", 0.0))
            <= float(track_best_internal["numeric"]["stats"].get("turnover_proxy", 0.0)) * 1.05
        )
        passed = bool(return_pass and mdd_pass and turnover_pass)
        high_density_checks[candidate] = {
            "return_pass": return_pass,
            "mdd_pass": mdd_pass,
            "turnover_pass": turnover_pass,
            "pass": passed,
            "core_return": float(core_cand["total_return"]),
            "core_mdd": float(core_cand["mdd"]),
            "turnover_proxy": float(track_best_internal[candidate]["stats"].get("turnover_proxy", 0.0)),
        }
        if passed and winner_candidate == "none":
            winner_candidate = candidate
            high_density_pass = True

    comparison_rows = [row_for_compare(m, "v3_9_internal_reuse") for m in internal_models]
    comparison_rows += [row_for_compare(m, "v3_21_incremental_external") for m in external_runs]

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

    period_returns = []
    for key, label in [
        ("core_2023_2025", "core_2023_2025"),
        ("official_2021_plus", "official_2021_plus"),
        ("reference_2016_plus", "reference_2016_plus"),
        ("legacy_2016_2020_low_weight", "legacy_2016_2020_low_weight"),
    ]:
        period_returns.append(
            {
                "period": label,
                "numeric_total_return": float(track_period_metrics["numeric"][key]["total_return"]),
                "numeric_cagr": float(track_period_metrics["numeric"][key]["cagr"]),
                "qualitative_total_return": float(track_period_metrics["qualitative"][key]["total_return"]),
                "qualitative_cagr": float(track_period_metrics["qualitative"][key]["cagr"]),
                "hybrid_total_return": float(track_period_metrics["hybrid"][key]["total_return"]),
                "hybrid_cagr": float(track_period_metrics["hybrid"][key]["cagr"]),
            }
        )

    text_filter_counts = load_text_filter_pass_counts()

    gate_status = {
        "gate1": "PASS" if gate1 else "FAIL",
        "gate2": "PASS" if gate2 else "FAIL",
        "gate3": "PASS" if gate3 else "FAIL",
        "gate4": "PASS" if gate4 else "FAIL",
        "high_density": "PASS" if high_density_pass else "FAIL",
    }

    final_decision = "ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL_V321" if all(
        [gate1, gate2, gate3, gate4, high_density_pass]
    ) else "REDESIGN"
    stop_reason = "OFFICIAL_2021_CORE_2023_WEIGHTED_GATE_PASS" if final_decision.startswith("ADOPT") else "GATE_FAIL_REDESIGN"

    repeat_counter = prev_repeat + 1

    payload = {
        "result_grade": "VALIDATED",
        "scope": "KRX_ONLY",
        "version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_scope": "official_2021_plus",
        "evaluation_windows": {
            "official": {"start_year": OFFICIAL_START_YEAR, "end_year": None, "label": "official(2021~현재)"},
            "core_high_density": {
                "start_year": CORE_START_YEAR,
                "end_year": CORE_END_YEAR,
                "label": "high_density_core(2023~2025)",
                "weight": CORE_WEIGHT,
            },
            "legacy_reference_low_weight": {
                "start_year": REFERENCE_START_YEAR,
                "end_year": LEGACY_END_YEAR,
                "label": "reference_low_weight(2016~2020)",
                "weight": LEGACY_LOW_WEIGHT,
            },
        },
        "selection_policy": {
            "main_selection_tracks": ["numeric", "qualitative", "hybrid"],
            "external_pretrained_in_main_selection": False,
            "external_pretrained_role": "comparison_reference_only",
            "weighted_scoring": {
                "core_weight": CORE_WEIGHT,
                "official_weight": OFFICIAL_WEIGHT,
                "legacy_low_weight": LEGACY_LOW_WEIGHT,
                "equation": "core*core_weight + official*official_weight + legacy*legacy_low_weight",
            },
        },
        "v3_19_fail_marker": {
            "path": str(FAIL_V319_JSON.relative_to(BASE)),
            "exists": FAIL_V319_JSON.exists(),
            "status": "FAIL",
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
            "rulebook": "V1_20260218+v3_21_official2021_core2023",
            "holdings_range": "1~6",
            "min_hold_days": 20,
            "replace_edge": 0.15,
            "monthly_replace_cap": 0.30,
            "external_proxy_selection_excluded": True,
            "baseline_protocol": "12_baseline_protocol_3x4",
            "official_scope": "official_2021_plus",
            "high_density_core_band": "2023_2025",
            "legacy_reference_mode": "2016_2020_reference_or_low_weight",
            "high_density_advantage_gate": {
                "enabled": True,
                "return_margin": 0.25,
                "mdd_rule": "abs(candidate_mdd)<=abs(numeric_mdd)",
                "turnover_multiplier_limit": 1.05,
            },
            "repeat_counter_start": prev_repeat + 1,
            "repeat_counter_final": repeat_counter,
        },
        "gate_status": gate_status,
        "gate_detail": {
            "gate2": {
                "reason": gate2_reason,
                "epsilon": EPSILON,
                "numeric_weighted_score": numeric_score,
                "non_numeric_candidate": non_numeric_candidate,
                "non_numeric_weighted_score": non_numeric_score,
                "condition_i": cond_i,
                "condition_ii": cond_ii,
                "near_tie": near,
                "risk_superior": risk_superior,
            },
            "gate3": {
                "official_samples_ok": official_samples_ok,
                "core_samples_ok": core_samples_ok,
                "official_required_years": 5,
                "core_required_years": 3,
            },
            "high_density": {
                "winner_candidate": winner_candidate,
                "thresholds": {
                    "return_margin": 0.25,
                    "mdd_rule": "abs(candidate_mdd)<=abs(numeric_mdd)",
                    "turnover_multiplier_limit": 1.05,
                },
                "numeric_core": {
                    "core_return": float(core_numeric["total_return"]),
                    "core_mdd": float(core_numeric["mdd"]),
                    "turnover_proxy": float(track_best_internal["numeric"]["stats"].get("turnover_proxy", 0.0)),
                },
                "candidate_checks": high_density_checks,
            },
        },
        "protocol_enforced": bool(guard_info["protocol_enforced"]),
        "track_counts_assertion": guard_info["track_counts_assertion"],
        "expected_track_counts": EXPECTED_TRACK_COUNTS_12_BASELINE,
        "track_counts": track_counts,
        "comparison_12": comparison_rows,
        "models": all_models_12,
        "track_best": track_best,
        "track_period_metrics": track_period_metrics,
        "weighted_scores_internal": weighted_scores,
        "period_returns": period_returns,
        "text_filter_pass_counts_by_year": text_filter_counts,
        "final_decision": final_decision,
        "repeat_counter": repeat_counter,
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
