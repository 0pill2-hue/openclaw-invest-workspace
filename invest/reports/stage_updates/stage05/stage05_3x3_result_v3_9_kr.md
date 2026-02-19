# stage05_3x3_result_v3_9_kr

## inputs
- restart_mode: 기존 진행 결과 폐기 후 Stage05 3x3 전면 재실행
- KRX OHLCV + supply
- model_matrix: numeric3 / qualitative3 / hybrid3

## run_command(or process)
- `python3 invest/scripts/stage05_3x3_v3_9_kr.py`

## outputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage05/stage05_3x3_result_v3_9_kr.md

## quality_gates
- result_grade=VALIDATED: VALIDATED
- scope=KRX_ONLY: KRX_ONLY
- external_proxy_selection_excluded: True
- track_variant_3x3_distinct: True
- internal_3000_gate_pass: True

## failure_policy
- internal_3000_gate_pass=false -> Stage06 진입 금지
- 비교군(external_proxy) 성과는 선발 기준에서 제외

## proof
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/scripts/stage05_3x3_v3_9_kr.py

## 모델별 성과표
| model_id | track | cumulative_return | MDD | CAGR | turnover_proxy |
|---|---|---:|---:|---:|---:|
| numeric_n1_horizon_fast | numeric | 176.05% | -81.39% | 10.64% | 4.717 |
| numeric_n2_flow_tilt | numeric | 2528.83% | -59.94% | 38.48% | 5.882 |
| numeric_n3_fee_stress | numeric | 403.65% | -65.30% | 17.47% | 5.621 |
| qual_q1_buzz_heavy | qualitative | 531.01% | -48.64% | 20.13% | 6.929 |
| qual_q2_ret_up_mix | qualitative | 1328.60% | -41.01% | 30.32% | 5.795 |
| qual_q3_fee_stress | qualitative | 1755.63% | -47.14% | 33.76% | 6.102 |
| hybrid_h1_quant_tilt | hybrid | 3138.49% | -52.25% | 41.38% | 4.899 |
| hybrid_h2_consensus_tilt | hybrid | 4538.83% | -73.96% | 46.53% | 3.860 |
| hybrid_h3_fee_stress | hybrid | 559.27% | -76.17% | 20.66% | 6.637 |

## track별 best
- numeric_best: numeric_n2_flow_tilt (2528.83%)
- qualitative_best: qual_q3_fee_stress (1755.63%)
- hybrid_best: hybrid_h2_consensus_tilt (4538.83%)
- overall_best: hybrid_h2_consensus_tilt (4538.83%)

## 변수 영향도 요약
- corr(ret_short, total_return): 0.3756
- corr(ret_mid, total_return): 0.3756
- corr(qual_buzz_w, total_return): -0.0983
- corr(flow_scale, total_return): -0.2190
- corr(trend_fast, total_return): 0.3756
- corr(trend_slow, total_return): 0.3756
- corr(fee, total_return): -0.3822
- fee sensitivity: high_fee(0.0045) - low_fee(0.003) = -1134.11%

## external_proxy (비교군 전용)
- model_id: external_proxy_ref
- cumulative_return: 1122.37%
- selection_used: false

## required fields
- numeric_best: numeric_n2_flow_tilt
- qualitative_best: qual_q3_fee_stress
- hybrid_best: hybrid_h2_consensus_tilt
- overall_best: hybrid_h2_consensus_tilt
- internal_3000_gate_pass: True

## next (Stage06 진입안)
- 3x3 결과의 track별 best 3개를 seed로 사용
- seed별로 ret_horizon / flow / fee 3축 조합 후보를 생성
- external_proxy는 여전히 비교군으로만 유지하고 내부 모델만 컷오프
