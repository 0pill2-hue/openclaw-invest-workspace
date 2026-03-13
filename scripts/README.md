# scripts/ 구조 인덱스

역할: **실제 실행 진입점과 대표 호출 예시만 모은 얇은 인덱스**.

## 디렉터리
- `scripts/lib/` — 공통 유틸
- `scripts/tasks/` — taskdb / gate / auto-dispatch
- `scripts/watchdog/` — stale/context hygiene/notify cycle
- `scripts/directives/` — directives db / gate
- `scripts/heartbeat/` — local brain guard

## 대표 호출
- TASKS summary: `python3 scripts/tasks/db.py summary --top 5 --recent 5`
- TASK gate: `python3 scripts/tasks/gate.py --ticket <ID>`
- TASK auto-dispatch: `python3 scripts/tasks/dispatch_tick.py`
- TASK phase: `python3 scripts/tasks/db.py mark-phase --id <ID> --phase <phase> --resume-due "YYYY-MM-DD HH:MM:SS"`
- TASK assignee 해제: `python3 scripts/tasks/db.py release --id <ID>`
- TASK blocked 재큐잉: `python3 scripts/tasks/db.py requeue-blocked`
- TASK event 기록: `python3 scripts/tasks/record_task_event.py --task-id <ID> --source <src> --summary <text> [--phase <phase>] [--release-assignee]`
- context snapshot: `python3 scripts/context_policy.py snapshot ...`
- context resume-check: `python3 scripts/context_policy.py resume-check --strict`
- watchdog cycle: `python3 scripts/watchdog/watchdog_cycle.py`
- heartbeat guard: `python3 scripts/heartbeat/local_brain_guard.py`

## 계약 메모
- task/phase/rule SSOT는 `TASKS.md`
- 프로그램 역할 총람은 `docs/operations/runtime/PROGRAMS.md`
- detached wait 설명/다이어그램은 `docs/operations/orchestration/README.md`
- 이 문서는 **호출 예시만** 유지한다.
