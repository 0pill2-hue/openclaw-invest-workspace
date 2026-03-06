# scripts/ 구조 인덱스

## 목적
정리된 운영 스크립트의 실제 진입점을 한 곳에 모읍니다.

## 디렉터리
- `scripts/lib/`
  - `runtime_env.py`: 공통 경로/환경 유틸
  - `common_env.sh`: 공통 쉘 환경 변수
- `scripts/tasks/`
  - `db.py`: TASKS SQLite CLI
  - `gate.py`: TASK fail-close gate
  - `dispatch_tick.py`: 다음 task 자동 배정/기동 tick
  - `watchdog_validate.py`: TASK ledger 정합성 검사
  - `watchdog_recover.py`: stale task 자동 BLOCKED 전환
  - `launchd_dispatch.sh`: task auto-dispatch용 launchd 진입 쉘
  - `launchd_watchdog.sh`: task watchdog용 launchd 진입 쉘
- `scripts/directives/`
  - `db.py`: DIRECTIVES SQLite CLI
  - `gate.py`: DIRECTIVES fail-close gate
- `scripts/heartbeat/`
  - `local_brain_guard.py`: 메인 로컬 브레인 헬스체크/복구
  - `launchd_local_brain_guard.sh`: heartbeat launchd 진입 쉘
  - `reset_local_brain.sh`: 로컬 브레인 수동 리셋

## 현재 표준 호출 예시
- TASKS 요약: `python3 scripts/tasks/db.py summary --top 5 --recent 5`
- TASK 게이트: `python3 scripts/tasks/gate.py --ticket JB-YYYYMMDD-001`
- TASK watchdog 검사: `python3 scripts/tasks/watchdog_validate.py`
- TASK watchdog 복구: `python3 scripts/tasks/watchdog_recover.py`
- TASK auto-dispatch: `python3 scripts/tasks/dispatch_tick.py`
- DIRECTIVES 요약: `python3 scripts/directives/db.py summary --top 5 --recent 5`
- DIRECTIVE 게이트: `python3 scripts/directives/gate.py --id <ID>`
- Heartbeat guard: `python3 scripts/heartbeat/local_brain_guard.py`

## 메모
- 이전 평면 경로(`scripts/taskdb.py` 등)는 더 이상 표준이 아님.
- 문서와 자동화는 하위 디렉터리 기준 경로를 사용해야 함.
- 세션 리셋은 커스텀 래퍼 대신 OpenClaw 기본 명령/표준 운영 절차 사용.
