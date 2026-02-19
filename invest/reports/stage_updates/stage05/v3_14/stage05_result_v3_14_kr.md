# stage05_result_v3_14_kr

## inputs
- baseline reference: `invest/results/validated/stage05_baselines_v3_12_kr.json`
- policy update source: 사용자 확정 지시(동적밴드 B + 2계층 게이트 C)
- raw market/text data:
  - `invest/data/raw/kr/ohlcv/*.csv`
  - `invest/data/raw/kr/supply/*_supply.csv`
  - `invest/data/raw/text/blog/**/*.md`
  - `invest/data/raw/text/telegram/*.md`

## run_command(or process)
- `python3 invest/scripts/stage05_rerun_v3_14_kr.py | tee invest/reports/stage_updates/logs/stage05_rerun_v3_14_kr.log`

## outputs
- `invest/results/validated/stage05_baselines_v3_14_kr.json`
- `invest/reports/stage_updates/stage05/stage05_result_v3_14_kr.md`
- `invest/reports/stage_updates/stage05/stage05_policy_patch_v3_14_kr.md`

## quality_gates
- KRX only guard: PASS
- RULEBOOK 하드룰 유지(보유1~6/최소보유20/교체+15/월교체30): PASS
- numeric baseline 고정(라운드 간 numeric_return 동일): PASS (`26.816945` 고정)
- Gate1(동적밴드) 적용: PASS (전 라운드)
- Gate2(비수치 채택조건) 적용: FAIL (전 라운드)
- repeat_counter 이어서 기록: PASS (`7 -> 12`)
- stop_reason 필수 기록: PASS (`MAX_REPEAT_REACHED_REDESIGN`)

## failure_policy
- Gate1 미통과 라운드: FAIL 라운드 처리
- Gate2 미통과 지속 + max repeat 도달: `MAX_REPEAT_REACHED_REDESIGN`
- clone_detected=true: 즉시 FAIL 라운드 처리

## proof
- script: `invest/scripts/stage05_rerun_v3_14_kr.py`
- log: `invest/reports/stage_updates/logs/stage05_rerun_v3_14_kr.log`
- result json: `invest/results/validated/stage05_baselines_v3_14_kr.json`

---

## 1) 최종 판정 요약
- repeat_counter_start: `7`
- repeat_counter_final: `12`
- stop_reason: `MAX_REPEAT_REACHED_REDESIGN`
- final_decision: `REDESIGN`
- non_numeric_top_valid: `false`

### numeric_return vs qual/hybrid_return (최종 채택 라운드 rF)
- numeric_return: `26.816945`
- qualitative_return: `7.292953`
- hybrid_return: `15.213548`

### 필수 상태값
- tie_detected: `false`
- clone_detected: `false`

---

## 2) 라운드별 게이트 결과

| repeat_counter | round_id | hybrid_qual_mix_ratio | density/noise regime | 적용 밴드(min~max / reco_min) | gate1_pass | gate2_pass | numeric_return | qual_return | hybrid_return | tie_detected | clone_detected | non_numeric_top_valid |
|---:|---|---:|---|---|---|---|---:|---:|---:|---|---|---|
| 7 | rA_blog_boost_low_noise | 0.35 | LOW_DENSITY_OR_HIGH_NOISE | 0.35~0.60 / 0.35 | true | false | 26.8169 | 2.5746 | 13.5054 | false | false | false |
| 8 | rB_blog_boost_mid_noise | 0.38 | LOW_DENSITY_OR_HIGH_NOISE | 0.35~0.60 / 0.35 | true | false | 26.8169 | 1.3920 | 9.7746 | false | false | false |
| 9 | rC_density_noise_balance | 0.42 | LOW_DENSITY_OR_HIGH_NOISE | 0.35~0.60 / 0.35 | true | false | 26.8169 | 2.6712 | 10.4477 | false | false | false |
| 10 | rD_high_density_pref | 0.50 | LOW_DENSITY_OR_HIGH_NOISE | 0.35~0.60 / 0.35 | true | false | 26.8169 | 3.1630 | 8.7837 | false | false | false |
| 11 | rE_high_density_upper_band | 0.55 | LOW_DENSITY_OR_HIGH_NOISE | 0.35~0.60 / 0.35 | true | false | 26.8169 | 9.6411 | 13.4259 | false | false | false |
| 12 | rF_upper_band_stress | 0.60 | LOW_DENSITY_OR_HIGH_NOISE | 0.35~0.60 / 0.35 | true | false | 26.8169 | 7.2930 | 15.2135 | false | false | false |

> 관찰: 이번 데이터/파라미터 조합에서는 모든 라운드가 LOW_DENSITY_OR_HIGH_NOISE regime로 분류되어 권장 하한(reco_min)=0.35가 적용됨.

---

## 3) Gate2 실패 원인
Gate2 조건:
1. (i) `non_numeric_return >= numeric + epsilon(0.005)`
2. (ii) `|non_numeric - numeric| <= 0.005` + `MDD/turnover 동시 우위`

실행 결과:
- 모든 라운드에서 non_numeric_return(최대 15.2135)이 numeric_return(26.8169) 대비 크게 낮아
  - (i) 미충족
  - (ii) 근접조건 자체 미충족
- 따라서 gate2_pass = false 지속

---

## 4) changed_params / why
- 핵심 축 변화(강완화):
  - `blog_weight` 0.92 -> 0.98 (공격적 상향)
  - `signal_lag_days` 2 -> 7 (탐색 폭 확장)
  - `density_pow` 0.45 -> 1.30 (밀도 민감도 확대)
  - `noise_w` 0.05 -> 0.16, `noise_buzz_cut` 0.86 -> 0.70 (noise 축 확장)
  - `hybrid_qual_mix_ratio` 0.35 -> 0.60 (동적밴드 전 구간 탐색)
- why:
  - 과적합 완화를 위해 single-point 고정 대신 밴드 전구간 탐색
  - blog 우선 가중을 공격적으로 높여 정성 신호 가시성 극대화
  - density/lag/noise 축을 동시에 넓혀 regime 적응 범위 확장

---

## 5) final_decision rationale
- `Gate1`은 모두 통과했으나, `Gate2`(비수치 채택조건)가 단 한 라운드도 충족되지 않음.
- tie/clone 꼼수 없이도 non-numeric 우위가 확보되지 않아, 정책상 ADOPT 불가.
- 따라서 최종 결정은 `REDESIGN`이며, stop_reason은 `MAX_REPEAT_REACHED_REDESIGN`.
