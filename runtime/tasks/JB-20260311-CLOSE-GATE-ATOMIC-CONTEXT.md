# JB-20260311-CLOSE-GATE-ATOMIC-CONTEXT

## 결과
- close path(`done`/`block`/`review-pass`)에 **hard gate + atomic handoff**를 넣었습니다.
- 닫히는 ticket이 `runtime/current-task.md` 또는 `runtime/context-handoff.md`에 걸려 있으면, close 전에 `WD-CONTEXT-HYGIENE`로 runtime 포인터를 먼저 넘기고 같은 트랜잭션 안에서 상태 전이를 commit합니다.
- `WD-CONTEXT-HYGIENE` 자체를 아직 `current-task`가 가리키는 상태에서 닫으려 하면 **hard fail**합니다.
- watchdog `context_hygiene.py`는 남아 있던 closed-pointer mismatch를 안전할 때 `WD-CONTEXT-HYGIENE` 또는 current-task 기준 handoff로 **self-heal**하도록 맞췄습니다.

## 변경 파일
- `scripts/tasks/db.py`
  - close 상태 계산을 `build_status_update_payload/apply_status_update`로 분리
  - `close_status_with_context_guard()` 추가
  - `done`/`block`/`review-pass`가 close guard 경로를 타도록 변경
  - `WD-CONTEXT-HYGIENE` upsert + runtime current-task/context-handoff atomic rewrite + rollback 복구 추가
- `scripts/context_policy.py`
  - runtime card write를 temp-file replace 기반으로 atomic write
  - `write_snapshot_pair()` / `write_context_handoff_from_current()` / `inspect_runtime_ticket_references()` 추가
  - close guard/self-heal이 같은 writer를 공유하도록 정리
- `scripts/watchdog/context_hygiene.py`
  - 닫힌 non-maintenance ticket 잔여 포인터를 감지하면 safe case에서 self-heal
  - self-heal 후 resume/handoff validation을 다시 같은 흐름으로 통과하게 정렬
- `scripts/README.md`
- `docs/operations/runtime/PROGRAMS.md`
- `docs/operations/context/CONTEXT_LOAD_POLICY.md`

## 핵심 보장 경로
1. `python3 scripts/tasks/db.py done|block|review-pass ...`
2. `scripts/tasks/db.py:close_status_with_context_guard()`
3. runtime 포인터가 닫히는 ticket을 가리키면:
   - `ensure_context_hygiene_ticket()`로 `WD-CONTEXT-HYGIENE` 활성화/갱신
   - `scripts/context_policy.py:write_snapshot_pair()` 또는 `write_context_handoff_from_current()`로 runtime card 선반영
   - 그 다음 `apply_status_update()`로 원 ticket 상태 전이
   - 예외 시 DB rollback + runtime card restore
4. 결과적으로 `current-task/context-handoff`가 닫힌 ticket을 계속 가리킨 채 close commit되는 경로를 차단

## 검증
### A. close guard atomic handoff 검증
실행:
- temp env(`OPENCLAW_TASKS_DB`, `OPENCLAW_CURRENT_TASK_PATH`, `OPENCLAW_CONTEXT_HANDOFF_PATH`) 구성
- `JB-20260311-900`을 `IN_PROGRESS`로 만들고 snapshot 작성
- `python3 scripts/tasks/db.py done --id JB-20260311-900 --proof "close-proof"`

확인:
- source ticket: `JB-20260311-900 -> DONE/done`
- maintenance ticket: `WD-CONTEXT-HYGIENE -> IN_PROGRESS/active`
- `runtime/current-task.md`의 `ticket_id: WD-CONTEXT-HYGIENE`
- `runtime/context-handoff.md`의 `source_ticket_id: WD-CONTEXT-HYGIENE`
- 즉, close 성공 직후에도 닫힌 ticket이 runtime 포인터에 남지 않음

### B. maintenance hard gate 검증
같은 temp env에서:
- `python3 scripts/tasks/db.py done --id WD-CONTEXT-HYGIENE --proof "should-fail"`

결과:
- non-zero 종료
- stderr: `close gate blocked: runtime/current-task.md still points to WD-CONTEXT-HYGIENE; snapshot the successor task before closing it`

### C. watchdog self-heal 검증
실행:
- temp env에서 `JB-20260311-901`을 `DONE`으로 두고, `current-task/context-handoff`를 일부러 그 ticket으로 snapshot
- `WD-CONTEXT-HYGIENE`는 `IN_PROGRESS`로 준비
- `python3 scripts/watchdog/context_hygiene.py`

결과:
- JSON `ok: true`
- `detail.self_healed_closed_ticket_reference = {"mode": "maintenance", "ticket_id": "JB-20260311-901"}`
- runtime cards가 `WD-CONTEXT-HYGIENE`로 이동

## proof path
- 구현: `scripts/tasks/db.py`, `scripts/context_policy.py`, `scripts/watchdog/context_hygiene.py`
- 계약/문서: `scripts/README.md`, `docs/operations/runtime/PROGRAMS.md`, `docs/operations/context/CONTEXT_LOAD_POLICY.md`
- 작업 보고: `runtime/tasks/JB-20260311-CLOSE-GATE-ATOMIC-CONTEXT.md`

## 리스크/메모
- SQLite + 파일 2개를 완전한 단일 OS-level transaction으로 묶을 수는 없어서, close guard는 **same command + DB transaction + temp-file replace + 실패 시 runtime card restore** 방식으로 안전성을 최대화했습니다.
- `WD-CONTEXT-HYGIENE`를 아직 current-task가 가리키는 동안 닫는 것은 의도적으로 막았습니다. 이 경우 먼저 다음 실제 task로 snapshot 전환해야 합니다.

## close recommendation
- DONE
