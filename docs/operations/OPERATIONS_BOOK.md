# OPERATIONS BOOK

역할: **운영 총괄 인덱스**.

세부 규칙은 각 canonical 문서로 위임하고,
이 문서는 공개 tracked 운영 문서의 진입점만 담당한다.

## 1. 공개 tracked 문서
### 핵심 운영 문서
- `docs/operations/OPERATIONS_BOOK.md`
- `docs/operations/DOCUMENT_STANDARD.md`
- `docs/operations/OPERATING_GOVERNANCE.md`
- `docs/operations/CONTEXT_POLICY.md`
- `docs/operations/CONTEXT_LOAD_POLICY.md`
- `docs/operations/CONTEXT_RESET_READLIST.md`
- `docs/operations/WORKSPACE_STRUCTURE.md`

### 공개 저장소 루트 tracked 문서
- `AGENTS.md`
- `DIRECTIVES.md`
- `runtime/current-task.md`

## 2. 로컬 전용 문서 정책
- 로컬 전용 문서는 공개 저장소 canonical 문서가 아니다.
- 개별 파일명을 여기서 나열하지 않는다.
- 기준은 `docs/operations/PRIVATE_LOCAL_DOCS_POLICY.md`를 따른다.

## 3. 필수 운영 문서
1. `docs/index.html` — 문서 루트 진입점
2. `docs/operations/OPERATIONS_BOOK.md` — 운영 문서 지도
3. `docs/operations/DOCUMENT_STANDARD.md` — 문서 작성/배치 표준
4. `runtime/current-task.md` — 현재 작업 재개 카드(작업 재개 시)

## 4. 필요 시 읽을 것
- `docs/operations/CONTEXT_POLICY.md` — 세션 컨텍스트 운용 기준
- `docs/operations/CONTEXT_LOAD_POLICY.md` — 세션 컨텍스트 로딩 규칙
- `docs/operations/CONTEXT_RESET_READLIST.md` — 리셋 직후 최소 재로딩 목록
- `docs/operations/OPERATING_GOVERNANCE.md` — 운영 거버넌스
- `docs/operations/WORKSPACE_STRUCTURE.md` — 저장소 구조 설명
- `docs/operations/BRAINS.md` — 2뇌 역할 분리
- `docs/operations/CONTRIBUTING.md` — Git/PR/커밋 규칙
- `docs/operations/OPENCLAW_RULES.md` — OpenClaw/로컬뇌 보조 규칙
- `docs/operations/OPENCLAW_SYSTEM_BASELINE.md` — 시스템 기준선/복구 보조 문서
- `docs/operations/PRIVATE_LOCAL_DOCS_POLICY.md` — 로컬 전용 문서 정책

## 5. 운영 프로그램
- `scripts/context_policy.py` — 메인 롤링 / 로컬뇌 flush / current-task snapshot / reload bundle / 토큰별 액션 판단
- `scripts/tasks/db.py` — 태스크 등록/전이 SSOT 관리
- `scripts/directives/db.py` — directive 등록/상태전이 SSOT 관리
- `scripts/heartbeat/local_brain_guard.py` — 로컬뇌/OpenClaw 상태 점검 및 복구 흐름 연동

## 6. 갱신 규칙
- 운영 문서 추가/삭제 시 이 문서를 먼저 갱신한다.
- 중복 인덱스는 보존하지 않는다.
- canonical 문서와 index 문서를 분리한다.
