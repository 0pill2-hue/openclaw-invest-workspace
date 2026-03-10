# JB-20260310-STAGE1-DB-CLEANUP follow-up

- generated_at: 2026-03-10T07:51:33.960183+09:00
- scope: Stage1 비파괴 cleanup 후속 — 우선순위 정리 + dry-run manifest 설계 + Stage1→Stage2 연결 전제 정리
- destructive action: 없음

## 1. Stage1→Stage2 연결 기준
- Stage2 authoritative input: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- 따라서 **live raw tree보다 DB snapshot 최신성**이 우선입니다.
- `raw/qualitative/market/news/url_index/*`, `.DS_Store`, `.mp4` 등은 Stage2 canonical 입력이 아니므로 handoff blocking 우선순위에서 제외할 수 있습니다.

## 2. 우선순위 판정
- P0 `manifest gap`: 143
  - 이유: `pdf_documents` structured index가 현재 raw manifest를 덜 반영함.
- P0 `size mismatch`: 460
  - 이유: Stage2는 DB snapshot을 읽으므로 live raw보다 DB가 늦으면 stale meta를 먹습니다.
- P1 `page_count mismatch`: 72
  - 이유: 파일 유실은 없고 structured page index 품질 이슈입니다.
- P1 `disk-only`: 659
  - Stage2 관련 후보만 추리면 590건, 나머지는 비정상/비canonical/보류 버킷입니다.
- P2 `alias duplicates`: 3
- P2 `pdf original path gap`: 608

## 3. 추천 안전 순서
1. 현재 생성한 dry-run manifest로 범위를 확정한다.
2. Stage1 DB sync + PDF index refresh를 **1회성 단일 패스**로 수행해 `raw_artifacts`와 `pdf_documents`를 current raw에 맞춘다.
3. 같은 audit를 재실행해 `manifest gap / size mismatch / disk-only(stage2 relevant)` 감소 여부를 확인한다.
4. 남는 `page_count mismatch` 72건만 targeted rebuild 대상으로 넘긴다.
5. alias 정리는 Stage1→Stage2 handoff 이후 별도 비파괴 정책으로 진행한다.

## 4. 산출물
- priority matrix: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_priority_matrix.json`
- manifest gap: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_manifest_gap_manifest.json`
- size mismatch: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_size_mismatch_manifest.json`
- disk only: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_disk_only_manifest.json`
- page count mismatch: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_page_count_mismatch_manifest.json`
- alias map dry-run: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_alias_map_dryrun.json`
- pdf original path gap: `runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_pdf_original_path_gap.json`

## 5. 미확인
- live raw와 DB 불일치의 단일 원인(동시 실행/후속 수집/순서 문제)은 미확인
- alias canonical slug 결정은 미확인
