# CONTEXT POLICY

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

## 핵심
- 메인 5.4 세션: 120k 근접 시 롤링/압축
- 로컬뇌: task 종료 시 flush
- 재로딩: 기본 규칙 + `runtime/current-task.md`
- `memory/YYYY-MM-DD.md`는 기록/검색용이며 통재로딩 금지
- 자동화 스크립트: `python3 scripts/context_policy.py --help`
