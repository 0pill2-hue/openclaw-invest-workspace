# RULEBOOK_MASTER

공통 하드룰 문서입니다.

본 문서는 투자 파이프라인 전반에 적용되는 **공통 실행 규칙**만 정의합니다.

## 공통 하드룰

- 단계 우회 금지: upstream FAIL 상태에서 downstream 실행 금지
- 데이터 경계: stage 스크립트는 동일 stage `inputs/` 경유 입력만 사용
- 결과 등급 분리: `DRAFT | VALIDATED | PRODUCTION`
- 증빙 필수: 실행/검증/산출물 경로가 없는 보고는 PASS 금지
- 실패 시 fail-close: 무시/우회 실행 금지

## 상세 stage 룰북 위치

- Stage1: `invest/stages/stage1/docs/STAGE1_RULEBOOK_AND_REPRO.md`
- Stage2: `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- Stage3: `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`
- Stage4: `docs/invest/stage4/STAGE4_RULEBOOK_AND_REPRO.md`
- Stage5: `docs/invest/stage5/STAGE5_RULEBOOK_AND_REPRO.md`
- Stage6: `docs/invest/stage6/STAGE6_RULEBOOK_AND_REPRO.md`
