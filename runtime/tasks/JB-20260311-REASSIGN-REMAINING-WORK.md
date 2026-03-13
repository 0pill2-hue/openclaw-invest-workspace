# JB-20260311-REASSIGN-REMAINING-WORK

- directive_id: JB-20260311-REASSIGN-REMAINING-WORK
- status: IN_PROGRESS
- owner: main-orchestrator
- goal: 남은 작업을 main/sub lane으로 재배정하고 실제 완료될 때까지 진행한다.
- decision:
  - main lane: selected_articles blocker 해소(판단/정책/정리 비중 큼)
  - subagent lane: PDF extract/count recovery rerun + DB reflection(장시간 실행/증빙 수집)
- constraints: 삭제/배포/외부전송 없음.
- proof_log:
  - 2026-03-11 14:12 KST: 남은 작업 재배정/지속실행 전용 task/directive 등록.
  - 2026-03-11 14:14 KST: selected_articles live dir를 재검사한 결과 `selected_articles_20260311-025510.jsonl` mixed-source file이 다시 들어와 있었고, 원인은 `news_backfill`/`stage01_backfill_10y.py`가 generic collector를 live selected_articles에 직접 쓰는 경로임을 확인.
  - 2026-03-11 14:14 KST: `stage01_daily_update.py`의 `news_backfill`과 `stage01_backfill_10y.py`에서 generic selected_articles step을 제거해, selected_articles가 별도 verifiable lane만 쓰도록 재오염 경로를 차단.
  - 2026-03-11 14:14 KST: `JB-20260311-PDF-EXTRACT-COUNT-RECOVERY`는 fresh subagent `agent:main:subagent:71d02d1c-0dec-4f2e-9ae3-1e43de7945e3`에 재위임했다.
  - 2026-03-11 14:15 KST: orchestrator turn 기준 아직 close 불가. selected_articles는 active raw_db_sync writer(pid 62348) 종료 후 clean rerun이 필요하고, PDF recovery는 fresh subagent completion을 기다리는 중이라 umbrella ticket을 BLOCKED로 전환.
- 2026-03-11 15:07 KST: stale backlog 재배정 목적은 달성됐다. PDF recovery/overnight closeout은 DONE, selected_articles와 stage contract align은 개별 티켓으로 계속 추적하므로 umbrella coordination ticket은 종료한다.
