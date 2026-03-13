# JB-20260313-STAGE3-FULL-APPLESTOAPPLES-TIMING

- ticket: JB-20260313-STAGE3-FULL-APPLESTOAPPLES-TIMING
- status: DONE
- checked_at: 2026-03-13 13:39:50 KST

## Goal
로컬/서브/메인 속도를 완전 동일조건(같은 orchestration surface + 같은 eval-unit 처리 방식 + 같은 계측 기준)으로 다시 측정한다.

## Hard rule
- `JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING`의 `2.070943375s` 값은 최종 속도 판정 근거에서 제외한다.

## Fully apples-to-apples definition (fixed)
Stage3에서 `완전 동일조건` 속도 비교로 인정하려면 아래가 모두 동시에 만족되어야 한다.

1. **같은 입력 surface**
   - 같은 sample set
   - 같은 eval-unit key sequence
   - 같은 scoring contract / output schema
2. **같은 orchestration surface**
   - 같은 runner 성격(자동/수동 import 혼합 금지)
   - 같은 session topology(로컬 단일 실행 vs 메인 직접 실행 vs 서브 실행이 서로 독립 lane으로 실제 존재)
   - 같은 batching / parallelism / merge 방식
3. **같은 timing boundary**
   - 모두 end-to-end wall time이거나,
   - 모두 true per-unit observed latency여야 한다.
   - 한 lane은 `wall/611` 균등배분, 다른 lane은 row 수기/추정 runtime, 다른 lane은 batch wall/max wall이면 불가다.
4. **같은 measurement semantics**
   - 시작/종료 시점, transport/UI/manual fill 포함 범위, batch 합산 규칙이 동일해야 한다.
5. **독립 lane 실체**
   - `local`, `subagent`, `main` 3개가 각각 별도 실행 artifact와 동일 계측 필드를 가져야 한다.

`같은 611 eval-unit surface`는 필요조건일 뿐 충분조건이 아니다.

## Disposition
- **최종 판정: 비교 불가**
- 이유: 현재 repo/증빙 기준으로는 local/subagent/main 3-lane을 동일 orchestration + 동일 계측 의미로 다시 재는 canonical path가 없다.
- 따라서 이번 티켓에서는 **새 속도 우열 판정은 내리지 않는다.**
- 특히 이전 local rerun `2.070943375s`는 최종 speed judgment에서 **명시적으로 제외**한다.

## Why comparison is not executable now
1. **현재 benchmark adaptor는 local vs main import만 지원하고 subagent lane을 별도 입력/비교 대상으로 갖지 않는다.**
   - `invest/stages/stage3/scripts/stage3_main_brain_benchmark_adapter.py`는 `prepare(sample + local claim cards) -> main manual package -> compare(local_rows_jsonl, main_results_jsonl)` 구조다.
   - 즉 현재 구현 계약에는 독립 `subagent_results_jsonl` / `subagent_run_metrics.json` 자리가 없다.

2. **현재 "main100 actual run" 자체가 단일 main-lane 직실행이 아니라 5개 subagent batch 분할 실행이다.**
   - `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json` notes:
     - `main100 actual run split across 5 subagent batches`
   - `runtime/stage3_main_brain_package_sample100/main_brain_run_metrics.json` notes도 동일하다.
   - `runtime/stage3_main_brain_package_sample100/batches/manifest.json`은 실제로 5 batch 분할을 증명한다.
   - 따라서 현재 artifact에서 `main`과 `subagent`는 독립 비교 lane이 아니라 이미 섞여 있다.

3. **local timing은 unit-observed latency가 아니라 end-to-end wall time의 균등배분값이다.**
   - `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/same_condition_timing_proof.json`
     - `wall_time_sec = 2.070943375`
     - `ms_per_eval_unit = 3.3894326923`
     - comparability limit에 `wall/611` 균등배분이며 true unit latency가 아님이 명시돼 있다.
   - 즉 local row runtime은 observed per-row가 아니라 derived per-row다.

