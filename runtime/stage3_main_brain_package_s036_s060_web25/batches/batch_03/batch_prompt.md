# Stage3 Main Brain Benchmark Package

You are scoring Stage3 claim-card units using the same evaluation unit as local lane.

Evaluation unit key:
- eval_unit_id
- record_id
- chunk_id
- focus_symbol

For each row in `main_brain_input_rows.jsonl`, write one result row into
`main_brain_results_template.jsonl` by filling null fields only.

Required row-level fields to fill:
- main_upside_score_card (0~100)
- main_downside_risk_score_card (0~100)
- main_bm_sector_fit_score_card (0~100)
- main_persistence_score_card (0~100)
- main_dominant_axis (upside|downside|bm|persistence)
- main_claim_confidence (0~1)
- main_claim_weight (0~1)
- main_runtime_ms (elapsed inference time for this unit)
- main_model_ref (string)
- main_status (`ok` if filled, `error` if failed)
- main_error (set only when status=error)

Optional row-level fields:
- main_evidence_text
- main_note

After the run, also fill `main_brain_run_metrics_template.json` once per benchmark run.
Recommended run-level capture fields:
- total_input_tokens
- total_output_tokens
- total_cached_input_tokens (optional)
- total_tokens (optional if input+output available)
- run_wall_time_sec
- week_left_percent_before
- week_left_percent_after
- week_used_percent_before (optional if left% provided)
- week_used_percent_after (optional if left% provided)
- context_tokens_before / context_tokens_after (optional)

Do not change key IDs. Do not drop rows.


## Batch scope
- batch_id: batch_03
- rows_in_batch: 31
- start_row_1indexed: 65
- end_row_1indexed: 95
- fill only this batch's results_template.jsonl, then merge later into package root main_brain_results_actual.jsonl.
