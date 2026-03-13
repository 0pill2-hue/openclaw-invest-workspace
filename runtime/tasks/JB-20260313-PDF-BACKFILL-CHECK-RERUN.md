# JB-20260313-PDF-BACKFILL-CHECK-RERUN

- ticket: JB-20260313-PDF-BACKFILL-CHECK-RERUN
- status: IN_PROGRESS
- checked_at: 2026-03-13 11:48 KST

## Goal
PDF backfill이 실제로 도는지 확인하고, 미구동이면 재실행한 뒤 총 PDF 대비 확보/추출 개수를 보고한다.

## Next action
- backfill status/runtime/credential 상태 확인
- 미구동이면 bounded rerun 가능 여부 판단 후 실행
- total vs collected/extracted counts 보고

## Check result
- PDF backfill is currently running; a live shell wrapper process for `stage01_telegram_attachment_extract_backfill.py` is active with recovery flags enabled, so no extra rerun was started in this turn.
- observed pid: `60059` (`etime=20:35:36` at check time).
- latest persisted status file is still the previous WARN snapshot, so current live completion counters may advance after this run finishes.

## Current counts from latest status snapshot
- total pdf documents: 63735
- original present/decompose-ready: 15634 (24.53%)
- extract ok: 15513 (24.34%)
- missing original: 48101 (75.47%)
