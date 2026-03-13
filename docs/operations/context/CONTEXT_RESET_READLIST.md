# CONTEXT RESET READLIST

역할: **컨텍스트 리셋 직후 최소 재로딩 목록**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`
관련 포맷: `docs/operations/context/CONTEXT_HANDOFF_FORMAT.md`

이 문서는 리셋 직후 무엇을 다시 읽고 어떤 요약/체크를 실행할지 최소 순서를 정의한다.
임계치/정책은 `CONTEXT_POLICY.md`, 로딩 트리거와 daily memory/MEMORY scope는 `CONTEXT_LOAD_POLICY.md`를 따른다.

## L1 — MUST
1. `docs/operations/OPERATIONS_BOOK.md`
2. `DIRECTIVES.md`
3. `TASKS.md`
4. `python3 scripts/directives/db.py summary --top 5 --recent 5`
5. `python3 scripts/tasks/db.py summary --top 5 --recent 5`
6. `runtime/current-task.md`
7. `runtime/context-handoff.md`
8. `python3 scripts/context_policy.py resume-check --strict`
9. `python3 scripts/context_policy.py handoff-validate --strict`
10. `memory/YYYY-MM-DD.md`
11. `MEMORY.md` (메인 세션 필요 시)

## L2 — On-demand
- `docs/operations/context/CONTEXT_LOAD_POLICY.md`
- `docs/operations/context/CONTEXT_HANDOFF_FORMAT.md`
- `docs/operations/governance/OPERATING_GOVERNANCE.md`
- `docs/operations/governance/WORKSPACE_STRUCTURE.md`
- `docs/operations/runtime/BRAINS.md`
- `docs/operations/governance/CONTRIBUTING.md`
- `docs/invest/OPERATIONS_SOP.md`
