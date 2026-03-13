# JB-20260311-POLICY-CONFLICT-AUDIT

- directive_id: JB-20260311-POLICY-CONFLICT-AUDIT
- status: IN_PROGRESS
- owner: main-orchestrator
- goal: 메인/서브 non-idle 병행 원칙과 충돌하는 기존 원칙/지시를 찾아 최신 운영 기준으로 정리한다.
- proof_log:
  - 2026-03-11 14:55 KST: 정책 충돌 감사/수정 작업 등록.
  - 2026-03-11 14:56 KST: 충돌 원칙으로 directive `3737`(작업 순서를 순차 처리로 고정)와 `미확인-0145`(Stage1부터 순차 실행)를 식별.
  - 2026-03-11 14:56 KST: 두 directive를 최신 non-idle 병행 원칙에 맞게 superseded 처리(block)하고, AGENTS.md에 순차 실행은 동일 파이프라인/동일 writer chain에만 적용된다는 범위를 명시.
