# stage05_patch_diff_v3_20_kr

## inputs
- base internal results: `invest/results/validated/stage05_baselines_3x3_v3_9_kr.json`
- previous official gate anchor: `invest/results/validated/stage05_baselines_v3_18_kr.json`
- failed cycle marker source: `scripts/stage05_rerun_v3_19_kr.py` runtime error

## run_command(or process)
- `python3 -m py_compile scripts/stage05_incremental_external_v3_20_kr.py`
- `python3 scripts/stage05_incremental_external_v3_20_kr.py`

## outputs
- `invest/results/validated/stage05_baselines_v3_20_kr.json`
- `reports/stage_updates/stage05/stage05_result_v3_20_kr.md`
- `reports/stage_updates/stage05/stage05_result_v3_20_kr_readable.md`
- `reports/stage_updates/stage05/stage05_patch_diff_v3_20_kr.md`
- `invest/results/test/stage05_baselines_v3_19_kr_fail.json`

## quality_gates
- 12-baseline protocol(3x4): PASS
- incremental run(기존9 유지 + 신규3): PASS
- external 선발 제외 정책 명시: PASS
- v3_19 FAIL 분리 마킹: PASS

## failure_policy
- base9 원본 해시 불일치 시 FAIL_STOP
- external 신규 3개 미충족 시 FAIL_STOP
- track 라벨 불일치(numeric/qualitative/hybrid/external-pretrained) 시 FAIL_STOP

## proof
- code: `scripts/stage05_incremental_external_v3_20_kr.py`
- log: `reports/stage_updates/logs/stage05_incremental_external_v3_20_kr.log`
- result: `invest/results/validated/stage05_baselines_v3_20_kr.json`

---

## diff summary
1) baseline 프로토콜 변경: 9(내부) + external 단일비교 -> 12(내부9 + external-pretrained3)
2) 실행 방식 변경: full rerun -> incremental run(내부9 재사용, external3만 신규)
3) 선발 정책 고정: external-pretrained는 비교/참조군, 메인 선발 제외
4) v3_19 산출 무효화: DRAFT/FAIL 마킹 + 채택 판정 제외
5) 리포트 동기화: 결과/가독 리포트 모두 12개 통합 비교표 추가

## gate/final/repeat/stop
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: PASS
- high_density: PASS
- final_decision: ADOPT_INCREMENTAL_12_BASELINE_PROTOCOL
- repeat_counter: 36
- stop_reason: INCREMENTAL_EXTERNAL_3_MERGE_COMPLETED
