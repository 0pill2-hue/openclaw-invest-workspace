# WD-CONTEXT-UNLOCK

- change_type: Rule
- verdict: FIXED_AND_VERIFIED

## finding
- stale context lock 해제용 `unlock/언락` 힌트가 있어도 watchdog이 `context_tokens_high`를 먼저 보면서 reset-required를 유지할 수 있었다.
- `scripts/watchdog/context_hygiene.py`는 threshold 초과 시 handoff를 무조건 `finish_current_step_then_reset`로 다시 써서 explicit unlock notes를 덮어쓸 수 있었다.

## action
- `scripts/watchdog/watchdog_cycle.py`에서 `handoff_requests_unlock()`를 `context_tokens_high`보다 먼저 평가하도록 순서를 변경했다.
- `scripts/watchdog/context_hygiene.py`에서 현재 handoff에 `unlock/언락` 요청이 있으면 threshold 초과 상황에서도 handoff refresh를 건너뛰도록 보강했다.
- `docs/operations/context/CONTEXT_HANDOFF_FORMAT.md`를 explicit unlock 우선 규칙에 맞게 갱신했다.

## verification
- `python3 -m py_compile scripts/watchdog/context_hygiene.py scripts/watchdog/watchdog_cycle.py scripts/context_policy.py`
- synthetic check: `context_requires_reset({'detail': {'context_tokens_high': '121657>=120000', 'context_handoff_notes': 'unlock_requested_by_user'}}) == False`
- `python3 scripts/context_policy.py handoff-from-current --handoff-reason work_update --trigger work_update --required-action read_then_resume --notes "change_type=Rule; unlock_requested_by_user; unlock"`
- `python3 scripts/watchdog/context_hygiene.py`
- `python3 scripts/watchdog/watchdog_cycle.py`
- result: `runtime/context-lock.json` cleared

## proof
- scripts/watchdog/context_hygiene.py
- scripts/watchdog/watchdog_cycle.py
- docs/operations/context/CONTEXT_HANDOFF_FORMAT.md
- runtime/tasks/proofs/WD-CONTEXT-UNLOCK.txt
