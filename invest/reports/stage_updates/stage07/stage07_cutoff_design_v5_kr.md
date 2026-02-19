# stage07_cutoff_design_v5_kr

## inputs
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v5_kr.json`
- `/Users/jobiseu/.openclaw/workspace/invest/docs/strategy/RULEBOOK_V3.md`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_candidates_v5_kr.md`

## run_command(or process)
- `python3 invest/scripts/stage07_cutoff_v5_kr.py` (설계 반영 대상)

## outputs
- `/Users/jobiseu/.openclaw/workspace/invest/results/validated/stage07_candidates_cut_v5_kr.json`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage07/stage07_cutoff_v5_kr.md`

## hard_gate (new_selection_gate)
- policy_id: `anti_numeric_monopoly_gate_v1`
- hard_rule: `numeric 단독 1등 즉시 최종 채택 금지`
- adopt_allowed_if:
  - (a) `hybrid` 또는 `qualitative` 후보가 numeric 최고 후보 total_return 추월
  - (b) numeric 대비 수익률 근접 + MDD 우위 + turnover_proxy 우위 동시 충족
- stage_binding:
  - Stage07 컷오프: 통과/보류 판정에 강제
  - Stage09 최종검토: ADOPT 이전 재검증 강제

## cutoff flow (초안)
1) Stage06 72개 입력 로드
2) 1차 품질 컷: 하드규칙 위반/필드 누락/산출 이상치 제거
3) 트랙별 상위 후보군 추출(numeric/qualitative/hybrid)
4) **new_selection_gate 판정**:
   - numeric 1위 단독일 경우 즉시 ADOPT 금지
   - 조건 (a) 또는 (b) 만족 시에만 ADOPT 후보군 승격
   - 미충족 시 상태를 `HOLD`로 표기하고 Stage08 추가검증으로 이관
5) Stage07 산출물에 gate 판정근거(수익률/MDD/turnover 비교표) 필수 기록

## quality_gates
- stage06 입력 후보 수 72 확인
- 트랙 분배 24/24/24 확인
- RULEBOOK 하드규칙 고정값 통과 여부 확인
- `new_selection_gate` 판정 컬럼 필수(`gate_pass`, `gate_reason`)
- numeric 단독 1등의 direct adopt 금지 확인

## failure_policy
- 입력 누락/비검증 결과(VALIDATED 아님) 발견 시 FAIL_STOP
- gate 판정 근거(수익률/MDD/turnover) 누락 시 FAIL_STOP
- numeric 단독 1등이 gate 우회로 ADOPT로 표기되면 FAIL_STOP

## proof
- `/Users/jobiseu/.openclaw/workspace/invest/docs/strategy/RULEBOOK_V3.md`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage07/stage07_cutoff_design_v5_kr.md`
- `/Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage06/stage06_candidates_v4_kr.md`
