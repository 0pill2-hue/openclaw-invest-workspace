# JB-20260311-PDF-DELIVERABLE-CRITERIA-LOCK

- status: DONE
- owner: subagent
- completed_at: 2026-03-11 14:36 KST

## what
- taskdb row와 관련 문서/스크립트/산출물을 읽기 전용으로 감사해 PDF 최종 deliverable 계약을 확정했다.
- 기존 live DB sync writer(`stage01_sync_raw_to_db.py`)나 raw DB writer 실행은 하지 않았다.
- 충돌 방지를 위해 이미 수정 중인 writer 파일은 편집하지 않고, **새 계약 문서 + 읽기 전용 감사 스크립트 + 본 티켓 증빙 문서**만 추가했다.

## intended contract (locked)
1. **성공 기준**
   - 원본 PDF 보관은 필수 아님.
   - 성공은 `분해/추출 결과가 DB에 반영되었는가` 기준으로 판단.
   - physical `.pdf` file count, `original_present_count`는 진단용 보조지표일 뿐 최종 success gate가 아님.
2. **최종 보고 필수 필드**
   - `pdf_meta_total`
   - `pdf_extract_ok_total`
   - `documents_with_text`
   - `coverage_start`
   - proof paths (runtime status / catalog / final report)
3. **coverage_start 정의**
   - generic telegram markdown coverage가 아니라 **PDF-specific attachment scope** 기준이어야 함.
   - canonical source priority:
     1) `telegram_attachment_extract_backfill_status.json -> pdf_db_index_summary.earliest_message_date`
     2) `source_coverage_index.sources.telegram.scope.attachment_artifacts.earliest_message_date`
   - 최종 출력 형식은 `YYYY-MM-DD`.

## evidence
- taskdb row
  - `JB-20260311-PDF-DELIVERABLE-CRITERIA-LOCK`
  - title: `PDF 성공기준/카탈로그 필드 고정: DB 반영 + counts + coverage_start`
- user acceptance / prior ticket
  - `runtime/tasks/JB-20260311-PDF-IMPROVE-COLLECT.md`
- runtime status source
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- catalog source
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- DB index contract source
  - `invest/stages/common/stage_raw_db.py` (`PdfIndexSummary.documents_with_text`, `earliest_message_date`, `latest_message_date`)
- status writer source
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py` (`pdf_meta_total`, `pdf_extract_ok_total`, `pdf_decompose_ok_total`, `pdf_pages_total`, `pdf_db_index_summary`)
- catalog writer source
  - `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py` (`sources.telegram.scope.attachment_artifacts.earliest_message_date` etc.)

## audited current values
- `pdf_meta_total = 63735`
- `pdf_extract_ok_total = 59672`
- `documents_with_text = 608`
- `pdf_decompose_ok_total = 608`
- `pdf_pages_total = 9632`
- `coverage_start = 2019-10-29`
- `coverage_end = 2026-03-09`
- generic telegram `earliest_date = 20191025` (**PDF coverage_start로 사용하면 안 됨**)
- physical `pdf_files = 87` (**diagnostic only; logical doc count 63735와 다름**)

## added for contract clarity
- doc: `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
- read-only audit helper: `scripts/tasks/pdf_deliverable_contract_audit.py`
- audit proof json: `runtime/tasks/proofs/JB-20260311-PDF-DELIVERABLE-CRITERIA-LOCK_audit.json`

## proof
- `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
- `scripts/tasks/pdf_deliverable_contract_audit.py`
- `runtime/tasks/proofs/JB-20260311-PDF-DELIVERABLE-CRITERIA-LOCK_audit.json`

## conclusion
- 본 티켓 목표(성공기준/카탈로그 필드 계약 감사 및 고정)는 **DB write 없이 완료 가능**했고, 읽기 전용 감사 + 새 계약 문서/검증 스크립트로 DONE 처리 가능하다.
- 남은 운영 작업이 있다면, 이후 실제 writer run에서 최종 report/catalog 출력부에 이 계약을 flatten해서 쓰는 일뿐이며, 이 티켓 자체의 blocker는 남지 않았다.
