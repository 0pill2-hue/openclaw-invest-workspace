# JB-20260313-TOKEN-STRUCTURE-SLIMMING

- ticket: JB-20260313-TOKEN-STRUCTURE-SLIMMING
- status: IN_PROGRESS
- repo: openclaw-invest-workspace
- baseline_commit: a9d8fdea7c8b971e753a0f7ac8f10bb987146350
- checked_at: 2026-03-13 17:03 KST

## Goal
토큰 낭비를 구조적으로 줄이기 위해 generated runtime outputs 제거, canonical contract 단일화, hot evidence 최소화, mixed batch/package/result compaction을 구현한다.

## Workstreams
1. runtime/generated hot-cold separation
2. Stage3/web-review contract dedupe
3. evidence/search/proof rule hardening
4. mixed-item batch compact policy + run compaction

## Owner intent
- tracked source vs generated runtime 강한 분리
- canonical contract 1곳
- hot layer는 summary/card/index만
- raw/template/actual batch artifacts는 warm/cold 강등
- DB 10년 롤링 / raw 1개월 롤링

## Docs/contract update
- Stage3 external package canonical: `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- full prompt/schema canonical: `runtime/templates/*`
- web-review skill / operations docs는 overview+orchestration 위주로 slim화 완료
- 상세 landed/remaining/proof: `runtime/tasks/JB-20260313-TOKEN-STRUCTURE-SLIMMING-docs.md`
- runtime/ops landed/remaining/proof: `runtime/tasks/JB-20260313-TOKEN-STRUCTURE-SLIMMING-runtime.md`
