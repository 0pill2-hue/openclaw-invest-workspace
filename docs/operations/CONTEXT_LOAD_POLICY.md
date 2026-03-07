# CONTEXT LOAD POLICY

역할: **세션 컨텍스트 로딩 규칙**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

이 문서는 어떤 문서를 언제 로드할지 정의한다.
운용 임계치 자체는 `CONTEXT_POLICY.md`를 따른다.

## 기본 원칙
- 문서 삭제보다 계층 로딩을 우선한다.
- 일자 메모리는 `memory/YYYY-MM-DD.md` 오늘 only
- `MEMORY.md`는 MAIN 1:1 세션에서만
- TASKS SSOT: `runtime/tasks/tasks.db` + `python3 scripts/tasks/db.py`
- DIRECTIVES SSOT: `runtime/directives/directives.db` + `python3 scripts/directives/db.py`

## On-demand 트리거
- 뇌 역할/폴백 기준 확인: `docs/operations/BRAINS.md`
- Git 기준 확인: `docs/operations/CONTRIBUTING.md`
- 시스템/구조 변경: `docs/operations/WORKSPACE_STRUCTURE.md`, `docs/operations/OPENCLAW_SYSTEM_BASELINE.md`
- 투자 운영 기준: `docs/invest/OPERATIONS_SOP.md`, `docs/invest/INVEST_STRUCTURE_POLICY.md`
