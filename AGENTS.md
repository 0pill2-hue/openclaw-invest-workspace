# AGENTS.md (ULTRA-SLIM)

## Session Load (minimal)
1) SOUL.md
2) USER.md
3) `docs/operations/CONTEXT_LOAD_POLICY.md` for daily memory / MEMORY.md load scope
4) `docs/operations/OPERATIONS_BOOK.md` as the root index for operations/programs/docs map
5) `python3 scripts/tasks/db.py summary --top 5 --recent 5`
6) `python3 scripts/directives/db.py summary --top 5 --recent 5`
7) `runtime/current-task.md` only for current-work reload (must contain ticket/directive/next_action/proof; do not bulk-reload daily memory)

## Hard Rules
- No guessing. If unverified, write `미확인`.
- Pre-approval required: delete/deploy/external-send/payment/live-trade.
- Never store secrets in plaintext.
- Version control is Git-only; do not create legacy files/compat wrappers (e.g., `invest/scripts/*`).
- Backup policy: back up only non-Git-managed artifacts (runtime/log/local generated outputs).
- Important decisions/param changes must be logged to `memory/YYYY-MM-DD.md` (`what/why/next + proof`).
- For research/crawling/trading/security, provide grounded evidence.

## Gates before DONE/promise
- Promise/ETA before ticketing is forbidden. 먼저 `python3 scripts/tasks/db.py`로 티켓을 등록/전이한다 (SSOT: `runtime/tasks/tasks.db`, `TASKS.md`는 usage index).
- 작업 착수 전에는 관련 directive를 `python3 scripts/directives/db.py`에 반영하고, `python3 scripts/context_policy.py snapshot ...`으로 `runtime/current-task.md`를 최신 상태로 기록한다.
- DONE report requires all: instruction match / memory record / immediate verification / proof path.
- New instruction/status change는 `python3 scripts/directives/db.py`로만 관리한다 (SSOT: `runtime/directives/directives.db`, `DIRECTIVES.md`는 usage index).

## Workflow/Skill Rules (integrated)
- 충돌 우선순위: `AGENTS.md > DIRECTIVES.md > TASKS.md > 주인님 명시 지시 > 스킬 제안`.
- 요구사항이 모호하면 실행 전에 1문장 확인 후 착수.
- 스킬은 과업과 정확히 맞을 때만 사용하고, 미적합하면 스킬 미사용으로 직접 수행.

## Algorithm/Docs Governance
- Before algorithm work: check `docs/invest/STRATEGY_MASTER.md` and declare change type (Strategy|Rule|Tuning).
- System/strategy changes must sync related docs.
- Result label required: DRAFT | VALIDATED | PRODUCTION (official reporting = PRODUCTION only).

## Token Efficiency
- 서브에이전트 완료는 **감시(poll) 기반이 아니라 callback/event 기반**으로 처리한다.
- 서브 시작 시 `ticket_id/run_id`를 전달하고, 완료 시 `openclaw system event --mode now`로 메인을 호출한다.
- 메인은 완료 이벤트를 수신하면 같은 턴에서 `taskdb proof + 상태전이(DONE/REWORK/BLOCKED)`까지 즉시 처리한다.
- 운영 상세(컨텍스트 운영, heartbeat, task/directive 절차, 문서 체계)는 `docs/operations/OPERATIONS_BOOK.md`를 따른다.
- 문서 위치/네이밍/작성 형식 표준은 `docs/operations/DOCUMENT_STANDARD.md`를 따른다.
- Never re-read files you just wrote or edited. You know the contents.
- Never re-run commands to "verify" unless the outcome was uncertain.
- Don't echo back large blocks of code or file contents unless asked.
- Batch related edits into single operations. Don't make 5 edits when 1 handles it.
- Skip confirmations like "I'll continue..."  Just do it.
- If a task needs 1 tool call, don't use 3. Plan before acting.
- Do not summarize what you just did unless the result is ambiguous or you need additional input.
