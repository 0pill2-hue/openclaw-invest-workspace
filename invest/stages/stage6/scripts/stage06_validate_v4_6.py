#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List
import pandas as pd

from stage06_v4_6_winner_formula import rank_candidates_v4_6


SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_workspace_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if p.name == "invest" and (p / "stages" / "stage6").exists():
            return p.parent
        if (p / "invest" / "stages" / "stage6").exists():
            return p
    raise RuntimeError("FAIL: cannot resolve workspace root")


WORKSPACE_ROOT = _resolve_workspace_root(SCRIPT_DIR)
ROOT = WORKSPACE_ROOT / "invest/stages/stage6/outputs/reports/stage_updates/v4_6"
VALIDATED_JSON = WORKSPACE_ROOT / "invest/stages/stage6/outputs/results/validated/stage06_baselines_v4_6_kr.json"
SUMMARY_JSON = ROOT / "summary.json"
UI_DATA_JSON = ROOT / "ui" / "ui_data_v4_6.json"
PORTFOLIO_SOURCE_JSON = ROOT / "stage06_portfolio_single_source_v4_6_kr.json"
TRADE_EVENTS_CSV = ROOT / "stage06_trade_events_v4_6_kr.csv"
TIMELINE_CSV = ROOT / "stage06_portfolio_timeline_v4_6_kr.csv"
WEIGHTS_CSV = ROOT / "stage06_portfolio_weights_v4_6_kr.csv"
WINNER_SIGNAL_CSV = ROOT / "stage06_winner_signal_matrix_v4_6_kr.csv"
EQUITY_CSV = ROOT / "stage06_portfolio_equity_v4_6_kr.csv"
CHART_SOURCE_JSON = ROOT / "stage06_chart_inputs_v4_6_kr.json"
BASELINE_MANIFEST_JSON = WORKSPACE_ROOT / "invest/stages/stage6/outputs/results/validated/stage6_baseline_inheritance/manifest.json"
CHART_CONT = ROOT / "charts/stage06_v4_6_yearly_continuous_2021plus.png"
CHART_RESET = ROOT / "charts/stage06_v4_6_yearly_reset_2021plus.png"
CHART_SOURCE_JSON = ROOT / "stage06_chart_inputs_v4_6_kr.json"
EXPECTED_SINGLE_SOURCE_REL = "invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_portfolio_single_source_v4_6_kr.json"
PROOF_DIR = ROOT / "proof"
VERDICT_JSON = PROOF_DIR / "stage06_v4_6_validation_verdict.json"
REPORT_MD = PROOF_DIR / "stage06_v4_6_validation_report.md"
SIMULATED_LABEL = "SIMULATED"
LIVE_LABEL = "LIVE"
PARITY_LABEL = "실거래 일치 보장"
PARITY_GATE_JSON = WORKSPACE_ROOT / "invest/stages/stage6/outputs/reports/stage06_real_execution_parity_latest.json"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _nearly_equal(a, b, tol: float = 1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def _find_reports(base: Path) -> List[Path]:
    names = [
        "stage06_result_v4_6_kr.md",
        "stage06_result_v4_6_kr_readable.md",
    ]
    return [base / n for n in names if (base / n).exists()]


def _load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _extract_codes(text: str) -> set[str]:
    if not text or str(text).strip() in {"", "-", "nan", "NaN"}:
        return set()
    return set(re.findall(r"\((\d{6})\)", str(text)))


def _ranked_from_validated(validated: dict) -> list[dict]:
    all_results = validated.get("all_results", {}) or {}
    candidates = []
    for model_id, info in all_results.items():
        candidates.append(
            {
                "model_id": str(model_id),
                "track": str(info.get("track", "") or ""),
                "stats": info.get("stats", {}) or {},
            }
        )
    return rank_candidates_v4_6(candidates)


def _single_source_top1_v4_6(validated: dict) -> str:
    ranked = _ranked_from_validated(validated)
    return str(ranked[0]["model_id"]) if ranked else ""


def _strip_html(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", "", raw or "")
    return re.sub(r"\s+", " ", txt).strip()


def _pct_text_to_float(raw: str):
    txt = (raw or "").strip()
    if txt in {"", "-", "—"}:
        return None
    m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", txt)
    if not m:
        return None
    try:
        return float(m.group(1)) / 100.0
    except Exception:
        return None


def _fmt_pct_text(v) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v) * 100:.2f}%"
    except Exception:
        return "-"


def _extract_ui_ranking_rows(ui_text: str) -> dict[str, dict]:
    anchor = re.search(r"수익률\s*랭킹.*?<table[^>]*>.*?<tbody>(.*?)</tbody>", ui_text, flags=re.IGNORECASE | re.DOTALL)
    if not anchor:
        anchor = re.search(r"<table[^>]*>.*?<tbody>(.*?)</tbody>", ui_text, flags=re.IGNORECASE | re.DOTALL)
    if not anchor:
        return {}

    body = anchor.group(1)
    row_map: dict[str, dict] = {}
    key_by_label = {
        "1위": "top1",
        "2위": "top2",
        "3위": "top3",
        "베이스라인": "baseline",
        "우승모델": "winner",
    }
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 7:
            continue
        vals = [_strip_html(c) for c in cells[:7]]
        label = vals[0]
        row_key = key_by_label.get(label)
        if not row_key:
            continue
        row_map[row_key] = {
            "rank_label": label,
            "model_id": vals[1],
            "period": vals[2],
            "return_text": vals[3],
            "cagr_text": vals[4],
            "mdd_text": vals[5],
            "note": vals[6],
            "return_2021_plus": _pct_text_to_float(vals[3]),
            "cagr_2021_plus": _pct_text_to_float(vals[4]),
            "mdd_2021_plus": _pct_text_to_float(vals[5]),
        }
    return row_map


def _metric_from_row(row: dict, metric: str):
    if not isinstance(row, dict):
        return None
    aliases = {
        "return_2021_plus": ["return_2021_plus", "return"],
        "cagr_2021_plus": ["cagr_2021_plus", "cagr"],
        "mdd_2021_plus": ["mdd_2021_plus", "mdd"],
    }
    for key in aliases.get(metric, [metric]):
        if key in row and row.get(key) is not None:
            return row.get(key)
    return None


