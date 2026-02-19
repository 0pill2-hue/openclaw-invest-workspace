# stage05_result_v3_7_kr

## inputs
- `invest/data/raw/kr/ohlcv/*.csv`
- `invest/data/raw/kr/supply/*_supply.csv`
- lock reference: `invest/results/validated/stage05_baselines_v3_6_kr_r03.json`
- execution script: `scripts/stage05_tuning_loop_v3_7_kr.py`

## run_command(or process)
- `python3 scripts/stage05_tuning_loop_v3_7_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_7_kr.json`
- `reports/stage_updates/stage05/stage05_brainstorm_decision_v3_7_kr.md`
- `reports/stage_updates/stage05/stage05_result_v3_7_kr.md`

## quality_gates
- Rulebook 고정 제약(1~6 / 20거래일 / +15% / 월30%): PASS
- KRX only: PASS
- external_proxy 비교군 전용: PASS
- numeric_locked=true: PASS
- numeric_guard(-5%) PASS: PASS
- internal_3000_gate_pass: PASS

## failure_policy
- numeric_guard FAIL 라운드는 즉시 폐기
- changed_params 공백 라운드는 즉시 폐기
- internal_3000_gate FAIL 시 Stage06 진입 금지

## proof
- `invest/results/validated/stage05_baselines_v3_7_kr.json`
- `scripts/stage05_tuning_loop_v3_7_kr.py`
- `invest/docs/strategy/RULEBOOK_V3.md`

---

## A) 라운드 결과 (numeric freeze governance)

| round | numeric_locked | numeric_return | numeric_guard_floor | numeric_guard_pass | qualitative_return | hybrid_return | qual/hybrid changed_params |
|---|---|---:|---:|---|---:|---:|---|
| r01_qh_tune | true | 40.086584 | 38.082255 | pass | 6.310726 | 3.258784 | qual_buzz 0.80→0.82, qual_ret 0.20→0.18 |
| r02_qh_tune (adopted) | true | 40.086584 | 38.082255 | pass | 6.033227 | 4.701117 | qual_buzz 0.82→0.78, qual_ret 0.18→0.21 |
| r03_qh_tune (backup) | true | 40.086584 | 38.082255 | pass | 6.033227 | 4.638488 | qual_buzz 0.78→0.76, qual_ret 0.21→0.20 |

---

## B) 핵심 검증
- baseline_internal_best_id: `numeric`
- baseline_internal_best_return: `40.08658392425643` (4008.66%)
- internal_3000_gate_pass: `pass`

### 3종 성과 분포(쏠림 점검)
- numeric: `40.08658392425643`
- qualitative: `6.033227472401938`
- hybrid: `4.701117098206695`
- best_to_second_ratio: `6.6443`
- one_sided_skew_flag: `true`

해석:
- 단일 numeric 우위는 여전히 큼(쏠림 잔존).
- 다만 v3_7에서 hybrid는 잠금기준 대비 상승(+0.2159)하여 내부 일관성은 소폭 개선.

---

## C) changed_params (직전 대비)

### 직전 베이스라인(v3_6_kr_r03) 대비
- 고정(LOCK): numeric 파라미터 전부 유지
  - `universe_limit=180, max_pos=5, trend_span_fast=8, trend_span_slow=36, ret_short=10, ret_mid=40, flow_scale=1.2e8, fee=0.003`
  - Rulebook 고정치: `min_hold_days=20, replace_edge=0.15, monthly_replace_cap=0.30`
- 변경(qual/hybrid only):
  - `qual_buzz_w: 0.80 -> 0.78`
  - `qual_ret_w: 0.20 -> 0.21`

### why
- numeric 고성과를 보전하면서(guard), qual/hybrid 개선 여지를 탐색하기 위함.
- 글로벌 파라미터 재탐색 대신 q/h 축으로 변경해 ping-pong 반복을 차단.

### next
- **Stage06 진입 가능** (내부 3000% gate pass 유지).
- 다음 단계에서 할 일:
  1) qual/hybrid seed 확장으로 best_to_second_ratio 추가 완화 시도
  2) one_sided_skew_flag 해소 여부를 Stage06 평가항목으로 명시
