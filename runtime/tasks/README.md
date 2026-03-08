# runtime/tasks README

## 기본 경로
- DB: `runtime/tasks/tasks.db`
- 렌더 대상: `TASKS_ACTIVE.md`
- auto-dispatch 상태: `runtime/tasks/auto_dispatch_status.json`
- auto-dispatch 로그: `runtime/tasks/auto_dispatch.launchd.log`, `runtime/tasks/auto_dispatch_debug.log`
- watchdog 로그: `runtime/tasks/watchdog.launchd.log`
- 프로그램 총람: `docs/operations/PROGRAMS.md`

## 초기 1회 절차
1. `python3 scripts/tasks/db.py init`
2. `python3 scripts/tasks/db.py migrate-md`
3. `python3 scripts/tasks/db.py render-md`

## 운영 규칙
- task는 1개만 active일 필요가 없다. 메인 executor task와 서브 callback 대기 task가 동시에 active일 수 있다.
- 메인이 서브에이전트에 위임해도 메인은 대기 전용으로 멈추지 않는다. 다른 수행 가능한 task를 계속 진행한다.
- **메인 직접 실행분과 서브 deliverable은 섞어 적지 말고 분리 등록**한다. 메인이 orchestration만 맡는 parent task와, 서브가 독립 산출물을 만드는 child task를 나누고 서로 `note:`로 참조를 남긴다.
- task 상태 표현은 `status/bucket` + `task_state(assignee/phase/review/resume_due)` 조합으로 본다.
- 단일 task 안에서 현재 executor/단계를 `phase:`로 기록한다. 권장값: `main_exec`, `subagent_running`, `awaiting_callback`, `main_review`.
- 서브를 붙인 task는 callback deadline(`resume_due`)을 반드시 남긴다.
- `DONE` 전이 시 stale blocker/pending review는 자동 정리하고, `BLOCKED`는 callback/runtime 대기 metadata만 남기지 않도록 정리한다.
- deadline을 넘기면 watchdog이 무한 대기하지 않고 `BLOCKED`로 전환한다.
- task의 제목/범위/완료조건이 바뀌면 새 task를 만들지 말고 같은 id에 `python3 scripts/tasks/db.py add --id ... --title ... --scope ...`로 즉시 갱신한다.
- 작업 착수 첫 보고에는 canonical `ticket_id`를 함께 알린다. 여러 task가 걸려 있어도 현재 주 실행 ticket 1개를 먼저 명시한다.
- watchdog은 `scripts/watchdog/watchdog_cycle.py`가 canonical 진입점이다.
- context hygiene는 기본적으로 `openclaw status --json` 기준 session `totalTokens >= 120000`이면 이상으로 본다(`WATCHDOG_CONTEXT_TOKEN_THRESHOLD`로 조정 가능).
- watchdog은 **120k 도달/초과 시점에만** `runtime/context-handoff.md` 검증 후 clean reset/cutover를 요구한다. 그 이전 구간에는 별도 선제 경고를 두지 않는다.
- `python3 scripts/context_policy.py snapshot ...`은 `runtime/current-task.md`와 `runtime/context-handoff.md`를 같이 갱신한다.
- watchdog이 context threshold/current-task mismatch/handoff invalid를 감지하면 `openclaw system event --mode now`로 메인 에이전트를 즉시 깨운다.
- background watchdog은 maintenance task를 자동 등록/갱신한다: task 계열은 `WD-TASK-HYGIENE`, context 계열은 `WD-CONTEXT-HYGIENE`.
- `WD-CONTEXT-HYGIENE` note에는 최소한 `active_ticket_id`, `business_goal`, `business_next_action`, `handoff_file`, `handoff_valid`, `required_action`이 구조화돼야 한다.
- `scripts/tasks/gate.py`는 `WD-*` maintenance task가 active일 때 다른 ticket 실행을 거부한다. maintenance 선점이 기본이다.
- `scripts/heartbeat/*` guard는 즉시 경고/자동복구가 본역할이므로, 기본은 task 발행보다 alert/recovery 우선으로 둔다.
- 메인은 watchdog alert를 받으면 같은 턴에서 handoff/current-task/proof 확인, 사용자 보고, 후속 task 정리까지 처리한다.

## 운영 예시
- 요약: `python3 scripts/tasks/db.py summary --top 5 --recent 5`
- 조회: `python3 scripts/tasks/db.py list --status IN_PROGRESS`
- 시작: `python3 scripts/tasks/db.py start --id JB-20260305-037`
- 완료: `python3 scripts/tasks/db.py done --id JB-20260305-037 --proof "..."`
- 차단: `python3 scripts/tasks/db.py block --id JB-20260305-037 --reason "..."`
- 잘못 붙은 assignee 해제: `python3 scripts/tasks/db.py release --id JB-20260305-037`
- 서브 실행/콜백 대기 표시: `python3 scripts/tasks/db.py mark-phase --id JB-20260305-037 --phase subagent_running --child-session <session> --resume-due "2026-03-07 21:00:00"`
- 중복/레거시 task 삭제: `python3 scripts/tasks/db.py remove --id JB-20260305-037`
- fail-close 게이트: `python3 scripts/tasks/gate.py --ticket JB-20260305-037`
