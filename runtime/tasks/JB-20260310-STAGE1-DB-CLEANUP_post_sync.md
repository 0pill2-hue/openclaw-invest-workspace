# JB-20260310-STAGE1-DB-CLEANUP post-sync

- scope: Stage1 비파괴 single-pass DB sync + PDF index refresh 후 cleanup proof 재생성 및 비교
- destructive action: 없음
- commands:
  - `python3 invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
  - `python3 runtime/tasks/JB-20260310_STAGE1_DB_CLEANUP_proof.py`

## 1. Sync 실행 결과
- scanned_files: **210,070**
- inserted_files: **1,399**
- updated_files: **1,395**
- unchanged_files: **207,276**
- inactive_files: **0**
- proof_json: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_proof.json`
- proof_commands: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_commands.txt`

## 2. latest pre-sync snapshot vs post-sync
기준 pre-sync snapshot은 `runtime/tasks/JB-20260310-STAGE1-DB-CLEANUP_followup.md` + `runtime/current-task.md` 입니다. 해당 snapshot에 명시되지 않은 baseline 값은 **미기록/미확인**으로 둡니다.

| metric | latest pre-sync | post-sync | delta | note |
|---|---:|---:|---:|---|
| disk_only_count | 659 | 595 | -64 | 감소 |
| size_mismatch_count | 460 | 393 | -67 | 감소 |
| manifest_missing_in_pdf_documents_count | 143 | 27 | -116 | 크게 감소 |
| page_count mismatch (`page_count_vs_rows`) | 72 | 72 | 0 | 변화 없음 |
| runtime_status_sync_id | 미기록/미확인 | `20260309T230505Z` | 미확인 | status/meta skew 잔존 |
| sync_meta_last_sync_id | 미기록/미확인 | `20260309T230000Z` | 미확인 | status/meta skew 잔존 |
| actual_raw_disk_file_count | 미기록/미확인 | 210665 | 미확인 | 현재 disk > runtime_status_scanned_files(210604) |
| actual_raw_db_active_count | 미기록/미확인 | 210070 | 미확인 | Stage1 DB active snapshot |

## 3. 판정
- **Stage1→Stage2 handoff는 이전보다 더 안전해졌습니다.**
- 근거:
  - Stage2 authoritative input인 `stage1_raw_archive.sqlite3` 기준 stale risk 지표가 줄었습니다.
  - `manifest_missing_in_pdf_documents_count`가 **143 → 27**로 크게 줄어 structured PDF index 누락이 많이 완화됐습니다.
  - `size_mismatch_count`가 **460 → 393**, `disk_only_count`가 **659 → 595**로 내려가 raw↔DB 차이가 줄었습니다.
- 남은 리스크:
  - `page_count mismatch` **72건**은 그대로입니다.
  - `runtime_status_sync_id`와 `sync_meta_last_sync_id`가 여전히 다릅니다.
  - 현재 proof에서도 `actual_raw_disk_file_count(210665)`가 recorded scan counts보다 큽니다. live corpus drift 여부와 직접 원인은 **미확인**입니다.

## 4. 다음 권장 액션
1. `page_count mismatch` 72건에 대해 targeted rebuild/audit를 수행한다.
2. `runtime_status_sync_id` / `sync_meta_last_sync_id` skew 원인을 audit한다. 원인 확인 전까지는 **미확인**으로 유지한다.
3. Stage2를 바로 이어야 한다면, live raw가 아니라 `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`를 canonical input으로 사용하되 위 잔여 리스크를 명시하고 진행한다.
