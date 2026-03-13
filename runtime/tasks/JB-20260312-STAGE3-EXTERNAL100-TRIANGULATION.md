# JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION

- ticket: JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION
- status: IN_PROGRESS
- checked_at: 2026-03-12 09:54 KST

## Goal
산업/종목/매크로를 섞고 블로그/텔레그램/애널리스트 보고서 등 다양한 source를 섞은 100건 샘플로 local / main / external(ChatGPT Pro web) 삼각비교를 수행한다.

## What is ready now
- local 100-sample actual run proof exists:
  - `runtime/stage3_calibration_sample100.jsonl`
  - `runtime/tasks/JB-20260312-STAGE3-ACTUAL-CALIBRATION-RUN.md`
- main 100 actual run + compare is now complete:
  - `runtime/stage3_main_brain_package_sample100/main_brain_results_actual.jsonl`
  - `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json`
- external/web package contract and schema are already prepared:
  - `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
  - `runtime/tmp/stage3_external_web_package/`

## Current blocker
- external(ChatGPT Pro web) 100건 actual scoring은 아직 실행 전이다.
- 현재 남은 실작업은 package instance 생성 + batch prompt/attachment 정리 + external actual run 회수다.

## Next action
1. `runtime/tmp/stage3_external_web_package/` 아래에 실제 `sample_index.csv`, `attachment_inventory.csv`, `documents/S001..S100.md`를 채운 package instance를 만든다.
2. mixed 100을 20건 × 5배치로 나눠 external 제출 prompt를 생성한다.
3. external/web actual 결과를 회수해 local/main/external 시간·점수·근거 비교로 확장한다.
4. benchmark 종료 시 lane별 전체 DB 예상 소요시간도 함께 산출한다.

## Proof anchors
- main compare summary: `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json`
- external package spec: `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- external package template dir: `runtime/tmp/stage3_external_web_package/`

## 2026-03-12 direct-attachment run note (batch_01)
- method: direct attachments only (shared 5 + documents S001..S020 = 25 files)
- attach-list artifacts generated:
  - `runtime/tmp/stage3_external_web_package/attach_lists/batch_01_attach_list.txt`
  - `runtime/tmp/stage3_external_web_package/attach_lists/batch_02_attach_list.txt`
  - `runtime/tmp/stage3_external_web_package/attach_lists/batch_03_attach_list.txt`
  - `runtime/tmp/stage3_external_web_package/attach_lists/batch_04_attach_list.txt`
  - `runtime/tmp/stage3_external_web_package/attach_lists/batch_05_attach_list.txt`
- blocker: ChatGPT web sender failed before prompt send (`composer_not_found`, page title `잠시만 기다리십시오…`), so conversation URL was not created and watcher could not start.
- proofs:
  - `runtime/tmp/stage3_external_batch_01_direct_send_result.json`
  - `runtime/tmp/stage3_external_direct_run_summary.json`

## 2026-03-12 Pro-mode hard requirement blocker
- new rule: ChatGPT Pro mode only; if Pro mode cannot be verified, stop instead of proceeding.
- verification result: `not_verifiable_due_to_ui_interstitial`
- observed UI state: title `잠시만 기다리십시오…`, no composer, no fresh-chat control detected.
- proofs:
  - `runtime/tmp/stage3_external_pro_mode_check.json`
  - `runtime/browser-profiles/stage3_external_pro_mode_check.png`
  - `runtime/tmp/stage3_external_pro_mode_blocker.json`

## Auto updates

### 2026-03-12 23:22:56 KST | stage3 external watcher retrofit
- summary: Retroactive watcher start-sync applied because this Stage3 external run used an older/manual watch path without task-aware start hook.
- phase: awaiting_callback
- detail: batch_id=batch_02b conversation response already exists; reopening task into waiting state before syncing completion event
- proof:
  - `runtime/tmp/stage3_external_batch_02b_watch_resume_result.json`

### 2026-03-12 23:22:56 KST | watcher
<!-- task_event_id: stage3-batch_02b-complete-retrofit -->
- summary: watcher synced completion status=complete verdict=-
- phase: main_resume
- detail: status=complete verdict=- matched_by=explicit_task_id
- detail: url=https://chatgpt.com/c/69b2be7c-4ba4-83aa-8f7e-bf0f9eca6456
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/watch-events/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION--stage3-batch-02b-complete-retrofit.md`

### 2026-03-12 23:51:44 KST | stage3 external watcher
- summary: Stage3 ChatGPT watcher started; main should continue other non-conflicting backlog while waiting.
- phase: awaiting_callback
- detail: url=/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_web_package/split20/batch_01b_prompt.txt
- detail: timeout_seconds=1800 poll_seconds=5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_batch_01b_fresh1_watch_result.json`

