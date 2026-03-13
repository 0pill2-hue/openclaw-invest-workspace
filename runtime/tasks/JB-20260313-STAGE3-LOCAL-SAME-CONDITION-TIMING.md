# JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING

- ticket: JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING
- status: DONE
- checked_at: 2026-03-13 13:28:53 KST

## Goal
메인과 동일한 sample100 -> 611 eval-unit 조건으로 local 실행시간을 다시 측정해 기존 0.88초와 분리 보고한다.

## Result
- canonical local rerun path는 별도 611-row 전용 로컬 러너가 아니라, 아래 2단계였다.
  1. `python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --input-jsonl runtime/stage3_calibration_sample100.jsonl --output-csv runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_features.csv --claim-card-jsonl runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_claim_cards.jsonl --dart-signal-csv runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_dart.csv --macro-forecast-csv runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_macro.csv --summary-json runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_summary.json --backend llama_local --local-endpoint http://127.0.0.1:11434 --local-model llama_local_v1`
  2. `python3 invest/stages/stage3/scripts/stage3_main_brain_benchmark_adapter.py prepare --sample-jsonl runtime/stage3_calibration_sample100.jsonl --local-claim-cards-jsonl runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_claim_cards.jsonl --local-summary-json runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_summary.json --package-dir runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/same_condition_package --local-wall-time-sec 2.070943375`
- 2단계 fresh package의 `main_brain_input_rows.jsonl` eval-unit sequence는 기존 `runtime/stage3_main_brain_package_sample100/main_brain_input_rows.jsonl`와 `611/611` 완전 일치했다.
- fresh/local package 비교 시 row 내용은 `local_runtime_ms`를 제외하면 기존 package와 동일했다.
- main lane/token은 사용하지 않았다.

## Measured timing
- wall_time_sec: `2.070943375`
- records_loaded: `100`
- claim_cards_generated (= same eval units): `611`
- rows_output: `158`
- ms_per_eval_unit (= wall/611): `3.3894326923`
- ms_per_input_record (= wall/100): `20.70943375`
- existing package local_runtime_ms: `1.4402618658` (기존 0.88s 기반 균등배분값)
- fresh package local_runtime_ms: `3.3894326923` (이번 2.070943375s 기반 균등배분값)
- eval_unit_key_digest (fresh/existing): `e3c829c8ded8e3754ebbe195f24c4f6a72c97b2a`

## Apples-to-apples comparability limits
- 이번 local wall time은 `sample100`에 대한 local Stage3 스크립트 1회 end-to-end 실행시간이다. main timing은 동일 611 eval-unit 위에서 수동/분할된 5배치 main orchestration 실행시간이므로 orchestration surface가 다르다.
- local `per-row`는 스크립트가 unit-level latency를 직접 내보내지 않아 `wall_time / 611` 균등배분값이다. 즉 true unit latency는 미측정이다.
- main `main_runtime_ms`는 main 실행 중 row 단위로 별도 기록된 값이라 계측 방식이 다르다.
- 이번 재측정은 같은 host/runtime에서 나중 시점에 수행됐다. 원래 0.88s run과의 cache/warm-start/load 조건 차이는 `미확인`이다.
- 따라서 비교 가능한 핵심은 `같은 611 eval-unit surface`와 `같은 local script path`까지이며, runtime 환경조건까지 완전 동일하다고는 주장할 수 없다.

## Proof
- run timing: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/run_timing.json`
- run stdout: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/run_stdout.txt`
- run stderr: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/run_stderr.txt`
- fresh local summary: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_summary.json`
- fresh local claim cards: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/stage3_calibration_sample100_claim_cards.jsonl`
- same-condition package: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/same_condition_package/`
- proof summary: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/same_condition_timing_proof.json`

## Auto updates

### 2026-03-13 13:23:42 KST | auto_orchestrate
- summary: Delegated Stage3 local same-condition timing to subagent run e6f15882-06eb-446c-9c64-c96cef16e9e8
- phase: delegated_to_subagent
- detail: child_session=agent:main:subagent:026a8110-a9ad-49f0-bb4a-71bd6c8fdc62 local_only=true

### 2026-03-13 13:27:04 KST | owner_priority
- summary: Owner reprioritized this ticket above other analysis work; finish same-condition local timing first
- phase: delegated_to_subagent
- detail: focus=wall_time,per_row,comparability_limits only

### 2026-03-13 13:28:53 KST | subagent_complete
- summary: Measured fresh local same-condition timing and proved 611 eval-unit sequence equality vs existing main benchmark package
- phase: completed
- detail: wall_time_sec=2.070943375 ms_per_eval_unit=3.3894326923 eval_unit_key_digest=e3c829c8ded8e3754ebbe195f24c4f6a72c97b2a