4. **main timing도 단일 의미가 아니다.**
   기존 artifact에서 동시에 아래 3개 timing semantic이 존재한다.
   - row mean: `main_runtime_ms_mean = 3429.7872340425533`
   - full-run wall: `run_wall_time_sec = 1021.0`
   - batch wall sum: `run_wall_time_sec_sum_batches = 2418.8`

   그리고 `611 × 3429.7872340425533ms = 2095.6s`로 계산되어,
   - `2095.6s != 1021.0s`
   - `2095.6s != 2418.8s`

   즉 현재 main row runtime / full wall / batch walls는 같은 timing boundary가 아니다.

5. **수동/분할/병합 orchestration이 local 단일 스크립트 path와 동치가 아니다.**
   - local rerun은 sample100에 대한 local Stage3 스크립트 1회 end-to-end 실행이다.
   - current main artifact는 수동 package + 5-batch subagent fill + merge 결과다.
   - 같은 eval-unit 611개라도 실행 topology가 달라 apples-to-apples 속도 비교로 사용할 수 없다.

## Bounded measurement decision
- **새 benchmark run 미실행**
- 사유: 현재 계측/오케스트레이션 불일치가 해소되지 않은 상태에서 local/subagent/main을 다시 하나 더 재도 최종 apples-to-apples speed judgment 근거가 되지 않는다.
- 이번 티켓에서 수행한 것은 기존 증빙의 **bounded consistency extraction**뿐이며, 최종 속도 판정 수치 추가는 하지 않았다.

## Exact missing equivalence point
아래 중 하나가 먼저 있어야 full apples-to-apples timing이 가능하다.

1. **공통 benchmark harness**
   - 같은 input package를 `local / subagent / main` 각 lane에서 실행
   - 같은 batching/parallelism 정책 사용
   - 같은 start/stop boundary로 `run_wall_time_sec` 기록
   - 가능하면 같은 schema로 `observed_per_unit_runtime_ms` 기록
2. **독립 main lane와 독립 subagent lane 분리 artifact**
   - 현재처럼 `main` 결과가 실제로 subagent batches에 의해 채워지는 구조면 분리 비교 불가
3. **timing semantic 단일화**
   - derived row runtime, 수기 row runtime, batch wall max, batch wall sum을 섞지 않고 한 가지 의미로 고정

## Proof
- local same-condition proof: `runtime/tasks/proofs/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING/same_condition_timing_proof.json`
- local same-condition ticket: `runtime/tasks/JB-20260313-STAGE3-LOCAL-SAME-CONDITION-TIMING.md`
- current comparison summary: `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json`
- current main run metrics: `runtime/stage3_main_brain_package_sample100/main_brain_run_metrics.json`
- batch split manifest: `runtime/stage3_main_brain_package_sample100/batches/manifest.json`
- per-batch timing proofs:
  - `runtime/stage3_main_brain_package_sample100/batches/batch_01/batch_metrics.json`
  - `runtime/stage3_main_brain_package_sample100/batches/batch_02/batch_metrics.json`
  - `runtime/stage3_main_brain_package_sample100/batches/batch_03/batch_metrics.json`
  - `runtime/stage3_main_brain_package_sample100/batches/batch_04/batch_metrics.json`
  - `runtime/stage3_main_brain_package_sample100/batches/batch_05/batch_metrics.json`
- current adaptor contract: `invest/stages/stage3/scripts/stage3_main_brain_benchmark_adapter.py`
- design contract showing future target lanes only (not current executable equivalence): `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`

## Auto updates

### 2026-03-13 13:36:27 KST | owner_remeasure
- summary: Started fully apples-to-apples timing disposition via subagent run 728c0f60-1a74-4779-81e9-72a1577cb520
- phase: delegated_to_subagent
- detail: previous local 2.07s excluded from final judgment

### 2026-03-13 13:39:50 KST | subagent_complete
- summary: Full apples-to-apples Stage3 speed comparison is not executable now; disposition fixed as 비교 불가
- phase: completed
- detail: main artifact is already split across 5 subagent batches, local per-row runtime is derived from wall/611, and current adaptor has no independent subagent lane contract
