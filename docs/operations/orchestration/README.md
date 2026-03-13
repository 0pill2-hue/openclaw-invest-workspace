# orchestration

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

역할: **사람이 읽는 orchestration 설명/다이어그램 묶음**.

이 폴더는 background program / auto-dispatch / task-aware runner 흐름을
사람이 빠르게 이해하도록 정리한 **explainer 레이어**다.
규칙의 canonical source는 아래 문서에 남기고,
여기서는 **배경/흐름/다이어그램/연결 지도**만 제공한다.

## canonical source map
- `TASKS.md` — task 상태/phase/waiting contract SSOT
- `scripts/README.md` — 실제 스크립트 호출 예시
- `docs/operations/context/CONTEXT_LOAD_POLICY.md` — 기본 로드/옵션 로드 정책
- `docs/operations/runtime/MAIN_BRAIN_GUARD.md` — watchdog/auto-dispatch 상위 운영 가드
- `docs/operations/runtime/PROGRAMS.md` — 프로그램 총람

## 이 폴더의 원칙
- 규칙 장문 복제 금지
- command reference 장문 복제 금지
- diagram/explainer는 **기본 로드 제외**
- 규칙이 바뀌면 먼저 canonical 문서를 갱신하고, 여기서는 링크/설명만 맞춘다

## 문서
- `NONIDLE_ORCHESTRATION_GUIDE.md` — non-idle orchestrator 개념/상태/파일 맵 설명
- `diagrams/NONIDLE_ORCHESTRATION_FLOW.md` — task lifecycle / detached wait / resume 흐름도

## 언제 읽는가
- 주인님이 구조를 한눈에 보고 싶을 때
- auto-dispatch / watcher / backgrounded state 관계를 시각적으로 확인할 때
- 새 세션에서 규칙이 아니라 **맥락/구조**만 빠르게 복습할 때

기본 세션 로드에서는 이 폴더를 자동으로 읽지 않는다.
