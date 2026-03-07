# DOCUMENT STANDARD

역할: **문서 작성/배치 표준**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

## 문서 분류
- 루트 자동로드/시스템 문서: `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md`, `MEMORY.md`, `HEARTBEAT.md`
- 상태/기록 문서: `runtime/*.md`, `memory/*.md`
- docs 문서: 운영 인덱스, 설명서, 가이드, 투자 문서, 시스템 참고 문서

## 위치 표준
- `docs/` : 사람이 읽는 문서의 기본 위치
- `docs/operations/` : 운영 기준 / 인덱스 / 정책 / 구조 설명
- `docs/invest/` : 투자 문서 canonical
- `runtime/` : 현재 상태/재로딩 카드
- `memory/` : 일일 기록/로그

## 네이밍 표준
- 루트 인덱스/책: `*_BOOK.md`
- 폴더 안내: `README.md`
- 상태파일: 소문자-하이픈 (`current-task.md`)
- 일일 로그: `YYYY-MM-DD.md`
- HTML 진입점: `index.html`

## canonical / index 구분
- canonical 문서는 실제 규칙/절차/기준을 담는다.
- index 문서는 링크/탐색만 담당한다.
- 역할 없는 중복 인덱스는 삭제한다.

## historical / reserved 표시 규칙
- `HISTORICAL_ONLY` : 과거 산출/참고용, 현재 canonical 아님
- `LEGACY_REFERENCE` : 참조용 보존, 실행 기준 아님
- `RESERVED` : 구조 슬롯만 존재, 실행 기준 미구현
- `DRAFT_PLACEHOLDER` : 자리표시자, 활성 실행 문서 아님
- `GOVERNANCE_STAGE` : 실행보다 승인/채택 거버넌스 목적
