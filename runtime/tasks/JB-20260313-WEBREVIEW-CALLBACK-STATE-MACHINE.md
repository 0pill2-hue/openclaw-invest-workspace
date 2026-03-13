# JB-20260313-WEBREVIEW-CALLBACK-STATE-MACHINE

- ticket: JB-20260313-WEBREVIEW-CALLBACK-STATE-MACHINE
- status: IN_PROGRESS
- checked_at: 2026-03-13 14:25 KST

## Goal
web-review watcher를 단순 queue writer가 아니라 taskdb callback state machine의 정식 producer로 개편한다.

## Landed
1. **watcher task-bound callback contract 적용**
   - `skills/web-review/scripts/watch_chatgpt_response.py`
     - normal task-bound path에서 `--task-id + --event-id + --callback-token` 동시 요구
     - watcher 시작 시 `scripts/tasks/db.py detach-watch`를 호출해 formal callback contract 생성
     - `detach-watch`가 `awaiting_callback` + `callback_state=detached` + assignee release를 한 번에 수행
   - `scripts/tasks/db.py`
     - `detach-watch` primitive 추가
     - `callback-complete`에 `--resume-phase/--resume-note` 추가해서 web-review completion이 terminal DONE이 아니라 `main_resume` 복귀로 이어질 수 있게 확장

2. **completion path를 callback-complete/fail로 일원화**
   - `skills/web-review/scripts/sync_watch_event_to_task.py`
     - existing task match 시 더 이상 note/proof만 덧붙이지 않고 `db.py callback-complete` 또는 `db.py callback-fail`을 실제 호출
     - success path는 `main_resume` 복귀, failure path는 `callback_failed` phase + BLOCKED 처리

3. **sync false positive 제거**
   - queue/event ledger에 `task_match_status`, `task_apply_status`, `task_result_status`, `task_apply_error`, `task_apply_attempts`, `retries`를 분리 기록
   - `matched_existing`만으로 성공 취급하지 않고 callback apply / task_event append까지 포함한 결과를 `success|partial|error`로 구분
   - `skills/web-review/scripts/escalate_unreported_watch_events.py`가 `task_apply_status != success`인 stale event를 재시도 대상으로 취급

4. **completion detection 강화 + debug field 확장**
   - `skills/web-review/scripts/watch_chatgpt_response.py`
     - assistant selector path, assistant chars, assistant sha1, generation indicator, pending reason, stable hash polls를 수집
     - intro-only / generating / too-short / unstable 응답을 pending/partial로 남기고, 안정화된 assistant turn 기준으로만 completion 판정

5. **queue를 callback/report ledger로 승격**
   - `runtime/watch/unreported_watch_events.json` event schema를 v2 성격으로 확장
   - `task_id`, `source_task_id`, `parent_task_id`, `callback_token`, `callback_status`, `report_status`, `report_delivered_at`, `acked_at`, `errors`, `retries` 등 기록

6. **fallback task linkage 추가**
   - `sync_watch_event_to_task.py` fallback create 경로에 `source_task_id`, `parent_task_id`, `callback_token`, `watch_event_id` note/proof 반영

7. **ack/report contract hardening**
   - `skills/web-review/scripts/ack_watch_event.py`
     - apply success 전 ack 금지
     - `--report-delivered` 없이 ack 금지
     - ack 시 `report_status=acked` + `report_delivered_at` + `acked_at` 기록

8. **SKILL.md 계약 문구 동기화**
   - watcher normal path의 mandatory args
   - detach-watch / callback-complete/fail flow
   - queue ledger / ack / retry semantics 반영

## Remaining
- `send_chatgpt_new_chat_prompt.py`는 이번 티켓 범위에서 변경 불필요로 유지했다. 현재 계약상 blocker는 아님.
- 실제 ChatGPT live DOM end-to-end는 bounded validation 범위 밖이라 미실시. 이번 턴에서는 CLI/queue/state-machine 중심 검증만 수행했다.

## Changed files
- `skills/web-review/SKILL.md`
- `skills/web-review/scripts/watch_chatgpt_response.py`
- `skills/web-review/scripts/sync_watch_event_to_task.py`
- `skills/web-review/scripts/escalate_unreported_watch_events.py`
- `skills/web-review/scripts/ack_watch_event.py`
- `scripts/tasks/db.py`

## Validation
1. **syntax**
   - `python3 -m py_compile scripts/tasks/db.py skills/web-review/scripts/watch_chatgpt_response.py skills/web-review/scripts/sync_watch_event_to_task.py skills/web-review/scripts/escalate_unreported_watch_events.py skills/web-review/scripts/ack_watch_event.py`

2. **temp taskdb callback state machine**
   - temp DB: `/tmp/jb_webreview_callback_test2.db`
   - verified:
     - `detach-watch` clears assignee and sets detached callback contract
     - `callback-complete --resume-phase main_resume` returns task to resumable `IN_PROGRESS/main_resume`
     - `callback-fail` yields `BLOCKED/callback_failed` and clears `resume_due`

3. **ack/report hardening**
   - temp queue: `/tmp/jb_watch_queue_test.json`
   - verified:
     - ack without `--report-delivered` fails with `report_not_marked_delivered`
     - ack with `--report-delivered` succeeds and records `report_status=acked`

4. **escalator retry rule**
   - temp queue: `/tmp/jb_watch_queue_retry.json`
   - verified:
     - `task_apply_status=error` stale event is retried by escalator dry-run and no longer skipped as a false positive

5. **watcher contract guard**
   - verified:
     - `watch_chatgpt_response.py --task-id ... --event-id ...` without `--callback-token` exits with `invalid_callback_contract`

## Proof
- `skills/web-review/SKILL.md`
- `skills/web-review/scripts/watch_chatgpt_response.py`
- `skills/web-review/scripts/sync_watch_event_to_task.py`
- `skills/web-review/scripts/escalate_unreported_watch_events.py`
- `skills/web-review/scripts/ack_watch_event.py`
- `scripts/tasks/db.py`
- `/tmp/jb_webreview_callback_test2.db`
- `/tmp/jb_watch_queue_test.json`
- `/tmp/jb_watch_queue_retry.json`
