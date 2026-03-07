# stage08_cutoff_design_v5_kr

> status: HISTORICAL_ONLY
> role: LEGACY_REFERENCE
> note: 현재 canonical 실행 문서가 아니다. 당시 참조 파일 중 일부는 현재 main에 존재하지 않아, 아래에는 현재 존재하는 canonical 경로만 남긴다.

## inputs
- `invest/stages/stage7/outputs/results/validated/stage07_candidates_v5_kr.json`
- `docs/invest/RULEBOOK_MASTER.md`
- `docs/invest/stage7/STAGE7_RULEBOOK_AND_REPRO.md`

## run_command(or process)
- `python3 scripts/stage08_cutoff_v5_kr.py` (설계 반영 대상)

## outputs
- `invest/stages/stage8/outputs/results/validated/stage08_candidates_cut_v5_kr.json`
- `docs/invest/stage8/stage_updates/stage08_cutoff_v5_kr.md`

## hard_gate (new_selection_gate)
- policy_id: `anti_numeric_monopoly_gate_v1`
- hard_rule: `numeric 단독 1등 즉시 최종 채택 금지`
- adopt_allowed_if:
  - (a) `hybrid` 또는 `qualitative` 후보가 numeric 최고 후보 total_return 추월
  - (b) numeric 대비 수익률 근접 + MDD 우위 + turnover_proxy 우위 동시 충족
- stage_binding:
  - Stage08 컷오프: 통과/보류 판정에 강제
  - Stage10 최종검토: ADOPT 이전 재검증 강제

## cutoff flow (초안)
1) Stage07 입력 로드
2) 1차 품질 컷: 하드규칙 위반/필드 누락/산출 이상치 제거
3) 트랙별 상위 후보군 추출(numeric/qualitative/hybrid)
4) `new_selection_gate` 판정
5) Stage08 산출물에 gate 판정 근거 필수 기록

## quality_gates
- RULEBOOK 하드규칙 고정값 통과 여부 확인
- `new_selection_gate` 판정 컬럼 필수(`gate_pass`, `gate_reason`)
- numeric 단독 1등의 direct adopt 금지 확인

## failure_policy
- 입력 누락/비검증 결과(VALIDATED 아님) 발견 시 FAIL_STOP
- gate 판정 근거 누락 시 FAIL_STOP
- numeric 단독 1등이 gate 우회로 ADOPT로 표기되면 FAIL_STOP

## proof
- `docs/invest/RULEBOOK_MASTER.md`
- `docs/invest/stage8/stage_updates/stage08_cutoff_design_v5_kr.md`
- `docs/invest/stage7/STAGE7_RULEBOOK_AND_REPRO.md`
