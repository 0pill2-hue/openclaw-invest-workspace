# JB-20260313-TASKDB-DURABLE-DETACH-STATE-MACHINE

- ticket: JB-20260313-TASKDB-DURABLE-DETACH-STATE-MACHINE
- status: IN_PROGRESS
- checked_at: 2026-03-13 13:45 KST

## Goal
현재 taskdb 기반 멀티브레인 루틴 불안정을 줄이기 위해 durable detach/callback state machine을 taskdb 런타임에 직접 구현한다.

## Target areas
- `scripts/tasks/db.py`
- `scripts/tasks/record_task_event.py`
- `scripts/tasks/dispatch_tick.py`
- `scripts/watchdog/watchdog_recover.py`
- `scripts/tasks/gate.py`
- task 생성/갱신 시 `resource_keys` 입력/기본값

## Required principles
1. detached wait는 DB primitive로 구현
2. detached task는 callback 없이는 terminal close 금지
3. waiting state에는 resume_due + callback_token 필수
4. assign 시 resource_keys 충돌 금지
5. dispatch_tick은 launch scheduler만 수행
6. watchdog은 invalid waiting/detached state를 이상 상태로 회수

## Next action
- 코드베이스에서 현재 waiting/detach/dispatch/gate/watchdog 경로를 확인
- 리뷰안 기준으로 상태기계/CLI/schema 변경을 구현
- bounded validation과 proof를 남긴다

## Auto updates

### 2026-03-13 13:47:06 KST | owner_review_apply
- summary: Started durable detach/callback runtime implementation from reviewed design via subagent run 798b18bb-be24-4089-b751-ef2a21ea2eb8
- phase: delegated_to_subagent
- detail: targets=db.py,dispatch_tick.py,record_task_event.py,watchdog_recover.py,gate.py

### 2026-03-13 13:56:50 KST | implementation
- summary: Implemented durable detach/callback state machine primitives and launch-only dispatch flow.
- phase: in_progress
- detail: `scripts/tasks/db.py` extended schema with callback/detach/resource columns and added commands `detach`, `callback-heartbeat`, `callback-complete`, `callback-fail`.
- detail: waiting invariants enforced in phase/detach path (`waiting => resume_due + callback_token`, `detached => callback_token`), and detached terminal close is blocked for plain done/block/review-pass.
- detail: assign path now enforces `resource_keys` conflict-free scheduling with conservative default `repo:global` when missing.
- detail: `scripts/tasks/dispatch_tick.py` changed to launch-only scheduler (no close-wait lifecycle); orchestrator contract now requires `db.py detach` + callback-complete/fail/heartbeat.
- detail: `scripts/tasks/record_task_event.py` now rejects waiting/detached phase creation and directs to `db.py detach`.
- detail: `scripts/tasks/gate.py` strict mode now rejects overlapping active `resource_keys` locks.
- detail: `scripts/watchdog/watchdog_recover.py` now detects/recover-blocks waiting/detached metadata violations and stale heartbeat with explicit reason/proof notes.
- proof:
  - `scripts/tasks/db.py`
  - `scripts/tasks/dispatch_tick.py`
  - `scripts/tasks/record_task_event.py`
  - `scripts/tasks/gate.py`
  - `scripts/watchdog/watchdog_recover.py`

### 2026-03-13 13:57:30 KST | validation
- summary: Ran bounded validations for changed paths and detach/callback/watchdog flows.
- detail: `python3 -B - <<'PY' ... ast.parse(...)` on 5 changed scripts => `ast-parse-ok 5`.
- detail: `python3 scripts/tasks/db.py summary --top 3 --recent 3` executed successfully after schema migration.
- detail: `python3 scripts/tasks/db.py detach --help && callback-heartbeat --help && callback-complete --help && callback-fail --help` executed successfully.
- detail: temp-db flow validated:
- detail: `init -> add -> assign-next -> detach -> callback-heartbeat -> done(blocked) -> callback-complete -> callback-complete(idempotent)`.
- detail: observed `detached ticket cannot be terminally closed without callback-complete/fail` and `callback-complete: already completed ...`.
- detail: waiting invariant validated: `mark-phase awaiting_callback` without callback token rejected with `waiting phase requires callback_token (use db.py detach)`.
- detail: gate strict resource lock validated on temp db: overlapping `repo:global` rejected with `gate fail: resource_keys overlap ...`.
- detail: watchdog validated on temp db (`OPENCLAW_TASKS_DB=/tmp/jb_watchdog_test.db`) detecting stale detached heartbeat and moving ticket with reason `watchdog_stale_heartbeat>30m`.
- detail: `record_task_event.py --phase awaiting_callback` now returns `deprecated_waiting_phase_record` and redirects callers to `db.py detach`.
- proof:
  - `/tmp/jb_test_done_blocked.err`
  - `/tmp/jb_test_cb_done.out`
  - `/tmp/jb_test_cb_done_idem.out`
  - `/tmp/jb_test_mark_wait.err`
  - `/tmp/jb_gate_err.txt`
  - `/tmp/jb_watchdog_out.json`
  - `/tmp/jb_record_wait_block.json`

### 2026-03-13 14:02:33 KST | compatibility_hardening
- summary: Fixed watchdog compatibility for pre-migration task DBs where callback/detach columns are still absent.
- detail: `scripts/watchdog/watchdog_recover.py` now builds optional callback/detach column SELECTs dynamically instead of assuming migrated schema.
- detail: when legacy DBs lack the columns needed by `auto_requeue_blocked_tasks`, watchdog now skips that requeue sub-step instead of crashing, while still BLOCKING invalid waiting rows with explicit proof.
- detail: old-schema smoke test (`OPENCLAW_TASKS_DB=/tmp/jb_watchdog_oldschema.db python3 scripts/watchdog/watchdog_recover.py`) successfully returned JSON and recovered `watchdog_waiting_missing_resume_due` instead of failing on `no such column: callback_token`.
- proof:
  - `/tmp/jb_watchdog_oldschema.db`
