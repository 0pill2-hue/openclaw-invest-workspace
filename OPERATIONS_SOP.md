# OPERATIONS_SOP.md

## Daily Ops (Automation-first)

### Timezone Policy
- Store all raw/event timestamps in UTC (source of truth)
- Display/report timestamps in KST (Asia/Seoul) for user-facing outputs
- If needed, include both fields: `ts_utc`, `ts_kst`

### 1) Pipeline Order (E2E)
1. Data collection
2. Feature generation
3. Backtest
4. Validation (OOS/WF)
5. Report
6. Result grading (DRAFT/VALIDATED/PRODUCTION)
7. Delivery (only allowed grade)
8. Memory/log update

### 2) Completion Gate (Mandatory)
- Instruction-check: user requirements reflected
- Record-check: memory/YYYY-MM-DD.md updated
- Verify-check: run/syntax/test verification done

If one is missing, task is not complete.

### 3) Result Governance
- Missing grade => DRAFT
- DRAFT must include `TEST ONLY`
- Storage separation:
  - `invest/results/test/`
  - `invest/results/validated/`
  - `invest/results/prod/`
- Only PRODUCTION can be treated as official/adoptable

### 4) Failure Branch Rule
- Retryable failure: retry with timeout/backoff (max 3)
- Recompute (param/data refresh): max 5
- Data-quality failure: quarantine and exclude from scoring
- Unknown critical failure: stop downstream immediately, alert, patch then rerun
- Deploy failure: immediate rollback to last good version

### 4-1) New MUST Guards (low-noise)
- DC-01 (Data): same symbol/feed missing for 3 consecutive ticks -> block algorithm input for that symbol, recover after 3 normal ticks.
- AL-01 (Algo): same-direction signal burst (>= strategy baseline x3 within 1h) while position already open -> hold new entries for 1h.
- RP-01 (Report): promised report SLA +15m exceeded -> immediate alert + pending report escalation.

(오탐 억제 원칙: 단발 이벤트가 아닌 연속 N회/N봉 조건으로만 발동)

### 5) Reporting Rule (user preference)
Use execution-first language:
- "~해야 합니다" ❌
- "~보강 중입니다, 완료 후 보고드리겠습니다" ✅

### 6) Heartbeat Rule
If all checks pass, reply `HEARTBEAT_OK`.
If any issue exists, report issue text only.

### 7) Pending Report Concurrency
- Open pending report does NOT block parallel execution.
- However, pending report must keep fixed updates (start/mid/end) until closure.
