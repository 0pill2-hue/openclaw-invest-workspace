# JB-20260313-RUNTIME-GITIGNORE-HARDEN

- ticket: JB-20260313-RUNTIME-GITIGNORE-HARDEN
- status: IN_PROGRESS
- checked_at: 2026-03-13 11:45 KST

## Goal
runtime 하위 로컬 전용/임시/세션 산출물이 Git에 섞이지 않도록 .gitignore를 보강한다.

## Next action
- 기존 .gitignore 확인
- runtime/browser-profiles, runtime/tmp, runtime/watch, runtime/backups, runtime/dashboard 등 로컬 생성물 ignore 추가
- sqlite 보조파일(.db-shm/.db-wal) 패턴 정리
