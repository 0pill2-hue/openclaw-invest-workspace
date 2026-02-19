# stage05_result_v3_20_kr

## inputs
- 기존 9개(내부 3x3) 결과 재사용: `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- 신규 3개 external/pretrained 증분 실행: `invest/scripts/stage05_incremental_external_v3_20_kr.py`
- v3_19 FAIL 마킹: `invest/results/test/stage05_baselines_v3_19_kr_fail.json`
- 규칙 기준: Rulebook 하드룰 + official_scope=effective_window(reference/full 분리 유지)

## run_command(or process)
- `python3 -m py_compile invest/scripts/stage05_incremental_external_v3_20_kr.py`
- `python3 invest/scripts/stage05_incremental_external_v3_20_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_20_kr.json`
- `invest/reports/stage_updates/stage05/stage05_result_v3_20_kr.md`
- `invest/reports/stage_updates/stage05/stage05_result_v3_20_kr_readable.md`
- `invest/reports/stage_updates/stage05/stage05_patch_diff_v3_20_kr.md`

## quality_gates
- gate1(track 12개, 3x4): PASS
- gate2(main selection internal only): PASS
- gate3(incremental run: 기존9 재사용 + 신규3 실행): PASS
- gate4(rulebook hard룰 상속): PASS
- high_density(강화 게이트): PASS

## failure_policy
- v3_19 결과는 DRAFT/FAIL로 채택 판정에서 제외
- 12-baseline track/cardinality 불일치 시 v3_20 결과 무효
- external-pretrained는 비교/참조군이며 메인 선발 기준에서 제외

## proof
- result json: `invest/results/validated/stage05_baselines_v3_20_kr.json`
- fail marker: `invest/results/test/stage05_baselines_v3_19_kr_fail.json`
- log: `invest/reports/stage_updates/logs/stage05_incremental_external_v3_20_kr.log`
- code: `invest/scripts/stage05_incremental_external_v3_20_kr.py`

---

## 1) v3_19 FAIL 처리 근거
- 상태: **DRAFT/FAIL (TEST ONLY)**
- 근거: `TypeError: ModelRun.__init__() missing 4 required positional arguments`
- 누락 필드: `monthly_holdings`, `replacement_logs`, `supercycle_trace`, `strategy_summary`
- 채택 반영: **제외(excluded_from_adoption=true)**

## 2) incremental run 명시 (기존 9 + 신규 3)
- reused_internal_models: **9**
- new_external_models: **3**
- recomputed_internal_models: **0 (금지 준수)**
- source_hash(base9 models): `8d10c9e520f599972cd0fd9f4414763c4daf64994c63d2a8c6bf0333182df352`

## 3) 모델별 전략 차이 (숫자/정성/복합/external-pretrained)
- numeric: 가격/수급 독립 축 유지, 부분동기화 원칙 하에서 고정축+실험축 분리
- qualitative: 턴어라운드/슈퍼사이클 대전제 강반영(텍스트/이벤트 반응 축)
- hybrid: 정량+정성 합의항 강화(대전제 반영 유지)
- external-pretrained: 기성 프록시 3종 증분 추가(비교/참조군, 선발 제외)

### fixed_numeric_config / varied_numeric_configs
- fixed_numeric_config:
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
- varied_numeric_configs:
  - numeric_n1_horizon_fast: {'ret_short': 8, 'ret_mid': 32, 'trend_fast': 6, 'trend_slow': 28}
  - numeric_n2_flow_tilt: {'flow_scale': 80000000.0, 'quant_trend_w': 0.55, 'quant_flow_w': 0.45}
  - numeric_n3_fee_stress: {'fee': 0.0045}

## 4) 구간별 수익률 (누적%, CAGR%)
| 구간 | numeric | qualitative | hybrid |
|---|---:|---:|---:|
| reference_full_period(v3_18 anchor) | 55.11% / 4.45% | 137.40% / 8.95% | 117.41% / 8.01% |
| official_effective_window(v3_18 anchor) | -1.30% / -0.44% | 57.48% / 16.34% | 207.85% / 45.47% |

## 5) 12개 baseline 통합 비교표 (필수)
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
| external_pretrained_e1_anchor | external-pretrained | v3_20_incremental_external | 1250.17% | 29.53% | -61.14% | 3.423 |
| external_pretrained_e2_turnaround_fast | external-pretrained | v3_20_incremental_external | 719.09% | 23.25% | -61.50% | 3.334 |
| external_pretrained_e3_supercycle_stable | external-pretrained | v3_20_incremental_external | 221.68% | 12.32% | -76.95% | 4.024 |

## 6) 월별 보유종목/교체사유/슈퍼사이클 추적표 (incremental 제약 공지)
- 본 사이클은 **증분 실행(기존 9 재계산 금지)** 조건이므로, 월별 보유/교체 로그는 신규 3개 external-pretrained에 한해 생성됨.
- 기존 9개의 월별 상세는 원본 산출(`stage05_baselines_3x3_v3_9_kr.json`) 범위를 그대로 유지.
- supercycle 추적은 v3_20 설계 원칙으로 유지하되, 이번 증분 실행에서는 external 비교군 확장만 수행.

## 7) gate/final/repeat/stop 필수 필드
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL
- repeat_counter: 36
- stop_reason: INCREMENTAL_EXTERNAL_3_MERGE_COMPLETED
