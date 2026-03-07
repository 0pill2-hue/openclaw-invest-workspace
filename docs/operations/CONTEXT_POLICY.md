# CONTEXT POLICY

역할: **세션 컨텍스트 운용 기준**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

이 문서는 메인/로컬뇌의 운용 임계치와 유지 원칙을 정의한다.
재로딩 목록 자체는 `CONTEXT_RESET_READLIST.md`, 로딩 규칙은 `CONTEXT_LOAD_POLICY.md`를 따른다.

## 핵심 기준
- 메인 5.4 세션: 120k 근접 시 롤링/압축
- 로컬뇌: task 종료 시 flush
- 재로딩: 기본 규칙 + `runtime/current-task.md`
- `memory/YYYY-MM-DD.md`는 기록/검색용이며 통재로딩 금지
- 자동화 스크립트: `python3 scripts/context_policy.py --help`
