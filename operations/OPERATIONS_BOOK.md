# OPERATIONS BOOK

목적: 사람이 운영 문서를 펼쳐 보고, **무슨 운영 프로그램이 있고 / 언제 무엇을 읽고 / 어디서 실행하는지** 바로 찾게 하는 운영 기준서.

상위 역할: 운영 관련 문서/프로그램/상태파일의 **루트 인덱스**.

## 목차
1. 운영 문서 읽는 순서
2. 반드시 읽어야 할 운영 문서
3. 필요 시 읽는 운영 문서
4. 운영 프로그램 목록
5. 운영 상태파일 목록
6. 상황별 어디를 볼지
7. 현재 컨텍스트 운영 기준
8. 문서 정규화 기준

---

## 1. 운영 문서 읽는 순서

### 자동 로드되는 상위 규칙
- `AGENTS.md` — 최상위 운영 규칙 (자동 로드 대상)

### 기본 진입
1) `operations/OPERATIONS_BOOK.md` — 운영 프로그램 전체 지도
2) `operations/DOCUMENT_STANDARD.md` — 문서 위치/이름/형식 표준
3) 현재 상황에 맞는 문서/프로그램으로 이동

### 현재 작업을 이어갈 때
1) `runtime/current-task.md`
2) 필요하면 `memory/YYYY-MM-DD.md`
3) 재로딩/판단이 필요하면 `scripts/context_policy.py`

### heartbeat/장애 대응 때
1) `HEARTBEAT.md`
2) `operations/OPERATIONS_BOOK.md`의 heartbeat 섹션
3) 필요 시 `scripts/heartbeat/local_brain_guard.py`

### 태스크/지시 관리 때
1) `AGENTS.md`의 규칙 확인
2) `scripts/tasks/db.py` 또는 `scripts/directives/db.py`
3) SSOT DB 위치 확인

---

## 2. 반드시 읽어야 할 운영 문서

| 문서 | 언제 | 역할 | 위치 |
|---|---|---|---|
| `operations/OPERATIONS_BOOK.md` | 운영 구조를 파악할 때 항상 | 운영 프로그램/상태파일/절차의 전체 지도 | `operations/OPERATIONS_BOOK.md` |
| `runtime/current-task.md` | 현재 작업 이어갈 때 | 지금 작업 handoff 카드 | `runtime/current-task.md` |

### 자동 로드/상위 규칙 문서
| 문서 | 성격 | 위치 |
|---|---|---|
| `AGENTS.md` | 자동 로드되는 최상위 운영 규칙 | `AGENTS.md` |

### 해석
- 운영 프로그램이 뭐가 있는지는 `OPERATIONS_BOOK.md`에서 찾고,
- 지금 하던 일을 이어갈 때만 `runtime/current-task.md`를 읽는다.
- `AGENTS.md`는 문서 체계에는 포함되지만, 자동 로드되는 상위 규칙이므로 여기서는 별도 구분한다.

---

## 3. 필요 시 읽는 운영 문서

| 문서 | 읽는 상황 | 역할 | 위치 |
|---|---|---|---|
| `HEARTBEAT.md` | heartbeat, 장애, 로컬뇌 이상 | heartbeat 규칙/복구 절차 | `HEARTBEAT.md` |
| `MEMORY.md` | 메인 1:1 세션 핵심 기억 필요 시 | 초핵심 장기 기억 | `MEMORY.md` |
| `memory/YYYY-MM-DD.md` | 오늘 결정/이유/proof 확인 시 | 일일 로그북 | `memory/` |
| `SOUL.md` | 호칭/톤/태도 확인 시 | 응답 태도 기준 | `SOUL.md` |
| `USER.md` | 사용자 기본 정보 확인 시 | 사용자 기본 정보 | `USER.md` |

### 해석
- `memory/YYYY-MM-DD.md`는 **기록용**이므로 통째 재로딩하지 않는다.
- `HEARTBEAT.md`는 평소 상시 읽는 문서가 아니라 **장애/점검 시** 읽는다.

---

## 4. 운영 프로그램 목록

