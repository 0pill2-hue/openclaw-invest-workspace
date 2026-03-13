# JB-20260312-WATCHER-TASK-INTEGRATION

- ticket: JB-20260312-WATCHER-TASK-INTEGRATION
- status: DONE
- checked_at: 2026-03-12 22:22 KST

## Goal
돌아가는 프로그램(watcher)이 대기만 하지 않고, ChatGPT/external completion이 오면
1) 매핑 가능한 기존 task를 자동 갱신하고
2) 매핑 불가면 새 task를 자동 등록하도록 watcher->task 연동을 강화한다.

## Applied design
- completion 이벤트를 queue에 넣는 기존 경로는 유지하고, queue sync 단계에서 task 처리 분기 강화:
  - existing task resolve 성공 -> `updated_existing`
  - existing task resolve 실패 + allow_create -> `created_new`
  - 실패/보류 -> `pending_unmapped`
- 기존 task 갱신 시에는 단순 queue 필드만 바꾸지 않고, task 문서/증빙도 자동 반영:
  - watcher proof md 생성
  - taskdb note/proof/last_activity 갱신
  - `scripts/tasks/record_task_event.py` 호출로 task md에 concise event block 추가 + touch

## Code changes
- `skills/web-review/scripts/watch_chatgpt_response.py`
  - `--task-id` 인자 경로로 queue sync에 explicit mapping 전달
  - queue 기록 시 `sync_event_to_task(...)` 연동 유지
- `skills/web-review/scripts/sync_watch_event_to_task.py`
  - 기존 task auto-update / 미매핑 fallback create 경로 정리
  - existing task 갱신 후 `scripts/tasks/record_task_event.py`로 task 문서 append/touch 연동
- `skills/web-review/scripts/escalate_unreported_watch_events.py`
  - stale unacked 이벤트를 sync 경로로 승격(기존/신규 task 분기)
- `scripts/tasks/record_task_event.py` (new)
  - 범용 task-event 기록 유틸
  - task md에 event block append(중복 event id 방지)
  - taskdb touch/phase 갱신 실행

## Focused verification
1) Syntax check
- `python3 -m py_compile scripts/tasks/record_task_event.py skills/web-review/scripts/sync_watch_event_to_task.py skills/web-review/scripts/watch_chatgpt_response.py skills/web-review/scripts/escalate_unreported_watch_events.py`

2) Existing-task mapping path (actual)
- test queue: `runtime/tmp/test_watch_sync_queue_mapped.json`
- command:
  - `python3 skills/web-review/scripts/sync_watch_event_to_task.py --queue-file runtime/tmp/test_watch_sync_queue_mapped.json --event-id test-watch-map-1`
- result:
  - action=`updated_existing`
  - task_id=`JB-20260312-WATCHER-TASK-INTEGRATION`
  - proof 생성 + task md append + taskdb touch 확인

3) Unmapped fallback path (dry-run)
- test queue: `runtime/tmp/test_watch_sync_queue_unmapped.json`
- command:
  - `python3 skills/web-review/scripts/sync_watch_event_to_task.py --queue-file runtime/tmp/test_watch_sync_queue_unmapped.json --event-id test-watch-unmapped-1 --allow-create --dry-run`
- result:
  - action=`created_new`
  - fallback task id/proof path 계산 확인

4) Escalation wrapper dry-run
- command:
  - `python3 skills/web-review/scripts/escalate_unreported_watch_events.py --queue-file runtime/tmp/test_watch_sync_queue_unmapped.json --older-than-seconds 0 --dry-run`
- result:
  - stale queue event가 `created_new` 경로로 승격 판정됨

## Proof
- `scripts/tasks/record_task_event.py`
- `skills/web-review/scripts/sync_watch_event_to_task.py`
- `skills/web-review/scripts/watch_chatgpt_response.py`
- `skills/web-review/scripts/escalate_unreported_watch_events.py`
- `runtime/tmp/test_watch_sync_queue_mapped.json`
- `runtime/tmp/test_watch_sync_queue_unmapped.json`
- `runtime/tasks/proofs/watch-events/JB-20260312-WATCHER-TASK-INTEGRATION--test-watch-map-1.md`
