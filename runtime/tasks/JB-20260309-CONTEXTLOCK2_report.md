# JB-20260309-CONTEXTLOCK2

- change_type: Rule
- verdict: FIXED_AND_VERIFIED

## finding
- 실제 `runtime/context-lock.json`이 비워진 뒤에도 `runtime/tasks/auto_dispatch_status.json`의 `context_lock_active ...` 에러가 stale로 남아 lock이 계속 유지되는 것처럼 보일 수 있다.
- `runtime/current-task.md`가 닫힌 maintenance ticket(`WD-CONTEXT-HYGIENE`)를 계속 가리키는 steady-state 구간에서 `scripts/watchdog/context_hygiene.py`가 이를 다시 이상 상태로 해석해 watchdog maintenance를 재기동할 수 있다.

## action
- `scripts/tasks/dispatch_tick.py`에 stale `context_lock_active` 상태를 다음 tick에서 즉시 비우는 정리 경로를 추가했다.
- `scripts/watchdog/context_hygiene.py`에 활성 실작업이 없고 handoff가 `read_then_resume`인 steady-state라면 닫힌 `WD-*` maintenance snapshot을 false positive로 보지 않도록 예외를 추가했다.

## verification
- `python3 -m py_compile scripts/watchdog/context_hygiene.py scripts/tasks/dispatch_tick.py scripts/watchdog/watchdog_cycle.py scripts/context_policy.py`
- `python3 scripts/watchdog/context_hygiene.py` → `ok: true`, `issues: []`
- `python3 scripts/watchdog/watchdog_cycle.py` → `issues: []`, `maintenance_tasks: {task: [], context: []}`
- dispatch tick stale status simulation: seeded `context_lock_active ...` in `runtime/tasks/auto_dispatch_status.json`, monkeypatched `dispatch_tick.main()` no-lock/no-assignable path 실행 결과 `error: ""`로 즉시 cleared 확인

## proof
- commit: `18fbb1f61` (`Fix stale context lock state after reset`)
- scripts/tasks/dispatch_tick.py
- scripts/watchdog/context_hygiene.py
