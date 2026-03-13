# JB-20260311-SUBAGENT-WAITING-CLEANUP

- directive_id: JB-20260311-SUBAGENT-WAITING-CLEANUP
- status: IN_PROGRESS
- owner: main-orchestrator
- goal: 살아 있지 않은 subagent callback/waiting 티켓을 정리하고 current-task/context-handoff를 열린 작업 기준으로 정상화한다.
- constraints: 삭제/배포/외부전송 없음.
- proof_log:
  - 2026-03-11 14:00 KST: stale subagent waiting 티켓 정리 작업을 등록.
  - 2026-03-11 14:01 KST: sessions/subagents 점검 결과 active subagent는 0개였고, selected_articles/PDF recovery/overnight observer 티켓의 child session은 비어 있거나 원래 작업과 무관한 heartbeat 기록으로 대체되어 stale delegation으로 판정.
  - 2026-03-11 14:01 KST: JB-20260311-SELECTED-ARTICLES-ALT-PATH, JB-20260311-PDF-EXTRACT-COUNT-RECOVERY, JB-20260311-OVERNIGHT-LINK-PDF-CONTROL, JB-20260311-PDF-DELIVERABLE-CRITERIA-LOCK의 phase/blocked_reason을 stale delegation 기준으로 갱신하고 false lease를 release 처리.
  - 2026-03-11 14:02 KST: stale waiting 정리 후 current-task를 cleanup 티켓으로 재스냅샷했고, active subagent 0 / stale delegation 4건 반영 상태를 list로 즉시 검증했다.
