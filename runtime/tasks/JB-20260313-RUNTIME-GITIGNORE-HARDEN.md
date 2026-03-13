# JB-20260313-RUNTIME-GITIGNORE-HARDEN

- ticket: JB-20260313-RUNTIME-GITIGNORE-HARDEN
- status: IN_PROGRESS
- checked_at: 2026-03-13 13:31 KST

## Goal
runtime 하위 로컬 전용/임시/세션 산출물이 Git에 섞이지 않도록 .gitignore를 보강한다.

## Findings
- `.gitignore`에는 이미 아래 runtime 로컬 산출물 ignore가 들어가 있음:
  - `runtime/backups/`
  - `runtime/browser-profiles/`
  - `runtime/dashboard/`
  - `runtime/tmp/`
  - `runtime/watch/`
  - `runtime/current-task.md`
  - `runtime/context-handoff.md`
  - `runtime/context-handoff-*.md`
  - `runtime/tasks/proofs/`
  - `runtime/**/*.db`
  - `runtime/**/*.db-shm`
  - `runtime/**/*.db-wal`
  - `runtime/**/*.db-journal`
- `git check-ignore -v`로 위 패턴들이 샘플 경로에 실제 적용되는 것 확인.
- `git status --short --ignored runtime`에서 `runtime/backups/`, `runtime/browser-profiles/`, `runtime/dashboard/`, `runtime/tmp/`, `runtime/watch/`, `runtime/current-task.md`, `runtime/context-handoff.md`, `runtime/tasks/proofs/`, `runtime/directives/directives.db*`, `runtime/tasks/tasks.db` 등이 ignore 상태(`!!`)로 확인됨.
- `git ls-files runtime | grep -E '^(runtime/(backups|browser-profiles|dashboard|tmp|watch)/|runtime/current-task\\.md$|runtime/context-handoff|runtime/tasks/proofs/|runtime/.*\\.db(-shm|-wal|-journal)?$)'` 결과는 비어 있었음. 즉, 현재 ignore 대상으로 잡은 runtime 디렉터리/DB 보조파일 중 이미 추적 중인 항목은 확인되지 않음.

## Remaining tracked candidates (cleanup or proof needed)
아래 파일들은 현재 Git 추적 중이며 이름상 임시/로컬 실행 산출물 후보이지만, 의도적 추적 여부는 미확인:
- `runtime/tmp_guardian_probe_index.jsonl`
- `runtime/tmp_selected_articles_free_backfill_2016_2019.jsonl`
- `runtime/tmp_selected_articles_guardian_only_2016_2019.jsonl`
- `runtime/tmp_selected_articles_reuters2019.jsonl`
- `runtime/tmp_selected_articles_sec_filtered_2016_2019.jsonl`
- `runtime/tmp_stage1_before_snapshot.json`
- `runtime/stage3_external_webusable_s036_s060_local_run_meta.json`
- `runtime/stage3_external_webusable_s036_s060_local_run_stdout.txt`
- `runtime/stage3_external_webusable_s036_s060_local_run_stderr.txt`

## Assessment
- 기존에 목표로 적어둔 `runtime/browser-profiles`, `runtime/tmp`, `runtime/watch`, `runtime/backups`, `runtime/dashboard`, sqlite 보조파일 패턴 보강 자체는 현재 .gitignore 기준으로 반영/적용 확인됨.
- 다만 root-level `runtime/tmp_*` 계열 및 `*_local_run_*` 계열 추적 파일이 남아 있어, 이 티켓을 DONE으로 닫으려면 아래 둘 중 하나가 추가로 필요함:
  1. 로컬 전용 산출물로 확정 후 ignore 패턴 추가 + `git rm --cached` 정리
  2. 의도적 추적 산출물임을 이 티켓에 명시 증빙

## Next action
- 위 9개 tracked 후보의 의도적 추적 여부를 확인한다.
- 로컬 전용으로 판정되면 `.gitignore`에 `runtime/tmp_*` 및 필요 시 `runtime/*_local_run_{meta.json,stdout.txt,stderr.txt}` 계열 패턴을 추가하고 index cleanup 근거를 남긴다.
- 의도적 추적이면 해당 이유를 이 티켓에 적고 DONE 처리한다.

## Proof
- `.gitignore`
- `git check-ignore -v runtime/backups/example.txt runtime/browser-profiles/p1/a runtime/dashboard/cache.json runtime/tmp/foo.txt runtime/watch/state.json runtime/current-task.md runtime/context-handoff.md runtime/context-handoff-123.md runtime/tasks/proofs/x.txt runtime/sample.db-shm runtime/sample.db-wal runtime/sample.db-journal runtime/sample.db`
- `git status --short --ignored runtime`
- `git ls-files runtime | grep -E '^(runtime/(backups|browser-profiles|dashboard|tmp|watch)/|runtime/current-task\\.md$|runtime/context-handoff|runtime/tasks/proofs/|runtime/.*\\.db(-shm|-wal|-journal)?$)'`
- `git ls-files runtime | grep -E '^runtime/tmp_|^runtime/.*_local_run_(meta\\.json|stdout\\.txt|stderr\\.txt)$'`
