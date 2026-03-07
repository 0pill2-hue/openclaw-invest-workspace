# OPERATIONS BOOK

목적: OpenClaw 운영 문서/운영 프로그램/상태파일의 루트 인덱스.

## 반드시 읽을 것
1. `docs/index.html` — 문서 진입점
2. `docs/operations/OPERATIONS_BOOK.md` — 운영 전체 지도
3. `docs/operations/DOCUMENT_STANDARD.md` — 문서 위치/네이밍/작성 표준
4. `runtime/current-task.md` — 현재 작업 재개 카드(작업 재개 시)

## 필요 시 읽을 것
- `HEARTBEAT.md` — heartbeat/복구 규칙
- `MEMORY.md` — 메인 1:1 초핵심 기억
- `memory/YYYY-MM-DD.md` — 일일 로그북(통재로딩 금지)
- `docs/operations/BRAINS.md` — 2뇌 역할 분리
- `docs/operations/CONTRIBUTING.md` — Git/PR/커밋 규칙
- `docs/operations/OPENCLAW_RULES.md` — OpenClaw/로컬뇌 운영 보조 규칙
- `docs/operations/RULES_INDEX.md` — 기존 OpenClaw 규칙 인덱스
- `docs/operations/CONTEXT_LOAD_POLICY.md` — 컨텍스트 로딩 정책
- `docs/operations/CONTEXT_RESET_READLIST.md` — 리셋 직후 최소 readlist
- `docs/operations/OPERATING_GOVERNANCE.md` — 운영 고정 기준
- `docs/operations/WORKSPACE_STRUCTURE.md` — 워크스페이스 구조/배치 기준
- `docs/operations/OPENCLAW_SYSTEM_BASELINE.md` — 시스템 복구/기준선

## 루트에 남기는 문서
- `AGENTS.md` — 자동 로드 최상위 규칙
- `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md` — 세션 기본 문서
- `MEMORY.md`, `HEARTBEAT.md` — 시스템/기억 문서
- `runtime/current-task.md` — 상태파일
- `memory/*.md` — 기록 파일
- `DIRECTIVES.md`, `TASKS.md` — SSOT usage index

## 운영 프로그램 목록
| 이름 | 종류 | 역할 | 기본 사용법 | 위치 |
|---|---|---|---|---|
| `context_policy.py` | 컨텍스트 운영 | 메인 롤링 / 로컬뇌 flush / current-task snapshot / reload bundle / 토큰별 액션 판단 | `python3 scripts/context_policy.py --help` | `scripts/context_policy.py` |
| `scripts/tasks/db.py` | 태스크 운영 | 티켓 등록/전이 SSOT 관리 | `python3 scripts/tasks/db.py` | `scripts/tasks/db.py` |
| `scripts/directives/db.py` | 지시 운영 | directive 등록/상태전이 SSOT 관리 | `python3 scripts/directives/db.py` | `scripts/directives/db.py` |
| `scripts/heartbeat/local_brain_guard.py` | heartbeat/헬스체크 | 로컬뇌 및 OpenClaw 상태 점검/복구 흐름 연동 | `python3 scripts/heartbeat/local_brain_guard.py` | `scripts/heartbeat/local_brain_guard.py` |

## 운영 상태파일 목록
| 파일 | 역할 | 재로딩 여부 | 위치 |
|---|---|---|---|
| `runtime/current-task.md` | 현재 작업 handoff 카드 | O | `runtime/current-task.md` |
| `memory/YYYY-MM-DD.md` | 일일 로그북 | X (검색/참조만) | `memory/` |
| `MEMORY.md` | 메인 세션 핵심 기억 | 메인만 O | `MEMORY.md` |
| `HEARTBEAT.md` | heartbeat 규칙/복구 절차 | heartbeat 시 참조 | `HEARTBEAT.md` |

## 상황별 어디를 볼지
- 작업 재개: `runtime/current-task.md` → 필요 시 `memory/YYYY-MM-DD.md`
- 태스크 등록/전이: `TASKS.md` → `python3 scripts/tasks/db.py`
- 새 지시/상태 변경: `DIRECTIVES.md` → `python3 scripts/directives/db.py`
- heartbeat/로컬뇌 이상: `HEARTBEAT.md` → `python3 scripts/heartbeat/local_brain_guard.py`
- 문서 구조/네이밍 기준: `docs/operations/DOCUMENT_STANDARD.md`

## 현재 컨텍스트 운영 기준
- 메인 5.4 세션: 120k 근접 시 롤링/압축
- 로컬뇌: task 종료 시 flush
- 재로딩: 기본 규칙 + `runtime/current-task.md`
- `memory/YYYY-MM-DD.md`는 기록/검색용이며 통재로딩 금지

## 갱신 규칙
- 새 운영 프로그램/운영 문서 추가 시 이 문서를 먼저 갱신한다.
- 운영 관련 상세 기준은 `docs/operations/DOCUMENT_STANDARD.md`를 따른다.
- 중복 규칙은 canonical 1곳만 남기고 나머지는 제거하거나 usage index만 남긴다.
