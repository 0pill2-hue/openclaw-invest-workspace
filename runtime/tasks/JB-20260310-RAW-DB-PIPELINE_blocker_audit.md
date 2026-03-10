# JB-20260310-RAW-DB-PIPELINE blocker audit

- generated_at: 2026-03-10 19:42:07 +0900
- status: DONE_CANDIDATE
- quiescence_reason: quiescent: no stage1 writers and db/wal/status mtimes stable across 5s sample
- destructive action: 없음

## current state
- writers_absent: True
- mtimes_stable_5s: True
- page_count_vs_rows_total: 0
- text_pages_vs_rows: 0
- rendered_pages_vs_rows: 0
- status_sync_id: 20260310T101154Z
- meta_last_sync_id: 20260310T101154Z
- status_finished_at: 2026-03-10T10:11:54.412804+00:00
- meta_last_sync_finished_at: 2026-03-10T10:11:54.412804+00:00
- status_scanned_files: 232162
- meta_scanned_files: 232162
- status_pdf_index_finished_at: 2026-03-10T10:17:13.458041+00:00
- meta_pdf_index_finished_at: 2026-03-10T10:17:13.458041+00:00

## counts
- raw_disk_file_count: 232253
- raw_db_active_count: 232162
- pdf_meta_files_total: 64140
- unique_doc_keys_from_meta: 63735
- pdf_documents_rows: 63735

## proof paths
- report: `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_blocker_audit.md`
- json: `runtime/tasks/proofs/JB-20260310-RAW-DB-PIPELINE_quiescent_audit.json`
- db: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- status: `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
