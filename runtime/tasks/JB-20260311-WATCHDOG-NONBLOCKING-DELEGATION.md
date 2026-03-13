# JB-20260311-WATCHDOG-NONBLOCKING-DELEGATION

- status: READY_FOR_REVIEW
- recommendation: DONE
- updated_at: 2026-03-11 17:24 KST

## files changed
- `scripts/lib/task_runtime.py`
- `scripts/tasks/db.py`
- `scripts/context_policy.py`
- `scripts/tasks/dispatch_tick.py`
- `scripts/watchdog/watchdog_recover.py`
- `scripts/watchdog/watchdog_validate.py`
- `scripts/watchdog/context_hygiene.py`
- `scripts/watchdog/watchdog_cycle.py`
- `docs/operations/runtime/PROGRAMS.md`
- `docs/operations/runtime/MAIN_BRAIN_GUARD.md`
- `scripts/README.md`

## why it was blocking before
- watchdog는 `IN_PROGRESS` task를 phase와 무관하게 오래됐다는 이유만으로 `BLOCKED`로 돌릴 수 있었고, `delegated_to_subagent` 같은 실제 wait phase를 인식하지 못했다.
- context hygiene / watchdog cycle / auto-dispatch는 `subagent_running`, `awaiting_callback` 정도만 legacy 예외로 보아서 `delegated_to_subagent` 류 상태를 닫힌 task처럼 취급했다.
- 특히 auto-dispatch는 `BLOCKED + waiting phase`를 nonterminal wait로 보지 못해 `spawned but not closed`를 hard error로 올릴 수 있었다.

## what changed
1. `scripts/lib/task_runtime.py`에 nonterminal waiting phase 판정 헬퍼를 추가했다.
   - `delegated_to_subagent`, `subagent_running`, `awaiting_callback`, `awaiting_result`, `waiting_child_completion`, `long_running_execution` 등과 subagent/delegation 계열 alias를 공통 판정한다.
2. watchdog validate/recover를 waiting-aware로 바꿨다.
   - nonterminal waiting phase는 age만으로 stale BLOCKED 전환하지 않는다.
   - `resume_due`가 있는 waiting phase만 deadline 초과 시 true blocker로 승격한다.
3. context hygiene / watchdog cycle / auto-dispatch를 같은 waiting 판정에 맞췄다.
   - legacy `BLOCKED + waiting phase`도 ongoing work로 취급한다.
   - current-task ↔ taskdb mismatch/closed-task escalation에서 waiting state는 false positive로 올리지 않는다.
   - auto-dispatch는 `BLOCKED + waiting phase`를 hard-close 실패가 아니라 still waiting으로 본다.
4. taskdb phase semantics를 정리했다.
   - `mark-phase`로 nonterminal waiting phase를 찍으면 `TODO`/`BLOCKED` task를 자동으로 `IN_PROGRESS/active`로 되돌린다.
   - runtime_state 표시에 `wait_state=nonterminal`를 붙여 snapshot/current-task에서 blocked vs waiting을 구분하기 쉽게 했다.
   - legacy `BLOCKED + waiting phase`는 `closed_by`를 비워 closed 느낌을 줄인다.
5. 관련 운영 문서를 waiting-vs-blocked 계약에 맞게 갱신했다.

## quick verification
- `python3 -m py_compile scripts/lib/task_runtime.py scripts/tasks/db.py scripts/context_policy.py scripts/watchdog/watchdog_recover.py scripts/watchdog/watchdog_validate.py scripts/watchdog/context_hygiene.py scripts/watchdog/watchdog_cycle.py scripts/tasks/dispatch_tick.py`
- temp DB 시나리오 검증:
  - `IN_PROGRESS + phase=delegated_to_subagent + 오래된 last_activity_at + resume_due 없음` → validate stale issue 없음 / recover 미전환
  - `IN_PROGRESS + phase=delegated_to_subagent + expired resume_due` → validate deadline issue / recover가 `watchdog_delegated_to_subagent_deadline_expired`로 BLOCKED 전환
  - `BLOCKED` ticket에 `mark-phase --phase delegated_to_subagent` 실행 → `IN_PROGRESS/active`로 자동 복귀 확인
  - `dispatch_tick.ticket_closure_state()` probe에서 `BLOCKED + phase=delegated_to_subagent`를 closed가 아닌 ongoing wait로 판정 확인

## close recommendation
- DONE
- 이유: false blocking의 핵심 경로(watchdog stale 전환, context mismatch escalation, auto-dispatch close 판정)를 모두 waiting-aware로 정렬했고, 신규 phase 계약/문서도 함께 맞췄다.
