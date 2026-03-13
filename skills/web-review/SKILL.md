---
name: web-review
description: Prepare and use ChatGPT web review flows for (a) repo/code/doc change review and (b) Stage3 external-primary batch scoring packages for mixed analysis items. Default to ChatGPT Thinking 5.4 unless the user explicitly requires another model. For review_mode, require git commit + git push and use the commit as baseline. For batch_scoring_mode, use the attached package/manifest as baseline, preserve mixed/chatter/opinion/no-symbol items, and request exactly one JSON object matching the runtime schema. Prefer the local Playwright + Chrome cookie-injected automation path when available.
---

# Web Review

Use this skill when 주인님 wants an external **ChatGPT web flow**. Default model target is **Thinking 5.4** unless 주인님 explicitly asks for another tier/model.

## Choose exactly one mode

### `review_mode`
- use for repo/code/doc change review
- baseline = pushed git commit only
- canonical prompt = `runtime/templates/web_review_review_mode_prompt.txt`
- canonical response schema = `runtime/templates/web_review_review_mode_response_schema.json`

### `batch_scoring_mode`
- use for Stage3 external-primary scoring
- baseline = attached package + `batch_manifest.json`
- package data contract = `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- canonical prompt = `runtime/templates/stage3_external_review_prompt.txt`
- canonical response schema = `runtime/templates/stage3_response_schema.json`
- preserve mixed/chatter/opinion/no-symbol items; the unit is an **analysis item**, not a stock sample

## Source-of-truth and deployment
- Edit the tracked source at `/Users/jobiseu/.openclaw/workspace/skills/web-review`.
- Treat `~/.agents/skills/web-review` as the deployed runtime copy that OpenClaw loads.
- After source edits, run `bash /Users/jobiseu/.openclaw/workspace/scripts/skills/sync_web_review_skill.sh`.
- Keep script references relative so the same SKILL works from either location.

## Common orchestration rules
- Prefer the local Playwright + Chrome cookie-injected session path first.
- Use a fresh ChatGPT new chat for each request.
- After capture, delete that chat so review threads do not accumulate.
- Verify/select **Thinking 5.4** before sending unless 주인님 explicitly asked for another model.
- When 주인님 explicitly requires direct file attachment, attach the real files themselves.
- Before sending, verify the attachment chips/list are visible in the composer.
- In this UI, direct attachment may effectively top out around **20 files per fresh chat**. Keep attachment count below that ceiling, and for Stage3 mixed-item runs target **20-40 items per batch** (default target = 30) via compact packages/partitions rather than prompt/template duplication.
- After attachments are visible and the prompt is filled, try **`Enter` then `Meta+Enter`** before concluding send failed.
- For completion handling, treat JSON or clearly JSON-shaped replies as successful capture; do not rely only on verdict tokens.
- Raw watcher text save is **OFF by default**. Only use `--debug-save-raw` when cold forensic capture is explicitly needed.
- Do not use `grep -R` against runtime raw/log/tmp trees. Use `python3 scripts/tasks/db.py evidence-search` first; add `--include-raw` only with explicit justification.

## `review_mode` workflow
1. Make the repo current on GitHub: `git status`, commit if needed, `git push`, `git rev-parse HEAD`, `git branch --show-current`.
2. Treat `<commit_hash>` as the only baseline; include extra context only when the commit alone is insufficient.
3. Fill the prompt from `runtime/templates/web_review_review_mode_prompt.txt` and use the matching response schema.
4. Capture exactly one short JSON object.
5. Review the answer before applying anything. Decide `APPLY` / `REJECT` / `NEED_MORE_CONTEXT` yourself.
6. Report the review result briefly to 주인님 first; do not auto-create follow-up improvements just because a web answer arrived.

## `batch_scoring_mode` workflow
1. Build or inspect the package per `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`.
2. Keep package expression compact: `item_id`, `item_type`, `title`, `source_kind`, `published_at_utc`, `locator`, curated `source_text`, and one-line `minimal_operator_notes` are the center of gravity.
3. Keep one canonical prompt/schema template in `runtime/templates/`; do **not** create per-run full prompt copies or `results_template` copies unless a debug exception is explicitly required.
4. Use `runtime/templates/stage3_external_review_prompt.txt` and `runtime/templates/stage3_response_schema.json`; package attachments are the baseline, repo commit is provenance only.
5. Partition mixed-item batches at **20-40 items** (default target = 30) and carry `partition_index`, `partition_count`, and `partial_failure.failed_item_ids` metadata so failed subsets can be repartitioned without rerunning the full package.
6. Send via fresh chat with direct attachments and Thinking 5.4.
7. Start the watcher instead of waiting in place.
8. Capture JSON only and validate against the runtime schema.
9. After capture, compact runtime outputs with `python3 scripts/stage3/compact_runtime_outputs.py <run_dir>` and keep only manifest/result/summary/card/proof-index as hot artifacts.
10. Route malformed, partial, or high-ambiguity batches to Stage3 adjudication / exception review.

## Queue / watcher discipline
- On the normal task-bound path, watcher start must create a formal callback contract first: pass `--task-id`, `--event-id`, and `--callback-token` together.
- When the response is captured, write the watcher JSON and record completion into `runtime/watch/unreported_watch_events.json` first.
- Completion sync must go through taskdb callback APIs (`callback-complete` / `callback-fail`).
- Ack after result delivery only: `python3 scripts/ack_watch_event.py --event-id <stable-id> --report-delivered`.
- Retry/escalate stale or failed-apply events: `python3 scripts/escalate_unreported_watch_events.py --older-than-seconds 90`.

## Browser scripts
- sender: `python3 scripts/send_chatgpt_new_chat_prompt.py --prompt-file <prompt.txt> [--attach-list-file <paths.txt>] --headful --screenshot <png>`
- watcher: `python3 scripts/watch_chatgpt_response.py --url '<chat-url>' --poll-seconds 15 --timeout-seconds 900 --headful --delete-after --output-json <result.json> --record-unreported-queue --task-id <ticket> --event-id <stable-id> --callback-token <token> --screenshot <png>`
- cold raw debug opt-in only: append `--debug-save-raw` when a forensic copy is required; raw text will be written under `runtime/watch/raw/` instead of the hot watcher JSON.

## Human-facing overview docs
- `docs/operations/skills/web-review.md`
- `docs/operations/skills/web-review-templates.md`
