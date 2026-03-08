# CONTEXT POLICY

역할: **세션 컨텍스트 운용 기준**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`
관련 포맷: `docs/operations/CONTEXT_HANDOFF_FORMAT.md`

이 문서는 메인/로컬뇌의 운용 임계치와 유지 원칙을 정의한다.
재로딩 목록 자체는 `CONTEXT_RESET_READLIST.md`, 로딩 규칙은 `CONTEXT_LOAD_POLICY.md`를 따른다.

## 핵심 기준
- 메인 5.4 세션: **120k 도달/초과 시점에는 현재 진행 중인 작업 step을 먼저 완료/체크포인트**하고, 그 다음 validated handoff를 거쳐 clean reset/cutover를 수행한다.
- 120k 미만 구간은 별도 선제 경고/감시를 두지 않고, 불필요한 운영 오버헤드를 만들지 않는다.
- 메인 hard action 기본값: `finish_current_step_then_reset`
- 로컬뇌: task 종료 시 flush
- 재로딩: 기본 규칙 + `runtime/current-task.md` + `runtime/context-handoff.md` + TASKS/DIRECTIVES DB summary
- `memory/YYYY-MM-DD.md`는 기록/검색용이며 통재로딩 금지
- `runtime/context-handoff.md`는 평소 상시 적재하지 않고 reset/cutover 직후에만 읽는다
- clean reset/cutover 전 검증:
  - `python3 scripts/context_policy.py resume-check --strict`
  - `python3 scripts/context_policy.py handoff-validate --strict`
- 자동화 스크립트: `python3 scripts/context_policy.py --help`
