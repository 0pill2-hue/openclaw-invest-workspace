---
name: web-review
description: Prepare and use a ChatGPT web review flow for code changes. Default to ChatGPT Thinking 5.4 unless the user explicitly requires another model. Use when the user wants an external ChatGPT-on-the-web review of a repo/change before applying it. Before every use, require git commit + git push so GitHub is current, capture branch + commit hash, tell the reviewer to ignore prior context and use only that commit as the baseline, and request a tiny code-block/JSON answer only. Prefer the local Playwright + Chrome cookie-injected automation path when available. The assistant must review the returned answer before applying anything.
---

# Web Review

Use this skill when 주인님 wants an external **ChatGPT web review** before deciding whether to apply a change. Default model target is **Thinking 5.4** unless 주인님 explicitly asks for another tier/model.

## Source-of-truth and deployment
- Edit the tracked source at `/Users/jobiseu/.openclaw/workspace/skills/web-review`.
- Treat `~/.agents/skills/web-review` as the deployed runtime copy that OpenClaw loads.
- After source edits, run `bash /Users/jobiseu/.openclaw/workspace/scripts/skills/sync_web_review_skill.sh` to refresh the deployed copy.
- Keep script references relative (for example `scripts/watch_chatgpt_response.py`) so the same SKILL works from either location.

## Hard rules
- Before asking ChatGPT on the web, always make the repo current on GitHub:
  1. `git status`
  2. `git add -A && git commit ...` (or confirm clean tree)
  3. `git push`
  4. `git rev-parse HEAD`
  5. `git branch --show-current`
- Treat `<commit_hash>` as the only baseline. In the prompt, explicitly say: **ignore previous conversation/context; use only this commit as baseline**.
- Ask for a **short code block only**. No long prose.
- Do not apply the web answer blindly. Review it first, then decide APPLY / REJECT / NEED_MORE_CONTEXT.
- Even when a review answer arrives, do **not** auto-create improvements or start implementation immediately.
- First, report the review result back to 주인님 in a concise summary.
- The assistant must judge whether modification is actually needed.
- If modification is needed, the assistant should automatically open the proper task/directive/proof flow and then proceed.
- If the repo is private or the commit alone is insufficient, include only the minimum extra context needed: goal, touched files, and a tiny diff/snippet.
- Prefer the local Playwright + Chrome cookie-injected session path first.
- Use a fresh ChatGPT new chat for each web-review request.
- After the answer is captured, delete that chat so review threads do not accumulate.
- Do not depend on a specific ChatGPT project/workspace for web-review.
- Default model target for this environment is **Thinking 5.4**. Verify/select it via the model selector before sending unless 주인님 explicitly asked for another model/tier.
- When 주인님 explicitly requires **ChatGPT Pro model selection**, verify/select that exact model instead of the default.
- Do not misread the first `+` menu as attachment-only and stop early when the UI exposes model choices there; inspect the visible model selector path that actually appears in the current session.
- For multi-batch review workloads, do **not** wait for one chat to finish before sending the next. Send each batch in a fresh chat, capture the conversation URL, start a watcher, then continue to the next fresh chat.
- When 주인님 explicitly requires **direct file attachment**, attach the real files themselves in ChatGPT. Do **not** replace the primary document set with a compiled surrogate file unless 주인님 explicitly allows that fallback.
- Before sending, verify the attachment chips/list are visible in the composer so the real files are actually queued.
- In this ChatGPT UI, direct attachment may effectively top out around **20 files per fresh chat**; if a larger set causes `파일 추가 불가능` or stalls attachment, split the package into fresh-chat batches of **20 files or fewer** instead of reverting to compiled surrogate files.
- In this ChatGPT UI, send may require keyboard fallback. After attachments are visible and the prompt is filled, try **`Enter` then `Meta+Enter`** before concluding that send failed.
- For benchmark/review watches, do not rely only on `APPLY|REJECT|NEED_MORE_CONTEXT` verdict tokens. Large assistant replies may arrive as raw JSON without verdict words, so watcher/completion handling must treat JSON or clearly JSON-shaped replies as successful capture.

## Fixed question format
Use this exact structure by default when asking ChatGPT web:

```txt
Use ONLY this baseline:
- repo: <repo_name>
- repo_url: <github_repo_url>
- branch: <branch_name>
- commit: <commit_hash>
- commit_url: <github_commit_url_if_available>

Ignore all prior conversation/context/memory.
If the commit alone is not enough, return NEED_MORE_CONTEXT instead of guessing.

Goal:
<1-3 short lines>

Scope:
- area: <folder / subsystem / docset>
- read: <read all relevant docs/code under this scope>
- focus: <must-fix issues / contradictions / best improvements>

Optional minimal context (only if needed):
- anchor files: <a few representative paths>
- tiny diff/snippet: <minimum only>

Return ONLY one JSON code block.
No prose.
```

## Fixed answer format
Preferred response format (slightly richer but still concise):

```json
{"decision":"APPLY|REJECT|NEED_MORE_CONTEXT","must_fix":["..."],"improvements":["..."],"risks":["..."],"token_cost":"LOW|MEDIUM|HIGH","questions":["..."]}
```

Ultra-short fallback:

```txt
APPLY|REJECT|NEED_MORE_CONTEXT
- must_fix: <none or short item>
- improvement: <short item>
- token_cost: LOW|MEDIUM|HIGH - <short reason>
```

## Prompt template
Fill this in with the current repo/task and give it to ChatGPT web:

