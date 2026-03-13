# JB-20260311-PDF-IMPROVE-COLLECT

## Goal
- 개선된 PDF 처리 경로로 재수집/수합을 진행하되, 최종 성공 기준을 `원본 파일 보관`이 아니라 `분해추출 + DB 반영`으로 맞춘다.

## User acceptance criteria (2026-03-11)
- Original PDF file retention is **not required**.
- Success means PDFs are decomposed/extracted and stored/reflected into DB outputs.
- Final catalog/report must explicitly include:
  - numeric counts for processed/extracted/decomposed PDFs
  - `coverage_start` (date coverage start, 즉 언제부터의 데이터인지)

## Required final deliverable fields
- `pdf_meta_total` or equivalent candidate population count
- `pdf_extract_ok_total` or equivalent extracted-text count
- `documents_with_text` / DB reflected extracted-doc count
- `coverage_start`
- proof paths for the runtime status JSON, DB sync/index status JSON, and the final catalog/report artifact

## Reporting rule
- `original_present_count`는 진단용 보조지표로만 남긴다.
- 최종 성공/실패 판정은 `DB 반영된 분해추출 결과`와 `numeric counts + coverage_start 명시 여부`로 판단한다.

## Immediate next action
- 재수집/수합 경로에서 카탈로그/보고서 출력부가 위 필드를 빠짐없이 기록하는지 확인하고, 누락 시 해당 집계/출력 경로를 수정한다.

## Proof
- User update: telegram/web instruction at 2026-03-11 08:12 KST
- Related directive: `JB-20260311-PDF-NO-ORIGINAL-CATALOG-RULE`
- Related recovery report: `runtime/tasks/JB-20260311-PDF-EXTRACT-COUNT-RECOVERY.md`
