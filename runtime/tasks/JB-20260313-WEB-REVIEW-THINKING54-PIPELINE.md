# JB-20260313-WEB-REVIEW-THINKING54-PIPELINE

- ticket: JB-20260313-WEB-REVIEW-THINKING54-PIPELINE
- status: IN_PROGRESS
- checked_at: 2026-03-13 11:25 KST

## Goal
web-review/Stage3 external web 경로를 ChatGPT Thinking 5.4 기준으로 바꾸고, batch별 전송은 fresh chat으로 연속 제출한 뒤 watcher가 별도로 회수하도록 정리한다.

## Current understanding
- current Stage3 external actual runner is `runtime/tmp/stage3_external_chatgpt_batch_runner.py`.
- this runner imports watch queue helpers from `skills/web-review/scripts`, but model selection and send/watch flow are implemented ad-hoc inside the runtime/tmp runner.
- current runner explicitly uses `ensure_pro54()` and then waits for response inside the same process, which is contrary to the requested `send continuously first, wait later` pattern.

## Next action
- patch source instructions and runner logic for Thinking 5.4 selection
- split `send` from `watch` or add a no-wait handoff mode so batches can be launched in fresh chats continuously
- sync web-review skill deployment copy
- then use the updated path for remaining Stage3 external sends only if still needed
