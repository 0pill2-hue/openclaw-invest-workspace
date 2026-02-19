# stage05_result_v3_20_kr_readable

## 한 줄 결론
- **incremental run 완료: 기존 9개 유지 + external-pretrained 3개 신규 실행으로 12-baseline 통합 비교표 확정**

## 이번 사이클 핵심
- 기준: **12-baseline protocol (numeric3 / qualitative3 / hybrid3 / external-pretrained3)**
- 방식: **풀 리런 금지, 증분 실행(기존 9 + 신규 3)**
- 선발정책: **external-pretrained는 비교/참조군, 메인 선발 제외**
- v3_19: **DRAFT/FAIL 처리, 채택 제외**

## 12개 비교표
| 트랙 | 모델 | 누적수익률 | CAGR | MDD | 비고 |
|---|---|---:|---:|---:|---|
| numeric | numeric_n1_horizon_fast | 176.05% | 10.64% | -81.39% | 기존9 재사용 |
| numeric | numeric_n2_flow_tilt | 2528.83% | 38.48% | -59.94% | 기존9 재사용 |
| numeric | numeric_n3_fee_stress | 403.65% | 17.47% | -65.30% | 기존9 재사용 |
| qualitative | qual_q1_buzz_heavy | 531.01% | 20.13% | -48.64% | 기존9 재사용 |
| qualitative | qual_q2_ret_up_mix | 1328.60% | 30.32% | -41.01% | 기존9 재사용 |
| qualitative | qual_q3_fee_stress | 1755.63% | 33.76% | -47.14% | 기존9 재사용 |
| hybrid | hybrid_h1_quant_tilt | 3138.49% | 41.38% | -52.25% | 기존9 재사용 |
| hybrid | hybrid_h2_consensus_tilt | 4538.83% | 46.53% | -73.96% | 기존9 재사용 |
| hybrid | hybrid_h3_fee_stress | 559.27% | 20.66% | -76.17% | 기존9 재사용 |
| external-pretrained | external_pretrained_e1_anchor | 1250.17% | 29.53% | -61.14% | 신규3 |
| external-pretrained | external_pretrained_e2_turnaround_fast | 719.09% | 23.25% | -61.50% | 신규3 |
| external-pretrained | external_pretrained_e3_supercycle_stable | 221.68% | 12.32% | -76.95% | 신규3 |

## 트랙별 best
- numeric: **numeric_n2_flow_tilt** (2528.83%)
- qualitative: **qual_q3_fee_stress** (1755.63%)
- hybrid: **hybrid_h2_consensus_tilt** (4538.83%)
- external-pretrained: **external_pretrained_e1_anchor** (1250.17%)

## 숫자모델 고정/변경 이력
- fixed_numeric_config(고정축):
  - source: stage05_3x3_v3_9_kr.BASE_PARAMS (anchor, incremental mode)
  - universe_limit: 120
  - max_pos: 6
  - min_hold_days: 20
  - replace_edge: 0.15
  - monthly_replace_cap: 0.3
  - trend_fast: 8
  - trend_slow: 36
  - ret_short: 10
  - ret_mid: 40
  - flow_scale: 120000000.0
  - fee: 0.003
- varied_numeric_configs(변경축):
  - numeric_n1_horizon_fast: {'ret_short': 8, 'ret_mid': 32, 'trend_fast': 6, 'trend_slow': 28}
  - numeric_n2_flow_tilt: {'flow_scale': 80000000.0, 'quant_trend_w': 0.55, 'quant_flow_w': 0.45}
  - numeric_n3_fee_stress: {'fee': 0.0045}

## 게이트 상태
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL

## 참고
- 공식 판정 스코프는 `effective_window` 유지, 12-baseline 비교는 reference/full 성능표로 병행 제공
