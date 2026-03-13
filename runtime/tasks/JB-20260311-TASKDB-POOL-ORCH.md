# JB-20260311-TASKDB-POOL-ORCH

- directive_id: JB-20260311-TASKDB-POOL-ORCH
- status: IN_PROGRESS
- owner: main-orchestrator
- goal: taskdb에 assign 주체/담당 주체/확인완료 주체를 기록하고, 쉬운 장시간 작업은 서브에이전트에 맡기며 어려운 작업은 메인이 직접 처리하고, main/sub 유휴 시간이 생기면 미배정 태스크를 계속 배정하는 풀 기반 오케스트레이션으로 정리한다.
- constraints: 삭제/배포/외부전송 없음. 기존 taskdb/current-task 호환 유지.
- plan:
  1. tasks DB / current-task / summary 출력에 주체 필드 추가
  2. assign-next 및 review-pass/release 흐름에 assigner/reviewer 반영
  3. main/sub 풀 배정 정책과 자동 미배정 태스크 선택 로직 추가
  4. 검증 및 문서/메모리 반영
- proof_log:
  - 2026-03-11 13:16 KST: 사용자 지시를 새 directive/task로 등록하고 구현 설계 착수.
  - 2026-03-11 13:33 KST: scripts/tasks/db.py에 assigned_by/owner/closed_by 컬럼, assign-pool 명령, lane 기반 assign-next 정책을 추가.
  - 2026-03-11 13:33 KST: scripts/context_policy.py에 current-task/context-handoff 주체 필드(task_assigned_by/task_owner/task_closed_by) 노출을 추가.
  - 2026-03-11 13:33 KST: scripts/tasks/dispatch_tick.py를 worker pool(assign-pool) 기반으로 바꾸고 main/subagent lane 지시를 main orchestrator 메시지에 반영.
  - 2026-03-11 13:34 KST: watchdog maintenance/recover 경로도 assigned_by/owner/closed_by를 기록하도록 보강하고 py_compile로 핵심 스크립트 문법 검증 완료.
