# stage08_cutoff_v3_4_kr

> status: HISTORICAL_ONLY
> role: LEGACY_REFERENCE
> note: 현재 canonical 실행 문서가 아니다.

## inputs
- `invest/stages/stage7/outputs/results/validated/stage07_candidates_v3_4_kr.json`

## run_command(or process)
- `python3 scripts/run_stage06_09_v3_4_kr.py`

## outputs
- `invest/stages/stage8/outputs/results/validated/stage08_candidates_cut_v3_4_kr.json`
- `docs/invest/stage8/stage_updates/stage08_cutoff_v3_4_kr.md`

## quality_gates
- 컷오프 규칙 적용(Return>2000%, MDD>-40%)
- 0건 시 재탐색

## failure_policy
- 재탐색 후에도 0건이면 최고수익 후보를 조건부 승격

## proof
- `invest/stages/stage8/outputs/results/validated/stage08_candidates_cut_v3_4_kr.json`

## summary
- passed: 0 / 120
- champion final cumulative return: 238.50% | final asset multiple: 3.39x
