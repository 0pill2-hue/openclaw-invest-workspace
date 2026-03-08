# PROGRAMS

status: CANONICAL (program catalog)
updated_at: 2026-03-08 KST
parent: `docs/operations/OPERATIONS_BOOK.md`

역할: 운영 프로그램의 **짧은 총람**.

원칙:
- 프로그램마다 별도 문서를 만들지 않는다.
- 이 문서는 프로그램의 역할/입력/출력/실패 시 행동만 짧게 적는다.
- 세부 운영 규칙은 각 canonical 문서에서 다루고, 거기서는 이 문서로 링크만 건다.

## 1) SSOT / Ledger
### `scripts/tasks/db.py`
- 역할: TASKS SQLite 원장 등록/상태전이/요약/render SSOT
- 주 입력: CLI 인자, `runtime/tasks/tasks.db`
- 주 출력: task 상태 변경, `TASKS_ACTIVE.md` 렌더
- 실패 시: non-zero 반환, summary에서 hygiene alert 확인
- 관련 문서: `runtime/tasks/README.md`

### `scripts/directives/db.py`
- 역할: DIRECTIVES SQLite 원장 등록/상태전이 SSOT
- 주 입력: CLI 인자, `runtime/directives/directives.db`
- 주 출력: directive 상태 변경
- 실패 시: non-zero 반환
- 관련 문서: `DIRECTIVES.md`

## 2) Context / Resume
### `scripts/context_policy.py`
- 역할: `current-task` + `context-handoff` snapshot, reload bundle, resume-check, handoff-validate, token action 판단
- 주 입력: `runtime/current-task.md`, `runtime/context-handoff.md`, tasks/directives DB
- 주 출력: snapshot 파일, reload/resume-check JSON, handoff validation JSON
- 실패 시: strict resume-check/handoff-validate non-zero
- 관련 문서: `docs/operations/CONTEXT_POLICY.md`, `docs/operations/CONTEXT_LOAD_POLICY.md`, `docs/operations/CONTEXT_HANDOFF_FORMAT.md`

## 3) Watchdog / Hygiene
### `scripts/watchdog/watchdog_validate.py`
- 역할: task stale/deadline/review 이상 검사
- 주 입력: `runtime/tasks/tasks.db`
- 주 출력: 검사 JSON
- 실패 시: `ok=false`, issue 목록 반환

### `scripts/watchdog/watchdog_recover.py`
- 역할: stale/deadline 초과 task를 BLOCKED 전환
- 주 입력: `runtime/tasks/tasks.db`
- 주 출력: 상태 전이 JSON
- 실패 시: non-zero 또는 parse_error

### `scripts/watchdog/context_hygiene.py`
- 역할: context resume-check strict, context-handoff 유효성, blocked_with_proof_no_reason, current-task snapshot↔taskdb 상태 불일치, closed ticket 잔존, session context token threshold(기본 120k 도달/초과 시점) 같은 최소 hygiene 검사와 `finish_current_step_then_reset` handoff 갱신
- 주 입력: `runtime/current-task.md`, `runtime/context-handoff.md`, `runtime/tasks/tasks.db`, `scripts/context_policy.py` 상태 조회, `openclaw status --json`
- 주 출력: hygiene JSON
- 실패 시: `ok=false`, issue 목록 반환

### `scripts/watchdog/watchdog_cycle.py`
- 역할: validate + recover + context hygiene를 묶고, 이상 시 메인 에이전트를 즉시 깨우며 maintenance task(`WD-TASK-HYGIENE`, `WD-CONTEXT-HYGIENE`)를 자동 등록/갱신. context threshold는 fail로만 두지 않고 **synthetic reset trigger**로 승격해, 메인이 현재 step을 끝낸 뒤 reset을 실행하도록 깨운다.
- 주 입력: watchdog 하위 검사 결과
- 주 출력: 종합 JSON, `runtime/tasks/watchdog_notify_state.json`, maintenance task 상태 반영
- 실패 시: `openclaw system event --mode now`로 메인 notify
- 관련 문서: `runtime/tasks/README.md`, `docs/operations/MAIN_BRAIN_GUARD.md`

### `scripts/watchdog/launchd_watchdog.sh`
- 역할: launchd 진입 쉘에서 watchdog cycle 실행
- 주 입력: launchd
- 주 출력: `runtime/tasks/watchdog.launchd.log`

## 4) Brain Guard
### `scripts/heartbeat/local_brain_guard.py`
- 역할: local brain/OpenClaw/Gateway 상태 점검 및 복구
- 주 입력: OpenClaw status, local model 상태
- 주 출력: guard JSON
- 실패 시: 자동 복구 시도 후 alert 반환
- 관련 문서: `docs/operations/MAIN_BRAIN_GUARD.md`, `HEARTBEAT.md`

## 5) 문서 링크 원칙
- `OPERATIONS_BOOK.md`: 이 문서를 총람 링크로 포함
- 개별 운영 문서: 필요한 프로그램만 1~2줄로 언급하고 이 문서 링크
- `scripts/README.md`: 파일 경로와 실행 예시 중심 유지
