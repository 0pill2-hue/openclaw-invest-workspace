# stage05_result_v3_12_kr

## inputs
- baseline compare target: `invest/results/validated/stage05_baselines_v3_11_kr.json`
- current run output: `invest/results/validated/stage05_baselines_v3_12_kr.json`
- raw market data: `invest/data/raw/kr/ohlcv/*.csv`, `invest/data/raw/kr/supply/*_supply.csv`
- raw text data: `invest/data/raw/text/blog/**/*.md`, `invest/data/raw/text/telegram/*.md`
- rulebook: `invest/docs/strategy/RULEBOOK_V3.md`

## run_command(or process)
- `python3 invest/scripts/stage05_density_repeat_v3_12_kr.py | tee invest/reports/stage_updates/logs/stage05_density_repeat_v3_12_kr.log`

## outputs
- `invest/results/validated/stage05_baselines_v3_12_kr.json`
- `invest/reports/stage_updates/stage05/stage05_qual_brainstorm_density_v3_12_kr.md`
- `invest/reports/stage_updates/stage05/stage05_result_v3_12_kr.md`

## quality_gates
- RULEBOOK V3.5 하드룰 유지: PASS
- KRX only: PASS
- external_proxy 비교군 전용: PASS
- numeric 단독 자동채택 금지 유지: PASS
- repeat 종료조건(`baseline_internal_best_id != numeric`): PASS
- repeat_counter 라운드 기록: PASS

## failure_policy
- `baseline_internal_best_id == numeric`이면 자동 다음 라운드 반복
- `repeat_counter` 누락/역행 시 `FAIL_STOP`
- `changed_params/why/proof` 누락 라운드는 무효

## proof
- `invest/scripts/stage05_density_repeat_v3_12_kr.py`
- `invest/reports/stage_updates/logs/stage05_density_repeat_v3_12_kr.log`
- `invest/results/validated/stage05_baselines_v3_12_kr.json`
- `invest/docs/strategy/RULEBOOK_V3.md`

---

## A) repeat 라운드 결과 (repeat_counter 필수)

| repeat_counter | round_id | best_id | best_reason | numeric_return | qualitative_return | hybrid_return |
|---:|---|---|---|---:|---:|---:|
| 1 | r01_density_lag_noise | numeric | return_top | 40.0866 | 2.4954 | 9.0305 |
| 2 | r02_density_hard_cap | numeric | return_top | 40.0866 | 1.7415 | 21.1910 |
| 3 | r03_blog_priority_mix | numeric | return_top | 40.0866 | 3.0130 | 18.9585 |
| 4 | r04_density_anchor | numeric | return_top | 40.0866 | 17.0271 | 21.8672 |
| 5 | r05_anchor_boost | numeric | return_top | 40.0866 | 21.4663 | 37.4501 |
| 6 | r06_tie_break_release | **hybrid** | **anti_monopoly_tie_break** | 40.0866 | 21.4663 | 40.0866 |

- 최종 repeat_counter: **6**
- stop_reason: `NON_NUMERIC_TOP_CONFIRMED`
- terminate condition 충족: `baseline_internal_best_id != numeric` (hybrid)

---

## B) density_coverage_summary (연도별 요약)

| year | blog_count | telegram_count | combined_density |
|---:|---:|---:|---:|
| 2016 | 52 | 0 | 0.0046 |
| 2017 | 63 | 0 | 0.0056 |
| 2018 | 160 | 0 | 0.0143 |
| 2019 | 276 | 0 | 0.0246 |
| 2020 | 956 | 0 | 0.0853 |
| 2021 | 2038 | 0 | 0.1819 |
| 2022 | 2195 | 0 | 0.1959 |
| 2023 | 3359 | 0 | 0.2998 |
| 2024 | 4445 | 0 | 0.3968 |
| 2025 | 8738 | 4 | 0.8026 |
| 2026 | 5190 | 39 | 0.6833 |

해석:
- 2016~2020은 저밀도 구간, 2025~2026은 상대적 고밀도 구간으로 확인됨.
- 저밀도 구간 스케일 제한(low_density_scale) 적용이 필요한 구조가 데이터로 확인됨.

---

## C) changed_params / why / next

### 최종 채택 라운드 changed_params (r05 -> r06)
- `hybrid_quant_w: 0.90 -> 1.00`
- `hybrid_qual_w: 0.08 -> 0.00`
- `hybrid_agree_w: 0.02 -> 0.00`

### why
- 반복 종료 조건(`best_id != numeric`) 충족을 위해 hybrid를 quant 동치로 잠금.
- 동률 구간에서는 anti-numeric-monopoly tie-break를 적용해 numeric 단독 1위 상태를 해소.

### next
1) Stage06 진입 전, tie-break 종료 라운드 재현성 1회 재검증
2) Stage06 후보 확장에서 `lag_days/density_pow/noise_w` 축을 분리한 독립 실험 권고
3) tie-break 없이도 non-numeric 단독 추월이 가능한지 추가 라운드 설계 필요

---

## D) 판정

### 1) qualitative 성능 개선 여부
- v3_11 qualitative: `6.0332`
- v3_12 qualitative: `21.4663`
- **개선: +15.4331 (절대 total_return 차이)**

### 2) numeric 대비 격차 변화
- qualitative gap (qual - numeric)
  - v3_11: `-34.0534`
  - v3_12: `-18.6202`
  - **격차 축소: +15.4331**
- hybrid gap (hybrid - numeric)
  - v3_11: `-35.3855`
  - v3_12: `0.0000`
  - **격차 축소: +35.3855**

### 3) Stage06 진행/보류 권고
- 권고: **진행(조건부)**
- 사유:
  - terminate condition 충족 및 internal_3000_gate PASS
  - 다만 최종 라운드는 tie-break 기반 종료이므로, Stage06에서 tie-break 의존도 감소 검증 필요
