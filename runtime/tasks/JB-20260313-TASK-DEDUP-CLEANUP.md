# JB-20260313-TASK-DEDUP-CLEANUP

- ticket: JB-20260313-TASK-DEDUP-CLEANUP
- status: IN_PROGRESS
- title: 중복/구태스크 정리 삭제
- created_by: auto task event bridge
- created_at: 2026-03-13 00:10:24 KST

## Auto updates

### 2026-03-13 00:10:24 KST | cleanup
- summary: Removed obsolete/duplicate backlog tasks that were already superseded.
- phase: main_review
- detail: deleted JB-20260311-POST-CLOSE-AUTO-ADVANCE because its intent is now covered by JB-20260312-BLOCKED-BACKLOG-REQUEUE
- detail: deleted JB-20260311-OVERNIGHT-CLOSEOUT because it was a stale temporal closeout task from 2026-03-11 and no longer a meaningful open backlog item
- proof:
  - `runtime/tasks/JB-20260313-TASK-DEDUP-CLEANUP.md`
