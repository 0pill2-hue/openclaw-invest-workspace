# JB-20260313-GIT-REWRITE-IGNORE-CLEANUP

- ticket: JB-20260313-GIT-REWRITE-IGNORE-CLEANUP
- status: IN_PROGRESS
- checked_at: 2026-03-13 11:48 KST

## Goal
.gitignore 필요한 부분을 보강하고 마지막 GitHub push를 rewrite해서 다시 올린다.

## Next action
- tracked ignored/runtime local files 식별
- .gitignore 보강
- index 정리 후 마지막 commit amend
- force-with-lease push

## Result
- `.gitignore` expanded for runtime local-only/generated files: current-task/context-handoff*, auto_dispatch/watchdog state files, browser-profiles/tmp/watch/backups/dashboard, runtime db sidecars, review_repo, and the 3 oversized proof jsonl files.
- tracked ignored runtime state files were removed from the commit/index and the last pushed commit was rewritten.
- force-push completed: `main` -> `16afaab5b` (`--force-with-lease`).
