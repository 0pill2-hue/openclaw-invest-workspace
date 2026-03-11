# scripts/ 구조 인덱스

## 목적
정리된 운영 스크립트의 실제 진입점을 한 곳에 모읍니다.

## 디렉터리
- `scripts/lib/`
  - `runtime_env.py`: 공통 경로/환경 유틸
  - `common_env.sh`: 공통 쉘 환경 변수
- `scripts/tasks/`
  - `db.py`: TASKS SQLite CLI
  - `gate.py`: TASK fail-close gate (`clean_reset`/`hard_reset`급 context lock만 신규 진행 차단, `finish_current_step_then_reset`은 advisory)
  - `dispatch_tick.py`: 다음 task 자동 배정/기동 tick (soft advisory는 계속 진행, hard lock만 idle)
  - `launchd_dispatch.sh`: task auto-dispatch용 launchd 진입 쉘
- `scripts/watchdog/`
  - `watchdog_validate.py`: TASK ledger 정합성 검사
  - `watchdog_recover.py`: stale task 자동 BLOCKED 전환 (단, delegated/awaiting/long-running nonterminal waiting phase는 age만으로 막지 않고 `resume_due` 초과 시에만 승격)
  - `context_hygiene.py`: current-task/context-handoff/resume-check/blocked-proof hygiene 검사 + 120k threshold에서 `finish_current_step_then_reset` handoff 갱신
  - `watchdog_cycle.py`: watchdog validate/recover + context hygiene + main notify cycle (soft advisory+nudge 우선, hard lock only for reset-grade actions)
  - `launchd_watchdog.sh`: watchdog용 launchd 진입 쉘
- `scripts/directives/`
  - `db.py`: DIRECTIVES SQLite CLI
  - `gate.py`: DIRECTIVES fail-close gate
- `scripts/heartbeat/`
  - `local_brain_guard.py`: 메인 로컬 브레인 헬스체크/복구
  - `launchd_local_brain_guard.sh`: heartbeat launchd 진입 쉘
  - `reset_local_brain.sh`: 로컬 브레인 수동 리셋

## 현재 표준 호출 예시
- TASKS 요약: `python3 scripts/tasks/db.py summary --top 5 --recent 5` (`task_state=assignee/phase/review/resume_due` 포함)
- TASK 게이트: `python3 scripts/tasks/gate.py --ticket JB-YYYYMMDD-001`
- TASK watchdog 검사: `python3 scripts/watchdog/watchdog_validate.py`
- TASK watchdog 복구: `python3 scripts/watchdog/watchdog_recover.py`
- TASK/context watchdog cycle: `python3 scripts/watchdog/watchdog_cycle.py`
- TASK auto-dispatch: `python3 scripts/tasks/dispatch_tick.py`
- TASK assignee 해제: `python3 scripts/tasks/db.py release --id <ID>`
- TASK phase 표기(예: `delegated_to_subagent`/`subagent_running`/`awaiting_callback`/`long_running_execution`/`main_review`): `python3 scripts/tasks/db.py mark-phase --id <ID> --phase <phase> --child-session <session> --resume-due "YYYY-MM-DD HH:MM:SS"` (`TODO`/`BLOCKED` task에 nonterminal waiting phase를 찍으면 자동으로 `IN_PROGRESS/active`로 되돌림)
- TASK 삭제: `python3 scripts/tasks/db.py remove --id <ID>`
- DIRECTIVES 요약: `python3 scripts/directives/db.py summary --top 5 --recent 5`
- DIRECTIVE 게이트: `python3 scripts/directives/gate.py --id <ID>`
- context 복구 상태 점검: `python3 scripts/context_policy.py resume-check --strict`
- context handoff 검증: `python3 scripts/context_policy.py handoff-validate --strict`
- current-task + context-handoff 스냅샷: `python3 scripts/context_policy.py snapshot --ticket-id <id> --directive-ids <id[,id]> --goal "..." --last "..." --next-action "..." --touched-paths "..." --proof "..." --paths "..." --notes "..."` (taskdb에 같은 ticket이 있으면 `task_status/task_phase/task_runtime_state` 자동 포함)
- current-task 기준 handoff 갱신: `python3 scripts/context_policy.py handoff-from-current --handoff-reason <reason> --trigger <trigger> --required-action <action> --observed-total-tokens <n> --threshold <n>`
- Heartbeat guard: `python3 scripts/heartbeat/local_brain_guard.py`

## 메모
- 이전 평면 경로(`scripts/taskdb.py` 등)는 더 이상 표준이 아님.
- 문서와 자동화는 하위 디렉터리 기준 경로를 사용해야 함.
- 세션 리셋은 커스텀 래퍼 대신 OpenClaw 기본 명령/표준 운영 절차 사용.
