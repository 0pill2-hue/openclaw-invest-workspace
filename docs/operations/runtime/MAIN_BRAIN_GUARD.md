# MAIN BRAIN GUARD

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`
프로그램 총람: `docs/operations/runtime/PROGRAMS.md`

역할: **메인 운영 경로의 상위 health/dispatch 가드**.

## 감시 대상
1. Gateway reachable / service running
2. 메인 세션 응답 가능성
3. Telegram 등 활성 채널 상태
4. `tasks watchdog` + `auto-dispatch` 생존성
5. `runtime/current-task.md` 복구 가능성

## 하위 구성요소
- `local_brain_guard` — 로컬뇌/Gateway 컴포넌트 복구
- `tasks watchdog` — stale/deadline/context hygiene 감시
- `auto-dispatch` — 남은 task 재기동
- heartbeat — 상위 상태 보고

## 실패 기준
- Gateway unreachable / service down
- 채널 상태 이상
- watchdog/auto-dispatch launchd 이상
- 남은 assignable task가 있는데 auto-dispatch가 재기동 못 함
- `runtime/current-task.md` 복구 불가
- `local_brain_guard` FAIL은 advisory이며 단독 main FAIL 조건은 아니다.

## 운영 핵심
- waiting phase는 age만으로 blocker 취급하지 않는다.
- `nonterminal waiting phase + released assignee`는 detached waiting/backgrounded의 정상 ongoing 상태다.
- auto-dispatch는 close만이 아니라 backgrounded ongoing도 정상으로 본다.
- watchdog는 deadline(`resume_due`) 초과 시점에만 wait phase를 blocker로 승격한다.

## 기본 확인 명령
- `openclaw status`
- `python3 scripts/tasks/db.py summary --top 5 --recent 5`
- `python3 scripts/context_policy.py resume-check --strict`
- `python3 scripts/watchdog/watchdog_cycle.py`
- `python3 scripts/heartbeat/main_brain_guard.py`

## 문서 경계
- non-idle 흐름 설명/다이어그램: `docs/operations/orchestration/NONIDLE_ORCHESTRATION_GUIDE.md`
- task contract: `TASKS.md`
- 프로그램별 역할: `docs/operations/runtime/PROGRAMS.md`

## 후속 과제
- 채널 실송수신 self-check 표준화
- 메인 세션 장기 무응답 기준 정식화
- launchd/heartbeat 경로 표준화 강화
