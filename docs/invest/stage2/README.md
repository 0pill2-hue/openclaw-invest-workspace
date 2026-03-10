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
  - blog/telegram/premium 링크 원문 enrichment 기본 ON 규칙
- `STAGE2_PDF_REFINEMENT_DESIGN.md`
  - Telegram PDF inline promotion의 세부 설계/계약/diagnostics

## 한 줄 요약
- Stage2는 `upstream_stage1/master` + `stage1_raw_archive.sqlite3`를 읽고, raw DB snapshot을 stage-local mirror로 materialize해 사용한다.
- `stage02_onepass_refine_full.py`는 **market signal + qualitative** canonical writer다.
- `stage02_qc_cleaning_full.py`는 **kr/us signal** canonical writer이자 QC gate다.
- clean/quarantine 경계, taxonomy, rerun 규칙은 `STAGE2_RULEBOOK_AND_REPRO.md`를 기준으로 본다.
