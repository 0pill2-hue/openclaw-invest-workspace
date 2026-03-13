# JB-20260312-BLOCKED-BACKLOG-REQUEUE

- ticket: JB-20260312-BLOCKED-BACKLOG-REQUEUE
- status: DONE
- reviewed_at: 2026-03-13 07:19 KST
- note: task DB/directive DB/backlog proof alignment confirmed after auto-requeue validation

## Goal
BLOCKED backlog를 주기적으로 다시 평가해서, 진짜 blocker만 BLOCKED에 남기고 retryable/resumable/조건 해소된 건은 자동으로 다시 큐에 태운다.

## What changed
1. `scripts/lib/blocked_requeue.py` 추가
   - BLOCKED ticket를 공통 규칙으로 재평가하는 helper를 만들었다.
   - 현재 자동 requeue 조건:
     - watchdog/time-based blocker (`watchdog_*`, stale/timeout 계열)
     - `deferred_by_owner_priority` + 참조 ticket가 더 이상 `IN_PROGRESS` 아님
     - `prereq_*` + 참조 ticket들이 모두 `DONE`
     - `07:00_status_window` 같은 시간창 blocker가 이미 경과함
   - requeue 시 `status=TODO`, `bucket=active`, `phase=main_resume`로 바꾸고 assignee/run/review/closed metadata를 정리한다.

2. `scripts/tasks/db.py`
   - `assign_next_task()` 시작 시 BLOCKED backlog auto-requeue를 먼저 실행하게 해서, auto-dispatch pick 직전에 재평가가 항상 일어나도록 했다.
   - 수동/증빙용 CLI `python3 scripts/tasks/db.py requeue-blocked`를 추가했다.

3. `scripts/watchdog/watchdog_recover.py`
   - 기존 stale/deadline blocker 승격 뒤에 same-pass requeue를 추가했다.
   - 출력 JSON에 `requeued`를 포함시켜 watchdog 증빙에서 바로 확인 가능하게 했다.

4. 문서 업데이트
   - `runtime/tasks/README.md`
   - `docs/operations/runtime/PROGRAMS.md`
   - `scripts/README.md`

## Verification
- syntax:
  - `python3 -m py_compile scripts/lib/blocked_requeue.py scripts/tasks/db.py scripts/watchdog/watchdog_recover.py`
- fixture proof:
  - `runtime/tasks/proofs/JB-20260312-BLOCKED-BACKLOG-REQUEUE_fixture.json`
  - watchdog blocker / elapsed window / deferred-by-priority-cleared 는 requeue되고, 참조 없는 real prereq blocker는 그대로 BLOCKED로 남는 것을 확인했다.
- live apply:
  - `python3 scripts/tasks/db.py requeue-blocked`
  - `python3 scripts/tasks/db.py summary --top 10 --recent 10`
  - `runtime/tasks/proofs/JB-20260312-BLOCKED-BACKLOG-REQUEUE_live.json`

## Live effect
- BLOCKED backlog에서 아래 ticket들이 자동으로 다시 TODO/active로 복귀했다.
  - `JB-20260311-OVERNIGHT-CLOSEOUT` (07:00 window 경과)
  - `JB-20260311-POST-CLOSE-AUTO-ADVANCE` (runtime idle/system-gap blocker 해소)
  - `JB-20260310-RAW-DB-PIPELINE` (watchdog stale blocker 재큐잉)
  - `JB-20260311-STAGE-CONTRACT-ALIGN` (watchdog stale blocker 재큐잉)
  - `JB-20260311-STAGE2-PDF-CONTRACT-ALIGN-FIX` (watchdog stale blocker 재큐잉)
  - `JB-20260311-WEB-REVIEW-STAGE12-IMPROVE` (watchdog stale blocker 재큐잉)
- 반대로 real blocker는 BLOCKED에 남도록 유지했다.
  - 예: `JB-20260312-STAGE3-BRAIN-BENCHMARK`는 한 차례 과도하게 풀린 것을 즉시 원복했고, 현재 helper 기준으로는 auto-requeue 대상이 아니다.

## Notes
- auto-requeue 정확도는 `blocked_reason`에 unblock 조건이 얼마나 구조적으로 적히느냐에 크게 의존한다.
- 참조 ticket 없이 free-text로만 적힌 prereq/blocker는 보수적으로 그대로 BLOCKED에 남긴다.

## Proof
- `scripts/lib/blocked_requeue.py`
- `scripts/tasks/db.py`
- `scripts/watchdog/watchdog_recover.py`
- `runtime/tasks/README.md`
- `docs/operations/runtime/PROGRAMS.md`
- `scripts/README.md`
- `runtime/tasks/proofs/JB-20260312-BLOCKED-BACKLOG-REQUEUE_fixture.json`
- `runtime/tasks/proofs/JB-20260312-BLOCKED-BACKLOG-REQUEUE_live.json`
