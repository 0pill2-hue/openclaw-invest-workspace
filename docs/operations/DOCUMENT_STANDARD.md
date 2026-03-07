# DOCUMENT STANDARD

역할: **문서 작성/배치 표준**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

## 1. 문서 분류
### 루트 자동로드/시스템 문서
- `AGENTS.md`
- `DIRECTIVES.md`
- `SOUL.md`
- `USER.md`
- `TOOLS.md`
- `IDENTITY.md`
- `MEMORY.md`
- `HEARTBEAT.md`

### 상태/기록 문서
- `runtime/*.md`
- `memory/*.md`

### docs 문서
- 운영 인덱스
- 운영 규칙/정책
- 투자 문서
- 설명서/가이드

## 2. 위치 표준
- `docs/` : 사람이 읽는 문서의 기본 위치
- `docs/operations/` : 운영 기준 / 인덱스 / 정책 / 구조 설명
- `docs/invest/` : 투자 문서 canonical
- `runtime/` : 현재 상태/재로딩 카드
- `memory/` : 일일 기록/로그

## 3. 네이밍 표준
- 루트 인덱스/책: `*_BOOK.md`
- 폴더 안내: `README.md`
- 상태파일: 소문자-하이픈 (`current-task.md`)
- 일일 로그: `YYYY-MM-DD.md`
- HTML 진입점: `index.html`

## 4. canonical / index 구분
- canonical 문서는 실제 규칙/절차/기준을 담는다.
- index 문서는 링크/탐색만 담당한다.
- 역할 없는 중복 인덱스는 삭제한다.

## 5. historical / reserved 표시 규칙
- `HISTORICAL_ONLY` : 과거 산출/참고용, 현재 canonical 아님
- `LEGACY_REFERENCE` : 참조용 보존, 실행 기준 아님
- `RESERVED` : 구조 슬롯만 존재, 실행 기준 미구현
- `DRAFT_PLACEHOLDER` : 자리표시자, 활성 실행 문서 아님
- `GOVERNANCE_STAGE` : 실행보다 승인/채택 거버넌스 목적

## 6. 공개 / 로컬 전용 기준
- 공개 repo canonical 판단은 Git tracked 문서만 대상으로 한다.
- 로컬 전용 문서는 canonical source 로 취급하지 않는다.
- 공개 문서에서는 로컬 전용 파일에 직접 링크하지 않는다.
- 세부 기준은 `docs/operations/PRIVATE_LOCAL_DOCS_POLICY.md`를 따른다.
