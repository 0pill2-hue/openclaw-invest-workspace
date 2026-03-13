# Stage2 Docs

Stage2 문서는 **문서만 보고 현재 Stage2 refine/QC를 재현 구현할 수 있는 수준**으로 유지한다.

## Canonical 문서
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`

## 문서 역할
- `STAGE2_RULEBOOK_AND_REPRO.md`
  - Stage2 전체 계약
  - folder ownership
  - input/output contract
  - refine/QC 규칙
  - dedup/link/PDF 승격/processed-index/report schema
  - Telegram PDF path resolution의 현재 계약 요약
  - Stage2 recovery 범위(로컬 artifact resolve + local extract) 경계
- `STAGE2_PDF_REFINEMENT_DESIGN.md`
  - Telegram PDF inline promotion의 세부 설계/계약/diagnostics
  - bucketed flat attachment path 기준의 current path resolution order
  - legacy `msg_<message_id>/` 디렉터리의 fallback-only 위치

## Historical / non-canonical 참고
- `runtime/tasks/JB-20260311-TELEGRAM-PDF-*.md`
- `runtime/tasks/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX.md`

위 문서들은 **운영 로그/조사/증빙**이며 Stage2 계약 SSOT가 아니다. 현재 Stage2 path/recovery 계약은 위 canonical 2문서만 기준으로 본다.

## 한 줄 요약
- Stage2는 `upstream_stage1/master` + `stage1_raw_archive.sqlite3`를 읽고, raw DB snapshot을 stage-local mirror로 materialize해 사용한다.
- `stage02_onepass_refine_full.py`는 **market signal + qualitative** canonical writer다.
- `stage02_qc_cleaning_full.py`는 **kr/us signal** canonical writer이자 QC gate다.
- Stage1은 PDF/문서를 문서·페이지 단위로만 분해하고, Stage2는 정제 이후 **산업/종목 deterministic 태깅**을 추가한다.
- Telegram PDF는 별도 corpus가 아니라 기존 `text/telegram` clean 본문에 inline 승격된다.
- clean/quarantine 경계, taxonomy, rerun 규칙은 `STAGE2_RULEBOOK_AND_REPRO.md`를 기준으로 본다.
