# stage05_result_v3_22_kr

## inputs
- 전체 12개 baseline 재실행: numeric3 / qualitative3 / hybrid3 / external-pretrained3
- 재사용 금지 강제: v3_20/v3_21 내부 결과 incremental reuse 미사용
- 공식 평가 윈도우: official(2021~현재), core(2023~2025), reference(2016~현재)

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_full_recompute_v3_22_kr.py`
- `python3 invest/scripts/stage05_full_recompute_v3_22_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_22_kr.json`
- `invest/reports/stage_updates/stage05/v3_22/stage05_result_v3_22_kr.md`
- `invest/reports/stage_updates/stage05/v3_22/stage05_result_v3_22_kr_readable.md`
- `invest/reports/stage_updates/stage05/v3_22/stage05_patch_diff_v3_22_kr.md`
- `invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_continuous_2021plus.png` (누적 평가용)
- `invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_reset_2021plus.png` (연도별 리셋 평가용)
- `invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_v3_22_kr.csv` (리밸런싱별 종목 비중 스냅샷)
- `invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_summary_v3_22_kr.json` (비중 집중도 요약)

## recompute evidence (필수)
- full_recompute=true: true
- reused_models=0
- recomputed_models=12

## quality_gates
- gate1(track 12개, 3x4): PASS
- gate2(official+core+reference weighted internal selection): PASS
- gate3(official/core/reference sample coverage): PASS
- gate4(rulebook hard룰 고정): PASS
- gate5(MDD 구간분리 표기): PASS
- gate6(UI 템플릿 동일성: template/ui 대비 파일구조/개수 일치): PASS
- high_density(+25%p/MDD/turnover): PASS

## 1) 필수 구간 성과 (누적/CAGR)
| 구간 | numeric | qualitative | hybrid |
|---|---:|---:|---:|
| core(2023~2025) | 583.72% / 89.80% | 315.96% / 60.82% | 1122.32% / 130.35% |
| official(2021~현재) | 569.75% / 37.29% | 282.65% / 25.06% | 2997.33% / 77.21% |
| reference(2016~현재) | 2199.49% / 32.98% | 290.98% / 13.20% | 2218.28% / 33.08% |

## 2) gate/final/repeat/stop 필수 필드
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_FULL_RECOMPUTE_12_BASELINE_PROTOCOL_V322
- repeat_counter: 38
- stop_reason: OFFICIAL_2021_CORE_2023_REFERENCE_2016_GATE_PASS

## 3) 12개 baseline 비교표
| model_id | track | source | cumulative_return | CAGR | MDD | turnover_proxy |
|---|---|---|---:|---:|---:|---:|
| numeric_n1_horizon_fast | numeric | v3_22_full_recompute | 621.63% | 21.71% | -73.88% | 4.850 |
| numeric_n2_flow_tilt | numeric | v3_22_full_recompute | 4073.66% | 44.91% | -45.61% | 5.806 |
| numeric_n3_fee_stress | numeric | v3_22_full_recompute | 577.25% | 20.95% | -45.17% | 6.685 |
| qual_q1_buzz_heavy | qualitative | v3_22_full_recompute | 445.55% | 18.37% | -54.43% | 6.881 |
| qual_q2_ret_up_mix | qualitative | v3_22_full_recompute | 1217.36% | 29.22% | -47.85% | 6.696 |
| qual_q3_fee_stress | qualitative | v3_22_full_recompute | 1652.22% | 32.93% | -59.93% | 6.511 |
| hybrid_h1_quant_tilt | hybrid | v3_22_full_recompute | 1521.70% | 31.91% | -57.11% | 7.148 |
| hybrid_h2_consensus_tilt | hybrid | v3_22_full_recompute | 4262.04% | 45.55% | -73.96% | 3.815 |
| hybrid_h3_fee_stress | hybrid | v3_22_full_recompute | 612.34% | 21.55% | -76.17% | 6.463 |
| external_pretrained_e1_anchor | external-pretrained | v3_22_full_recompute | 1250.17% | 29.53% | -61.14% | 3.423 |
| external_pretrained_e2_turnaround_fast | external-pretrained | v3_22_full_recompute | 719.09% | 23.25% | -61.50% | 3.334 |
| external_pretrained_e3_supercycle_stable | external-pretrained | v3_22_full_recompute | 221.68% | 12.32% | -76.95% | 4.024 |

## 4) 수익률/CAGR/MDD 한표 (12모델)
| model_id | cumulative_return | CAGR | MDD |
|---|---:|---:|---:|
| numeric_n1_horizon_fast | 621.63% | 21.71% | -73.88% |
| numeric_n2_flow_tilt | 4073.66% | 44.91% | -45.61% |
| numeric_n3_fee_stress | 577.25% | 20.95% | -45.17% |
| qual_q1_buzz_heavy | 445.55% | 18.37% | -54.43% |
| qual_q2_ret_up_mix | 1217.36% | 29.22% | -47.85% |
| qual_q3_fee_stress | 1652.22% | 32.93% | -59.93% |
| hybrid_h1_quant_tilt | 1521.70% | 31.91% | -57.11% |
| hybrid_h2_consensus_tilt | 4262.04% | 45.55% | -73.96% |
| hybrid_h3_fee_stress | 612.34% | 21.55% | -76.17% |
| external_pretrained_e1_anchor | 1250.17% | 29.53% | -61.14% |
| external_pretrained_e2_turnaround_fast | 719.09% | 23.25% | -61.50% |
| external_pretrained_e3_supercycle_stable | 221.68% | 12.32% | -76.95% |

## 5) weighted / high-density 상세
- weighted_score = core*0.55 + official*0.40 + reference*0.05
- gate2_non_numeric_candidate: hybrid
- gate2_reason: (i) weighted_return_excess_over_numeric
- high_density_candidate: hybrid

## 6) 차트 재현 스펙(형태 고정)
- 생성 스크립트: `invest/scripts/stage05_plot_v3_22_top3.py`
- 실행 커맨드: `./venv/bin/python invest/scripts/stage05_plot_v3_22_top3.py`
- 입력: `invest/results/validated/stage05_baselines_v3_22_kr.json`
- Top3 선정 규칙: `stats.total_return` 내림차순 상위 3개(트랙 고정 없음)
- **평가 산출물 canonical 폴더:** `invest/reports/stage_updates/stage05/v3_22/` (분산 경로 사용 금지)

### 차트 A (누적 평가용)
- 원본: `invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_continuous_2021plus.png`
- 평가 템플릿 고정: `invest/reports/stage_updates/stage05/v3_22/charts/stage05_eval_yearly_continuous_2021plus.png`
- 기간: 2021+ (일간 축)
- 형태: 일간 연속 곡선(지글지글), 연도 리셋 없음
- 포함선: Top1/Top2/Top3 + KOSPI + KOSDAQ

### 차트 B (연도별 리셋 평가용)
- 원본: `invest/reports/stage_updates/stage05/v3_22/charts/stage05_v3_22_yearly_reset_2021plus.png`
- 평가 템플릿 고정: `invest/reports/stage_updates/stage05/v3_22/charts/stage05_eval_yearly_reset_2021plus.png`
- 기간: 2021+ (일간 축)
- 형태: **연도 경계에서 선을 끊고** 각 연도 1월 첫 거래일을 0%로 리베이스
- 포함선: Top1/Top2/Top3 + KOSPI + KOSDAQ

### 시각 규칙(색/스타일 고정)
- Top1: `#1f77b4` (blue)
- Top2: `#ff7f0e` (orange)
- Top3: `#2ca02c` (green)
- KOSPI: `#d62728` (red, dashed)
- KOSDAQ: `#9467bd` (purple, dotted)
- 두 차트에서 동일 색상 매핑 유지(모델별 색상 통일)

## 7) 포트폴리오 비중/집중도 평가 반영
- 생성 스크립트: `./venv/bin/python invest/scripts/stage05_portfolio_weights_v3_22.py`
- 종목 비중 스냅샷 CSV: `invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_v3_22_kr.csv`
- 집중도 요약 JSON: `invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_summary_v3_22_kr.json`
- 현재 요약(Top1 모델 기준):
  - top1_weight_pct_max: **99.90%**
  - top1_weight_pct_avg: **72.17%**
  - hhi_max: **0.9980**
  - hhi_avg: **0.6127**
- 평가 해석: 수익 반영으로 승자 비중이 커지는 동학이 실제로 발생하며, 고집중 구간(Top1 비중 급증) 리스크를 별도 모니터링한다.
