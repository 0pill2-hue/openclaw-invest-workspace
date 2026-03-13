# JB-20260311-HEARTBEAT-LLAMA-16K

- directive_id: JB-20260311-HEARTBEAT-LLAMA-16K
- status: IN_PROGRESS
- owner: main-orchestrator
- goal: heartbeat/local_brain_guard 기준 llama-server context를 16k로 올리고, llama-server를 1회 리셋한 뒤 후속 작업을 이어간다.
- constraints: Gateway 재시작 금지. 삭제/배포/외부전송 없음.
- proof_log:
  - 2026-03-11 13:54 KST: 사용자 지시를 task/directive로 등록하고 구현 착수.
  - 2026-03-11 13:55 KST: HEARTBEAT.md와 scripts/heartbeat/local_brain_guard.py의 llama-server context 기본값을 16k(16384)로 상향.
  - 2026-03-11 13:55 KST: llama-server를 1회 재시작했고 wait_for_llama 기준 정상 응답 확인(ctx=16384).
  - 2026-03-11 13:56 KST: assign-pool의 idle을 정상 종료로 처리하도록 scripts/tasks/db.py와 scripts/tasks/dispatch_tick.py를 보정하고 launchctl kickstart 후 auto-dispatch last_exit_code=0으로 회복.
  - 2026-03-11 13:56 KST: python3 scripts/heartbeat/main_brain_guard.py 재확인 결과 MAIN_BRAIN_GUARD_OK.
  - 2026-03-11 13:57 KST: assigned main orchestration turn에서 proof를 확정하고 ticket/directive를 DONE으로 종결.
