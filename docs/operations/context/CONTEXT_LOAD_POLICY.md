# CONTEXT LOAD POLICY

역할: **세션에서 무엇을 언제 읽는지 정하는 규칙**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`
프로그램 총람: `docs/operations/runtime/PROGRAMS.md`

## 기본 원칙
- 기본 대응은 **로드량 축소**다.
- 같은 목적의 재읽기/재확인은 최소화한다.
- 긴 로그는 원문 전체 대신 **필요 구간 + 구조화 요약**만 본다.
- 사람용 category/explainer/diagram 문서는 기본 로드 대상이 아니다.

## 기본 로드
- `SOUL.md`
- `USER.md`
- `docs/operations/context/CONTEXT_LOAD_POLICY.md`
- `docs/operations/OPERATIONS_BOOK.md`
- `python3 scripts/tasks/db.py summary --top 5 --recent 5`
- `python3 scripts/directives/db.py summary --top 5 --recent 5`
- `runtime/current-task.md`

## 기본 제외
- `docs/operations/context/README.md`
- `docs/operations/governance/README.md`
- `docs/operations/runtime/README.md`
- `docs/operations/orchestration/`
- `docs/operations/skills/`
- 대량 `sessions_history`
- 긴 `exec`/`process log` 원문 전체

## 복구 우선순위
1. `runtime/context-handoff.md`
2. `runtime/current-task.md`
3. TASKS/DIRECTIVES summary
4. 필요 시 `python3 scripts/context_policy.py resume-check --strict`

## 최소 필수 확인
- TASKS SSOT: `runtime/tasks/tasks.db` + `python3 scripts/tasks/db.py`
- DIRECTIVES SSOT: `runtime/directives/directives.db` + `python3 scripts/directives/db.py`
- `runtime/current-task.md` 필수 필드: `ticket_id`, `directive_ids`, `current_goal`, `last_completed_step`, `next_action`, `touched_paths`, `latest_proof`
- `runtime/context-handoff.md`는 reset/cutover 직후에만 읽는 짧은 인계 카드다.

## On-demand 로드
- 구조/다이어그램: `docs/operations/orchestration/README.md`
- Git 규칙: `docs/operations/governance/CONTRIBUTING.md`
- 저장소 구조: `docs/operations/governance/WORKSPACE_STRUCTURE.md`
- 2뇌 역할: `docs/operations/runtime/BRAINS.md`
- 투자 운영 기준: `docs/invest/OPERATIONS_SOP.md`, `docs/invest/INVEST_STRUCTURE_POLICY.md`

## 금지/주의
- usage index만 읽고 복구를 끝내지 않는다.
- 닫힌 ticket을 current-task가 가리키는 상태를 방치하지 않는다.
- clean reset/cutover는 유효한 handoff 확인 전에는 하지 않는다.
