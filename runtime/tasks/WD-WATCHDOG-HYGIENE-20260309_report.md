# WD-WATCHDOG-HYGIENE-20260309 proof

- checked_at: 2026-03-09 21:50 KST
- issue:
  - `WD-CONTEXT-HYGIENE`: `runtime/current-task.md` / `runtime/context-handoff.md`가 `directive_ids=미정` placeholder 상태라 strict resume-check가 실패.
  - `WD-TASK-HYGIENE`: `JB-20260309-STAGE1PDF100MON`가 watchdog stale rule로 BLOCKED 되었지만, 실제 legacy backfill 프로세스가 살아 있어 status mismatch 발생.
- actions:
  1. `python3 scripts/tasks/db.py start --id JB-20260309-STAGE1PDF100MON`
  2. `python3 scripts/context_policy.py snapshot --ticket-id JB-20260309-STAGE1PDF100MON --directive-ids JB-20260309-STAGE1PDF100MON ...`
  3. main proof report에 watchdog recovery update 추가
- evidence:
  - `runtime/tasks/JB-20260309-STAGE1PDF100MON_report.md`
  - `runtime/current-task.md`
  - `runtime/context-handoff.md`
  - active backfill pids observed at 21:49 KST: `91602`, `91603`
- expected result:
  - main ticket is `IN_PROGRESS`
  - current-task / handoff no longer use placeholder directive ids
  - watchdog hygiene maintenance tickets can be closed
