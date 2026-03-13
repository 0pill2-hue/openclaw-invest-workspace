# JB-20260312-STAGE3-WATCHER-TASK-SYNC-FIX

- ticket: JB-20260312-STAGE3-WATCHER-TASK-SYNC-FIX
- status: IN_PROGRESS
- title: Stage3 external watcher 감지/태스크 자동갱신 경로 점검 및 수정
- created_by: auto task event bridge
- created_at: 2026-03-12 23:23:31 KST

## Auto updates

### 2026-03-12 23:23:31 KST | implementation
- summary: Stage3 external custom watcher paths now auto-sync task updates, and the already-arrived batch_02b response was retroactively synced into the Stage3 task.
- phase: main_review
- detail: patched runtime/tmp/stage3_external_chatgpt_batch_runner.py and runtime/tmp/stage3_external_chatgpt_watch_url.py to add task-aware start sync + queue/task completion sync with default Stage3 task mapping
- detail: retrofit sync reopened JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION into awaiting_callback then advanced it to main_resume with watch-event proof
- proof:
  - `runtime/tmp/stage3_external_chatgpt_batch_runner.py`
  - `runtime/tmp/stage3_external_chatgpt_watch_url.py`
  - `runtime/tmp/stage3_external_batch_02b_watch_resume_result.json`
  - `runtime/tasks/proofs/watch-events/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION--stage3-batch-02b-complete-retrofit.md`
  - `runtime/watch/unreported_watch_events.json`
