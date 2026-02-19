# stage05_result_v3_21_kr_readable

## 한 줄 결론
- **ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL_V321** (official=2021~, core=2023~2025 가중 평가 반영)

## 이번 변경 포인트
- v3_20 체계/12-baseline 유지 + 증분 실행(기존9 재사용, external3 신규)
- 공식 평가구간을 2021~현재로 상향
- 2023~2025 core band를 가중(필수) 반영
- 2016~2020은 reference/저가중으로 분리

## 필수 수익률 요약 (누적/CAGR)
| 구간 | numeric | qualitative | hybrid |
|---|---:|---:|---:|
| 3년 core(2023~2025) | 517.27% / 83.44% | 299.86% / 58.72% | 1126.80% / 130.63% |
| 공식 official(2021~현재) | 287.15% / 25.31% | 253.40% / 23.42% | 3185.62% / 78.97% |
| 참고 reference(2016~현재) | 1436.51% / 28.19% | 490.72% / 17.52% | 2359.21% / 33.79% |

## gate 상태
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL_V321
- repeat_counter: 37
- stop_reason: OFFICIAL_2021_CORE_2023_WEIGHTED_GATE_PASS
