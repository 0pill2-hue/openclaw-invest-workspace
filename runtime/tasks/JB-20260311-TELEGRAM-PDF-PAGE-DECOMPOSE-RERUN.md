# JB-20260311-TELEGRAM-PDF-PAGE-DECOMPOSE-RERUN

- status: BLOCKED
- started_at: 2026-03-11 16:37 KST
- closed_at: 2026-03-11 16:47 KST

## goal
- Telegram PDF 페이지 분해가 608건에서 멈춘 원인을 확인하고, missing_original recovery를 켜서 페이지 분해를 재가동한다.

## result
- 원인 확인은 완료했다.
- recovery-enabled backfill 재가동도 완료했다.
- 하지만 실제 recovery download/분해 증가는 발생하지 않아 현재 티켓은 BLOCKED로 닫는다.

## evidence summary
- current DB counts:
  - `pdf_documents = 63735`
  - `pdf_extract_ok_total = 59672`
  - `pdf_decompose_ok_total = 608`
  - `pdf_pages_total = 9632`
  - `ok_page0_total = 59065`
- latest backfill status:
  - `telegram_recovery_candidates_selected = 63129`
  - `telegram_recovery_attempted = 0`
  - `telegram_recovery_ok = 0`
  - `telegram_recovery_skipped = 63129`
  - `reason_counts.telegram_recovery_missing_credentials = 1`
  - `pdf_db_reindex_ok = 0`
  - `status = WARN`

## blocker
1. Telegram recovery는 후보 63129건을 잡았지만, 실제 dialog scan/attempt가 0건이었다.
2. status reason 기준 direct blocker는 `telegram_recovery_missing_credentials`다.
3. 그래서 original PDF 복구가 일어나지 않았고, 분해 완료 수치도 `608`에서 증가하지 않았다.
4. 같은 run에서 `pdf_db_index_error:OperationalError`도 기록되어 후속 reindex 안정성 점검이 필요하다.

## close decision
- decision: BLOCKED
- reason: Telegram recovery credentials 부재로 original PDF 재다운로드가 전부 skip되어 page decomposition이 전혀 진행되지 않음.

## proof paths
- `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- `runtime/tasks/JB-20260311-TELEGRAM-PDF-PAGE-DECOMPOSE-RERUN.md`

## next required action
- Stage1 Telegram recovery에 필요한 credentials/session을 확인한 뒤 backfill을 다시 실행한다.
- 재실행 후 `pdf_decompose_ok_total`과 `pdf_pages_total` 증가 여부를 기준으로 재판정한다.
