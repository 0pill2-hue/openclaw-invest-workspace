# Stage2 Docs

Stage2 문서는 contract와 implementation-current를 분리해 유지한다.

## Canonical 문서
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md` (계약/재현 경계)
- `docs/invest/stage2/STAGE2_IMPLEMENTATION_CURRENT_SPEC.md` (현재 구현값/세부 동작)
- `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md` (Telegram PDF 세부 설계)

## 한 줄 요약
- Stage2는 Stage1 raw/master를 읽어 `clean/quarantine`을 만든다.
- writer ownership, 입력/출력 계약, PASS/FAIL은 RULEBOOK 기준이다.
- exact threshold/runtime default/report schema는 IMPLEMENTATION_CURRENT_SPEC 기준이다.
