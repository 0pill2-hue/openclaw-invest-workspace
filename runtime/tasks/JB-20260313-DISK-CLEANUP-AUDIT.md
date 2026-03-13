# JB-20260313-DISK-CLEANUP-AUDIT

- ticket: JB-20260313-DISK-CLEANUP-AUDIT
- status: DONE
- checked_at: 2026-03-13 16:18 KST

## Goal
PDF backfill 실패 원인과 연동된 디스크 압박 상황에서 삭제 우선순위 후보를 찾는다.

## Findings
- filesystem: `/System/Volumes/Data` 사용률 98%, available 9.6GiB
- 가장 먼저 지워도 안전한 local/generated 후보:
  1. `runtime/tasks/proofs/` ≈ 954MB
     - 대형 파일 상위:
       - `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_claim_cards.jsonl` ≈ 687MB
       - `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d.jsonl` ≈ 153MB
       - `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d_strict.jsonl` ≈ 153MB
  2. `runtime/browser-profiles/` ≈ 81MB
  3. `runtime/backups/` ≈ 12MB
  4. `runtime/tmp*` / `runtime/tmp/` 합산 수십 MB
- 큰 용량이지만 운영 데이터라 삭제 주의가 필요한 후보:
  1. `invest/stages/stage1/outputs/raw` ≈ 127447454306 bytes (~118.7GiB)
  2. `invest/stages/stage1/outputs/db` ≈ 55304053464 bytes (~51.5GiB)
  3. `invest/stages/stage1/outputs/archive` ≈ 159743486 bytes (~152MB)
  4. `invest/stages/stage1/outputs/logs` ≈ 36010286 bytes (~34MB)
  5. `invest/stages/stage1/outputs/runtime` ≈ 21461250 bytes (~20MB)

## Judgment
- 즉시 공간 확보 목적의 **1차 삭제 후보는 runtime local-only/generated 영역**이다.
- 특히 `runtime/tasks/proofs`의 Stage3 대형 proof 3개만 정리해도 약 1GB 회수 가능하다.
- 근본적으로는 `stage1/outputs/raw`와 `stage1/outputs/db`가 압도적으로 크지만, 이는 운영/증빙 데이터일 가능성이 높아 삭제 전 세부 정책 확정이 필요하다.

## Next
- 주인님 승인 시 1차로 `runtime/tasks/proofs`, `runtime/browser-profiles`, `runtime/tmp`, `runtime/backups` 순서로 안전 삭제 진행.
- 그 다음 `stage1/outputs/raw` 와 `stage1/outputs/db` 는 보존정책/보관주기 기준을 먼저 확인한 뒤 축소 또는 아카이브 전략으로 접근.
