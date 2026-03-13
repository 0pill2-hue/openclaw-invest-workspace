# JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING

- ticket: JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING
- status: IN_PROGRESS
- checked_at: 2026-03-13 11:22 KST

## Goal
메인과 동일한 sample100 -> 611 eval-unit 조건으로 local 실행시간을 다시 측정해 기존 0.88초와 분리 보고한다.

## Current understanding
- existing local 0.88s is the 100-doc calibration pipeline wall time, not necessarily the same orchestration/eval-unit surface as main 611-row execution.
- same-input package exists under `runtime/stage3_main_brain_package_sample100/` and includes `main_brain_input_rows.jsonl`, `local_benchmark_rows.jsonl`, and package manifest linking back to `runtime/stage3_calibration_sample100.jsonl`.

## Next action
- identify the canonical local rerun path that consumes the same 611 eval-unit set (or prove why current package rows already represent that timing surface)
- run local timing measurement and record wall / per-row metrics
- report apples-to-apples comparability limits explicitly