def validate() -> dict:
    checks: List[CheckResult] = []

    reports = _find_reports(ROOT)
    report_text = "\n\n".join(_read_text(p) for p in reports)

    ui_path = ROOT / "ui" / "index.html"
    ui_text = _read_text(ui_path)

    # 1) performance report/table
    has_report = len(reports) > 0
    checks.append(CheckResult("performance_report_exists", has_report, f"reports={len(reports)}"))

    has_perf_markers = (
        ("수익률" in report_text or "total_return" in report_text)
        and ("CAGR" in report_text or "cagr" in report_text)
        and ("MDD" in report_text or "mdd" in report_text)
    )
    has_perf_table = ("<table" in ui_text.lower() and ("cagr" in ui_text.lower()) and ("mdd" in ui_text.lower()))
    checks.append(CheckResult(
        "performance_table_or_metrics",
        bool(has_perf_markers or has_perf_table),
        f"report_markers={has_perf_markers}, ui_table={has_perf_table}",
    ))

    # 2) 2 chart png files
    chart_dir = ROOT / "charts"
    pngs = sorted(chart_dir.glob("*.png")) if chart_dir.exists() else []
    checks.append(CheckResult("chart_png_count>=2", len(pngs) >= 2, f"count={len(pngs)}"))
    checks.append(CheckResult("hardfail_chart_continuous_exists", CHART_CONT.exists(), str(CHART_CONT)))
    checks.append(CheckResult("hardfail_chart_reset_exists", CHART_RESET.exists(), str(CHART_RESET)))
    checks.append(CheckResult("hardfail_chart_source_json_exists", CHART_SOURCE_JSON.exists(), str(CHART_SOURCE_JSON)))

    # 3) csv files
    csvs = sorted(ROOT.glob("*.csv"))
    checks.append(CheckResult("csv_count>=2", len(csvs) >= 2, f"count={len(csvs)}"))
    checks.append(CheckResult("hardfail_equity_csv_exists", EQUITY_CSV.exists(), str(EQUITY_CSV)))
    checks.append(CheckResult("hardfail_winner_signal_csv_exists", WINNER_SIGNAL_CSV.exists(), str(WINNER_SIGNAL_CSV)))
    checks.append(CheckResult("hardfail_chart_input_source_exists", CHART_SOURCE_JSON.exists(), str(CHART_SOURCE_JSON)))

    # 4) gate decision log
    gate_markers = bool(re.search(r"gate\d+", report_text, flags=re.IGNORECASE))
    decision_markers = ("final_decision" in report_text) or ("stop_reason" in report_text)
    checks.append(CheckResult(
        "gate_decision_log_present",
        bool(gate_markers and decision_markers),
        f"gate_markers={gate_markers}, decision_markers={decision_markers}",
    ))

    # 5) ui parity and chart link policy
    checks.append(CheckResult("ui_index_exists", ui_path.exists(), str(ui_path)))

    ui_lower = ui_text.lower()
    parity_required = {
        "kpi_section": any(k in ui_text for k in ["KPI", "핵심 KPI", "총수익률", "연평균수익률"]),
        "gate_summary": any(k in ui_text for k in ["게이트 요약", "gate 요약", "gate summary"]),
        "replacement_decision": any(k in ui_text for k in ["교체 판단", "replacement", "edge", "persistence", "confidence"]),
        "recent_changes": any(k in ui_text for k in ["최근 변동", "포트폴리오 변경 이력", "recent"]),
        "two_charts_text": any(k in ui_text for k in ["차트 2종", "평가 차트", "yearly reset", "continuous"]),
    }
    for k, v in parity_required.items():
        checks.append(CheckResult(f"ui_parity_{k}", v, f"present={v}"))

    img_links = re.findall(r"<img[^>]+src=[\"'](charts/[^\"']+\.png)[\"']", ui_text, flags=re.IGNORECASE)
    checks.append(CheckResult("ui_chart_img_src_charts_png>=2", len(img_links) >= 2, f"count={len(img_links)}"))

    no_base64 = "data:image" not in ui_lower
    checks.append(CheckResult("ui_no_base64_images", no_base64, f"no_base64={no_base64}"))

    summary = _load_json(SUMMARY_JSON)
    validated = _load_json(VALIDATED_JSON)
    ui_data = _load_json(UI_DATA_JSON)
    portfolio_source = _load_json(PORTFOLIO_SOURCE_JSON)
    chart_source = _load_json(CHART_SOURCE_JSON)
    baseline_manifest = _load_json(BASELINE_MANIFEST_JSON)
    trade_df = _load_csv(TRADE_EVENTS_CSV).fillna("")
    timeline_df = _load_csv(TIMELINE_CSV).fillna("")
    weights_df = _load_csv(WEIGHTS_CSV).fillna("")
    signal_df = _load_csv(WINNER_SIGNAL_CSV).fillna("")
    equity_df = _load_csv(EQUITY_CSV).fillna("")
    chart_source = _load_json(CHART_SOURCE_JSON)

    summary_has_explicit = (
        ("winner_return_2021_plus" in summary)
        and ("winner_cagr_2021_plus" in summary)
        and ("winner_mdd_2021_plus" in summary)
    )
    checks.append(CheckResult("summary_explicit_period_fields_present", summary_has_explicit, f"present={summary_has_explicit}"))

    summary_dup_guard = summary.get("duplication_guard", {}) or {}
    validated_dup_guard = ((validated.get("rules", {}) or {}).get("duplication_guard", {}) or {})

    checks.append(CheckResult(
        "hardfail_summary_duplication_guard_present",
        bool(summary_dup_guard),
        f"summary_duplication_guard_keys={sorted(summary_dup_guard.keys()) if isinstance(summary_dup_guard, dict) else []}",
    ))
    checks.append(CheckResult(
        "hardfail_validated_duplication_guard_present",
        bool(validated_dup_guard),
        f"validated_duplication_guard_keys={sorted(validated_dup_guard.keys()) if isinstance(validated_dup_guard, dict) else []}",
    ))

    summary_cap = float(summary_dup_guard.get("axis_cap", 0.0) or 0.0)
    validated_cap = float(validated_dup_guard.get("axis_cap", 0.0) or 0.0)
    checks.append(CheckResult(
        "hardfail_duplication_guard_axis_cap_le_0_25",
        summary_cap <= 0.25 + 1e-12 and validated_cap <= 0.25 + 1e-12,
        f"summary_cap={summary_cap}, validated_cap={validated_cap}",
    ))

    summary_corr_th = float(summary_dup_guard.get("corr_threshold", 0.0) or 0.0)
    validated_corr_th = float(validated_dup_guard.get("corr_threshold", 0.0) or 0.0)
    checks.append(CheckResult(
        "hardfail_duplication_guard_corr_threshold_eq_0_7",
        _nearly_equal(summary_corr_th, 0.7, tol=1e-12) and _nearly_equal(validated_corr_th, 0.7, tol=1e-12),
        f"summary_corr={summary_corr_th}, validated_corr={validated_corr_th}",
    ))

    summary_pre_corr = int(summary_dup_guard.get("pre_high_corr_pair_count", 0) or 0)
    summary_post_corr = int(summary_dup_guard.get("post_high_corr_pair_count", 0) or 0)
    checks.append(CheckResult(
        "hardfail_duplication_guard_post_corr_not_increase",
        summary_post_corr <= summary_pre_corr,
        f"summary_pre={summary_pre_corr}, summary_post={summary_post_corr}",
    ))

    gate11 = str((summary.get("gates", {}) or {}).get("gate11_winner_signal_1to1_match", ""))
    checks.append(CheckResult(
        "hardfail_summary_gate11_winner_signal_match_pass",
        gate11 == "PASS",
        f"gate11={gate11}",
    ))
    gate5 = str((summary.get("gates", {}) or {}).get("gate5_switch_control_schema", ""))
    summary_switch_validation = (summary.get("switch_control_validation", {}) or {})
    summary_policy = (summary.get("replacement_policy", {}) or {})
    monthly_cap_cfg = int(summary_policy.get("monthly_replacement_cap", 1) or 1)
    summary_mode = str(summary.get("data_mode", SIMULATED_LABEL) or SIMULATED_LABEL).upper()
    validated_mode = str(validated.get("data_mode", SIMULATED_LABEL) or SIMULATED_LABEL).upper()
    ui_mode = str(((ui_data.get("summary_snapshot", {}) or {}).get("data_mode", summary_mode) or summary_mode)).upper()
    summary_real_ledger = bool(summary.get("real_execution_ledger_used", False))
    validated_real_ledger = bool(validated.get("real_execution_ledger_used", False))
    mode_alignment = bool(summary_mode and summary_mode == validated_mode == ui_mode)
    checks.append(CheckResult(
        "hardfail_data_mode_alignment_summary_validated_ui",
        mode_alignment,
        f"summary={summary_mode}, validated={validated_mode}, ui={ui_mode}",
    ))
    checks.append(CheckResult(
        "hardfail_data_mode_is_simulated_or_live",
        summary_mode in {SIMULATED_LABEL, LIVE_LABEL},
        f"summary_data_mode={summary_mode}",
    ))
    checks.append(CheckResult(
        "hardfail_live_mode_requires_real_execution_ledger",
        not (summary_mode == LIVE_LABEL and (not summary_real_ledger or not validated_real_ledger)),
        f"summary_mode={summary_mode}, summary_real_ledger={summary_real_ledger}, validated_real_ledger={validated_real_ledger}",
    ))
    checks.append(CheckResult(
        "hardfail_non_real_ledger_must_be_simulated",
        not ((not summary_real_ledger) and summary_mode != SIMULATED_LABEL),
        f"summary_mode={summary_mode}, summary_real_ledger={summary_real_ledger}",
    ))

    parity_payload = _load_json(PARITY_GATE_JSON)
    parity_verdict = str(parity_payload.get("verdict", "")).upper()
    parity_label_requested = str(summary.get("real_execution_parity_label", "") or "").strip()
    parity_mode = str(summary.get("real_execution_parity_mode", "DISABLED") or "DISABLED").upper()
    parity_allowed = bool((parity_payload.get("label_policy", {}) or {}).get("allowed", False))
    checks.append(CheckResult(
        "hardfail_parity_mode_strict_requires_gate_pass",
        parity_mode != "STRICT" or parity_verdict == "PASS",
        f"parity_mode={parity_mode}, parity_verdict={parity_verdict}, parity_json={PARITY_GATE_JSON}",
    ))
    checks.append(CheckResult(
        "hardfail_parity_label_requires_gate_pass",
        parity_label_requested != PARITY_LABEL or (parity_verdict == "PASS" and parity_allowed and summary_real_ledger and validated_real_ledger),
        f"label={parity_label_requested}, parity_verdict={parity_verdict}, parity_allowed={parity_allowed}, summary_real_ledger={summary_real_ledger}, validated_real_ledger={validated_real_ledger}",
    ))

    summary_op_policy = summary.get("operational_aggregation_policy", {}) or {}
    validated_op_policy = validated.get("operational_aggregation_policy", {}) or {}
    ui_snap = ui_data.get("summary_snapshot", {}) or {}
    checks.append(CheckResult(
        "hardfail_operational_aggregation_target_champion_only",
        str(summary_op_policy.get("target", "")).strip() == "champion_only" and str(validated_op_policy.get("target", "")).strip() == "champion_only",
        f"summary_target={summary_op_policy.get('target')}, validated_target={validated_op_policy.get('target')}",
    ))
    checks.append(CheckResult(
        "hardfail_non_winners_policy_research_archive_only",
        str(summary_op_policy.get("non_winners", "")).strip() == "research_archive_only" and str(validated_op_policy.get("non_winners", "")).strip() == "research_archive_only",
        f"summary_non_winners={summary_op_policy.get('non_winners')}, validated_non_winners={validated_op_policy.get('non_winners')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_operational_policy_snapshot_present",
        str(ui_snap.get("operational_aggregation_target", "")).strip() == "champion_only" and str(ui_snap.get("non_winners_policy", "")).strip() == "research_archive_only",
        f"ui_target={ui_snap.get('operational_aggregation_target')}, ui_non_winners={ui_snap.get('non_winners_policy')}",
    ))

    winner_id_summary = str(summary.get("winner", "") or "")
    winner_id_validated = str((validated.get("winner", {}) or {}).get("model_id", "") or "")
    winner_id_single_source = str(portfolio_source.get("model_id", "") or "")
    checks.append(CheckResult("consistency_winner_id_summary_vs_validated", winner_id_summary == winner_id_validated and winner_id_summary != "", f"summary={winner_id_summary}, validated={winner_id_validated}"))
    checks.append(CheckResult(
        "hardfail_winner_id_single_source_alignment",
        bool(winner_id_single_source and winner_id_single_source == winner_id_summary == winner_id_validated),
        f"single_source={winner_id_single_source}, summary={winner_id_summary}, validated={winner_id_validated}",
    ))

    chart_winner_id = str(chart_source.get("winner_model_id", "") or "")
    checks.append(CheckResult(
        "hardfail_winner_id_chart_source_alignment",
        bool(chart_winner_id and chart_winner_id == winner_id_summary == winner_id_validated),
        f"chart_source={chart_winner_id}, summary={winner_id_summary}, validated={winner_id_validated}",
    ))

    expected_top1 = _single_source_top1_v4_6(validated)
    checks.append(CheckResult(
        "hardfail_winner_matches_single_source_top1",
        bool(expected_top1 and winner_id_validated == expected_top1),
        f"validated_winner={winner_id_validated}, expected_top1={expected_top1}",
    ))

    ranked_formula = _ranked_from_validated(validated)
    recomputed_top_ids = [str(r.get("model_id", "")) for r in ranked_formula]
    stored_leaderboard = list(validated.get("winner_score_leaderboard", []) or [])
    checks.append(CheckResult(
        "hardfail_score_leaderboard_present",
        len(stored_leaderboard) > 0,
        f"count={len(stored_leaderboard)}",
    ))
    leaderboard_sorted_ok = True
    for i in range(1, len(stored_leaderboard)):
        prev_score = float(stored_leaderboard[i - 1].get("final_score", 0.0) or 0.0)
        cur_score = float(stored_leaderboard[i].get("final_score", 0.0) or 0.0)
        if cur_score > prev_score + 1e-12:
            leaderboard_sorted_ok = False
            break
    checks.append(CheckResult(
        "hardfail_score_leaderboard_sorted_desc",
        leaderboard_sorted_ok,
        f"sorted={leaderboard_sorted_ok}",
    ))

    leaderboard_top1 = str(stored_leaderboard[0].get("model_id", "")) if stored_leaderboard else ""
    checks.append(CheckResult(
        "hardfail_winner_matches_score_leaderboard_top1",
        bool(leaderboard_top1 and winner_id_validated == leaderboard_top1),
        f"winner={winner_id_validated}, leaderboard_top1={leaderboard_top1}",
    ))

    overlap_n = min(len(stored_leaderboard), len(recomputed_top_ids), 10)
    leaderboard_ids = [str(x.get("model_id", "")) for x in stored_leaderboard[:overlap_n]]
    checks.append(CheckResult(
        "hardfail_score_leaderboard_topN_consistency",
        bool(overlap_n > 0 and leaderboard_ids == recomputed_top_ids[:overlap_n]),
        f"overlap_n={overlap_n}, leaderboard_topN={leaderboard_ids}, recomputed_topN={recomputed_top_ids[:overlap_n]}",
    ))

    summary_score_top1 = str(summary.get("winner_score_top1_model_id", "") or "")
    checks.append(CheckResult(
        "hardfail_summary_winner_score_top1_alignment",
        bool(summary_score_top1 and summary_score_top1 == winner_id_summary == winner_id_validated),
        f"summary_score_top1={summary_score_top1}, summary={winner_id_summary}, validated={winner_id_validated}",
    ))

    vstats = ((validated.get("winner", {}) or {}).get("stats", {}) or {})
    checks.append(CheckResult(
        "consistency_return_2021_plus_summary_vs_validated",
        _nearly_equal(summary.get("winner_return_2021_plus"), vstats.get("return_2021_plus")),
        f"summary={summary.get('winner_return_2021_plus')}, validated={vstats.get('return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "consistency_cagr_2021_plus_summary_vs_validated",
        _nearly_equal(summary.get("winner_cagr_2021_plus"), vstats.get("cagr_2021_plus")),
        f"summary={summary.get('winner_cagr_2021_plus')}, validated={vstats.get('cagr_2021_plus')}",
    ))
    checks.append(CheckResult(
        "consistency_mdd_2021_plus_summary_vs_validated",
        _nearly_equal(summary.get("winner_mdd_2021_plus"), vstats.get("mdd_2021_plus")),
        f"summary={summary.get('winner_mdd_2021_plus')}, validated={vstats.get('mdd_2021_plus')}",
    ))

    all_results_winner_stats = ((validated.get("all_results", {}) or {}).get(winner_id_validated, {}) or {}).get("stats", {}) or {}
    checks.append(CheckResult(
        "hardfail_validated_winner_return_2021_plus_eq_all_results_winner",
        _nearly_equal(vstats.get("return_2021_plus"), all_results_winner_stats.get("return_2021_plus")),
        f"winner_stats={vstats.get('return_2021_plus')}, all_results_winner={all_results_winner_stats.get('return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_validated_winner_cagr_2021_plus_eq_all_results_winner",
        _nearly_equal(vstats.get("cagr_2021_plus"), all_results_winner_stats.get("cagr_2021_plus")),
        f"winner_stats={vstats.get('cagr_2021_plus')}, all_results_winner={all_results_winner_stats.get('cagr_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_validated_winner_mdd_2021_plus_eq_all_results_winner",
        _nearly_equal(vstats.get("mdd_2021_plus"), all_results_winner_stats.get("mdd_2021_plus")),
        f"winner_stats={vstats.get('mdd_2021_plus')}, all_results_winner={all_results_winner_stats.get('mdd_2021_plus')}",
    ))

    ui_winner_name = str(((ui_data.get("ranking", {}) or {}).get("winner_name", "") or ""))
    ui_winner_row = ((ui_data.get("ranking", {}) or {}).get("winner", {}) or {})
    checks.append(CheckResult("consistency_winner_id_ui_vs_summary", ui_winner_name == winner_id_summary and ui_winner_name != "", f"summary={winner_id_summary}, ui={ui_winner_name}"))
    checks.append(CheckResult(
        "hardfail_winner_id_alignment_summary_ui_validated",
        bool(winner_id_summary and winner_id_summary == winner_id_validated == ui_winner_name),
        f"summary={winner_id_summary}, validated={winner_id_validated}, ui={ui_winner_name}",
    ))
    ui_top3 = list(((ui_data.get("ranking", {}) or {}).get("top3", []) or []))
    ui_top1_id = str(ui_top3[0].get("model_id", "")) if ui_top3 else ""
    checks.append(CheckResult(
        "hardfail_ui_top3_top1_matches_winner",
        bool(ui_top1_id and ui_top1_id == ui_winner_name == winner_id_validated),
        f"ui_top1={ui_top1_id}, ui_winner={ui_winner_name}, validated={winner_id_validated}",
    ))
    checks.append(CheckResult(
        "hardfail_winner_formula_top1_eq_summary_ui_validated",
        bool(expected_top1 and expected_top1 == winner_id_summary == winner_id_validated == ui_winner_name == ui_top1_id),
        f"expected_top1={expected_top1}, summary={winner_id_summary}, validated={winner_id_validated}, ui_winner={ui_winner_name}, ui_top1={ui_top1_id}",
    ))
    ui_top1_row = ui_top3[0] if ui_top3 else {}
    checks.append(CheckResult(
        "hardfail_ui_top3_winner_return_2021_plus_eq_summary",
        _nearly_equal(ui_top1_row.get("return"), summary.get("winner_return_2021_plus")),
        f"summary={summary.get('winner_return_2021_plus')}, ui_top1={ui_top1_row.get('return')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_top3_winner_cagr_2021_plus_eq_summary",
        _nearly_equal(ui_top1_row.get("cagr"), summary.get("winner_cagr_2021_plus")),
        f"summary={summary.get('winner_cagr_2021_plus')}, ui_top1={ui_top1_row.get('cagr')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_top3_winner_mdd_2021_plus_eq_summary",
        _nearly_equal(ui_top1_row.get("mdd"), summary.get("winner_mdd_2021_plus")),
        f"summary={summary.get('winner_mdd_2021_plus')}, ui_top1={ui_top1_row.get('mdd')}",
    ))
    checks.append(CheckResult(
        "consistency_return_2021_plus_ui_vs_summary",
        _nearly_equal(ui_winner_row.get("return"), summary.get("winner_return_2021_plus")),
        f"summary={summary.get('winner_return_2021_plus')}, ui={ui_winner_row.get('return')}",
    ))
    checks.append(CheckResult(
        "consistency_mdd_2021_plus_ui_vs_summary",
        _nearly_equal(ui_winner_row.get("mdd"), summary.get("winner_mdd_2021_plus")),
        f"summary={summary.get('winner_mdd_2021_plus')}, ui={ui_winner_row.get('mdd')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_cagr_2021_plus_eq_summary",
        _nearly_equal(ui_winner_row.get("cagr"), summary.get("winner_cagr_2021_plus")),
        f"summary={summary.get('winner_cagr_2021_plus')}, ui={ui_winner_row.get('cagr')}",
    ))
    ui_snap = ui_data.get("summary_snapshot", {}) or {}
    checks.append(CheckResult(
        "hardfail_ui_summary_snapshot_return_eq_summary",
        _nearly_equal(ui_snap.get("winner_return_2021_plus"), summary.get("winner_return_2021_plus")),
        f"summary={summary.get('winner_return_2021_plus')}, ui_snapshot={ui_snap.get('winner_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_summary_snapshot_cagr_eq_summary",
        _nearly_equal(ui_snap.get("winner_cagr_2021_plus"), summary.get("winner_cagr_2021_plus")),
        f"summary={summary.get('winner_cagr_2021_plus')}, ui_snapshot={ui_snap.get('winner_cagr_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_summary_snapshot_mdd_eq_summary",
        _nearly_equal(ui_snap.get("winner_mdd_2021_plus"), summary.get("winner_mdd_2021_plus")),
        f"summary={summary.get('winner_mdd_2021_plus')}, ui_snapshot={ui_snap.get('winner_mdd_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_summary_snapshot_decision_eq_summary",
        str(ui_snap.get("final_decision", "")) == str(summary.get("final_decision", "")) and str(summary.get("final_decision", "")) != "",
        f"summary={summary.get('final_decision')}, ui_snapshot={ui_snap.get('final_decision')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_summary_snapshot_stop_reason_eq_summary",
        str(ui_snap.get("stop_reason", "")) == str(summary.get("stop_reason", "")) and str(summary.get("stop_reason", "")) != "",
        f"summary={summary.get('stop_reason')}, ui_snapshot={ui_snap.get('stop_reason')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_summary_snapshot_parity_label_eq_summary",
        str(ui_snap.get("real_execution_parity_label", "") or "") == str(summary.get("real_execution_parity_label", "") or ""),
        f"summary={summary.get('real_execution_parity_label')}, ui_snapshot={ui_snap.get('real_execution_parity_label')}",
    ))

    chart_cont = (chart_source.get("continuous", {}) or {})
    chart_winner_series = list(chart_cont.get("winner_series", []) or [])
    chart_ui = ui_data.get("chart_source", {}) or {}
    chart_ui_year_end = list(chart_ui.get("winner_year_end", []) or [])
    chart_year_end = list(((chart_source.get("yearly_reset", {}) or {}).get("winner_year_end", []) or []))

    checks.append(CheckResult(
        "hardfail_chart_winner_series_present",
        len(chart_winner_series) > 0,
        f"rows={len(chart_winner_series)}",
    ))

    chart_right_edge = chart_cont.get("winner_right_edge_return_2021_plus")
    checks.append(CheckResult(
        "hardfail_chart_right_edge_eq_summary_kpi",
        _nearly_equal(chart_right_edge, summary.get("winner_return_2021_plus")),
        f"chart_right_edge={chart_right_edge}, summary_return={summary.get('winner_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_chart_right_edge_eq_ui_chart_snapshot",
        _nearly_equal(chart_right_edge, chart_ui.get("winner_right_edge_return_2021_plus")),
        f"chart_right_edge={chart_right_edge}, ui_chart_right_edge={chart_ui.get('winner_right_edge_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_chart_right_edge_eq_summary_field",
        _nearly_equal(chart_right_edge, summary.get("chart_winner_right_edge_return_2021_plus")),
        f"chart_right_edge={chart_right_edge}, summary_chart_field={summary.get('chart_winner_right_edge_return_2021_plus')}",
    ))

    chart_peak = chart_cont.get("winner_peak_return_2021_plus")
    chart_trough = chart_cont.get("winner_trough_return_2021_plus")
    if chart_winner_series:
        series_returns = [float(r.get("return_2021_plus")) for r in chart_winner_series if r.get("return_2021_plus") is not None]
    else:
        series_returns = []
    series_peak = max(series_returns) if series_returns else None
    series_trough = min(series_returns) if series_returns else None
    checks.append(CheckResult(
        "hardfail_chart_peak_point_consistency",
        _nearly_equal(chart_peak, series_peak),
        f"chart_peak={chart_peak}, series_peak={series_peak}",
    ))
    checks.append(CheckResult(
        "hardfail_chart_trough_point_consistency",
        _nearly_equal(chart_trough, series_trough),
        f"chart_trough={chart_trough}, series_trough={series_trough}",
    ))

    checks.append(CheckResult(
        "hardfail_chart_year_end_keypoints_present",
        len(chart_year_end) > 0,
        f"winner_year_end_rows={len(chart_year_end)}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_chart_year_end_keypoints_eq_chart_source",
        chart_ui_year_end == chart_year_end,
        f"ui_rows={len(chart_ui_year_end)}, chart_rows={len(chart_year_end)}",
    ))

    ui_kpi_snap = ui_data.get("kpi_source_snapshot", {}) or {}
    checks.append(CheckResult(
        "hardfail_ui_kpi_source_return_eq_summary",
        _nearly_equal(ui_kpi_snap.get("winner_return_2021_plus"), summary.get("winner_return_2021_plus")),
        f"ui_kpi_return={ui_kpi_snap.get('winner_return_2021_plus')}, summary={summary.get('winner_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_kpi_source_cagr_eq_summary",
        _nearly_equal(ui_kpi_snap.get("winner_cagr_2021_plus"), summary.get("winner_cagr_2021_plus")),
        f"ui_kpi_cagr={ui_kpi_snap.get('winner_cagr_2021_plus')}, summary={summary.get('winner_cagr_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_kpi_source_mdd_eq_summary",
        _nearly_equal(ui_kpi_snap.get("winner_mdd_2021_plus"), summary.get("winner_mdd_2021_plus")),
        f"ui_kpi_mdd={ui_kpi_snap.get('winner_mdd_2021_plus')}, summary={summary.get('winner_mdd_2021_plus')}",
    ))

    ui_ranking_rows = {
        str(r.get("row_key", "")): r
        for r in list(((ui_data.get("ranking", {}) or {}).get("rows", []) or []))
        if isinstance(r, dict)
    }
    has_required_ui_rows = all(k in ui_ranking_rows for k in ["top1", "baseline", "winner"])
    checks.append(CheckResult(
        "hardfail_ui_ranking_rows_present_top1_baseline_winner",
        has_required_ui_rows,
        f"rows={sorted(ui_ranking_rows.keys())}",
    ))

    ui_top1_row_unified = ui_ranking_rows.get("top1", ui_top1_row if isinstance(ui_top1_row, dict) else {})
    ui_winner_row_unified = ui_ranking_rows.get("winner", ui_winner_row if isinstance(ui_winner_row, dict) else {})
    ui_baseline_row_unified = ui_ranking_rows.get("baseline", ((ui_data.get("ranking", {}) or {}).get("baseline", {}) or {}))

    summary_baseline = summary.get("baseline_reference", {}) or {}
    summary_baseline_present = all(k in summary_baseline for k in ["return_2021_plus", "cagr_2021_plus", "mdd_2021_plus"])
    checks.append(CheckResult(
        "hardfail_summary_baseline_reference_fields_present",
        summary_baseline_present,
        f"present={summary_baseline_present}",
    ))

    ui_html_rows = _extract_ui_ranking_rows(ui_text)
    has_required_html_rows = all(k in ui_html_rows for k in ["top1", "baseline", "winner"])
    checks.append(CheckResult(
        "hardfail_index_html_ranking_rows_present_top1_baseline_winner",
        has_required_html_rows,
        f"rows={sorted(ui_html_rows.keys())}",
    ))

    for row_key in ["top1", "winner", "baseline"]:
        html_row = ui_html_rows.get(row_key, {})
        ui_row = {
            "top1": ui_top1_row_unified,
            "winner": ui_winner_row_unified,
            "baseline": ui_baseline_row_unified,
        }.get(row_key, {})

        row_model_ok = str(html_row.get("model_id", "")) == str(ui_row.get("model_id", "")) and str(ui_row.get("model_id", "")) != ""
        checks.append(CheckResult(
            f"hardfail_html_{row_key}_model_id_eq_ui_data",
            row_model_ok,
            f"html={html_row.get('model_id')}, ui={ui_row.get('model_id')}",
        ))

        for metric in ["return_2021_plus", "cagr_2021_plus", "mdd_2021_plus"]:
            ui_val = _metric_from_row(ui_row, metric)
            display_key = {
                "return_2021_plus": "return_display",
                "cagr_2021_plus": "cagr_display",
                "mdd_2021_plus": "mdd_display",
            }[metric]
            html_text_key = {
                "return_2021_plus": "return_text",
                "cagr_2021_plus": "cagr_text",
                "mdd_2021_plus": "mdd_text",
            }[metric]
            html_text = str(html_row.get(html_text_key, "-"))
            ui_text = str(ui_row.get(display_key) or _fmt_pct_text(ui_val))
            checks.append(CheckResult(
                f"hardfail_html_{row_key}_{metric}_eq_ui_data",
                html_text == ui_text,
                f"html={html_text}, ui_display={ui_text}, ui_raw={ui_val}",
            ))

    summary_row_ref = {
        "top1": {
            "model_id": winner_id_summary,
            "return_2021_plus": summary.get("winner_return_2021_plus"),
            "cagr_2021_plus": summary.get("winner_cagr_2021_plus"),
            "mdd_2021_plus": summary.get("winner_mdd_2021_plus"),
        },
        "winner": {
            "model_id": winner_id_summary,
            "return_2021_plus": summary.get("winner_return_2021_plus"),
            "cagr_2021_plus": summary.get("winner_cagr_2021_plus"),
            "mdd_2021_plus": summary.get("winner_mdd_2021_plus"),
        },
        "baseline": {
            "model_id": summary_baseline.get("label", summary_baseline.get("model_id")),
            "return_2021_plus": summary_baseline.get("return_2021_plus"),
            "cagr_2021_plus": summary_baseline.get("cagr_2021_plus"),
            "mdd_2021_plus": summary_baseline.get("mdd_2021_plus"),
        },
    }

    for row_key in ["top1", "winner", "baseline"]:
        html_row = ui_html_rows.get(row_key, {})
        srow = summary_row_ref.get(row_key, {})
        checks.append(CheckResult(
            f"hardfail_html_{row_key}_model_id_eq_summary",
            bool(str(srow.get("model_id", "")) and str(html_row.get("model_id", "")) == str(srow.get("model_id", ""))),
            f"html={html_row.get('model_id')}, summary={srow.get('model_id')}",
        ))
        for metric in ["return_2021_plus", "cagr_2021_plus", "mdd_2021_plus"]:
            html_text_key = {
                "return_2021_plus": "return_text",
                "cagr_2021_plus": "cagr_text",
                "mdd_2021_plus": "mdd_text",
            }[metric]
            html_text = str(html_row.get(html_text_key, "-"))
            summary_text = _fmt_pct_text(srow.get(metric))
            checks.append(CheckResult(
                f"hardfail_html_{row_key}_{metric}_eq_summary",
                html_text == summary_text,
                f"html={html_text}, summary_display={summary_text}, summary_raw={srow.get(metric)}",
            ))

    has_portfolio_source = bool(portfolio_source.get("weights") and portfolio_source.get("timeline") and portfolio_source.get("trade_events"))
    checks.append(CheckResult(
        "hardfail_single_source_payload_present",
        has_portfolio_source,
        f"weights={len(portfolio_source.get('weights', []))}, timeline={len(portfolio_source.get('timeline', []))}, trade_events={len(portfolio_source.get('trade_events', []))}",
    ))

    if not weights_df.empty and "date" in weights_df.columns and "weight_pct" in weights_df.columns:
        weights_df["date"] = weights_df["date"].astype(str)
        weights_df["weight_pct"] = pd.to_numeric(weights_df["weight_pct"], errors="coerce").fillna(0.0)
        daily_sum = weights_df.groupby("date")["weight_pct"].sum()
        weights_sum_ok = bool(((daily_sum - 100.0).abs() <= 0.2).all())
        weights_nonneg_ok = bool((weights_df["weight_pct"] >= -1e-9).all())
    else:
        weights_sum_ok = False
        weights_nonneg_ok = False
    checks.append(CheckResult("hardfail_weights_daily_sum_approx_100", weights_sum_ok, f"ok={weights_sum_ok}"))
    checks.append(CheckResult("hardfail_weights_non_negative", weights_nonneg_ok, f"ok={weights_nonneg_ok}"))

    if not timeline_df.empty and "rebalance_date" in timeline_df.columns and not weights_df.empty and "date" in weights_df.columns:
        timeline_dates = set(timeline_df["rebalance_date"].astype(str))
        weight_dates = set(weights_df["date"].astype(str))
        timeline_date_ok = timeline_dates.issubset(weight_dates)
    else:
        timeline_date_ok = False
    checks.append(CheckResult("hardfail_timeline_dates_exist_in_weights", timeline_date_ok, f"ok={timeline_date_ok}"))

    same_day_overlap_count = 0
    same_day_overlap_dates: list[str] = []
    normal_row_cap_violations = 0
    normal_monthly_removed: dict[str, int] = {}
    risk_event_rows = 0
    if not timeline_df.empty and "rebalance_date" in timeline_df.columns:
        for _, r in timeline_df.iterrows():
            d = str(r.get("rebalance_date", "")).strip()
            month_key = d[:7] if len(d) >= 7 else "unknown"
            is_risk_event = str(r.get("risk_event_escape", "N")).strip().upper() == "Y"
            add_codes = _extract_codes(str(r.get("added_codes", "")))
            rem_codes = _extract_codes(str(r.get("removed_codes", "")))
            overlap = sorted(add_codes & rem_codes)
            if overlap:
                same_day_overlap_count += 1
                same_day_overlap_dates.append(f"{d}:{','.join(overlap)}")
            removed_count = len(rem_codes)
            if is_risk_event:
                risk_event_rows += 1
            else:
                if removed_count > monthly_cap_cfg:
                    normal_row_cap_violations += 1
                normal_monthly_removed[month_key] = normal_monthly_removed.get(month_key, 0) + removed_count
    monthly_cap_violation_months = {
        m: c for m, c in normal_monthly_removed.items() if c > monthly_cap_cfg
    }
    checks.append(CheckResult(
        "hardfail_no_same_day_added_removed_overlap",
        same_day_overlap_count == 0,
        f"overlap_count={same_day_overlap_count}, samples={same_day_overlap_dates[:5]}",
    ))
    checks.append(CheckResult(
        "hardfail_universe_switch_normal_row_removed_lte_monthly_cap",
        normal_row_cap_violations == 0,
        f"monthly_cap={monthly_cap_cfg}, violations={normal_row_cap_violations}",
    ))
    checks.append(CheckResult(
        "hardfail_universe_switch_normal_monthly_removed_lte_cap",
        len(monthly_cap_violation_months) == 0,
        f"monthly_cap={monthly_cap_cfg}, monthly_removed={normal_monthly_removed}, violation_months={monthly_cap_violation_months}",
    ))
    computed_switch_pass = bool(
        same_day_overlap_count == 0
        and normal_row_cap_violations == 0
        and len(monthly_cap_violation_months) == 0
    )
    checks.append(CheckResult(
        "hardfail_summary_gate5_switch_control_schema_pass",
        gate5 == "PASS",
        f"gate5={gate5}",
    ))
    checks.append(CheckResult(
        "hardfail_summary_gate5_eq_computed_switch_validation",
        (gate5 == "PASS") == computed_switch_pass,
        f"gate5={gate5}, computed={computed_switch_pass}",
    ))
    checks.append(CheckResult(
        "hardfail_summary_switch_control_validation_eq_computed",
        bool(summary_switch_validation) and bool(summary_switch_validation.get("pass", False)) == computed_switch_pass,
        f"summary_switch={summary_switch_validation}, computed_pass={computed_switch_pass}, risk_event_rows={risk_event_rows}",
    ))
    single_source_switch_validation = ((portfolio_source.get("derived", {}) or {}).get("switch_control_validation", {}) or {})
    checks.append(CheckResult(
        "hardfail_single_source_switch_control_validation_eq_computed",
        bool(single_source_switch_validation) and bool(single_source_switch_validation.get("pass", False)) == computed_switch_pass,
        f"single_source_switch={single_source_switch_validation}, computed_pass={computed_switch_pass}",
    ))

    trade_date_ok = True
    if not trade_df.empty:
        if "buy_date" in trade_df.columns:
            buy_dates = {d for d in trade_df["buy_date"].astype(str) if d and d != "-"}
        else:
            buy_dates = set()
        if "sell_date" in trade_df.columns:
            sell_dates = {d for d in trade_df["sell_date"].astype(str) if d and d != "-"}
        else:
            sell_dates = set()
        if not weights_df.empty and "date" in weights_df.columns:
            weight_dates = set(weights_df["date"].astype(str))
            trade_date_ok = buy_dates.issubset(weight_dates) and sell_dates.issubset(weight_dates)
        else:
            trade_date_ok = False
    checks.append(CheckResult("hardfail_trade_event_dates_exist_in_weights", trade_date_ok, f"ok={trade_date_ok}"))

    timeline_change_ok = True
    timeline_vs_weights_ok = True
    weight_adjustment_trade_ok = True
    if not timeline_df.empty and not trade_df.empty:
        buys_new_by_date: dict[str, set[str]] = {}
        sells_full_by_date: dict[str, set[str]] = {}
        buys_adj_by_date: dict[str, list[dict]] = {}
        sells_adj_by_date: dict[str, list[dict]] = {}

        for _, r in trade_df.iterrows():
            bd = str(r.get("buy_date", "")).strip()
            sd = str(r.get("sell_date", "")).strip()
            code = str(r.get("stock_code", "")).strip().zfill(6)
            adj_type = str(r.get("adjustment_type", "")).strip()
            if code == "000000":
                continue

            if adj_type == "신규매수" and bd and bd != "-":
                buys_new_by_date.setdefault(bd, set()).add(code)
            if adj_type == "전량매도" and sd and sd != "-":
                sells_full_by_date.setdefault(sd, set()).add(code)
            if adj_type == "추가매수" and bd and bd != "-":
                buys_adj_by_date.setdefault(bd, []).append({"code": code, "delta": float(r.get("delta_weight", 0.0) or 0.0)})
            if adj_type == "추가매도" and sd and sd != "-":
                sells_adj_by_date.setdefault(sd, []).append({"code": code, "delta": float(r.get("delta_weight", 0.0) or 0.0)})

        date_to_weight_map: dict[str, dict[str, float]] = {}
        if not weights_df.empty and {"date", "stock_code", "weight_pct"}.issubset(set(weights_df.columns)):
            wtmp = weights_df.copy()
            wtmp["date"] = wtmp["date"].astype(str)
            wtmp["stock_code"] = wtmp["stock_code"].astype(str).str.zfill(6)
            wtmp["weight_pct"] = pd.to_numeric(wtmp["weight_pct"], errors="coerce").fillna(0.0)
            for d, g in wtmp.groupby("date"):
                date_to_weight_map[str(d)] = {
                    str(rr.stock_code): float(rr.weight_pct)
                    for rr in g.itertuples()
                    if float(rr.weight_pct) > 1e-9
                }

        added_from_weights: dict[str, set[str]] = {}
        removed_from_weights: dict[str, set[str]] = {}
        delta_from_weights: dict[str, dict[str, float]] = {}
        ordered_dates = sorted(date_to_weight_map.keys())
        prev_map = {}
        for d in ordered_dates:
            cur_map = date_to_weight_map.get(d, {})
            prev_codes = set(prev_map.keys())
            cur_codes = set(cur_map.keys())
            added_from_weights[d] = {c for c in (cur_codes - prev_codes) if cur_map.get(c, 0.0) > 0.0}
            removed_from_weights[d] = {c for c in (prev_codes - cur_codes) if prev_map.get(c, 0.0) > 0.0}
            dmap = {}
            for c in (cur_codes & prev_codes):
                dmap[c] = float(cur_map.get(c, 0.0) - prev_map.get(c, 0.0))
            delta_from_weights[d] = dmap
            prev_map = cur_map

        timeline_dates: set[str] = set()
        for _, r in timeline_df.iterrows():
            d = str(r.get("rebalance_date", "")).strip()
            timeline_dates.add(d)
            add_codes = _extract_codes(str(r.get("added_codes", "")))
            rem_codes = _extract_codes(str(r.get("removed_codes", "")))
            if add_codes != buys_new_by_date.get(d, set()):
                timeline_change_ok = False
            if rem_codes != sells_full_by_date.get(d, set()):
                timeline_change_ok = False
            net_add_codes = set(add_codes) - set(rem_codes)
            net_rem_codes = set(rem_codes) - set(add_codes)
            if net_add_codes != added_from_weights.get(d, set()):
                timeline_vs_weights_ok = False
            if net_rem_codes != removed_from_weights.get(d, set()):
                timeline_vs_weights_ok = False

            d_delta = delta_from_weights.get(d, {})
            for x in buys_adj_by_date.get(d, []):
                if d_delta.get(x["code"], 0.0) < 0.05:
                    weight_adjustment_trade_ok = False
                    break
            for x in sells_adj_by_date.get(d, []):
                if d_delta.get(x["code"], 0.0) > -0.05:
                    weight_adjustment_trade_ok = False
                    break

        if not set(buys_new_by_date.keys()).issubset(timeline_dates):
            timeline_change_ok = False
        if not set(sells_full_by_date.keys()).issubset(timeline_dates):
            timeline_change_ok = False

    checks.append(CheckResult("hardfail_timeline_change_consistency_vs_trade_events", timeline_change_ok, f"ok={timeline_change_ok}"))
    checks.append(CheckResult("hardfail_timeline_change_consistency_vs_weights", timeline_vs_weights_ok, f"ok={timeline_vs_weights_ok}"))
    checks.append(CheckResult("hardfail_weight_adjustment_trade_consistency_vs_weights", weight_adjustment_trade_ok, f"ok={weight_adjustment_trade_ok}"))

    weights_src = list(portfolio_source.get("weights", []) or [])
    timeline_src = list(portfolio_source.get("timeline", []) or [])
    trades_src = list(portfolio_source.get("trade_events", []) or [])
    checks.append(CheckResult(
        "hardfail_csv_row_count_eq_single_source_weights",
        len(weights_df) == len(weights_src),
        f"csv={len(weights_df)}, single_source={len(weights_src)}",
    ))
    checks.append(CheckResult(
        "hardfail_csv_row_count_eq_single_source_timeline",
        len(timeline_df) == len(timeline_src),
        f"csv={len(timeline_df)}, single_source={len(timeline_src)}",
    ))
    checks.append(CheckResult(
        "hardfail_csv_row_count_eq_single_source_trade_events",
        len(trade_df) == len(trades_src),
        f"csv={len(trade_df)}, single_source={len(trades_src)}",
    ))
    equity_src = list(portfolio_source.get("portfolio_daily", []) or [])
    checks.append(CheckResult(
        "hardfail_csv_row_count_eq_single_source_equity",
        len(equity_df) == len(equity_src),
        f"csv={len(equity_df)}, single_source={len(equity_src)}",
    ))

    signal_src = list(portfolio_source.get("winner_signals", []) or [])
    checks.append(CheckResult(
        "hardfail_csv_row_count_eq_single_source_winner_signals",
        len(signal_df) == len(signal_src),
        f"csv={len(signal_df)}, single_source={len(signal_src)}",
    ))

    signal_match_ratio = 0.0
    signal_match_all = False
    signal_total = 0
    signal_match_count = 0
    if not signal_df.empty and {"date", "stock_code", "target_weight_pct"}.issubset(set(signal_df.columns)) and not weights_df.empty and {"date", "stock_code", "weight_pct"}.issubset(set(weights_df.columns)):
        s = signal_df.copy()
        s["date"] = s["date"].astype(str)
        s["stock_code"] = s["stock_code"].astype(str).str.zfill(6)
        s["target_weight_pct"] = pd.to_numeric(s["target_weight_pct"], errors="coerce").fillna(0.0)
        s = s[s["target_weight_pct"] > 1e-9]
        signal_map = {
            (str(r.date), str(r.stock_code)): float(r.target_weight_pct)
            for r in s.itertuples()
        }

        w = weights_df.copy()
        w["date"] = w["date"].astype(str)
        w["stock_code"] = w["stock_code"].astype(str).str.zfill(6)
        w["weight_pct"] = pd.to_numeric(w["weight_pct"], errors="coerce").fillna(0.0)
        w = w[w["weight_pct"] > 1e-9]
        weight_map = {
            (str(r.date), str(r.stock_code)): float(r.weight_pct)
            for r in w.itertuples()
        }

        signal_total = int(len(signal_map))
        common = set(signal_map.keys()) & set(weight_map.keys())
        signal_match_count = int(sum(1 for k in common if _nearly_equal(signal_map[k], weight_map[k], tol=1e-9)))
        signal_match_ratio = float(signal_match_count / signal_total) if signal_total > 0 else 0.0
        signal_match_all = bool(signal_total > 0 and signal_map.keys() == weight_map.keys() and signal_match_count == signal_total)

    checks.append(CheckResult(
        "hardfail_winner_signal_target_weight_eq_weights_csv_100pct",
        signal_match_all,
        f"ratio={signal_match_ratio}, matched={signal_match_count}, total={signal_total}",
    ))

    summary_signal_ratio = summary.get("winner_signal_match_ratio")
    checks.append(CheckResult(
        "hardfail_summary_winner_signal_match_ratio_eq_1",
        _nearly_equal(summary_signal_ratio, 1.0, tol=1e-12),
        f"summary_ratio={summary_signal_ratio}",
    ))
    checks.append(CheckResult(
        "hardfail_summary_winner_signal_match_ratio_eq_computed",
        _nearly_equal(summary_signal_ratio, signal_match_ratio, tol=1e-12),
        f"summary_ratio={summary_signal_ratio}, computed_ratio={signal_match_ratio}",
    ))

    ui_portfolio_source = ui_data.get("portfolio_source", {}) or {}
    ui_portfolio_path = str(ui_portfolio_source.get("path", "") or "")
    checks.append(CheckResult(
        "hardfail_ui_portfolio_source_path_eq_canonical",
        ui_portfolio_path == EXPECTED_SINGLE_SOURCE_REL,
        f"ui_path={ui_portfolio_path}, expected={EXPECTED_SINGLE_SOURCE_REL}",
    ))
    checks.append(CheckResult(
        "hardfail_ui_portfolio_source_model_id_eq_winner",
        str(ui_portfolio_source.get("model_id", "")) == winner_id_validated and winner_id_validated != "",
        f"ui_model_id={ui_portfolio_source.get('model_id')}, winner={winner_id_validated}",
    ))
    ui_chart_path = str((ui_data.get("chart_source", {}) or {}).get("path", "") or "")
    checks.append(CheckResult(
        "hardfail_ui_chart_source_path_eq_canonical",
        ui_chart_path == "invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_chart_inputs_v4_6_kr.json",
        f"ui_chart_path={ui_chart_path}",
    ))

    summary_single_source = str(summary.get("portfolio_single_source_file", "") or "")
    checks.append(CheckResult(
        "hardfail_summary_single_source_path_eq_canonical",
        str(PORTFOLIO_SOURCE_JSON.resolve()) == str(Path(summary_single_source).resolve()) if summary_single_source else False,
        f"summary_path={summary_single_source}, canonical={PORTFOLIO_SOURCE_JSON}",
    ))
    summary_chart_source = str(summary.get("chart_input_source_file", "") or "")
    checks.append(CheckResult(
        "hardfail_summary_chart_source_path_eq_canonical",
        str(CHART_SOURCE_JSON.resolve()) == str(Path(summary_chart_source).resolve()) if summary_chart_source else False,
        f"summary_chart_source={summary_chart_source}, canonical={CHART_SOURCE_JSON}",
    ))

    ss_kpi = portfolio_source.get("kpi", {}) or {}
    checks.append(CheckResult(
        "hardfail_single_source_kpi_return_eq_summary",
        _nearly_equal(ss_kpi.get("return_2021_plus"), summary.get("winner_return_2021_plus")),
        f"single_source={ss_kpi.get('return_2021_plus')}, summary={summary.get('winner_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_single_source_kpi_cagr_eq_summary",
        _nearly_equal(ss_kpi.get("cagr_2021_plus"), summary.get("winner_cagr_2021_plus")),
        f"single_source={ss_kpi.get('cagr_2021_plus')}, summary={summary.get('winner_cagr_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_single_source_kpi_mdd_eq_summary",
        _nearly_equal(ss_kpi.get("mdd_2021_plus"), summary.get("winner_mdd_2021_plus")),
        f"single_source={ss_kpi.get('mdd_2021_plus')}, summary={summary.get('winner_mdd_2021_plus')}",
    ))

    chart_bridge = (chart_source.get("kpi_bridge", {}) or {})
    checks.append(CheckResult(
        "hardfail_chart_bridge_return_eq_summary",
        _nearly_equal(chart_bridge.get("winner_return_2021_plus_from_single_source"), summary.get("winner_return_2021_plus")),
        f"chart_bridge={chart_bridge.get('winner_return_2021_plus_from_single_source')}, summary={summary.get('winner_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_chart_bridge_cagr_eq_summary",
        _nearly_equal(chart_bridge.get("winner_cagr_2021_plus_from_single_source"), summary.get("winner_cagr_2021_plus")),
        f"chart_bridge={chart_bridge.get('winner_cagr_2021_plus_from_single_source')}, summary={summary.get('winner_cagr_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_chart_bridge_mdd_eq_summary",
        _nearly_equal(chart_bridge.get("winner_mdd_2021_plus_from_single_source"), summary.get("winner_mdd_2021_plus")),
        f"chart_bridge={chart_bridge.get('winner_mdd_2021_plus_from_single_source')}, summary={summary.get('winner_mdd_2021_plus')}",
    ))

    equity_return = None
    if not equity_df.empty and {"date", "equity"}.issubset(set(equity_df.columns)):
        eq = equity_df.copy()
        eq["date"] = pd.to_datetime(eq["date"], errors="coerce")
        eq["equity"] = pd.to_numeric(eq["equity"], errors="coerce")
        eq = eq.dropna(subset=["date", "equity"]).sort_values("date")
        eq = eq[eq["date"] >= pd.Timestamp("2021-01-01")]
        if not eq.empty and float(eq["equity"].iloc[0]) != 0.0:
            equity_return = float(eq["equity"].iloc[-1] / eq["equity"].iloc[0] - 1.0)
    checks.append(CheckResult(
        "hardfail_equity_right_edge_return_eq_summary",
        _nearly_equal(equity_return, summary.get("winner_return_2021_plus")),
        f"equity_return={equity_return}, summary_return={summary.get('winner_return_2021_plus')}",
    ))
    checks.append(CheckResult(
        "hardfail_equity_right_edge_return_eq_chart_right_edge",
        _nearly_equal(equity_return, chart_cont.get("winner_right_edge_return_2021_plus")),
        f"equity_return={equity_return}, chart_right_edge={chart_cont.get('winner_right_edge_return_2021_plus')}",
    ))

    baseline_path = baseline_manifest.get("promoted_baseline_file")
    checks.append(CheckResult(
        "baseline_manifest_single_path_present",
        bool(baseline_path),
        f"promoted_baseline_file={baseline_path}",
    ))

    failed = [c for c in checks if not c.passed]
    verdict = "PASS" if not failed else "FAIL"

    result = {
        "stage": "stage06",
        "version": "v4_6",
        "verdict": verdict,
        "reasons": [f"{c.name}: {c.detail}" for c in failed],
        "checks": [asdict(c) for c in checks],
        "artifacts": {
            "reports": [str(p) for p in reports],
            "charts": [str(p) for p in pngs],
            "csvs": [str(p) for p in csvs],
            "ui": str(ui_path),
            "single_source": str(PORTFOLIO_SOURCE_JSON),
            "equity_csv": str(EQUITY_CSV),
            "winner_signal_csv": str(WINNER_SIGNAL_CSV),
            "chart_source": str(CHART_SOURCE_JSON),
            "parity_gate_json": str(PARITY_GATE_JSON),
        },
        "data_mode_judgement": {
            "summary_data_mode": summary_mode,
            "validated_data_mode": validated_mode,
            "ui_data_mode": ui_mode,
            "summary_real_execution_ledger_used": summary_real_ledger,
            "validated_real_execution_ledger_used": validated_real_ledger,
            "summary_real_execution_parity_mode": parity_mode,
            "summary_real_execution_parity_label": parity_label_requested,
            "parity_gate_verdict": parity_verdict,
        },
    }
    return result