```txt
Use ONLY this baseline:
- repo: <repo_name>
- repo_url: <github_repo_url>
- branch: <branch_name>
- commit: <commit_hash>
- commit_url: <github_commit_url_if_available>

Ignore all prior conversation/context/memory.
If the commit alone is insufficient, answer NEED_MORE_CONTEXT instead of guessing.

Goal:
<1-3 short lines>

Scope:
- area: <folder / subsystem / docset>
- read: <read all relevant docs/code under this scope>
- focus: <must-fix issues / contradictions / best improvements>

Optional minimal context (only if needed):
- anchor files: <a few representative paths>
- tiny diff/snippet: <minimum only>

Return ONLY one JSON code block in this schema:
{"decision":"APPLY|REJECT|NEED_MORE_CONTEXT","must_fix":["..."],"improvements":["..."],"risks":["..."],"token_cost":"LOW|MEDIUM|HIGH","questions":["..."]}

No prose outside the code block.
```

## Assistant workflow
1. Verify repo state is committed and pushed.
2. Capture `branch`, `commit_hash`, and `github_repo_url` (plus `commit_url` when available).
3. Build the prompt above.
   - Default to **area/folder-level review**, not a tiny file list.
   - Ask the reviewer to read the relevant docs/code under that scope.
   - Use anchor files only as entry points, not as the whole review boundary.
4. Send the prompt in a fresh ChatGPT new chat. Use the bundled sender script if browser automation is available.
5. Do **not** wait in-place for long responses. Start/trigger a DOM watcher and continue other tasks.
6. When the response is captured, write the watcher JSON and record the completion into `runtime/watch/unreported_watch_events.json` first.
7. After you actually report the result to 주인님, immediately ack that queue item.
8. If the queue item is still unacked after the policy window (default 90 seconds), escalate it into taskdb.
9. Use `scripts/watch_chatgpt_response.py` to poll the chat DOM until the response finishes or a verdict token appears.
10. When DOM watcher is available, do **not** use periodic 5-minute reminder checks as the default path.
11. Parse the returned code block only.
12. Summarize the review result for 주인님 first, in a short actionable form.
13. Only after that ack the queued watch event.
14. Decide:
   - `APPLY`: a change is truly needed and should be implemented
   - `REJECT`: low value / unsafe / off-target / no change needed
   - `NEED_MORE_CONTEXT`: collect the smallest missing context and retry
15. If the decision implies a real change, automatically open the appropriate task/directive/proof path before implementation.
16. After applying, verify locally.

## New-chat sender
Browser automation is expected to be available here via the proven Playwright + live Chrome cookie-injected session path. Prefer the bundled sender script so each review starts in a fresh chat, and do not claim the path is unavailable unless it has been rechecked and actually failed.

Example:

```bash
python3 scripts/send_chatgpt_new_chat_prompt.py \
  --prompt-file runtime/tmp/web_review_prompt.txt \
  --headful \
  --screenshot runtime/browser-profiles/web-review-send.png
```

For direct file attachment work, prefer `--attach-list-file` with the real files that must be uploaded to ChatGPT:

```bash
python3 scripts/send_chatgpt_new_chat_prompt.py \
  --prompt-file runtime/tmp/web_review_prompt.txt \
  --attach-list-file runtime/tmp/chatgpt_attach_list.txt \
  --headful \
  --screenshot runtime/browser-profiles/web-review-send.png
```

`runtime/tmp/chatgpt_attach_list.txt` should contain one real file path per line. Use this for batch docs/manifests instead of collapsing the primary source set into one compiled surrogate file, unless 주인님 explicitly asked for that fallback.

Behavior:
- opens ChatGPT home
- creates a fresh new chat
- uploads the listed real files when attachment flags are supplied
- sends the prompt there
- returns the created conversation URL for watcher use

Verification anchor if the path is questioned:
- `runtime/tasks/JB-20260311-CHROME-SESSION-REUSE.md`
- `runtime/browser-profiles/cookie_injected_chatgpt.png`

## DOM watcher
When browser automation is available, prefer the bundled watcher script instead of waiting manually.

Example:

```bash
python3 scripts/watch_chatgpt_response.py \
  --url '<chatgpt-conversation-url>' \
  --poll-seconds 15 \
  --timeout-seconds 900 \
  --headful \
  --delete-after \
  --output-json runtime/tmp/web-review-watch-result.json \
  --record-unreported-queue \
  --task-id JB-20260312-EXAMPLE \
  --event-id web-review-batch-01 \
  --screenshot runtime/browser-profiles/web-review-watch.png
```

Behavior:
- reads Chrome ChatGPT cookies
- opens the target conversation URL
- checks DOM every few seconds
- returns JSON with `status` and optional `verdict`
- can also write the watcher JSON to disk and append a durable unreported-completion queue entry
- when `--task-id` (or another embedded ticket id) is available, watcher start immediately marks `awaiting_callback` + releases the worker slot by default, and completion syncs back into that task with concise note/proof plus a recognizable resume phase (`main_resume`) when appropriate
- if no existing ticket can be resolved, it creates a fallback watcher task immediately instead of silently dropping the event
- can delete the chat after response capture
- lets the agent do other work while waiting

Queue helpers:
- Ack after user report: `python3 scripts/ack_watch_event.py --event-id <stable-id>`
- Escalate stale unacked events: `python3 scripts/escalate_unreported_watch_events.py --older-than-seconds 90`

## Output discipline
- Keep prompts short.
- Keep expected answers shorter.
- Prefer structured bullets/JSON over narrative text.
- If token pressure is high, reduce context before reducing the schema.
