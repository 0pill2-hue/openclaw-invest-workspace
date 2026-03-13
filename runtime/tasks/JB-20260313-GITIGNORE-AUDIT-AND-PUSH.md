# JB-20260313-GITIGNORE-AUDIT-AND-PUSH

- ticket: JB-20260313-GITIGNORE-AUDIT-AND-PUSH
- status: DONE
- checked_at: 2026-03-13 17:51 KST

## Goal
지금까지 작업분을 GitHub에 push하고, 추가 gitignore 누락이 있는지 점검한다.

## Landed
- 현재 변경분을 commit/push 대상으로 정리했다.
- `.gitignore` 기준 추가 누락 후보를 재점검했다.
- 확인 결과 현재 핵심 generated 계층은 이미 untracked 방향으로 정리돼 있었다.
  - `runtime/tasks/proofs/**` tracked file 없음
  - `runtime/browser-profiles/**`, `runtime/logs/**`, `runtime/tmp/**`, `runtime/watch/**` tracked file 없음
  - `invest/stages/stage3/outputs/**` tracked file 없음
- canonical tracked 대상만 남김:
  - `runtime/tasks/evidence/cards/**`
  - `runtime/tasks/evidence/proof-index.jsonl`
  - `runtime/templates/*`
  - `scripts/stage3/*`

## Judgment
- 추가 ignore 패턴을 당장 더 늘려야 할 강한 누락은 미확인
- 핵심은 이미 tracked source vs generated runtime 분리 상태를 commit/push로 고정하는 것

## Proof
- `.gitignore`
- `git status --short`
- `git ls-files 'runtime/tasks/proofs/**'`
- `git ls-files 'runtime/browser-profiles/**' 'runtime/logs/**' 'runtime/tmp/**' 'runtime/watch/**'`
- `git ls-files 'invest/stages/stage3/outputs/**'`