### 2026-03-12 23:51:44 KST | stage3 external watcher
- summary: Stage3 ChatGPT watcher started; main should continue other non-conflicting backlog while waiting.
- phase: awaiting_callback
- detail: url=/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_web_package/split20/batch_02a_prompt.txt
- detail: timeout_seconds=1800 poll_seconds=5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_batch_02a_fresh1_watch_result.json`

### 2026-03-12 23:57:42 KST | stage3 external watcher
- summary: Stage3 ChatGPT watcher started; main should continue other non-conflicting backlog while waiting.
- phase: awaiting_callback
- detail: url=/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_web_package/split20/batch_02a_prompt.txt
- detail: timeout_seconds=1800 poll_seconds=5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_batch_02a_fresh2_watch_result.json`

### 2026-03-13 00:12:00 KST | subagent parallel re-collection
- summary: Owner instruction applied as fresh-chat parallel re-collection; kept batch_01b and batch_02a on separate fresh run ids so prior artifacts stay intact.
- phase: awaiting_callback
- detail: batch_01b_fresh1(pid=54470, session=mild-trail) running via task-aware stage3 runner; final conversation URL/result still pending until runner exits.
- detail: batch_02a_fresh1(pid=54469, session=plaid-breeze) failed early with upload toast `batch_manifest.json을(를) 업로드할 수 없습니다`.
- detail: batch_02a_fresh2(pid=54765, session=grand-dune) relaunched after the early upload blocker; final conversation URL/result still pending until runner exits.
- proof:
  - `runtime/tmp/stage3_external_parallel_recollect_status.json`

### 2026-03-13 00:28:15 KST | watcher
<!-- task_event_id: stage3-batch-02a-fresh2 -->
- summary: watcher synced completion status=timeout verdict=-
- phase: main_resume
- detail: status=timeout verdict=- matched_by=explicit_task_id
- detail: url=https://chatgpt.com/c/69b2d47b-0660-83a3-9688-a66e0f07c217
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/watch-events/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION--stage3-batch-02a-fresh2.md`

### 2026-03-13 07:15:55 KST | stage3 external watcher
- summary: Stage3 ChatGPT watcher started; main should continue other non-conflicting backlog while waiting.
- phase: awaiting_callback
- detail: url=/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_web_package/split20/batch_03b_prompt.txt
- detail: timeout_seconds=1800 poll_seconds=5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_batch_03b_run1_watch_result.json`

### 2026-03-13 07:32:12 KST | watcher
<!-- task_event_id: stage3-batch-03b-run1 -->
- summary: watcher synced completion status=complete verdict=-
- phase: main_resume
- detail: status=complete verdict=- matched_by=explicit_task_id
- detail: url=https://chatgpt.com/c/69b33b33-7810-83a6-874d-1ff0cfb05b55
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/watch-events/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION--stage3-batch-03b-run1.md`

### 2026-03-13 07:40:51 KST | watcher
<!-- task_event_id: stage3-batch-03a-run1 -->
- summary: watcher synced completion status=complete verdict=-
- detail: status=complete verdict=- matched_by=explicit_task_id
- detail: url=https://chatgpt.com/c/69b33b32-49dc-83a3-a06c-b96c266b2f8d
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/watch-events/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION--stage3-batch-03a-run1.md`

