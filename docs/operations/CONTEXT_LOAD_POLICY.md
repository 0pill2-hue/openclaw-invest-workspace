# CONTEXT LOAD POLICY

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

Purpose: 컨텍스트 절감 + 안전성 유지 로딩 정책

## 기본 원칙
- 문서 삭제보다 계층 로딩 우선
- 일자 메모리는 `memory/YYYY-MM-DD.md` 오늘 only
- `MEMORY.md`는 MAIN 1:1 세션에서만
- TASKS SSOT: `runtime/tasks/tasks.db` + `python3 scripts/tasks/db.py`
- DIRECTIVES SSOT: `runtime/directives/directives.db` + `python3 scripts/directives/db.py`

## On-demand 트리거
- 뇌 역할/폴백 기준 확인: `docs/operations/BRAINS.md`
- Git 기준 확인: `docs/operations/CONTRIBUTING.md`
- 시스템/구조 변경: `docs/operations/WORKSPACE_STRUCTURE.md`, `docs/operations/OPENCLAW_SYSTEM_BASELINE.md`
