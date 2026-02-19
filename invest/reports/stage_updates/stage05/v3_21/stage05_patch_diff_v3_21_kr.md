# stage05_patch_diff_v3_21_kr

## 변경 요약
1) official_scope를 `effective_window` -> `official_2021_plus`로 상향
2) core high-density 구간을 `2023~2025`로 명시하고 가중 평가 반영
3) 2016~2020 구간은 reference/저가중으로 분리
4) v3_20 incremental 12-baseline 실행 구조 유지(기존9 재사용 + 신규3 실행)

## 입력/출력
- input(base9): `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- output(result): `invest/results/validated/stage05_baselines_v3_21_kr.json`
- output(report): `invest/reports/stage_updates/stage05/stage05_result_v3_21_kr.md`
- output(readable): `invest/reports/stage_updates/stage05/stage05_result_v3_21_kr_readable.md`
- output(patch): `invest/reports/stage_updates/stage05/stage05_patch_diff_v3_21_kr.md`

## hard-rule 유지 확인
- KRX only: 유지
- 보유1~6: 유지
- 최소보유20일: 유지
- 교체+15%: 유지
- 월교체30%: 유지
- high-density gate(+25%p/MDD/turnover): 유지

## gate/final/repeat/stop
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL_V321
- repeat_counter: 37
- stop_reason: OFFICIAL_2021_CORE_2023_WEIGHTED_GATE_PASS
