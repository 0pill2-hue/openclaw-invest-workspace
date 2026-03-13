# JB-20260311-STAGE1-PDF-PAGE-MARKER

- status: READY_FOR_REVIEW
- started_at: 2026-03-11 16:58 KST
- updated_at: 2026-03-11 17:17 KST
- close_recommendation: DONE

## goal
- Stage1 PDF 처리에서 원문 비보관 정책을 유지하면서 추출 시 페이지번호/페이지마커를 붙인 텍스트 저장을 기본 계약으로 만든다.
- 이미 수집된 평문-only PDF는 재다운로드 가능분만 bounded backfill로 보강하고, 복구 불가분은 plain-text-only 상태를 명시한다.

## accomplished
1. **새 PDF 추출 경로 변경**
   - `stage01_scrape_telegram_highspeed.py`가 PDF 추출 시 plain text 대신 page-marked single text(`"[PAGE 001]"` 등)를 쓰도록 변경.
   - PDF meta에 `pdf_page_marked`, `pdf_page_marker_format`, `pdf_page_marker_count`, `pdf_page_mapping_status`, `extract_format`를 기록.

2. **공용 PDF page-marker helper 추가**
   - `stage_pdf_artifacts.py`에
     - original PDF → page-marked text 추출 helper
     - existing manifest/page text → page-marked text 재구성 helper
     - marker detection/count helper
     를 추가.
   - 기존 page artifact(manifest/page txt/page png/bundle) 지원은 유지.

3. **bounded backfill 명시화**
   - `stage01_telegram_attachment_extract_backfill.py`가 아래 순서로 동작하도록 변경.
     - original bytes 있으면 page-marked extracted text로 재생성
     - original은 없지만 manifest/page text 있으면 그 범위에서만 재구성
     - 둘 다 없으면 기존 plain text를 유지하고 `pdf_page_marked=false`, `pdf_page_mapping_status=missing_*`로 명시
   - original 미복구 PDF 때문에 전체 파이프라인이 hard-fail 되지 않도록 계약 정렬.

4. **raw DB/summary 계약 확장**
   - `stage_raw_db.py` schema를 v3로 올리고 `pdf_documents.page_marked/page_marker_count/page_mapping_status/extract_format` 컬럼을 추가.
   - backfill status JSON에 `pdf_page_marked_total`, `pdf_page_mapping_missing_total` 집계를 추가.

5. **문서/계약 동기화**
   - Stage1 data collection / runbook / PDF deliverable contract에
     - page-marked extracted text 기본 계약
     - bounded backfill 규칙
     - original PDF 비영구보관 정책
     - 새 metadata/DB 필드
     를 반영.

## files changed
- `invest/stages/common/stage_pdf_artifacts.py`
- `invest/stages/common/stage_raw_db.py`
- `invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- `docs/invest/stage1/stage01_data_collection.md`
- `docs/invest/stage1/RUNBOOK.md`
- `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
- `runtime/tasks/JB-20260311-STAGE1-PDF-PAGE-MARKER.md`

## exact proof paths
- verification JSON: `runtime/tasks/proofs/JB-20260311-STAGE1-PDF-PAGE-MARKER/verification.json`
- fixture DB: `runtime/tasks/proofs/JB-20260311-STAGE1-PDF-PAGE-MARKER/raw_db_fixture/stage1_raw_archive.sqlite3`

## verification runs
1. **Python compile check**
   - command:
     - `python3 -m py_compile invest/stages/common/stage_pdf_artifacts.py invest/stages/common/stage_raw_db.py invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
   - result: PASS

2. **Targeted functional verification**
   - wrote proof: `runtime/tasks/proofs/JB-20260311-STAGE1-PDF-PAGE-MARKER/verification.json`
   - verified:
     - original PDF sample → `extract_pdf_text_with_page_markers(...).page_marked = true`
     - existing manifest/page text sample → `build_pdf_page_marked_text_from_manifest(...).page_marked = true`
     - temp raw DB fixture → `pdf_documents.page_marked = 1`, `page_marker_count = 2`, `page_mapping_status = available_from_manifest_pages`, `extract_format = pdf_page_marked_text_v1`

## notes
- original PDF 영구보관 요구는 추가하지 않았다. page artifact 또는 durable page-marked extracted text가 있으면 original 삭제 후에도 계약을 유지하도록 맞췄다.
- 기존 corpus 삭제/파괴 작업은 수행하지 않았다.
- 본 작업은 task report만 갱신했으며 ticket DB 상태 전이는 하지 않았다.
