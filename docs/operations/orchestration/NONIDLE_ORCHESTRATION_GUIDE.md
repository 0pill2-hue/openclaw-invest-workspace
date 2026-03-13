# NONIDLE ORCHESTRATION GUIDE

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

> status: human-facing explainer only
> canonical rules live in `TASKS.md`, `scripts/README.md`, `docs/operations/runtime/MAIN_BRAIN_GUARD.md`

## 1. 목적
메인 뇌가 background program/subagent/watcher를 띄운 뒤
그 작업이 끝날 때까지 **통째로 놀지 않게** 하는 운영 구조를 설명한다.

핵심은 아래 두 가지다.
1. **running subject와 task 상태를 분리**한다.
2. detached wait 상태는 ongoing이지만 **worker slot을 붙잡지 않게** 한다.

## 2. 핵심 용어
- **active execution**: 메인 또는 서브가 지금 실제로 CPU/판단을 쓰며 수행 중인 상태
- **detached waiting**: background program/subagent가 이미 떠 있고, 현재 worker는 callback만 기다리는 상태
- **backgrounded**: `IN_PROGRESS + nonterminal waiting phase + released assignee`로 인식되는 detached waiting task
- **resume-ready**: background completion/progress가 들어와 메인이 다시 집어 review/close 가능한 상태 (`main_resume` 등)

## 3. 상태 해석 요약
- `main_exec` 같은 active execution phase는 **다음 배정을 막는다**.
- `awaiting_callback` / `subagent_running` / `long_running_execution` 같은 nonterminal waiting phase는
  ongoing으로 남지만, worker가 더 이상 직접 일하지 않으면 **assignee/run metadata를 해제**할 수 있다.
- 이렇게 released 된 waiting task는 다시 pick 대상이 되지 않고,
  다른 ready task가 있으면 auto-dispatch가 그쪽을 계속 집는다.
- completion/progress event가 오면 해당 task에 proof/phase가 붙고,
  메인이 `main_resume` 같은 resume phase를 보고 다시 이어서 처리한다.

## 4. 라이프사이클
1. ready task가 task pool에 있다.
2. `assign-pool`/`dispatch_tick.py`가 worker에 task를 배정한다.
3. orchestrator는 둘 중 하나를 한다.
   - inline 실행 후 terminal close
   - background work launch 후 task-aware proof/phase 기록 + detached waiting 전환
4. background work는 진행/완료 시 같은 `task_id`로 event/proof를 남긴다.
5. task가 resume-ready가 되면 메인이 다시 집어 review/close 한다.

## 5. 관련 파일 역할 맵
- `scripts/tasks/db.py`
  - task 배정, phase 변경, release, ready/ongoing 판정
- `scripts/tasks/dispatch_tick.py`
  - assign-pool → orchestrator 호출 → backgrounded/close 상태 판정
- `scripts/tasks/record_task_event.py`
  - background program 시작/진행/완료를 task md + taskdb에 반영
- `skills/web-review/scripts/watch_chatgpt_response.py`
  - watcher 시작 시 mapped task를 detached waiting으로 동기화 가능
- `skills/web-review/scripts/sync_watch_event_to_task.py`
  - watcher completion을 mapped task proof/resume phase로 연결
- `scripts/watchdog/watchdog_recover.py`
  - nonterminal waiting phase는 age만으로 막지 않고 `resume_due` 초과 시점에만 blocker 승격

## 6. 문서 ownership
- **규칙 변경**: 먼저 `TASKS.md` 또는 관련 canonical 문서를 수정
- **호출 예시 변경**: `scripts/README.md` 수정
- **구조 설명/이해용 정리**: 이 문서 또는 diagram 문서 수정

## 7. 토큰 정책
이 문서는 사람용 설명본이다.
세션 기본 로드에서는 읽지 않고,
필요할 때만 on-demand로 연다.
