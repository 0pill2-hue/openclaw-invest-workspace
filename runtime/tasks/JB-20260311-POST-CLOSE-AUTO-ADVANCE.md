# JB-20260311-POST-CLOSE-AUTO-ADVANCE

- status: BLOCKED
- started_at: 2026-03-11 20:00 KST
- updated_at: 2026-03-11 20:05 KST

## goal
- 태스크 종료 후 남은 backlog가 있으면 auto-dispatch/orchestrator가 즉시 다음 일을 자동 진행하게 한다.

## current finding
- 아직 목표를 달성하지 못했다.
- `tasks.db` 기준 active backlog가 남아 있는데도 `runtime/tasks/auto_dispatch_status.json`은 아래 상태였다:
  - `status = idle`
  - `error = idle main-orchestrator; idle subagent:long-1; idle subagent:long-2`
- 동시에 task summary는 다음 active work를 보여준다:
  - `WD-CONTEXT-HYGIENE` (IN_PROGRESS)
  - `JB-20260311-SELECTED-ARTICLES-ALT-PATH` (IN_PROGRESS)
  - `JB-20260311-POST-CLOSE-AUTO-ADVANCE` (IN_PROGRESS)
- 즉 `하나 끝난 뒤 남은 backlog로 즉시 이어붙이기`가 아직 시스템적으로 보장되지 않는다.

## close decision
- decision: BLOCKED
- reason: auto-dispatch/orchestrator post-close next-task handoff가 아직 구현/적용되지 않아 active backlog가 남아 있어도 idle 상태로 떨어짐.

## proof
- `runtime/tasks/auto_dispatch_status.json`
- `runtime/tasks/JB-20260311-POST-CLOSE-AUTO-ADVANCE.md`
- `python3 scripts/tasks/db.py summary --top 10 --recent 10`
