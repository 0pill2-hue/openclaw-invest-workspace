# JB-20260313-GIT-TRACKED-IGNORED-CLEANUP

- ticket: JB-20260313-GIT-TRACKED-IGNORED-CLEANUP
- status: DONE
- checked_at: 2026-03-13 16:14 KST

## Goal
GitHub 기준으로 ignore 대상이어야 하는데 이미 tracked 상태였던 generated/runtime 파일을 정리한다.

## Landed
- `.gitignore`에 `runtime/stage3_*` 패턴을 추가했다.
- 기존에 Git에 올라가 있던 Stage3 runtime generated artifact를 index에서 제거했다 (`git rm --cached`).
- 대상은 calibration/external-webusable/main-brain-package 계열 runtime 산출물 전체다.

## Verification
- `git ls-files 'runtime/stage3_*'` 에서 잡히던 tracked runtime Stage3 generated files를 정리 대상으로 식별했다.
- `git rm -r --cached --pathspec-from-file=-` 로 해당 tracked files를 index에서 제거했다.
- cleanup commit/push는 이 문서 작성 직후 진행한다.

## Next
- cleanup commit을 만들고 origin/main에 push한다.
- 이후 남은 active task는 PDF backfill 수집 런 병행 + backlog 지속 처리로 이어간다.
