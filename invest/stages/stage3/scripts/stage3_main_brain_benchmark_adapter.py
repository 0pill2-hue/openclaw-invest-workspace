#!/usr/bin/env python3
"""
Stage3 main_brain benchmark adaptor.

Workflow
1) prepare:
   - Build local benchmark rows from sample jsonl + local claim cards.
   - Generate main_brain manual package (input rows, prompt, results template).
2) compare:
   - Merge imported main_brain results with local rows.
   - Emit comparison rows + summary metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"invalid jsonl at {path}:{i}: {e}") from e
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _safe_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _safe_int(v) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _derive_week_used_percent(metrics: dict, key_used: str, key_left: str) -> float | None:
    used = _safe_float(metrics.get(key_used))
    if used is not None:
        return used
    left = _safe_float(metrics.get(key_left))
    if left is None:
        return None
    return 100.0 - left


def _eval_unit_id(record_id: str, chunk_id, focus_symbol: str) -> str:
    raw = f"{record_id}|{chunk_id}|{focus_symbol}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _build_local_rows(
    claim_cards: list[dict],
    sample_index: dict[str, dict],
    local_runtime_ms: float | None,
) -> list[dict]:
    rows: list[dict] = []
    for card in claim_cards:
        record_id = str(card.get("record_id", "")).strip()
        chunk_id = card.get("chunk_id")
        focus_symbol = str(card.get("focus_symbol", card.get("symbol", ""))).strip()
        if not record_id or chunk_id is None or not focus_symbol:
            continue
        eval_unit_id = _eval_unit_id(record_id, chunk_id, focus_symbol)
        sample_row = sample_index.get(record_id, {})
        rows.append(
            {
                "schema_version": "stage3_benchmark_row_v1",
                "eval_unit_id": eval_unit_id,
                "record_id": record_id,
                "chunk_id": chunk_id,
                "focus_symbol": focus_symbol,
                "date": card.get("date") or "",
                "source": card.get("source") or sample_row.get("source") or "",
                "source_family": card.get("source_family") or sample_row.get("source_family") or "",
                "published_at": sample_row.get("published_at") or "",
                "chunk_text": card.get("chunk_text") or "",
                "evidence_text": card.get("evidence_text") or "",
                "local_upside_score_card": _safe_float(card.get("upside_score_card")),
                "local_downside_risk_score_card": _safe_float(card.get("downside_risk_score_card")),
                "local_bm_sector_fit_score_card": _safe_float(card.get("bm_sector_fit_score_card")),
                "local_persistence_score_card": _safe_float(card.get("persistence_score_card")),
                "local_dominant_axis": card.get("dominant_axis"),
                "local_claim_confidence": _safe_float(card.get("claim_confidence")),
                "local_claim_weight": _safe_float(card.get("claim_weight")),
                "local_runtime_ms": local_runtime_ms,
            }
        )
    return rows


def _prompt_text() -> str:
    return (
        "# Stage3 Main Brain Benchmark Package\n\n"
        "You are scoring Stage3 claim-card units using the same evaluation unit as local lane.\n\n"
        "Evaluation unit key:\n"
        "- eval_unit_id\n"
        "- record_id\n"
        "- chunk_id\n"
        "- focus_symbol\n\n"
        "For each row in `main_brain_input_rows.jsonl`, write one result row into\n"
        "`main_brain_results_template.jsonl` by filling null fields only.\n\n"
        "Required row-level fields to fill:\n"
        "- main_upside_score_card (0~100)\n"
        "- main_downside_risk_score_card (0~100)\n"
        "- main_bm_sector_fit_score_card (0~100)\n"
        "- main_persistence_score_card (0~100)\n"
        "- main_dominant_axis (upside|downside|bm|persistence)\n"
        "- main_claim_confidence (0~1)\n"
        "- main_claim_weight (0~1)\n"
        "- main_runtime_ms (elapsed inference time for this unit)\n"
        "- main_model_ref (string)\n"
        "- main_status (`ok` if filled, `error` if failed)\n"
        "- main_error (set only when status=error)\n\n"
        "Optional row-level fields:\n"
        "- main_evidence_text\n"
        "- main_note\n\n"
        "After the run, also fill `main_brain_run_metrics_template.json` once per benchmark run.\n"
        "Recommended run-level capture fields:\n"
        "- total_input_tokens\n"
        "- total_output_tokens\n"
        "- total_cached_input_tokens (optional)\n"
        "- total_tokens (optional if input+output available)\n"
        "- run_wall_time_sec\n"
        "- week_left_percent_before\n"
        "- week_left_percent_after\n"
        "- week_used_percent_before (optional if left% provided)\n"
        "- week_used_percent_after (optional if left% provided)\n"
        "- context_tokens_before / context_tokens_after (optional)\n\n"
        "Do not change key IDs. Do not drop rows.\n"
    )


def cmd_prepare(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    sample_rows = _read_jsonl(args.sample_jsonl)
    claim_cards = _read_jsonl(args.local_claim_cards_jsonl)
    summary = json.loads(args.local_summary_json.read_text(encoding="utf-8"))
    sample_index = {str(r.get("record_id", "")).strip(): r for r in sample_rows if r.get("record_id")}

    local_runtime_ms = None
    if args.local_wall_time_sec is not None and len(claim_cards) > 0:
        local_runtime_ms = float(args.local_wall_time_sec) * 1000.0 / len(claim_cards)

    local_rows = _build_local_rows(claim_cards, sample_index, local_runtime_ms)
    input_rows = []
    template_rows = []
    for row in local_rows:
        input_rows.append(
            {
                "eval_unit_id": row["eval_unit_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "focus_symbol": row["focus_symbol"],
                "published_at": row["published_at"],
                "source_family": row["source_family"],
                "source": row["source"],
                "chunk_text": row["chunk_text"],
                "evidence_text": row["evidence_text"],
            }
        )
        template_rows.append(
            {
                "schema_version": "stage3_main_brain_result_v1",
                "eval_unit_id": row["eval_unit_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "focus_symbol": row["focus_symbol"],
                "main_upside_score_card": None,
                "main_downside_risk_score_card": None,
                "main_bm_sector_fit_score_card": None,
                "main_persistence_score_card": None,
                "main_dominant_axis": None,
                "main_claim_confidence": None,
                "main_claim_weight": None,
                "main_evidence_text": None,
                "main_runtime_ms": None,
                "main_model_ref": None,
                "main_status": "pending",
                "main_error": None,
                "main_note": None,
            }
        )

    out_dir = args.package_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "local_benchmark_rows.jsonl", local_rows)
    _write_jsonl(out_dir / "main_brain_input_rows.jsonl", input_rows)
    _write_jsonl(out_dir / "main_brain_results_template.jsonl", template_rows)
    (out_dir / "main_brain_prompt.md").write_text(_prompt_text(), encoding="utf-8")
    run_metrics_template = {
        "schema_version": "stage3_main_brain_run_metrics_v1",
        "generated_at_utc": _utc_now(),
        "rows_expected": len(local_rows),
        "main_model_ref": None,
        "run_wall_time_sec": None,
        "total_input_tokens": None,
        "total_output_tokens": None,
        "total_cached_input_tokens": None,
        "total_tokens": None,
        "week_left_percent_before": None,
        "week_left_percent_after": None,
        "week_used_percent_before": None,
        "week_used_percent_after": None,
        "context_tokens_before": None,
        "context_tokens_after": None,
        "notes": None,
    }
    (out_dir / "main_brain_run_metrics_template.json").write_text(
        json.dumps(run_metrics_template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prepare_elapsed_ms = (time.perf_counter() - t0) * 1000.0
    manifest = {
        "schema_version": "stage3_main_brain_package_v1",
        "generated_at_utc": _utc_now(),
        "sample_jsonl": str(args.sample_jsonl),
        "local_claim_cards_jsonl": str(args.local_claim_cards_jsonl),
        "local_summary_json": str(args.local_summary_json),
        "local_rows_count": len(local_rows),
        "sample_rows_count": len(sample_rows),
        "summary_records_loaded": summary.get("records_loaded"),
        "summary_claim_cards_generated": summary.get("claim_cards_generated"),
        "summary_rows_output": summary.get("rows_output"),
        "estimated_local_runtime_ms_per_unit": local_runtime_ms,
        "prepare_elapsed_ms": prepare_elapsed_ms,
        "files": [
            "local_benchmark_rows.jsonl",
            "main_brain_input_rows.jsonl",
            "main_brain_results_template.jsonl",
            "main_brain_prompt.md",
            "main_brain_run_metrics_template.json",
        ],
    }
    (out_dir / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"prepared package: {out_dir}")
    print(f"local_units={len(local_rows)} prepare_elapsed_ms={prepare_elapsed_ms:.2f}")


def _mae(values: list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def cmd_compare(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    local_rows = _read_jsonl(args.local_rows_jsonl)
    main_rows = _read_jsonl(args.main_results_jsonl)
    run_metrics: dict = {}
    if args.run_metrics_json is not None and args.run_metrics_json.exists():
        run_metrics = json.loads(args.run_metrics_json.read_text(encoding="utf-8"))

    local_by_id = {r["eval_unit_id"]: r for r in local_rows if r.get("eval_unit_id")}
    main_by_id = {r["eval_unit_id"]: r for r in main_rows if r.get("eval_unit_id")}

    comparison_rows: list[dict] = []
    axis_delta = {"upside": [], "downside": [], "bm": [], "persistence": [], "confidence": [], "weight": []}
    dominant_match = 0
    compared = 0
    main_runtime_values = []
    local_runtime_values = []
    status_counter = Counter()

    for eval_unit_id, local in local_by_id.items():
        main = main_by_id.get(eval_unit_id)
        main_status = "missing"
        if main is not None:
            main_status = str(main.get("main_status") or "ok")
        status_counter[main_status] += 1

        row = {
            "schema_version": "stage3_lane_comparison_row_v1",
            "eval_unit_id": eval_unit_id,
            "record_id": local["record_id"],
            "chunk_id": local["chunk_id"],
            "focus_symbol": local["focus_symbol"],
            "local_dominant_axis": local.get("local_dominant_axis"),
            "main_dominant_axis": main.get("main_dominant_axis") if main else None,
            "main_status": main_status,
            "local_runtime_ms": _safe_float(local.get("local_runtime_ms")),
            "main_runtime_ms": _safe_float(main.get("main_runtime_ms")) if main else None,
            "delta_upside_score_card": None,
            "delta_downside_risk_score_card": None,
            "delta_bm_sector_fit_score_card": None,
            "delta_persistence_score_card": None,
            "delta_claim_confidence": None,
            "delta_claim_weight": None,
        }

        if row["local_runtime_ms"] is not None:
            local_runtime_values.append(row["local_runtime_ms"])
        if row["main_runtime_ms"] is not None:
            main_runtime_values.append(row["main_runtime_ms"])

        if main is not None and main_status == "ok":
            pairs = [
                ("upside", local.get("local_upside_score_card"), main.get("main_upside_score_card"), "delta_upside_score_card"),
                ("downside", local.get("local_downside_risk_score_card"), main.get("main_downside_risk_score_card"), "delta_downside_risk_score_card"),
                ("bm", local.get("local_bm_sector_fit_score_card"), main.get("main_bm_sector_fit_score_card"), "delta_bm_sector_fit_score_card"),
                ("persistence", local.get("local_persistence_score_card"), main.get("main_persistence_score_card"), "delta_persistence_score_card"),
                ("confidence", local.get("local_claim_confidence"), main.get("main_claim_confidence"), "delta_claim_confidence"),
                ("weight", local.get("local_claim_weight"), main.get("main_claim_weight"), "delta_claim_weight"),
            ]
            has_numeric = False
            for key, lv, mv, out_key in pairs:
                lfv = _safe_float(lv)
                mfv = _safe_float(mv)
                if lfv is None or mfv is None:
                    continue
                delta = mfv - lfv
                row[out_key] = delta
                axis_delta[key].append(abs(delta))
                has_numeric = True
            if has_numeric:
                compared += 1
            if local.get("local_dominant_axis") and local.get("local_dominant_axis") == main.get("main_dominant_axis"):
                dominant_match += 1

        comparison_rows.append(row)

    compare_elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _write_jsonl(args.output_rows_jsonl, comparison_rows)

    total_input_tokens = _safe_int(run_metrics.get("total_input_tokens"))
    total_output_tokens = _safe_int(run_metrics.get("total_output_tokens"))
    total_cached_input_tokens = _safe_int(run_metrics.get("total_cached_input_tokens"))
    total_tokens = _safe_int(run_metrics.get("total_tokens"))
    if total_tokens is None and total_input_tokens is not None and total_output_tokens is not None:
        total_tokens = total_input_tokens + total_output_tokens

    week_left_before = _safe_float(run_metrics.get("week_left_percent_before"))
    week_left_after = _safe_float(run_metrics.get("week_left_percent_after"))
    week_used_before = _derive_week_used_percent(run_metrics, "week_used_percent_before", "week_left_percent_before")
    week_used_after = _derive_week_used_percent(run_metrics, "week_used_percent_after", "week_left_percent_after")
    week_usage_consumed_pct_points = None
    if week_used_before is not None and week_used_after is not None:
        week_usage_consumed_pct_points = week_used_after - week_used_before
    elif week_left_before is not None and week_left_after is not None:
        week_usage_consumed_pct_points = week_left_before - week_left_after

    remaining_week_budget_consumed_percent = None
    if week_usage_consumed_pct_points is not None and week_left_before not in (None, 0):
        remaining_week_budget_consumed_percent = (week_usage_consumed_pct_points / week_left_before) * 100.0

    summary = {
        "schema_version": "stage3_lane_comparison_summary_v2",
        "generated_at_utc": _utc_now(),
        "local_rows_jsonl": str(args.local_rows_jsonl),
        "main_results_jsonl": str(args.main_results_jsonl),
        "main_run_metrics_json": str(args.run_metrics_json) if args.run_metrics_json is not None else None,
        "rows_total": len(local_rows),
        "rows_compared_numeric": compared,
        "main_status_counts": dict(status_counter),
        "mae_upside_score_card": _mae(axis_delta["upside"]),
        "mae_downside_risk_score_card": _mae(axis_delta["downside"]),
        "mae_bm_sector_fit_score_card": _mae(axis_delta["bm"]),
        "mae_persistence_score_card": _mae(axis_delta["persistence"]),
        "mae_claim_confidence": _mae(axis_delta["confidence"]),
        "mae_claim_weight": _mae(axis_delta["weight"]),
        "dominant_axis_match_count": dominant_match,
        "dominant_axis_match_rate": (dominant_match / len(local_rows)) if local_rows else None,
        "local_runtime_ms_mean": _mae(local_runtime_values),
        "main_runtime_ms_mean": _mae(main_runtime_values),
        "compare_elapsed_ms": compare_elapsed_ms,
        "main_model_ref": run_metrics.get("main_model_ref"),
        "main_run_wall_time_sec": _safe_float(run_metrics.get("run_wall_time_sec")),
        "main_input_tokens_total": total_input_tokens,
        "main_output_tokens_total": total_output_tokens,
        "main_cached_input_tokens_total": total_cached_input_tokens,
        "main_total_tokens": total_tokens,
        "main_tokens_per_row": (total_tokens / len(local_rows)) if (total_tokens is not None and local_rows) else None,
        "week_left_percent_before": week_left_before,
        "week_left_percent_after": week_left_after,
        "week_used_percent_before": week_used_before,
        "week_used_percent_after": week_used_after,
        "week_usage_consumed_pct_points": week_usage_consumed_pct_points,
        "remaining_week_budget_consumed_percent": remaining_week_budget_consumed_percent,
        "context_tokens_before": _safe_int(run_metrics.get("context_tokens_before")),
        "context_tokens_after": _safe_int(run_metrics.get("context_tokens_after")),
        "notes": run_metrics.get("notes"),
    }
    args.output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"comparison rows: {args.output_rows_jsonl}")
    print(f"comparison summary: {args.output_summary_json}")
    print(
        f"rows_total={len(local_rows)} compared={compared} compare_elapsed_ms={compare_elapsed_ms:.2f} "
        f"total_tokens={total_tokens if total_tokens is not None else 'na'} "
        f"week_usage_consumed_pct_points={week_usage_consumed_pct_points if week_usage_consumed_pct_points is not None else 'na'}"
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage3 main_brain benchmark adaptor")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_prepare = sub.add_parser("prepare", help="Generate package for manual main_brain run")
    p_prepare.add_argument("--sample-jsonl", type=Path, required=True)
    p_prepare.add_argument("--local-claim-cards-jsonl", type=Path, required=True)
    p_prepare.add_argument("--local-summary-json", type=Path, required=True)
    p_prepare.add_argument("--package-dir", type=Path, required=True)
    p_prepare.add_argument(
        "--local-wall-time-sec",
        type=float,
        default=None,
        help="Optional wall time of local run; used to estimate local_runtime_ms per eval unit.",
    )
    p_prepare.set_defaults(func=cmd_prepare)

    p_compare = sub.add_parser("compare", help="Compare imported main_brain results vs local rows")
    p_compare.add_argument("--local-rows-jsonl", type=Path, required=True)
    p_compare.add_argument("--main-results-jsonl", type=Path, required=True)
    p_compare.add_argument("--output-rows-jsonl", type=Path, required=True)
    p_compare.add_argument("--output-summary-json", type=Path, required=True)
    p_compare.add_argument(
        "--run-metrics-json",
        type=Path,
        default=None,
        help="Optional aggregate run metrics json (tokens / week usage / context usage).",
    )
    p_compare.set_defaults(func=cmd_compare)
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
