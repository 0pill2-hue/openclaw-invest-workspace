# stage06_candidates_v4_kr

## inputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json
- KRX ohlcv: /Users/jobiseu/.openclaw/workspace/invest/data/raw/kr/ohlcv
- KRX supply: /Users/jobiseu/.openclaw/workspace/invest/data/raw/kr/supply
- chosen_plan: medium_12 (12 candidates)

## run_command(or process)
- `python3 scripts/stage06_candidates_v4_kr.py`

## outputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v4_kr.json
- /Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage06/stage06_candidates_v4_kr.md

## quality_gates
- candidate_count_match_plan: True
- external_proxy_selection_excluded: True
- changed_params_non_empty: True
- rulebook_fixed_hard_constraints: True

## failure_policy
- Stage05 seed 입력 누락/비검증(VALIDATED 아님) 시 FAIL_STOP
- 후보 수가 chosen_plan과 불일치하면 FAIL_STOP
- RULEBOOK V3.4 고정 파라미터(보유1~6/최소20일/교체+15%/월30%/트레일링-20%) 위반 시 FAIL_STOP

## proof
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v4_kr.json
- /Users/jobiseu/.openclaw/workspace/scripts/stage06_candidates_v4_kr.py

## summary
- version: v4_kr
- 후보 수: 12
- 트랙 비중: numeric=4 (33.3%), qualitative=4 (33.3%), hybrid=4 (33.3%)
- 외부아이디어 반영 여부: {'applied': True, 'mode': 'idea_transplant_operational_layer_only', 'selection_model_direct_use': 'N/A (비교/아이디어 참고만, 직접 외부모델 미사용)', 'notes': 'external_proxy는 비교군 전용, 후보 선발 제외'}

## new_selection_gate
- policy_id: `anti_numeric_monopoly_gate_v1`
- hard_rule: `numeric 단독 1등 즉시 채택 금지`
- adopt_allowed_if:
  - (a) `hybrid` 또는 `qualitative`가 numeric 최고 후보 total_return 추월
  - (b) numeric 대비 수익률 근접 + `MDD 우위` + `turnover_proxy 우위` 동시 충족
- stage_binding:
  - Stage07 컷오프: 필수 판정항목
  - Stage09 최종검토: ADOPT 전 필수 재검증

## top5 (by total_return)
| rank | candidate_id | track | seed_model | total_return | MDD | CAGR | external_ideas |
|---:|---|---|---|---:|---:|---:|---|
| 1 | s06v4_qual_q6_noise_filter | qualitative | qual_q3_fee_stress | 2656.71% | -50.42% | 39.13% | sentiment_smoothing, risk_management_filter |
| 2 | s06v4_numeric_n5_flow_balance | numeric | numeric_n2_flow_tilt | 1845.11% | -66.17% | 34.38% | cross_sectional_flow, risk_balance |
| 3 | s06v4_numeric_n6_flow_aggressive | numeric | numeric_n2_flow_tilt | 1545.50% | -59.94% | 32.16% | flow_tilt, ensemble_weight_shift |
| 4 | s06v4_qual_q4_event_balanced | qualitative | qual_q3_fee_stress | 1159.63% | -47.81% | 28.69% | event_sentiment, meta_labeling_idea |
| 5 | s06v4_numeric_n7_cost_guard | numeric | numeric_n2_flow_tilt | 1095.82% | -44.57% | 28.03% | cost_aware_execution, ts_momentum |