### 2026-03-13 08:10 KST | stage3 external triangulation snapshot
- summary: Web usable batches are now 02b/03a/03b, while 02a remains timeout; current external usable coverage is 25/100 samples (S036-S060 only).
- detail: `batch_02b` -> S036-S040, watcher retrofit proof says `complete`; normalized output exists at `runtime/tmp/stage3_external_batch_02b_watch_normalized.json`; status_counts=`scored 3 / ambiguous 2`; comparison_readiness=`ready_with_gaps`.
- detail: `batch_02a` -> S021-S035, watch result `timeout`; normalized output 미존재; last assistant text says focus-entity ID ambiguity was being checked; re-collection still needed.
- detail: `batch_03a` -> S041-S055, watch result `complete`; normalized output exists at `runtime/tmp/stage3_external_batch_03a_run1_watch_normalized.json`; status_counts=`scored 8 / insufficient_context 7`; comparison_readiness=`ready_with_gaps`.
- detail: `batch_03b` -> S056-S060, watch result `complete`; normalized output exists at `runtime/tmp/stage3_external_batch_03b_run1_watch_normalized.json`; status_counts=`scored 3 / insufficient_context 2`; comparison_readiness=`ready_with_gaps`.
- detail: usable external subtotal = scored 14 / ambiguous 2 / insufficient_context 9 across 25 recovered samples; no batch in this set reports observed timing fields inside normalized JSON.
- detail: local/main baseline remains complete for the 100-sample actual run (`rows_total=611`, `main_run_wall_time_sec=1021.0`, `local_runtime_ms_mean=1.4403`, `main_runtime_ms_mean=3429.7872`).
- detail: direct joined local/main/web per-sample comparison artifact for the recovered 25-sample window is 미확인 in this pass; if needed, build a dedicated join table from `sample_index.csv` + normalized web JSON + local/main source outputs.
- proof:
  - `runtime/tmp/stage3_external_batch_02b_watch_resume_result.json`
  - `runtime/tmp/stage3_external_batch_02a_fresh2_watch_result.json`
  - `runtime/tmp/stage3_external_batch_03a_run1_watch_normalized.json`
  - `runtime/tmp/stage3_external_batch_03b_run1_watch_normalized.json`
  - `runtime/stage3_main_brain_package_sample100/lane_comparison_summary_actual.json`

### 2026-03-13 08:16:55 KST | stage3 external watcher
- summary: Stage3 ChatGPT watcher started; main should continue other non-conflicting backlog while waiting.
- phase: awaiting_callback
- detail: url=/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_web_package/split20/batch_02a_prompt.txt
- detail: timeout_seconds=1800 poll_seconds=5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_batch_02a_run3_watch_result.json`

### 2026-03-13 08:33:39 KST | S036-S060 local/main realign kickoff
- summary: Did not wait for remaining external batches; resolved actual bridge from current external package and completed a fresh 25-sample local rerun for the web-usable window S036-S060.
- detail: bridge fixed as `external sample_id -> sample_index -> document_or_item_id == locator#record_id == input_31d.record_id`; this supersedes the stale `sample100 artifact mismatch` path for rerun purposes.
- detail: fresh local input created at `runtime/stage3_external_webusable_s036_s060_input25.jsonl` and actual local lane completed with `records_loaded=25`, `records_skipped_nosymbol=3`, `claim_cards_generated=95`, wall=`2.4598s`.
- detail: fresh main package prepared at `runtime/stage3_main_brain_package_s036_s060_web25` with `95` eval units and split into 3 ready-to-fill batches.
- detail: explicit blocker remains that repo has no automated in-tree main executor; actual main fill still needs manual/main-brain completion of prepared batch templates.
- phase: main_resume
- proof:
  - `runtime/tasks/proofs/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION_S036-S060_bridge_resolution.csv`
  - `runtime/tasks/proofs/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION_S036-S060_bridge_resolution.json`
  - `runtime/tasks/proofs/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION_S036-S060_realign_run.md`
  - `runtime/stage3_external_webusable_s036_s060_summary.json`
  - `runtime/stage3_main_brain_package_s036_s060_web25/run_status.json`

### 2026-03-13 08:35:53 KST | watcher
<!-- task_event_id: stage3-batch-02a-run3 -->
- summary: watcher synced completion status=complete verdict=-
- phase: main_resume
- detail: status=complete verdict=- matched_by=explicit_task_id
- detail: url=https://chatgpt.com/c/69b34980-9c74-83a9-a019-3138b965a1d5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/watch-events/JB-20260312-STAGE3-EXTERNAL100-TRIANGULATION--stage3-batch-02a-run3.md`

### 2026-03-13 11:37:10 KST | stage3 external watcher
- summary: Stage3 ChatGPT DOM watcher started; main should continue other non-conflicting backlog while waiting.
- phase: awaiting_callback
- detail: url=https://chatgpt.com/
- detail: timeout_seconds=1800 poll_seconds=5
- proof:
  - `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_batch_01a_t54_20260313113617_01_watch_resume_result.json`
