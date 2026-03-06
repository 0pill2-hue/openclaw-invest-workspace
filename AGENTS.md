# AGENTS.md (ULTRA-SLIM)

## Session Load (minimal)
1) SOUL.md
2) USER.md
3) memory/YYYY-MM-DD.md (today only)
4) MEMORY.md only in main 1:1 session

## Hard Rules
- No guessing. If unverified, write `미확인`.
- Pre-approval required: delete/deploy/external-send/payment/live-trade.
- Never store secrets in plaintext.
- Version control is Git-only; do not create legacy files/compat wrappers (e.g., `invest/scripts/*`).
- Backup policy: back up only non-Git-managed artifacts (runtime/log/local generated outputs).
- Important decisions/param changes must be logged to `memory/YYYY-MM-DD.md` (`what/why/next + proof`).
- For research/crawling/trading/security, provide grounded evidence.

## Gates before DONE/promise
- Promise/ETA before ticketing is forbidden. 먼저 `python3 scripts/taskdb.py`로 티켓을 등록/전이한다 (SSOT: `runtime/tasks/tasks.db`, `TASKS.md`는 usage index).
- DONE report requires all: instruction match / memory record / immediate verification / proof path.
- New instruction/status change는 `python3 scripts/directivesdb.py`로만 관리한다 (SSOT: `runtime/directives/directives.db`, `DIRECTIVES.md`는 usage index).

## Workflow/Skill Rules (integrated)
- 충돌 우선순위: `AGENTS.md > DIRECTIVES.md > TASKS.md > 주인님 명시 지시 > 스킬 제안`.
- 요구사항이 모호하면 실행 전에 1문장 확인 후 착수.
- 스킬은 과업과 정확히 맞을 때만 사용하고, 미적합하면 스킬 미사용으로 직접 수행.

## Algorithm/Docs Governance
- Before algorithm work: check `invest/docs/strategy/STRATEGY_MASTER.md` and declare change type (Strategy|Rule|Tuning).
- System/strategy changes must sync related docs.
- Result label required: DRAFT | VALIDATED | PRODUCTION (official reporting = PRODUCTION only).

## Token Efficiency
- 기본은 메인이 직접 수행한다.
- 예외적으로만 위임한다: 장시간, 반복, 대량, 크롤링, 배치, 비동기 작업.
- 서브에이전트 완료는 poll 남용 없이 이벤트/필요 시점 기준으로 확인한다.
- Never re-read files you just wrote or edited.
- Never re-run commands to verify unless the outcome was uncertain.
- Batch related edits into single operations.
- If a task needs 1 tool call, don't use 3. Plan before acting.
- Do not summarize what you just did unless the result is ambiguous or you need additional input.
