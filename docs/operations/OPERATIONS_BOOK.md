# OPERATIONS BOOK

역할: **운영 총괄 인덱스**.

이 문서는 운영 문서의 진입점만 담당한다.
세부 규칙은 각 canonical 문서로 위임한다.

## 반드시 읽을 것
1. `docs/index.html` — 문서 루트 진입점
2. `docs/operations/OPERATIONS_BOOK.md` — 운영 문서 지도
3. `docs/operations/DOCUMENT_STANDARD.md` — 문서 작성/배치 표준
4. `runtime/current-task.md` — 현재 작업 재개 카드(작업 재개 시)

## 필요 시 읽을 것
| 문서 | 역할 |
|---|---|
| `docs/operations/CONTEXT_POLICY.md` | 세션 컨텍스트 운용 기준 |
| `docs/operations/CONTEXT_LOAD_POLICY.md` | 세션 컨텍스트 로딩 규칙 |
| `docs/operations/CONTEXT_RESET_READLIST.md` | 컨텍스트 리셋 직후 최소 재로딩 목록 |
| `docs/operations/OPERATING_GOVERNANCE.md` | 운영 거버넌스 |
| `docs/operations/WORKSPACE_STRUCTURE.md` | 저장소 구조 설명 |
| `HEARTBEAT.md` | heartbeat/복구 규칙 |
| `MEMORY.md` | 메인 1:1 핵심 기억 |
| `memory/YYYY-MM-DD.md` | 일일 로그북(통재로딩 금지) |
| `docs/operations/BRAINS.md` | 2뇌 역할 분리 |
| `docs/operations/CONTRIBUTING.md` | Git/PR/커밋 규칙 |
| `docs/operations/OPENCLAW_RULES.md` | OpenClaw/로컬뇌 보조 규칙 |
| `docs/operations/OPENCLAW_SYSTEM_BASELINE.md` | 시스템 기준선/복구 보조 문서 |

## 루트에 남기는 문서
- `AGENTS.md` — 자동 로드 최상위 규칙
- `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md` — 세션 기본 문서
- `MEMORY.md`, `HEARTBEAT.md` — 시스템/기억 문서
- `runtime/current-task.md` — 상태파일
- `memory/*.md` — 기록 파일
- `DIRECTIVES.md`, `TASKS.md` — SSOT usage index

## 운영 프로그램
| 이름 | 역할 | 위치 |
|---|---|---|
| `context_policy.py` | 메인 롤링 / 로컬뇌 flush / current-task snapshot / reload bundle / 토큰별 액션 판단 | `scripts/context_policy.py` |
| `scripts/tasks/db.py` | 태스크 등록/전이 SSOT 관리 | `scripts/tasks/db.py` |
| `scripts/directives/db.py` | directive 등록/상태전이 SSOT 관리 | `scripts/directives/db.py` |
| `scripts/heartbeat/local_brain_guard.py` | 로컬뇌/OpenClaw 상태 점검 및 복구 흐름 연동 | `scripts/heartbeat/local_brain_guard.py` |

## 갱신 규칙
- 운영 문서 추가/삭제 시 이 문서를 먼저 갱신한다.
- 중복 인덱스는 보존하지 않는다. canonical 문서와 index 문서를 분리한다.
