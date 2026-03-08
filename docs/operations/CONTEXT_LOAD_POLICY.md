# CONTEXT LOAD POLICY

역할: **세션 컨텍스트 로딩 규칙**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`
프로그램 총람: `docs/operations/PROGRAMS.md`
관련 포맷: `docs/operations/CONTEXT_HANDOFF_FORMAT.md`

이 문서는 어떤 문서를 언제 로드할지 정의한다.
운용 임계치 자체는 `CONTEXT_POLICY.md`를 따른다.

## 기본 원칙
- 문서 삭제보다 계층 로딩을 우선한다.
- 일자 메모리는 `memory/YYYY-MM-DD.md` 오늘 only
- `MEMORY.md`는 MAIN 1:1 세션에서만
- TASKS SSOT: `runtime/tasks/tasks.db` + `python3 scripts/tasks/db.py`
- DIRECTIVES SSOT: `runtime/directives/directives.db` + `python3 scripts/directives/db.py`
- 리셋/신규 세션 복구 시 usage index만 읽고 끝내지 않는다. 반드시 TASKS/DIRECTIVES DB summary를 함께 확인한다.
- `runtime/current-task.md`는 **본작업 SSOT 요약 카드**다.
- `runtime/context-handoff.md`는 **reset/cutover 직후에만 읽는 짧은 인계 카드**다.
- `runtime/current-task.md`는 placeholder 상태(`미정`, 빈 필드)면 복구 실패로 간주한다.
- `runtime/current-task.md` 최소 필수 필드: `ticket_id`, `directive_ids`, `current_goal`, `last_completed_step`, `next_action`, `touched_paths`, `latest_proof`
- `runtime/context-handoff.md` 최소 필수 필드: `source_ticket_id`, `source_directive_ids`, `business_goal`, `last_completed_step`, `next_action`, `latest_proof`, `touched_paths`, `required_action`, `reset_guard`
- 가능하면 같은 ticket의 taskdb 상태를 함께 적재한다: `task_status`, `task_phase`, `task_assignee`, `task_runtime_state`, `task_resume_due`
- `runtime/current-task.md`의 `task_status`가 taskdb 실제 상태와 다르면 stale snapshot으로 간주하고 즉시 다시 snapshot 한다.
- clean reset/cutover는 `runtime/context-handoff.md` 검증 통과 전에는 금지한다.

## 세션 복구 체크
- TASKS summary: `python3 scripts/tasks/db.py summary --top 5 --recent 5`
- DIRECTIVES summary: `python3 scripts/directives/db.py summary --top 5 --recent 5`
- current-task/DB 복구 상태 점검: `python3 scripts/context_policy.py resume-check --strict`
- handoff 유효성 점검: `python3 scripts/context_policy.py handoff-validate --strict`
- current-task + handoff 갱신: `python3 scripts/context_policy.py snapshot --ticket-id <id> --directive-ids <id[,id]> --goal "..." --last "..." --next-action "..." --touched-paths "..." --proof "..." --paths "..." --notes "..."`

## On-demand 트리거
- 뇌 역할/폴백 기준 확인: `docs/operations/BRAINS.md`
- Git 기준 확인: `docs/operations/CONTRIBUTING.md`
- 시스템/구조 변경: `docs/operations/WORKSPACE_STRUCTURE.md`, `docs/operations/OPENCLAW_SYSTEM_BASELINE.md`
- 투자 운영 기준: `docs/invest/OPERATIONS_SOP.md`, `docs/invest/INVEST_STRUCTURE_POLICY.md`
