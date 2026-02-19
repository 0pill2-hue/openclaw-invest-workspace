# stage05_patch_diff_v3_22_kr

## 변경 요약
1) v3_21 incremental 구조 -> v3_22 full recompute 구조로 전환
2) 기존 v3_20/v3_21 결과 재사용 금지(reused_models=0)
3) 12 baseline(3x4) 전량 재계산
4) 공식 윈도우 유지: official(2021~), core(2023~2025), reference(2016~)

## hard-rule 유지 확인
- KRX only: 유지
- 보유1~6: 유지
- 최소보유20일: 유지
- 교체+15%: 유지
- 월교체30%: 유지
- high-density gate(+25%p/MDD/turnover): 유지

## recompute evidence
- full_recompute=true: true
- reused_models=0
- recomputed_models=12

## gate/final/repeat/stop
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_FULL_RECOMPUTE_12_BASELINE_PROTOCOL_V322
- repeat_counter: 38
- stop_reason: OFFICIAL_2021_CORE_2023_REFERENCE_2016_GATE_PASS
