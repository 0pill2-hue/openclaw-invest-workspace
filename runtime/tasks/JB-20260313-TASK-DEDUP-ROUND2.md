# JB-20260313-TASK-DEDUP-ROUND2

- checked_at: 2026-03-13 15:36 KST
- status: DONE

## Goal
현재 active/backlog에서 중복·상위작업에 흡수된 태스크를 정리한다.

## Removed task rows
1. `JB-20260313-RUNTIME-GITIGNORE-HARDEN`
   - reason: `JB-20260313-GIT-REWRITE-IGNORE-CLEANUP`에서 실제 ignore 보강 + push rewrite까지 완료되어 상위/후속 티켓으로 흡수됨.
2. `JB-20260311-WEB-REVIEW-STAGE12-IMPROVE`
   - reason: current HEAD 기준 재검토 티켓 `JB-20260313-WEB-REVIEW-STAGE12-REREVIEW`로 대체되었고, 기존 task는 baseline mismatch로 close 불가 상태에서 중복 backlog만 남기고 있었음.
3. `JB-20260311-TELEGRAM-PDF-PAGE-DECOMPOSE-RERUN`
   - reason: 좁은 page decompose rerun 범위는 이후 `JB-20260312-TELEGRAM-PDF-RECOVERY-FIX` 및 `JB-20260313-STAGE12-PDF-MUSTFIX-RUNTIME`에 흡수됨.

## Directive alignment
- `JB-20260313-RUNTIME-GITIGNORE-HARDEN` => DONE (`superseded_by: runtime/tasks/JB-20260313-GIT-REWRITE-IGNORE-CLEANUP.md`)
- `JB-20260311-TELEGRAM-PDF-PAGE-DECOMPOSE-RERUN` => DONE (`superseded_by: runtime/tasks/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX.md; runtime/tasks/JB-20260313-STAGE12-PDF-MUSTFIX-RUNTIME.md`)
- `JB-20260311-WEB-REVIEW-STAGE12-IMPROVE` directive는 이미 DONE 상태였고, task row만 제거했다.

## Result
- active/backlog에서 중복 태스크 3건 제거
- broader successor ticket만 남기도록 정리
