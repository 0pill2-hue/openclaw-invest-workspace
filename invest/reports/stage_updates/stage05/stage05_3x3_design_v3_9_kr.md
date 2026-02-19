# stage05_3x3_design_v3_9_kr

## inputs
- restart_mode: 기존 진행 결과 폐기 후 Stage05 3x3 재설계/재실행
- RULEBOOK V3.4 고정 제약: 보유1~6, 최소보유20일, 교체+15%, 월교체30%
- KRX raw data: invest/data/raw/kr/ohlcv/*.csv, invest/data/raw/kr/supply/*_supply.csv
- 내부 모델 9개(3x3) + external_proxy 비교군 1개

## run_command(or process)
- `python3 scripts/stage05_3x3_v3_9_kr.py`

## outputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_3x3_v3_9_kr.json
- /Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage05/stage05_3x3_design_v3_9_kr.md
- /Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage05/stage05_3x3_result_v3_9_kr.md

## quality_gates
- KRX only guard pass (US ticker/path reject)
- RULEBOOK V3.4 핵심 가드 고정 (보유1~6, 최소보유20일, 교체+15%, 월교체30%)
- external_proxy는 비교군 전용(선발 제외)
- track별 3개 changed_params 명확 구분(핑퐁 금지)

## failure_policy
- KRX guard fail 또는 track별 3개 구성 위반 시 즉시 FAIL_STOP
- internal 3000% gate 미충족 시 Stage06 진입 금지

## proof
- /Users/jobiseu/.openclaw/workspace/scripts/stage05_3x3_v3_9_kr.py

## Stage05-3x3 모델 설계
| track | model_id | changed_params | why | expected_risk |
|---|---|---|---|---|
| numeric | numeric_n1_horizon_fast | ret_mid=32, ret_short=8, trend_fast=6, trend_slow=28 | 단기/중기 모멘텀 및 추세 span 단축으로 가격 반응 민감도 측정 | 횡보 구간에서 신호 과민 반응(whipsaw) 가능 |
| numeric | numeric_n2_flow_tilt | flow_scale=80000000.0, quant_flow_w=0.45, quant_trend_w=0.55 | 수급(flow) 영향도 확대 시 성과 변화 확인 | 수급 데이터 노이즈에 의한 과적합 가능 |
| numeric | numeric_n3_fee_stress | fee=0.0045 | 거래비용 민감도(수수료+슬리피지 스트레스) 측정 | 고회전 구간에서 수익 급감 가능 |
| qualitative | qual_q1_buzz_heavy | buzz_window=40, qual_buzz_w=0.84, qual_ret_w=0.12, qual_up_w=0.04 | buzz 중심 정성 점수 강화 시 성과/변동성 영향 확인 | 이슈 급등주 쏠림으로 drawdown 확대 가능 |
| qualitative | qual_q2_ret_up_mix | qual_buzz_w=0.56, qual_ret_w=0.24, qual_up_w=0.2, up_window=15 | ret_short + 상승일 비율(up_ratio) 혼합 시 지속성 측정 | 모멘텀 둔화 시 급격한 성과 저하 가능 |
| qualitative | qual_q3_fee_stress | fee=0.0045 | 정성 트랙의 거래비용 내구성 측정 | 정성 신호 고빈도 구간에서 turnover 비용 증가 |
| hybrid | hybrid_h1_quant_tilt | hybrid_agree_w=0.1, hybrid_qual_w=0.2, hybrid_quant_w=0.7 | hybrid 내 정량 비중 확대로 수익/리스크 변화 확인 | 정성 이벤트 반응 둔화 가능 |
| hybrid | hybrid_h2_consensus_tilt | hybrid_agree_w=0.26, hybrid_quant_w=0.5 | 합의항(min term) 비중 증가 + 정량축 완만 조정으로 보수적 합의형 효과 측정 | 신호 엄격화로 기회 손실 가능 |
| hybrid | hybrid_h3_fee_stress | fee=0.0045 | 하이브리드 트랙 거래비용 민감도 측정 | 혼합신호 고회전 시 비용 누적 |

## 변수 민감도 측정 포인트
- ret_short / ret_mid
- qual_buzz_w
- flow_scale
- trend_fast / trend_slow
- fee sensitivity
