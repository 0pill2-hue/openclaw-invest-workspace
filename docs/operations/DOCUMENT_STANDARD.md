# DOCUMENT STANDARD

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

목적: 문서 위치/이름/형식을 최소한으로 정규화해서, 사람이 문서를 찾고 유지하기 쉽게 만든다.

## 문서 분류
- 루트 자동로드/시스템 문서: `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md`, `MEMORY.md`, `HEARTBEAT.md`
- 상태/기록 문서: `runtime/*.md`, `memory/*.md`
- docs 문서: 운영 인덱스, 설명서, 가이드, 시스템 참고 문서

## 위치 표준
- `docs/` : 사람이 읽는 문서의 기본 위치
- `docs/operations/` : 문서 표준/운영 보조 기준
- `docs/openclaw/` : OpenClaw 시스템/운영 참고 문서
- `runtime/` : 현재 상태/재로딩 카드
- `memory/` : 일일 기록/로그

## 네이밍 표준
- 루트 인덱스/책: `*_BOOK.md`
- 폴더 안내: `README.md`
- 상태파일: 소문자-하이픈 (`current-task.md`)
- 일일 로그: `YYYY-MM-DD.md`
- HTML 진입점: `index.html`

## 문서북 작성 요령
1. 목적
2. 반드시 읽을 것
3. 필요 시 읽을 것
4. 대상 목록(프로그램/상태파일/문서)
5. 상황별 사용법
6. 갱신 규칙

## 최소 정리 원칙
- docs 밖에 둘 문서는 자동로드/시스템/상태/기록으로 제한한다.
- 사람이 읽는 장문 설명서는 docs로 이동한다.
- 루트에 남는 인간용 문서는 가능한 한 짧은 usage index 또는 포인터로 유지한다.
- 중복 문서는 canonical 1개 + 포인터 구조로 줄인다.