| 이름 | 종류 | 역할 | 기본 사용법 | 위치 | 상태 |
|---|---|---|---|---|---|
| `context_policy.py` | 컨텍스트 운영 | 메인 120k 롤링 / 로컬뇌 flush / current-task snapshot / reload bundle 생성 / 토큰 기준 액션 판단 | `python3 scripts/context_policy.py --help` | `scripts/context_policy.py` | 확인됨 |
| `local_brain_guard.py` | heartbeat/헬스체크 | 로컬뇌 및 OpenClaw 상태 점검, heartbeat 복구 흐름과 연동 | `python3 scripts/heartbeat/local_brain_guard.py` | `scripts/heartbeat/local_brain_guard.py` | 경로/실행 미확인 |
| `tasks db` | 태스크 운영 | 티켓 등록/전이 SSOT 관리 | `python3 scripts/tasks/db.py` | `scripts/tasks/db.py` | 경로/실행 미확인 |
| `directives db` | 지시 운영 | instruction/status change SSOT 관리 | `python3 scripts/directives/db.py` | `scripts/directives/db.py` | 경로/실행 미확인 |

### 해석
- 컨텍스트 관련 자동화는 `context_policy.py`
- heartbeat/로컬뇌 상태 점검은 `local_brain_guard.py`
- 태스크 등록/전이는 `tasks db`
- 지시사항 등록/변경은 `directives db`

---

## 5. 운영 상태파일 목록

| 파일 | 역할 | 재로딩 여부 | 위치 |
|---|---|---|---|
| `runtime/current-task.md` | 현재 작업 handoff 카드 | 재로딩 O | `runtime/current-task.md` |
| `memory/YYYY-MM-DD.md` | 일일 로그북(결정/이유/proof) | 통재로딩 X, 필요 시 검색/참조 | `memory/` |
| `MEMORY.md` | 메인 세션용 초핵심 기억 | 메인만 재로딩 O | `MEMORY.md` |
| `AGENTS.md` | 상위 운영 규칙 | 재로딩 O | `AGENTS.md` |
| `HEARTBEAT.md` | heartbeat 규칙/복구 절차 | heartbeat 시 참조 | `HEARTBEAT.md` |

### 가장 많이 헷갈리는 구분
- **지금 뭐 하던 중인지** → `runtime/current-task.md`
- **오늘 무슨 결정을 했는지** → `memory/YYYY-MM-DD.md`
- **어떻게 행동해야 하는지** → `AGENTS.md`
- **장애 시 무엇을 해야 하는지** → `HEARTBEAT.md`

---

## 6. 상황별 어디를 볼지

### A. 작업 재개
- 먼저: `runtime/current-task.md`
- 그다음: 필요 시 `memory/YYYY-MM-DD.md`
- 자동화 필요 시: `python3 scripts/context_policy.py reload --mode main|local`

### B. 태스크 등록/상태 전이
- 먼저: `AGENTS.md`
- 실행: `python3 scripts/tasks/db.py`
- SSOT: `runtime/tasks/tasks.db`

### C. 새 지시 / 상태 변경
- 먼저: `AGENTS.md`
- 실행: `python3 scripts/directives/db.py`
- SSOT: `runtime/directives/directives.db`

### D. heartbeat / 로컬뇌 이상
- 먼저: `HEARTBEAT.md`
- 필요 시: `python3 scripts/heartbeat/local_brain_guard.py`
- 관련 규칙: 라마 서버 재시작 → 2초 대기 → Gateway 재시작

### E. 컨텍스트가 커졌을 때
- 메인: 120k 근접 시 비우지 말고 롤링/압축
- 로컬뇌: task 종료 시 flush
- 도구: `python3 scripts/context_policy.py decide ...`

---

## 7. 현재 컨텍스트 운영 기준
- 메인 5.4 세션: 120k 근접 시 전체 비우기 대신 롤링/압축
- 로컬뇌: task 종료 시 flush
- 재로딩: 기본 규칙 + `runtime/current-task.md`
- `memory/YYYY-MM-DD.md`: 기록/검색용, 통재로딩 금지

---

## 8. 문서 정규화 기준
- 문서 위치/네이밍/문서북 작성 요령 표준은 `operations/DOCUMENT_STANDARD.md`를 따른다.
- 새 운영 문서를 만들기 전에 기존 BOOK/README/상태파일에 흡수 가능한지 먼저 본다.

---

## 운영북 갱신 규칙
- 운영 프로그램이 추가/변경되면 이 문서를 먼저 갱신한다.
- 프로그램별 장문 문서는 원칙적으로 만들지 않는다.
- 직접 확인하지 못한 항목은 `미확인`으로 남긴다.
