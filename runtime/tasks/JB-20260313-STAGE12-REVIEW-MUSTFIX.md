# JB-20260313-STAGE12-REVIEW-MUSTFIX

## landed
- Stage1 attachment recovery에 compact canonical summary `invest/stages/stage1/outputs/runtime/stage1_attachment_recovery_summary.json` 계약을 추가하고, `stage01_telegram_attachment_extract_backfill.py`가 `stage_status`, `completeness_status`, `completeness` 분해(`collected_total`, `recovered_from_manifest`, `original_present`, `missing_original`, `missing_manifest`, `placeholder_only`, `recoverable_missing_artifact`, `bounded_by_cap`, `unrecoverable_missing`) 및 `retry_visibility.retry_count/last_retry_at/last_error`를 기록하도록 반영.
- Stage1 backfill runtime status(`telegram_attachment_extract_backfill_status.json`)에도 동일한 `stage_status`, `completeness_status`, `completeness`, `recovery_lane`, `retry_visibility`를 노출하도록 정리.
- Stage1 operator-facing summary 경로를 승격:
  - `stage01_update_coverage_manifest.py` → `source_coverage_index.sources.telegram.scope.attachment_artifacts`에 `recovery_summary_path`, `stage_status`, `completeness_status`, `completeness`, `recovery_lane`, `retry_visibility` 반영.
  - `scripts/dashboard/read_stage1.py` → Attachment Recovery card 추가.
- Stage1 gate summary 분리:
  - `stage01_post_collection_validate.py` top-level에 `stage_status`(gate PASS/FAIL), `completeness_status`, `attachment_recovery_stage_status` 추가.
  - `details[]`에 `runtime/telegram_attachment_recovery` 항목 추가하도록 코드 반영.
- Stage1 Telegram cadence visibility 강화:
  - `stage01_scrape_telegram_launchd.py`가 attachment recovery summary path와 `attachment_recovery.{stage_status, completeness_status, retry_count, last_retry_at, last_error, selected_candidates, recovered_ok, failed}`를 collector status에 포함하도록 반영.
  - `docs/invest/stage1/RUNBOOK.md`에서 attachment recovery lane을 기본 cadence/runbook 단계로 승격.
- Stage2 top-level output 계약 수정:
  - `stage02_onepass_refine_full.py`가 top-level에 `input_source`, `input_source_status`, `fallback_reason`, `fallback_scope`를 명시하고, 상세는 `input_source_policy`에 분리.
  - raw fallback 상태명을 `degraded_raw_files_fallback_opt_in`으로 명확화.
  - processed index meta에도 `fallback_reason`, `fallback_scope` 반영.
- Stage2 addendum must-fix 반영:
  - Stage2 top-level summary에 PDF 상태 버킷을 분리: `promoted`, `bounded_by_cap`, `recoverable_missing_artifact`, `placeholder_only`, `extractor_unavailable`, `parse_failed`, `lineage_mismatch`, `diagnostics_only`.
  - bounded stop visibility를 top-level/telegram_pdf에 추가: `declared_page_count_total`, `indexed_page_rows_total`, `materialized_text_pages_total`, `materialized_render_pages_total`, `placeholder_page_rows_total`, `bounded_by_cap_docs`, `bounded_pages_total`.
  - legacy/fallback join visibility를 계측: `join_strategy(canonical_marker|canonical_flat|legacy_dir|recovered_local_extract)`, `join_confidence(strong|medium|weak)`, `lineage_status(confirmed|probable|unresolved)`.
  - weak/unresolved 계열은 `diagnostics_only` bucket이 우선되도록 분류 로직 반영(명시적 message mismatch는 `lineage_mismatch` bucket 유지).
  - operator-facing `invest/stages/stage2/outputs/runtime/stage2_integrity_summary.json` 추가.
  - Stage1→Stage2 handoff completeness 계약을 Stage2 payload에 추가: `raw_checkpoint_status`, `source_coverage_status`, `attachment_recovery_status`, `placeholder_ratio`, `recoverable_missing_ratio`, `severe_missing_ratio`, `handoff_status`.
  - Stage2 summary에 `origin_of_degradation(inherited_from_stage1|introduced_in_stage2|unresolved_mixed_origin)` 추가.
- 문서/코드/운영 계약 정렬:
  - Stage1: `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`, `RUNBOOK.md`, `PDF_DELIVERABLE_CONTRACT.md`
  - Stage2: `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`, `STAGE2_IMPLEMENTATION_CURRENT_SPEC.md`

## remaining
- `stage01_telegram_attachment_extract_backfill.py`의 새 compact summary는 코드에 landed 했고 현재 runtime에도 생성했지만, 이번 턴에서는 full backfill 재실행까지는 하지 않았다. 따라서 새 schema의 누적 `retry_count`는 기존 runtime 기준 1회로 seed 되었고, 다음 canonical backfill run부터 코드 경로로 누적된다.
- `stage01_update_coverage_manifest.py` / `stage01_post_collection_validate.py`는 코드 경로를 수정했고, 현재 runtime artifact는 lightweight patch로 반영했다. 전체 collector/gate 재실행 기준의 end-to-end smoke는 아직 미수행.
- Stage2 refine는 전체 재실행이 무거워 이번 턴에는 코드/문서 수정 + 최신 report artifact patch + `stage2_integrity_summary.json` 생성까지만 수행했다. 따라서 addendum의 lineage/join/bounded 계측값은 현재 운영 데이터 기준 패치/재계산값이며, 다음 실제 refine run에서 새 코드 경로 기준 누적값이 자연 생성되는지 재확인하면 마무리 가능.

## proof
- 문법 검증:
  - `python3 -m py_compile invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py invest/stages/stage1/scripts/stage01_update_coverage_manifest.py invest/stages/stage1/scripts/stage01_post_collection_validate.py invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py invest/stages/stage2/scripts/stage02_onepass_refine_full.py scripts/dashboard/read_stage1.py`
- 생성/갱신 artifact:
  - `invest/stages/stage1/outputs/runtime/stage1_attachment_recovery_summary.json`
    - generated summary result: `stage_status=WARN`, `completeness_status=UNRECOVERABLE`, `selected_candidates=256`, `retry_count=1`
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
  - `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260311_211926.json`
    - patched top-level addendum result: `stage3_ready_status=BLOCKED`, `origin_of_degradation=inherited_from_stage1`, `handoff_completeness.handoff_status=NEED_RECOVERY_FIRST`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260311_211926.md`
  - `invest/stages/stage2/outputs/runtime/stage2_integrity_summary.json`
    - required top-level keys 확인: `input_source_status`, `total_records_seen/clean/quarantine`, `pdf_docs_seen`, `pdf_promoted_docs`, `pdf_bounded_docs`, `pdf_missing_docs`, `pdf_placeholder_only_docs`, `lineage_unresolved_docs`, `stage3_ready_status`
    - generated result: `stage3_ready_status=BLOCKED`, `origin_of_degradation=inherited_from_stage1`, `handoff_completeness.handoff_status=NEED_RECOVERY_FIRST`
- 변경 파일(추적 기준 `git status --short` 확인):
  - `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
  - `docs/invest/stage1/RUNBOOK.md`
  - `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
  - `docs/invest/stage2/STAGE2_IMPLEMENTATION_CURRENT_SPEC.md`
  - `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
  - `invest/stages/stage1/scripts/stage01_post_collection_validate.py`
  - `invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py`
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
  - `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
  - `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
  - `scripts/dashboard/read_stage1.py`
