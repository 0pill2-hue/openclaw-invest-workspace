# JB-20260309-STAGE3OVERVIEWALIGN

- change_type: Rule
- verdict: FIXED_AND_UNIFIED

## finding
- `docs/invest/STAGES_OVERVIEW.md` 기준으로 보면 기존 Stage3 설명은 canonical 설계와 불일치했다.
- 불일치 핵심은 세 가지였다.
  1. Stage3 입력을 `Stage1 정성 원천 + Stage2 clean 메타`로 적어 두었지만 canonical 문서는 `Stage2 clean + Stage3 reference`만 허용한다.
  2. Stage3 출력을 `attention/sentiment feature` 중심으로 적어 두었지만 canonical 문서는 4축 정성 feature, claim-card, DART event signal을 출력으로 정의한다.
  3. Stage7을 RESERVED로 적어 두었지만 canonical 문서와 실행 스펙은 ACTIVE 단계로 정의한다.

## action
- `docs/invest/STAGES_OVERVIEW.md`를 canonical 문서에 맞춰 수정했다.
- Stage3를 로컬 브레인 claim-card 추출 + rule-engine 집계 기반 4축 정성신호 단계로 정렬했다.
- Stage7을 ACTIVE로 승격 표기하고 입력/출력/게이트를 Stage7 rulebook에 맞췄다.

## conclusion
- 따라서 수정 전 상태를 `문제없음`으로 통일하는 것은 부정확했다.
- 수정 후에는 Stage overview와 Stage3/Stage7 canonical 문서가 같은 기준으로 정렬됐다.

## proof
- docs/invest/STRATEGY_MASTER.md
- docs/invest/STAGE_EXECUTION_SPEC.md
- docs/invest/stage3/README.md
- docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md
- docs/invest/stage3/STAGE3_DESIGN.md
- docs/invest/stage4/STAGE4_RULEBOOK_AND_REPRO.md
- docs/invest/stage7/README.md
- docs/invest/stage7/STAGE7_RULEBOOK_AND_REPRO.md
- docs/invest/STAGES_OVERVIEW.md