def write_outputs(result: dict) -> None:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    VERDICT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Stage06 v4_6 Validation Report",
        "",
        f"- Verdict: **{result['verdict']}**",
        f"- Stage: {result['stage']}",
        f"- Version: {result['version']}",
        f"- data_mode(summary/validated/ui): {((result.get('data_mode_judgement') or {}).get('summary_data_mode'))}/{((result.get('data_mode_judgement') or {}).get('validated_data_mode'))}/{((result.get('data_mode_judgement') or {}).get('ui_data_mode'))}",
        "",
        "## Failed Reasons",
    ]
    if result["reasons"]:
        lines.extend([f"- {r}" for r in result["reasons"]])
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Check Results",
    ])
    for c in result["checks"]:
        badge = "PASS" if c["passed"] else "FAIL"
        lines.append(f"- [{badge}] {c['name']} — {c['detail']}")

    lines.extend([
        "",
        "## Artifact Inventory",
        "- Reports:",
    ])
    lines.extend([f"  - {p}" for p in result["artifacts"]["reports"]] or ["  - (none)"])
    lines.append("- Charts:")
    lines.extend([f"  - {p}" for p in result["artifacts"]["charts"]] or ["  - (none)"])
    lines.append("- CSVs:")
    lines.extend([f"  - {p}" for p in result["artifacts"]["csvs"]] or ["  - (none)"])
    lines.append(f"- UI: {result['artifacts']['ui']}")
    lines.append(f"- Single Source: {result['artifacts'].get('single_source')}")
    lines.append(f"- Equity CSV: {result['artifacts'].get('equity_csv')}")
    lines.append(f"- Winner Signal CSV: {result['artifacts'].get('winner_signal_csv')}")
    lines.append(f"- Chart Source: {result['artifacts'].get('chart_source')}")
    lines.append(f"- Parity Gate JSON: {result['artifacts'].get('parity_gate_json')}")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    result = validate()
    write_outputs(result)
    print(json.dumps({
        "verdict": result["verdict"],
        "report": str(REPORT_MD),
        "json": str(VERDICT_JSON),
        "failed": len(result["reasons"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
