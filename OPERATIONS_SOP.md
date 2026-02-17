# OPERATIONS_SOP.md

## Daily Ops (Automation-first)

### Timezone Policy
- Store all raw/event timestamps in UTC (source of truth)
- Display/report timestamps in KST (Asia/Seoul) for user-facing outputs
- If needed, include both fields: `ts_utc`, `ts_kst`

### 1) Pipeline Order (E2E)
1. Data collection (raw)
2. Clean/Quarantine split + audit log
3. Clean validation (schema/timezone/duplicates)
4. Feature generation (clean-only)
5. Train
6. Validation (Purged CV/OOS/WF)
7. Value scoring + comparison tables
8. Cross-review (rebuttal-oriented)
9. Report
10. Result grading (DRAFT/VALIDATED/PRODUCTION)
11. Delivery (only allowed grade)
12. Memory/log update

Hard stop rule: if any stage fails, downstream stages are blocked.

### 1-A) Gate Execution SOP (Fixed)
- run -> gate-check -> pass:next / fail:rollback-protocol
- FAIL 상태에서 다음 단계 우회 진입 금지
- 기준 임계치 버전은 `gate_threshold_v1_20260218` 사용

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

### 4-A) Dependency Integrity Hard-Gate (Mandatory)
- If upstream stage is not `PASS`, downstream execution is denied.
- `clean-only` violation (raw/legacy path input in feature/train/value) => immediate FAIL.
- `DONE + proof` not satisfied => completion rate cannot be 100%.

### 4-B) Lineage / Integrity Gate (Mandatory)
- Every run must emit lineage fields:
  - `run_id`, `rule_version`, `input_path`, `input_hash`, `output_hash`, `grade`
- Final report must include at least one hash evidence path.
- Hash mismatch between report and artifact => immediate FAIL + rerun.

### 4-C) Parallel Isolation Gate (Mandatory)
- Parallel workers (3 default, 4 max) must use separate run directories/log files.
- Shared file write without lock is prohibited.
- If contention detected (stale lock or collision), auto-fallback to sequential for that stage.

### 4-D) Repeatability (Idempotency) Gate
- Repeated 4~8 runs must reset cache/state before each run.
- If variance exceeds threshold, mark run set as unstable and block promotion.

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
