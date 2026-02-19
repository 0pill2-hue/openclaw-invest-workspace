# stage05_result_v3_22_kr_readable

## 한 줄 결론
- **ADOPT_FULL_RECOMPUTE_12_BASELINE_PROTOCOL_V322** (v3_22 full recompute, reused_models=0)

## 재실행 핵심
- 12개 baseline 전부 재계산 완료 (3x4)
- full_recompute=true, incremental reuse 금지 준수
- 공식 평가 윈도우 유지: official(2021~), core(2023~2025), reference(2016~)

## 필수 성과 요약 (누적 / CAGR / MDD 한표)
| 구간 | numeric (누적/CAGR/MDD) | qualitative (누적/CAGR/MDD) | hybrid (누적/CAGR/MDD) |
|---|---:|---:|---:|
| core(2023~2025) | 583.72% / 89.80% / -45.61% | 315.96% / 60.82% / -59.93% | 1122.32% / 130.35% / -73.96% |
| official(2021~현재) | 569.75% / 37.29% / -45.61% | 282.65% / 25.06% / -59.93% | 2997.33% / 77.21% / -73.96% |
| reference(2016~현재) | 2199.49% / 32.98% / -45.61% | 290.98% / 13.20% / -59.93% | 2218.28% / 33.08% / -73.96% |

## 그래프 (2021~ 시작, 2종)
- 누적 수익률(Top1~Top3 + KOSPI/KOSDAQ): `invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_continuous_2021plus.png`
- 연도별 리셋 그래프(Top1~Top3 + KOSPI/KOSDAQ, 매년 0부터 시작): `invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_reset_2021plus.png`
- 비중 평가: `invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_v3_22_kr.csv`
- 작성 기준: v3_22 `annual_returns` 실측값 기반(연말 기준), 임의 보간/가짜 월별 곡선 미사용

## 거래내역/포트타임라인
- `invest/reports/stage_updates/stage05/v3_22/stage05_trade_events_v3_22_kr.csv`
- `invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_timeline_v3_22_kr.csv`

## gate/final/repeat/stop
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_FULL_RECOMPUTE_12_BASELINE_PROTOCOL_V322
- repeat_counter: 38
- stop_reason: OFFICIAL_2021_CORE_2023_REFERENCE_2016_GATE_PASS
