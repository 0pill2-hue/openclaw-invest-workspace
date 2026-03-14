# JB-20260314-STAGE3-TRASH-CLEANUP-SUBAGENT-REPORT

- checked_at: 2026-03-14 07:37:25 KST
- scope: Stage3 image-automation redesign leftovers / trash / intermediate artifacts only
- handoff_source: `runtime/context-handoff.md`
- taskdb_directives_touched: no

## What I checked
- `runtime/context-handoff.md`
- `runtime/tasks/JB-20260313-STAGE3-EXTERNAL-PRIMARY-REDESIGN.md`
- `runtime/tmp/*stage3*`
- `runtime/browser-profiles/stage3*`
- `runtime/tmp/stage3_external_primary_runtime/*`
- `runtime/tmp/stage3_external_web_package/*`
- markdown/doc references for retained proof paths

## Findings
1. `runtime/tmp` contains many Stage3 redesign intermediates.
   - Stage3 top-level temp files: 119 files, about 3.6M total.
   - Rough grouping:
     - external batch send/watch intermediates: 83 files, 1162379 bytes
     - e2e/codeblock intermediates: 13 files, 741368 bytes
     - probe artifacts: 8 files, 81483 bytes
     - runtime helper scripts: 2 files (`stage3_external_chatgpt_batch_runner.py`, `stage3_external_chatgpt_watch_url.py`)
     - generated cache: `runtime/tmp/__pycache__/stage3_external_chatgpt_batch_runner.cpython-314.pyc`
2. `runtime/browser-profiles` contains Stage3 screenshots from send/watch/probe runs.
   - Stage3 screenshot files: 57 files, about 7.5M total.
   - Rough grouping:
     - batch send/watch screenshots: 40 files, 6215677 bytes
     - probe/menu screenshots: 16 files, 1548136 bytes
   - No markdown/doc references were found for these screenshot filenames.
3. `runtime/tmp/stage3_external_primary_runtime/` is still active and should not be treated as disposable right now.
   - dir size: about 1.3M
   - active/recent dirs include:
     - `runtime/tmp/stage3_external_primary_runtime/batch_image_probe/` (mtime 2026-03-14 05:31)
     - `runtime/tmp/stage3_external_primary_runtime/batch_image_probe_revalidate_20260314/` (mtime 2026-03-14 07:36)
   - older probe/e2e dirs also remain, but they are mixed with current image-aware validation outputs.
4. `runtime/tmp/stage3_external_web_package/` is explicitly documented as historical proof/input provenance in `runtime/tasks/JB-20260313-STAGE3-EXTERNAL-PRIMARY-REDESIGN.md` and should be retained unless owner explicitly approves cleanup/migration.

## Deleted
- None.
- Reason: workspace hard rule in `AGENTS.md` requires pre-approval for delete, and some redesign/runtime artifacts are still tied to active image-aware validation or historical proof.

## Low-risk cleanup candidates (approval still required)
1. `runtime/tmp/__pycache__/stage3_external_chatgpt_batch_runner.cpython-314.pyc`
   - generated Python bytecode cache only
2. `runtime/browser-profiles/stage3*.png`
   - likely one-off UI probe/send/watch screenshots
   - not referenced from checked markdown/doc files
3. `runtime/tmp/stage3_external_batch*`
   - send/watch raw responses, normalized JSON, resume logs, and probe results from 2026-03-13 runs
4. `runtime/tmp/stage3_e2e_batch_01a*`
   - codeblock/e2e retry intermediates from 2026-03-13

## Do not delete yet / pending review
- `runtime/tmp/stage3_external_primary_runtime/*`
  - current image-aware probe/runtime package area; activity seen on 2026-03-14
- `runtime/tmp/stage3_image_probe_attach_list.txt`
  - tied to current image-aware packaging flow
- `runtime/tmp/stage3_external_web_package/*`
  - explicitly retained as historical proof/input provenance in redesign report
- any Stage3 artifact already cited in task reports/proof notes unless owner says to prune proof after canonical pass

## Suggested next step
- If owner wants immediate disk cleanup, approve deletion of only the low-risk candidate set above first, then re-check whether any candidate is still referenced by fresh image-aware validation work.
