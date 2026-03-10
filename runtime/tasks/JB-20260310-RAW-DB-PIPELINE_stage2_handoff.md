# JB-20260310-RAW-DB-PIPELINE stage2 handoff readiness

- generated_at: 2026-03-10 09:55 KST
- scope: Stage1 잔여 blocker 재확인 후 Stage2 authoritative handoff 가능 여부 정리
- destructive action: 없음

## 1. current evidence
- `sync_meta.last_sync_id`: `20260310T004644Z`
- `sync_meta.last_sync_finished_at`: `2026-03-10T00:46:44.473365+00:00`
- `sync_meta.last_sync_summary.scanned_files`: `220528`
- `sync_meta.last_pdf_index_summary.finished_at`: `2026-03-10T00:50:30.510534+00:00`
- 경량 SQL/manifest audit 결과 `pdf_documents.page_count != pdf_pages row_count` 문서 수: **0건**

## 2. status skew 정리
- `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`에 `--status-only` 모드를 추가했다.
- 이 모드는 raw 재스캔 없이 DB `sync_meta.last_sync_summary` + `last_pdf_index_summary`를 읽어 `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`만 재생성한다.
- 실제 실행 결과 `raw_db_sync_status.json`은 `sync_id=20260310T004644Z`, `status_mode=status_only_from_sync_meta`로 갱신됐다.

## 3. page-count handoff contract
- Stage1/Stage2 문서에 아래 계약을 명시했다.
  - `pdf_documents.page_count` / manifest `page_count` = 원본 전체 페이지 수
  - `pdf_pages` row count / manifest `pages[]` 길이 = cap 적용 후 실제 indexed/stored page 수
  - `max_pages_applied`가 있으면 두 값이 달라도 손상으로 단정하지 않음

## 4. 판정
- 기존 blocker였던 `raw_db_sync_status/sync_meta skew`는 **status-only refresh로 해소**했다.
- 기존 blocker였던 `page_count mismatch 72건`은 현재 DB state 기준 **0건**으로 정리됐다.
- 따라서 현재 상태는 **Stage2 authoritative rebuild/handoff 진행 가능**으로 본다.

## 5. next
1. `python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild`
2. 이어서 `python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`
3. 결과 report/QC PASS 확인 후 task 상태를 정리한다.

## 6. proof
- `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- `docs/invest/stage1/stage01_data_collection.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
