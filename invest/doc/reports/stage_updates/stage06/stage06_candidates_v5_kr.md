# stage06_candidates_v5_kr

## inputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json
- KRX ohlcv: /Users/jobiseu/.openclaw/workspace/invest/data/raw/kr/ohlcv
- KRX supply: /Users/jobiseu/.openclaw/workspace/invest/data/raw/kr/supply
- chosen_plan: expanded_72 (72 candidates)

## run_command(or process)
- `python3 scripts/stage06_candidates_v5_kr.py`

## outputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v5_kr.json
- /Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage06/stage06_candidates_v5_kr.md

## quality_gates
- candidate_count_match_plan: True
- track_split_24_24_24: True
- external_proxy_selection_excluded: True
- changed_params_non_empty: True
- changed_params_pingpong_free: True
- rulebook_fixed_hard_constraints: True

## failure_policy
- Stage05 seed 입력 누락/비검증(VALIDATED 아님) 시 FAIL_STOP
- 후보 수(72) 또는 트랙 분배(24/24/24) 불일치 시 FAIL_STOP
- RULEBOOK V3.5/V3.4 고정 파라미터(보유1~6/최소20일/교체+15%/월30%/트레일링-20%) 위반 시 FAIL_STOP
- changed_params 중복/핑퐁 패턴 탐지 시 FAIL_STOP

## proof
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v5_kr.json
- /Users/jobiseu/.openclaw/workspace/scripts/stage06_candidates_v5_kr.py

## summary
- version: v5_kr
- 후보 수: 72
- 트랙 비중: numeric=24 (33.3%), qualitative=24 (33.3%), hybrid=24 (33.3%)
- 하드규칙 통과 여부: True
- 외부아이디어 반영 여부: {'applied': True, 'mode': 'idea_transplant_operational_layer_only', 'selection_model_direct_use': 'N/A (비교/아이디어 참고만, 직접 외부모델 미사용)', 'notes': 'external_proxy는 비교군 전용, 후보 선발 제외'}

## new_selection_gate
- policy_id: anti_numeric_monopoly_gate_v1
- hard_rule: numeric 단독 1등 즉시 채택 금지
- adopt_allowed_if:
  - (a) hybrid/qualitative 후보가 numeric 최고 후보 total_return 추월
  - (b) numeric 대비 수익률 근접 + MDD 우위 + turnover_proxy 우위 동시 충족
- stage_binding:
  - stage07: 컷오프 판정에 필수 포함
  - stage09: 최종 ADOPT 전 필수 재검증

## 변수 영향도 스냅샷 (|corr| top10)
| rank | param | corr(total_return) |
|---:|---|---:|
| 1 | qual_up_w | 0.3488 |
| 2 | buzz_window | 0.3018 |
| 3 | quant_trend_w | 0.2726 |
| 4 | quant_flow_w | -0.2726 |
| 5 | up_window | 0.2023 |
| 6 | qual_buzz_w | -0.1797 |
| 7 | qual_ret_w | 0.1564 |
| 8 | hybrid_qual_w | 0.1423 |
| 9 | ret_short | -0.1070 |
| 10 | ret_mid | -0.1070 |

## top10 (by total_return) + 핵심 changed_params
| rank | model_id | track | seed_model | total_return | MDD | CAGR | 핵심 changed_params |
|---:|---|---|---|---:|---:|---:|---|
| 1 | s06v5_hybrid_h18 | hybrid | hybrid_h2_consensus_tilt | 4225.34% | -57.55% | 45.52% | fee=0.0036, hybrid_agree_w=0.24, hybrid_quant_w=0.44, qual_up_w=0.14, quant_flow_w=0.28, quant_trend_w=0.72 |
| 2 | s06v5_qual_q14 | qualitative | qual_q3_fee_stress | 4104.21% | -44.63% | 45.10% | buzz_window=65, fee=0.0038, qual_buzz_w=0.8, qual_ret_w=0.12, qual_up_w=0.08 |
| 3 | s06v5_qual_q23 | qualitative | qual_q3_fee_stress | 3895.72% | -26.37% | 44.37% | buzz_window=80, fee=0.0034, qual_buzz_w=0.62, qual_ret_w=0.24, qual_up_w=0.14, up_window=25 |
| 4 | s06v5_qual_q15 | qualitative | qual_q3_fee_stress | 3150.36% | -58.45% | 41.43% | buzz_window=65, fee=0.0038, qual_buzz_w=0.74, qual_ret_w=0.16 |
| 5 | s06v5_qual_q12 | qualitative | qual_q3_fee_stress | 2942.25% | -44.59% | 40.51% | buzz_window=50, fee=0.0042, qual_buzz_w=0.56, qual_ret_w=0.28, qual_up_w=0.16, up_window=15 |
| 6 | s06v5_hybrid_h07 | hybrid | hybrid_h2_consensus_tilt | 2801.05% | -72.69% | 39.84% | fee=0.0033, hybrid_agree_w=0.12, hybrid_qual_w=0.24, hybrid_quant_w=0.64, qual_up_w=0.12, quant_flow_w=0.34, ...(+1) |
| 7 | s06v5_hybrid_h17 | hybrid | hybrid_h2_consensus_tilt | 2480.26% | -73.36% | 38.22% | fee=0.0036, hybrid_agree_w=0.22, hybrid_qual_w=0.3, hybrid_quant_w=0.48, qual_up_w=0.14, quant_flow_w=0.28, ...(+1) |
| 8 | s06v5_qual_q22 | qualitative | qual_q3_fee_stress | 2241.39% | -30.90% | 36.89% | buzz_window=80, fee=0.0034, qual_buzz_w=0.68, qual_ret_w=0.2, qual_up_w=0.12, up_window=25 |
| 9 | s06v5_numeric_n02 | numeric | numeric_n2_flow_tilt | 2087.84% | -49.47% | 35.97% | fee=0.0034, flow_scale=70000000.0, quant_flow_w=0.5, quant_trend_w=0.5, ret_mid=36, ret_short=9, ...(+2) |
| 10 | s06v5_qual_q16 | qualitative | qual_q3_fee_stress | 1923.13% | -54.07% | 34.91% | buzz_window=65, fee=0.0038, qual_buzz_w=0.68, qual_ret_w=0.2, qual_up_w=0.12 |
