# CONTEXT_RESET_READLIST.md (MIN)

Purpose: 컨텍스트 리셋/유실 직후 복구용 최소 Readlist

Drift rule: 이 문서는 `docs/openclaw/CONTEXT_MANIFEST.json`과 동일한 로딩 정책을 따라야 한다.

## L1 — MUST (항상/고정, 순서 엄수)
1) docs/openclaw/RULES_INDEX.md
2) DIRECTIVES.md  (usage/index)
3) TASKS.md       (usage/index)
4) memory/YYYY-MM-DD.md (오늘 only)
5) docs/openclaw/OPENCLAW_SYSTEM_BASELINE.md  (문제/복구 트리만)
6) (MAIN SESSION only, 필요 시) MEMORY.md (상단 원칙+최신 합의만)

## L2 — On-demand (필요할 때만 로드)
- 로딩 정책/우선순위: docs/openclaw/CONTEXT_LOAD_POLICY.md
- 운영 게이트/SLA: docs/openclaw/OPERATING_GOVERNANCE.md
- 티켓 SSOT: `runtime/tasks/tasks.db` + `scripts/taskdb.py` + `scripts/task_gate.py` (`TASKS.md`는 usage index)
- 지시 SSOT: `runtime/directives/directives.db` + `scripts/directivesdb.py` + `scripts/directives_gate.py` (`DIRECTIVES.md`는 usage index)
- 구조/경로: docs/openclaw/WORKSPACE_STRUCTURE.md, invest/docs/INVEST_STRUCTURE_POLICY.md
- 투자 실행 SOP: invest/docs/OPERATIONS_SOP.md
- 브레인 라우팅: BRAINS.md
- 스킬 충돌: AGENTS.md (Workflow/Skill Rules)
- Git: CONTRIBUTING.md
