# stage05_result_v3_21_kr

## inputs
- 기존 9개(내부 3x3) 결과 재사용: `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- 신규 3개 external/pretrained 증분 실행: `invest/scripts/stage05_incremental_external_v3_21_kr.py`
- v3_19 FAIL 마킹 재확인: `invest/results/test/stage05_baselines_v3_19_kr_fail.json`
- 정책 반영: official_scope=2021~현재, core_high_density=2023~2025(가중), legacy(2016~2020)=reference/low-weight

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_incremental_external_v3_21_kr.py`
- `python3 invest/scripts/stage05_incremental_external_v3_21_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_21_kr.json`
- `invest/reports/stage_updates/stage05/stage05_result_v3_21_kr.md`
- `invest/reports/stage_updates/stage05/stage05_result_v3_21_kr_readable.md`
- `invest/reports/stage_updates/stage05/stage05_patch_diff_v3_21_kr.md`

## quality_gates
- gate1(track 12개, 3x4): PASS
- gate2(official+core weighted internal selection): PASS
- gate3(official/core sample coverage): PASS
- gate4(rulebook hard룰 고정): PASS
- high_density(+25%p/MDD/turnover): PASS

## failure_policy
- gate1~4/high_density 중 1개라도 FAIL이면 최종결정은 REDESIGN
- external-pretrained는 비교/참조군이며 메인 선발 기준에서 제외
- v3_19 결과(DRAFT/FAIL)는 채택 판정에서 제외

## proof
- result json: `invest/results/validated/stage05_baselines_v3_21_kr.json`
- log: `invest/reports/stage_updates/logs/stage05_incremental_external_v3_21_kr.log`
- code: `invest/scripts/stage05_incremental_external_v3_21_kr.py`

---

## 1) 필수 구간 성과 (누적/CAGR)
| 구간 | numeric | qualitative | hybrid |
|---|---:|---:|---:|
| 3년 core(2023~2025) | 517.27% / 83.44% | 299.86% / 58.72% | 1126.80% / 130.63% |
| 공식 official(2021~현재) | 287.15% / 25.31% | 253.40% / 23.42% | 3185.62% / 78.97% |
| 참고 reference(2016~현재) | 1436.51% / 28.19% | 490.72% / 17.52% | 2359.21% / 33.79% |

## 2) gate/final/repeat/stop 필수 필드
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL_V321
- repeat_counter: 37
- stop_reason: OFFICIAL_2021_CORE_2023_WEIGHTED_GATE_PASS

## 3) 연도별 텔레그램/블로그 필터통과 데이터 카운트
| 연도 | telegram_filter_pass | blog_filter_pass | combined |
|---:|---:|---:|---:|
| 2016 | 0 | 52 | 52 |
| 2017 | 0 | 63 | 63 |
| 2018 | 0 | 160 | 160 |
| 2019 | 0 | 276 | 276 |
| 2020 | 0 | 956 | 956 |
| 2021 | 0 | 2038 | 2038 |
| 2022 | 0 | 2195 | 2195 |
| 2023 | 0 | 3359 | 3359 |
| 2024 | 0 | 4445 | 4445 |
| 2025 | 4 | 8738 | 8742 |
| 2026 | 55 | 5242 | 5297 |

## 4) 12개 baseline 통합 비교표
| model_id | track | source | cumulative_return | CAGR | MDD | turnover_proxy |
|---|---|---|---:|---:|---:|---:|
| numeric_n1_horizon_fast | numeric | v3_9_internal_reuse | 176.05% | 10.64% | -81.39% | 4.717 |
| numeric_n2_flow_tilt | numeric | v3_9_internal_reuse | 2528.83% | 38.48% | -59.94% | 5.882 |
| numeric_n3_fee_stress | numeric | v3_9_internal_reuse | 403.65% | 17.47% | -65.30% | 5.621 |
| qual_q1_buzz_heavy | qualitative | v3_9_internal_reuse | 531.01% | 20.13% | -48.64% | 6.929 |
| qual_q2_ret_up_mix | qualitative | v3_9_internal_reuse | 1328.60% | 30.32% | -41.01% | 5.795 |
| qual_q3_fee_stress | qualitative | v3_9_internal_reuse | 1755.63% | 33.76% | -47.14% | 6.102 |
| hybrid_h1_quant_tilt | hybrid | v3_9_internal_reuse | 3138.49% | 41.38% | -52.25% | 4.899 |
| hybrid_h2_consensus_tilt | hybrid | v3_9_internal_reuse | 4538.83% | 46.53% | -73.96% | 3.860 |
| hybrid_h3_fee_stress | hybrid | v3_9_internal_reuse | 559.27% | 20.66% | -76.17% | 6.637 |
| external_pretrained_e1_anchor | external-pretrained | v3_21_incremental_external | 1250.17% | 29.53% | -61.14% | 3.423 |
| external_pretrained_e2_turnaround_fast | external-pretrained | v3_21_incremental_external | 719.09% | 23.25% | -61.50% | 3.334 |
| external_pretrained_e3_supercycle_stable | external-pretrained | v3_21_incremental_external | 221.68% | 12.32% | -76.95% | 4.024 |

## 5) 핵심 가중(2023~) 반영 상세
- weighted_score = core*0.55 + official*0.40 + legacy*0.05
- gate2_non_numeric_candidate: hybrid
- gate2_reason: (i) weighted_return_excess_over_numeric
- high_density_candidate: hybrid
