# JB-20260312-WATCH-EVENT-QUEUE

## Goal
watcher completion을 먼저 durable 미보고 큐에 적재하고, ack가 늦으면 taskdb로 승격되는 최소 운영경로를 만든다.

## Applied
- `skills/web-review/scripts/watch_chatgpt_response.py`에 아래 옵션을 추가했다.
  - `--output-json`
  - `--record-unreported-queue`
  - `--queue-file`
  - `--event-id`
  - `--follow-up-required`
- watcher 성공 결과를 `runtime/watch/unreported_watch_events.json` 큐에 upsert하는 로직을 넣었다.
- `skills/web-review/scripts/ack_watch_event.py`를 추가해 보고 후 queue ack를 처리할 수 있게 했다.
- `skills/web-review/scripts/escalate_unreported_watch_events.py`를 추가해 미보고 event를 task 승격 대상으로 판정할 수 있게 했다.
- `docs/operations/skills/web-review.md`와 skill 본문에 queue/ack/escalate 사용법을 문서화했다.

## Verification
- `.venv/bin/python`으로 watcher queue record 함수 실행
- `python3 skills/web-review/scripts/ack_watch_event.py --queue-file runtime/tmp/test_unreported_watch_events.json --event-id test-watch-event`
- `python3 skills/web-review/scripts/escalate_unreported_watch_events.py --queue-file runtime/tmp/test_unreported_watch_events.json --older-than-seconds 90 --dry-run`

## Test result
- test event queue 적재 성공
- ack 성공
- 200초 경과한 test event가 dry-run 승격 대상으로 1건 검출됨

## Proof
- `skills/web-review/scripts/watch_chatgpt_response.py`
- `skills/web-review/scripts/ack_watch_event.py`
- `skills/web-review/scripts/escalate_unreported_watch_events.py`
- `runtime/tmp/test_unreported_watch_events.json`
- `docs/operations/skills/web-review.md`
- `skills/web-review/SKILL.md`
