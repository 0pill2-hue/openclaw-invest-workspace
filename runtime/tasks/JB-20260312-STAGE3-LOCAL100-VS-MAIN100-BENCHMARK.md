# JB-20260312-STAGE3-LOCAL100-VS-MAIN100-BENCHMARK

- ticket: JB-20260312-STAGE3-LOCAL100-VS-MAIN100-BENCHMARK
- status: DONE
- checked_at: 2026-03-12 09:54 KST

## Goal
동일 샘플 100건 기준으로 Stage3 local brain과 main brain의 점수/근거/시간을 실제 비교 측정한다.

## Summary
- sample100 local lane와 동일 evaluation unit 611개에 대해 main lane actual run을 5개 배치로 분할 실행했다.
- 배치 결과를 병합해 `main_brain_results_actual.jsonl`을 만들고 local vs main compare를 실제 수행했다.
- token 소요량과 주간 사용량 소모 비율까지 run metrics에 포함했다.

## Outputs
- main results: `runtime/stage3_main_brain_package_sample100/main_brain_results_actual.jsonl`
- run metrics: `runtime/stage3_main_brain_package_sample100/main_brain_run_metrics.json`
- comparison rows: `runtime/stage3_main_brain_package_sample100/lane_comparison_rows_actual.jsonl`
- comparison summary: `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json`

## Key measured results
- rows_total: `611`
- rows_compared_numeric: `611`
- main_status_counts: `ok=611`
- dominant_axis_match_rate: `0.4239`
- mae_upside_score_card: `17.9995`
- mae_downside_risk_score_card: `14.3006`
- mae_bm_sector_fit_score_card: `26.6678`
- mae_persistence_score_card: `14.5928`
- mae_claim_confidence: `0.1538`
- mae_claim_weight: `0.3749`
- local_runtime_ms_mean: `1.4403`
- main_runtime_ms_mean: `3429.7872`
- main_run_wall_time_sec: `1021.0`
- main_total_tokens: `959300`
- main_tokens_per_row: `1570.0491`
- week_usage_consumed_pct_points: `2.0`
- remaining_week_budget_consumed_percent: `2.2472`

## Proof
- summary: `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json`
- run metrics: `runtime/stage3_main_brain_package_sample100/main_brain_run_metrics.json`
- merged results: `runtime/stage3_main_brain_package_sample100/main_brain_results_actual.jsonl`

## Next action
- `JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION`로 넘어가 external/web 100 lane package instance를 만들고 local/main/external 삼각비교를 계속 진행한다.
