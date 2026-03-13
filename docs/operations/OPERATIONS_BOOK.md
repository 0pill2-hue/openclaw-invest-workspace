# OPERATIONS BOOK

역할: **운영 문서 루트 인덱스**.

세부 규칙은 각 canonical 문서에 두고,
이 문서는 **무엇을 어디서 읽는지**만 짧게 안내한다.

## 핵심 canonical
- `docs/operations/context/CONTEXT_LOAD_POLICY.md` — 무엇을 언제 읽는지
- `docs/operations/context/CONTEXT_POLICY.md` — 컨텍스트 판단/복구 기준
- `docs/operations/governance/DOCUMENT_STANDARD.md` — 문서 작성/배치 표준
- `docs/operations/governance/OPERATING_GOVERNANCE.md` — 운영 원칙/SOP
- `docs/operations/runtime/PROGRAMS.md` — 프로그램 총람
- `docs/operations/runtime/MAIN_BRAIN_GUARD.md` — 상위 health/dispatch 가드
- `runtime/current-task.md` — 현재 작업 재개 카드
- `runtime/context-handoff.md` — reset/cutover 직후 인계 카드

## 카테고리 인덱스 (기본 로드 제외)
- `docs/operations/context/README.md`
- `docs/operations/governance/README.md`
- `docs/operations/runtime/README.md`
- `docs/operations/orchestration/README.md`
- `docs/operations/skills/README.md`

## 공개 저장소 루트 tracked 문서
- `AGENTS.md`
- `DIRECTIVES.md`
- `TASKS.md`

## 필요 시 추가 참고
- Git/PR 규칙: `docs/operations/governance/CONTRIBUTING.md`
- 저장소 구조: `docs/operations/governance/WORKSPACE_STRUCTURE.md`
- 2뇌 역할: `docs/operations/runtime/BRAINS.md`
- OpenClaw/로컬뇌 보조 규칙: `docs/operations/runtime/OPENCLAW_RULES.md`
- 로컬 전용 문서 정책: `docs/operations/governance/PRIVATE_LOCAL_DOCS_POLICY.md`

## 갱신 규칙
- 운영 문서 경로가 바뀌면 먼저 이 문서를 갱신한다.
- index는 링크만, 규칙은 canonical에 둔다.
- 사람용 explainer/diagram 문서는 기본 로드에 넣지 않는다.
