# DOCS_MAINTENANCE_PLAYBOOK.md

Last updated: 2026-02-18 06:26 KST
Purpose: 시스템/전략 변경 시 어떤 문서를 반드시 갱신할지 빠르게 판단하기 위한 최소 실행 가이드

## 1) 변경 유형별 필수 갱신
- OpenClaw 시스템/설정/런타임 변경
  - `docs/openclaw/OPENCLAW_SYSTEM_BASELINE.md`
  - `docs/openclaw/WORKSPACE_STRUCTURE.md` (구조 변경 시)
  - `docs/openclaw/CONTEXT_RESET_READLIST.md` (읽기 순서 영향 시)
- 알고리즘 전략/게이트/운영 규칙 변경
  - `invest/strategy/RULEBOOK_V1_20260218.md`
  - `reports/stage_updates/stage01~11` 해당 문서

## 2) 재현성 최소 필드 (문서 공통)
- `inputs`
- `run_command` 또는 `process`
- `outputs`
- `quality_gate(s)`
- `failure_policy`
- `proof`

## 3) 완료 보고 조건
- 코드/설정 변경 + 문서 갱신 + proof 경로가 모두 있어야 완료 보고 가능
- 누락 시 `IN_PROGRESS` 유지
