# runtime/tasks README

## 기본 경로
- DB: `runtime/tasks/tasks.db`
- 렌더 대상: `TASKS_ACTIVE.md`

## 초기 1회 절차
1. `python3 scripts/taskdb.py init`
2. `python3 scripts/taskdb.py migrate-md`
3. `python3 scripts/taskdb.py render-md`

## 운영 예시
- 요약: `python3 scripts/taskdb.py summary --top 5 --recent 5`
- 조회: `python3 scripts/taskdb.py list --status IN_PROGRESS`
- 시작: `python3 scripts/taskdb.py start --id JB-20260305-037`
- 완료: `python3 scripts/taskdb.py done --id JB-20260305-037 --proof "..."`
- 차단: `python3 scripts/taskdb.py block --id JB-20260305-037 --reason "..."`
- fail-close 게이트: `python3 scripts/task_gate.py --ticket JB-20260305-037`
