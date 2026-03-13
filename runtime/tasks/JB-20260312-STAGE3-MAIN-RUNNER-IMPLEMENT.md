# JB-20260312-STAGE3-MAIN-RUNNER-IMPLEMENT

- ticket: JB-20260312-STAGE3-MAIN-RUNNER-IMPLEMENT
- status: IMPLEMENTED
- checked_at: 2026-03-12

## Summary
- Stage3 `main_brain` 자동 실행 lane이 현재 repo에서 즉시 가능하지 않은 제약을 반영해, 수동 패키지 생성 + 결과 import + lane 비교가 가능한 adaptor를 구현했다.
- 비교 키는 기존 local semantic unit을 유지해 `(record_id, chunk_id, focus_symbol)` 기반으로 고정했다.
- 비교 스키마에 runtime 필드(`local_runtime_ms`, `main_runtime_ms`)와 adapter 처리시간(`prepare_elapsed_ms`, `compare_elapsed_ms`)을 포함했다.
- 추가로 run-level 메트릭 템플릿(`main_brain_run_metrics_template.json`)과 compare 집계를 붙여 token 소요량, row당 token, 주간 사용량 소모 비율도 함께 계산할 수 있게 했다.

## Touched paths
- `invest/stages/stage3/scripts/stage3_main_brain_benchmark_adapter.py`
- `runtime/tasks/JB-20260312-STAGE3-MAIN-RUNNER-IMPLEMENT.md`

## Manual step (required)
1. `prepare`로 생성된 `main_brain_input_rows.jsonl` + `main_brain_prompt.md` + `main_brain_results_template.jsonl`을 사용해 main_brain 쪽에서 수동 점수를 채운다.
2. 같은 run에서 `main_brain_run_metrics_template.json`에 total input/output tokens, run wall time, 주간 사용량 before/after를 함께 기록한다.
3. 채워진 결과 파일과 run metrics 파일을 `compare`에 넣어 local 대비 비교 결과(`comparison rows + summary`)를 생성한다.

## Verification
- `python3 invest/stages/stage3/scripts/stage3_main_brain_benchmark_adapter.py prepare --sample-jsonl runtime/stage3_calibration_sample100.jsonl --local-claim-cards-jsonl runtime/stage3_calibration_sample100_claim_cards.jsonl --local-summary-json runtime/stage3_calibration_sample100_summary.json --package-dir runtime/stage3_main_brain_package_sample100 --local-wall-time-sec 0.88`
  - result: `runtime/stage3_main_brain_package_sample100/`
  - local_units=`611`
  - package now includes `main_brain_run_metrics_template.json`
- mock identity compare smoke:
  - outputs: `runtime/stage3_main_brain_package_sample100/lane_comparison_rows.jsonl`, `runtime/stage3_main_brain_package_sample100/lane_comparison_summary.json`
  - result: `rows_total=611`, `rows_compared_numeric=611`
  - compare accepts `--run-metrics-json` and emits token/week-usage summary fields when provided

## Next action
1. sample100 기준으로 `runtime/stage3_main_brain_package_sample100/main_brain_input_rows.jsonl` + `main_brain_prompt.md` + `main_brain_results_template.jsonl`을 사용해 실제 main_brain 결과를 수동 확보한다.
2. 같은 run의 token usage / weekly usage before-after를 `main_brain_run_metrics_template.json`에 기록한다.
3. 실제 결과 파일로 `compare --run-metrics-json ...`를 다시 실행해 MAE/축 일치율/시간/토큰/주간사용량 지표를 기록한다.
