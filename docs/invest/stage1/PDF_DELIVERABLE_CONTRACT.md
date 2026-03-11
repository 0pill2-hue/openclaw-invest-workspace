# Stage1 PDF Deliverable Contract

## Scope
이 문서는 **Stage1 Telegram PDF 최종 산출물**의 성공 기준과 카탈로그/보고 필드 계약을 고정한다.
핵심 목적은 `원본 PDF 파일이 몇 개 남아 있는가`가 아니라, **분해/추출 결과가 DB와 카탈로그에 얼마나 반영됐는가**를 일관되게 보고하는 데 있다.

## Success criteria
- Original PDF file retention is **not required**.
- Durable extracted text는 가능하면 single-file page-marked form(`[PAGE 001]` …)을 사용한다.
- 성공 판정은 **DB reflected decomposition/extraction** 기준으로 한다.
- `original_present_count`, physical `pdf_files` count는 **진단용 보조지표**일 뿐 최종 성공 게이트가 아니다.
- runtime `status=OK|WARN`는 backfill/collector health를 뜻하며, 최종 deliverable success와 동일 의미가 아니다.

## Canonical artifacts
1. Runtime status JSON
   - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
2. Coverage catalog
   - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
3. Structured DB summary embedded in runtime status
   - `pdf_db_index_summary` (`documents_with_text`, `earliest_message_date`, `latest_message_date`)

## Metadata contract for page markers
- Per-PDF meta (`msg_<id>__meta.json`) should expose:
  - `pdf_page_marked`
  - `pdf_page_marker_format` (`[PAGE NNN]`)
  - `pdf_page_marker_count`
  - `pdf_page_mapping_status`
  - `extract_format`
- bounded backfill rule:
  - original bytes available → regenerate page-marked extracted text
  - original missing but manifest/page text available → rebuild from manifest page text only
  - neither available → keep plain text if present, mark `pdf_page_marked=false` and `pdf_page_mapping_status=missing_*`, do not fail the whole collector chain

## Required final deliverable fields
최종 보고서/카탈로그 stanz​​a는 아래 필드를 **명시적으로** 가져야 한다.

| Final field | Canonical source | Notes |
| --- | --- | --- |
| `pdf_meta_total` | `telegram_attachment_extract_backfill_status.json -> pdf_meta_total` (fallback: `pdf_db_documents_total`) | logical PDF document count |
| `pdf_extract_ok_total` | `telegram_attachment_extract_backfill_status.json -> pdf_extract_ok_total` (fallback: `pdf_db_extract_ok_total`) | extracted-text success count |
| `documents_with_text` | `telegram_attachment_extract_backfill_status.json -> pdf_db_index_summary.documents_with_text` (fallback: `pdf_db_text_ready_total`) | DB reflected text-ready document count |
| `page_marked_total` | `telegram_attachment_extract_backfill_status.json -> pdf_page_marked_total` (fallback: `pdf_db_page_marked_total`) | page-marked durable extracted text count |
| `page_mapping_missing_total` | `telegram_attachment_extract_backfill_status.json -> pdf_page_mapping_missing_total` (fallback: `pdf_db_page_mapping_missing_total`) | explicit missing-page-mapping count that stayed plain-text-only |
| `coverage_start` | ISO date derived from `pdf_db_index_summary.earliest_message_date`; fallback: `source_coverage_index.sources.telegram.scope.attachment_artifacts.earliest_message_date` | **PDF-specific coverage start only** |
| `proof_paths` | paths to runtime status JSON, coverage catalog JSON, and final report artifact | required for auditability |

## Coverage-start rule
- `coverage_start`는 **generic telegram markdown corpus**가 아니라 **PDF deliverable scope** 기준이어야 한다.
- 따라서 `source_coverage_index.sources.telegram.earliest_date`를 쓰지 않는다.
- canonical source는 아래 우선순위를 따른다.
  1. `telegram_attachment_extract_backfill_status.json -> pdf_db_index_summary.earliest_message_date`
  2. `source_coverage_index.sources.telegram.scope.attachment_artifacts.earliest_message_date`
- 출력 형식은 `YYYY-MM-DD` ISO date로 정규화한다.

## Why physical PDF file count is not a success gate
현재 운영 계약에서는 decomposed 완료 후 original PDF를 삭제할 수 있다.
따라서 physical `.pdf` file count는 logical document count보다 훨씬 작을 수 있으며, 이 차이만으로 실패로 판정하면 안 된다.
page marker backfill도 동일하게 bounded 하다: original 또는 existing page artifact가 없으면 plain-text-only 상태를 metadata로 남기고 종료한다.

## Audited 2026-03-11 snapshot
읽기 전용 감사 기준 current observed values:
- `pdf_meta_total = 63735`
- `pdf_extract_ok_total = 59672`
- `documents_with_text = 608`
- `pdf_decompose_ok_total = 608`
- `pdf_pages_total = 9632`
- `coverage_start = 2019-10-29`
- `coverage_end = 2026-03-09`
- generic telegram `earliest_date = 20191025` (**do not use for PDF coverage_start**)
- physical `pdf_files = 87` (**diagnostic only**)

## Read-only audit helper
- `scripts/tasks/pdf_deliverable_contract_audit.py`
- purpose: validate that current artifacts expose the contract fields without touching DB writers
