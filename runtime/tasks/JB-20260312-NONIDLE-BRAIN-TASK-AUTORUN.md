# JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN

- ticket: JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN
- status: DONE
- checked_at: 2026-03-12 22:42 KST

## Goal
주인님 지시대로 메인 뇌가 프로그램들을 백그라운드로 돌려둔 뒤 대기만 하지 않도록 하고,
겹치지 않는 backlog를 계속 집어 실행하게 만든다. 또한 돌린 프로그램은 매핑된 task를 자동 갱신해서
메인이 상태를 인지할 수 있게 하거나, 최소한 proof/note/status 흔적을 남기게 한다.

## Design
1. long-running program / watcher / batch runner는 시작 시 task id를 명시적으로 가진다.
2. 각 프로그램 completion/progress event는 task bridge를 통해 taskdb + task md에 반영한다.
3. 매핑된 task가 있으면 `touch/mark-phase/proof append`로 자동 갱신한다.
4. 매핑이 없으면 fallback task를 즉시 등록한다.
5. 메인은 waiting callback 동안 idle로 멈추지 않고, IN_PROGRESS가 아닌 비충돌 backlog를 계속 집는다.
6. 동일 writer/lock 또는 같은 task lineage만 충돌로 보고, 나머지는 병렬 실행 허용한다.

## Applied changes
- `scripts/tasks/db.py`
  - assign/pick 경로가 nonterminal waiting phase(`awaiting_callback`, `subagent_running` 등)인 released task를 다시 집지 않도록 필터링했다.
  - 실제로 worker가 active execution 중인 task만 blocking으로 보고, detached waiting assignment는 별도 wait capacity로 계산해 non-idle 재배정을 허용한다.
- `scripts/tasks/dispatch_tick.py`
  - orchestrator prompt를 background wait contract 기준으로 재작성했다: detached long-running work는 `IN_PROGRESS + waiting phase + release assignee`로 남기고, 완료가 아니면 억지로 BLOCKED/DONE 처리하지 않게 했다.
  - wait 결과 판정에 `backgrounded` 상태를 추가해, waiting phase + released worker slot을 main이 recognisable한 정상 detached 상태로 인식한다.
- `scripts/tasks/record_task_event.py`
  - `--release-assignee` 옵션을 추가해 task-aware start/progress logging과 worker-slot release를 한 번에 처리하도록 확장했다.
- `skills/web-review/scripts/watch_chatgpt_response.py`
  - `--task-id`가 있으면 watcher 시작 시 기본적으로 `awaiting_callback` event를 남기고 assignee/run metadata를 release하는 start-sync를 넣었다(`--skip-task-start-sync`로만 예외).
- `skills/web-review/scripts/sync_watch_event_to_task.py`
  - mapped completion이 기존 task의 waiting phase를 끝내는 경우 `main_resume` phase까지 남겨, 메인이 completion proof를 recognisable한 resume state로 보게 했다.
- 문서/운영 경로
  - `scripts/README.md`, `skills/web-review/SKILL.md`에 detached background wait + task-aware resume contract를 반영했다.

## Focused verification
1. Syntax
- `python3 -m py_compile scripts/tasks/db.py scripts/tasks/dispatch_tick.py scripts/tasks/record_task_event.py skills/web-review/scripts/sync_watch_event_to_task.py skills/web-review/scripts/watch_chatgpt_response.py`

2. Task-pool skip/resume regression
- temp DB proof: `runtime/tmp/nonidle_task_pool_test_results.json`
- result:
  - `awaiting_callback + release` 상태의 `JB-20990101-WAIT`는 assign-pool이 즉시 다시 집지 않고, 대신 `JB-20990101-READY`를 배정했다.
  - 같은 ticket을 `main_resume`으로 바꾼 뒤에는 assign-pool이 다시 `JB-20990101-WAIT`를 집었다.

3. Real watcher-task bridge on this ticket
- start bridge:
  - `python3 scripts/tasks/record_task_event.py --task-id JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN --source nonidle-verification --summary 'background watcher launched for task-aware resume verification' --phase awaiting_callback --proof-path runtime/tmp/nonidle_watch_result.json --release-assignee`
- completion bridge:
  - `python3 skills/web-review/scripts/sync_watch_event_to_task.py --queue-file runtime/tmp/nonidle_watch_queue.json --event-id nonidle-watch-complete-1 --task-id JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN`
- result:
  - watcher sync returned `action=updated_existing`, `resume_phase=main_resume`, and task_event runtime update `phase-updated ... -> main_resume`.

4. Dispatch backgrounded recognition
- verification command:
  - `python3 - <<'PY' ... ticket_dispatch_state('JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN') ... PY`
- result:
  - `('backgrounded', 'status=IN_PROGRESS review_status= source=background_wait phase=awaiting_callback worker_slot=released', 'IN_PROGRESS', '')`

## Proof
- `scripts/tasks/db.py`
- `scripts/tasks/dispatch_tick.py`
- `scripts/tasks/record_task_event.py`
- `skills/web-review/scripts/watch_chatgpt_response.py`
- `skills/web-review/scripts/sync_watch_event_to_task.py`
- `scripts/README.md`
- `skills/web-review/SKILL.md`
- `runtime/tmp/nonidle_task_pool_test_results.json`
- `runtime/tmp/nonidle_watch_queue.json`
- `runtime/tasks/proofs/watch-events/JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN--nonidle-watch-complete-1.md`

## Auto updates

### 2026-03-12 22:40:47 KST | nonidle-verification
- summary: background watcher launched for task-aware resume verification
- phase: awaiting_callback
- detail: test=task-aware-start
- proof:
  - `runtime/tmp/nonidle_watch_result.json`

### 2026-03-12 22:41:04 KST | watcher
<!-- task_event_id: nonidle-watch-complete-1 -->
- summary: watcher synced completion status=complete_json verdict=APPLY
- phase: main_resume
- detail: status=complete_json verdict=APPLY matched_by=explicit_task_id
- detail: url=https://chatgpt.example/nonidle-watch
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/watch-events/JB-20260312-NONIDLE-BRAIN-TASK-AUTORUN--nonidle-watch-complete-1.md`

### 2026-03-12 22:41:23 KST | nonidle-verification
- summary: backgrounded state detection verification
- phase: awaiting_callback
- detail: test=dispatch-backgrounded

### 2026-03-12 22:41:23 KST | nonidle-verification
- summary: restore resume-ready state after backgrounded verification
- phase: main_resume
- detail: test=dispatch-backgrounded-reset

### 2026-03-12 22:41:39 KST | implementation
- summary: auto-dispatch non-idle slice implemented: waiting-state assignee capacity + detached wait orchestrator contract
- phase: main_exec
- detail: db.py now allows same assignee to take another task when existing assignments are nonterminal wait states, while active execution still blocks further picks
- detail: dispatch_tick.py now tells orchestrator to keep detached background work IN_PROGRESS, set waiting phase/resume_due, and release assignee metadata instead of forcing BLOCKED/close
- proof:
  - `scripts/tasks/db.py`
  - `scripts/tasks/dispatch_tick.py`
  - `TASKS.md`
  - `scripts/README.md`
