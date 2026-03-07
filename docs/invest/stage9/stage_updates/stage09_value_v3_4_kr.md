# stage09_value_v3_4_kr

> status: HISTORICAL_ONLY
> role: LEGACY_REFERENCE
> note: 현재 canonical 실행 문서가 아니다.

## inputs
- `invest/stages/stage8/outputs/results/validated/stage08_candidates_cut_v3_4_kr.json`

## run_command(or process)
- `python3 scripts/run_stage06_09_v3_4_kr.py`

## outputs
- `invest/stages/stage9/outputs/results/validated/stage09_value_assessment_v3_4_kr.json`
- `docs/invest/stage9/stage_updates/stage09_value_v3_4_kr.md`

## quality_gates
- 챔피언 1개 선정
- 수치=JSON 일치

## failure_policy
- 챔피언 미선정 시 FAIL

## proof
- `invest/stages/stage9/outputs/results/validated/stage09_value_assessment_v3_4_kr.json`

## summary
- champion: S06V3_4_KR_R020
- champion final cumulative return: 238.50% | final asset multiple: 3.39x
