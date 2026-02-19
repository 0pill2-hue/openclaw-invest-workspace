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
- Heartbeat는 **백그라운드 전용**으로 처리한다(메인 작업 포커스 변경 금지).
- Heartbeat 처리 전/후 반드시 `runtime/foreground_anchor.json`을 유지하며, heartbeat 처리 후 즉시 동일 앵커로 복귀한다.
- heartbeat 응답은 최소화(HEARTBEAT_OK 또는 MUST 경고 1줄)하고, 본작업 보고/설명은 heartbeat 턴에 수행하지 않는다.

### 7) Pending Report Concurrency
- Open pending report does NOT block parallel execution.
- However, pending report must keep fixed updates (start/mid/end) until closure.

### 8) 미완료 작업 종료시 제안 규칙 (신규)
- 실행 중이던 작업을 종료/중단할 때 미완료 할일이 남아 있으면, 종료 보고에 `남은 할일 + 다음 제안`을 1~3줄로 반드시 포함한다.
- 자동 스케줄(크론/하트비트)로 이미 보장된 항목이 아니면, `다음 실행 시점`을 함께 명시한다.
- 이 규칙은 수동 재요청 누락 방지를 위한 기본값이며, 주인님이 "지금은 제안 불필요"라고 지시하면 해당 턴에만 예외 적용.

### 9) 검수/중요 작업 교차모델 배정 규칙 (신규)
- 검수 코드 작성, 결과 검증, 중요 운영 작업은 기본적으로 다른 계열의 고성능 모델(서브에이전트)에 교차검토를 배정한다.
- 동일 계열 단일 모델의 자기검수만으로 완료 처리 금지.
- **검증 고정 3모델(주인님 지시):** `opus45` + `sonnet` + `agpro` 모두 통과해야 최종 PASS/완료 처리 가능.
- 3개 중 1개라도 FAIL/미참여면 상태는 DRAFT/IN_PROGRESS 유지.
- 완료 보고에는 `교차검토 모델/핵심 반증 포인트/반영 여부`를 1~3줄로 포함한다.

### 10) 지시 충돌/구버전 지시 정리 규칙 (신규)
- 상위 기준이 갱신되면(예: 10단계→11단계) 이전 지시는 같은 턴에 즉시 상태 정리한다.
- 정리 순서:
  1) 구버전 지시를 `DONE` 또는 `BLOCKED`로 전환
  2) `충돌 해소 메모(무엇이 최신 기준인지)` 1줄 추가
  3) 최신 지시에 증빙 경로(proof) 보강
- 동일 주제에서 `IN_PROGRESS`가 2개 이상이면 WIP 위반으로 간주하고 즉시 재정렬한다.

### 11) 정시/예약 보고 REPORT_QUEUE 선등록 규칙 (신규)
- 예약 보고(정시/크론/약속시간)는 due 10분 전까지 `TASKS.md`에 `[PENDING_REPORT]`로 반드시 선등록한다.
- 보고 전송 직후 같은 항목을 `[DONE_REPORT]`로 즉시 종료한다.
- 크론으로 자동 발송되는 보고도 동일 규칙 적용(자동이라도 큐 등록 생략 금지).

### 12) 주기작업 백그라운드 고정 + 인터럽트 예외 규칙 (신규)
- 수집/감시/크론 결과는 기본적으로 **항상 백그라운드 큐잉**한다.
- 메인 대화/본작업 중에는 주기작업 알림을 끼어들어 처리하지 않고, 본작업 종료 후 묶음 요약으로 전달한다.
- 즉시 인터럽트는 아래 MUST만 허용:
  1) 복구불가 데이터 손실/파손 위험
  2) 보안/권한 이상
  3) 약속 보고 SLA 임박(T-15m) 또는 초과
- SHOULD/CAN 알림은 인터럽트 금지, heartbeat/다음 자연 접점에서만 전달.

### 13) 인터럽트 후 복귀 루틴 (신규)
- 인터럽트 처리 직전 `복귀 앵커`를 `runtime/foreground_anchor.json`에 기록:
  - `task_id, current_step, next_step, due_kst, updated_at`
- 인터럽트 처리 직후 3단계 강제:
  1) `복귀 선언` 1줄
  2) 3분 타이머 시작
  3) 원작업 산출물 업데이트(파일/보고/로그 중 1개)
- 3분 내 산출물 갱신 실패 시 `복귀 실패`로 간주하고 즉시 원작업 재진입.
- 완료 보고 직전 `TASKS.md`의 해당 PENDING 항목 상태를 재확인 후 보고한다.

### 14) Foreground Anchor 강제 규칙 (신규)
- 메인 작업 시작/변경 시 `runtime/foreground_anchor.json`을 반드시 갱신한다.
- heartbeat/크론/경미 인터럽트 처리 후에는 앵커 `task_id`로 즉시 복귀한다.
- 컨텍스트 리셋 직후 첫 행동은 앵커 확인이며, 앵커가 존재하면 해당 `next_step`부터 재개한다.
- 앵커가 30분 이상 갱신되지 않았는데 TASKS에 OPEN/IN_PROGRESS가 있으면 `복귀 실패`로 간주하고 즉시 재개/보고한다.

### 15) 모델 전환(뇌 교체) 전 응답 확인 규칙 (신규)
- 모델 전환(뇌 갈아끼우기) 명령 수신 시, 실무 투입 전 해당 모델로 테스트 메시지(예: `ping` 또는 `status`)를 먼저 실행한다.
- 모델의 정상 응답이 확인된 경우에만 주 작업을 이관하며, 응답 실패 시 즉시 주인님께 알리고 이전 모델로 롤백하거나 대체 모델을 제안한다.
- 이 절차는 모델 전환 후 발생할 수 있는 세션 먹통 리스크를 방지하기 위한 필수 가드레일이다.
