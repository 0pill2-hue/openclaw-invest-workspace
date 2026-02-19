# CONTEXT_RESET_READLIST.md

Last updated: 2026-02-19 15:07 KST
Purpose: 컨텍스트 초기화(대화 리셋) 후 **전략/메모리 누락 방지 강제 로딩 순서**

## Mandatory Read Order (L1: Always)
1. `docs/openclaw/RESET_CORE.md`
2. `docs/openclaw/CONTEXT_RESET_READLIST.md` (this file)
3. `docs/openclaw/OPENCLAW_SYSTEM_BASELINE.md`
4. `docs/openclaw/OPERATING_GOVERNANCE.md`
5. `invest/docs/strategy/README.md`
6. `invest/docs/strategy/RULEBOOK_MASTER.md`
7. `invest/docs/strategy/PIPELINE_11_STAGE_MASTER.md`
8. `invest/docs/strategy/STAGE_STRATEGY_MASTER.md`
9. `DIRECTIVES.md` (상단 QUICK RESUME SNAPSHOT 우선)
10. `memory/오늘.md`
11. `memory/어제.md`
12. `runtime/foreground_anchor.json` (존재 시 next_step 즉시 복귀)
13. (main session only) `MEMORY.md`

## On-demand Read (L2: When needed)
1. `docs/openclaw/WORKSPACE_STRUCTURE.md`
2. `docs/openclaw/DOCS_MAINTENANCE_PLAYBOOK.md`
3. `docs/openclaw/NAMING_STRATEGY.md`
4. `docs/openclaw/CODING_RULES.md`
5. `docs/openclaw/DOC_TEMPLATES.md`
6. `invest/docs/INVEST_STRUCTURE_CANONICAL.md`
7. `invest/reports/stage_updates/README.md`
8. `invest/reports/stage_updates/stage01/stage01_data_collection.md` ~ `stage11/stage11_adopt_hold_promote.md`
9. `invest/docs/memory/README.md` (투자 메모 위치 기준)
10. `reports/{hourly,daily,weekly,monthly}/*` (정기 보고 위치 점검용)

## Hard Guard (Mandatory)
- 위 L1 재로딩 완료 전, 단계/운영 기준 관련 확정 답변 금지
- **전략 관련 답변 전 3종 문서(`RULEBOOK_MASTER`, `PIPELINE_11_STAGE_MASTER`, `STAGE_STRATEGY_MASTER`) 미독 상태면 즉시 재로딩**
- **사람/선호/과거결정/TODO 관련 답변 전 메모리(`memory/오늘`, `memory/어제`, main이면 `MEMORY.md`) 미독 상태면 즉시 재로딩**
- 기준 충돌 시 문서 우선순위: `RULEBOOK_MASTER` > `PIPELINE_11_STAGE_MASTER` > `STAGE_STRATEGY_MASTER` > stage 문서 > 실행 스크립트
