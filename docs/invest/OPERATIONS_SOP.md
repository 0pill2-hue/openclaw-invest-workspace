# OPERATIONS_SOP

## Purpose

운영 실행 표준(SOP) 단일 기준.
알고리즘 개발단계 정의는 `docs/invest/STRATEGY_MASTER.md`(Stage1~6 canonical)를 따른다.

## 재현 핵심 문서

- 부트스트랩: `docs/invest/BOOTSTRAP_REPRODUCTION.md`
- Stage 실행 명세: `docs/invest/STAGE_EXECUTION_SPEC.md`
- 구조 기준: `docs/invest/INVEST_STRUCTURE_POLICY.md`

## 1) Pipeline Order (E2E, canonical)

1. Stage1 데이터 수집
2. Stage2 데이터 정제
3. Stage3 로컬뇌 정성 신호 압축
4. Stage4 결합/산출
5. Stage5 VALIDATED 피처 산출
6. Stage6 선발/교체/운영 판단

운영 후속(보고/전달/로그·메모리 업데이트)은 Stage6 운영 판단 결과 기반으로 수행한다.

## 2) Hard Gates (Mandatory)

- **Hard stop**: 상위 단계 FAIL 시 하위 단계 실행 금지
- **Dependency integrity**: upstream PASS 없으면 downstream 차단
- **Clean-only**: raw/legacy 입력이 feature/train/value에 유입되면 즉시 FAIL
- **Completion gate**: 아래 3개 모두 충족 시에만 완료
  1. Instruction-check (요구사항 반영)
  2. Record-check (`memory/YYYY-MM-DD.md` 기록)
  3. Verify-check (run/syntax/test 검증)

## 3) Result Governance

- 기본 등급: `DRAFT | VALIDATED | PRODUCTION` (미표기 시 DRAFT)
- 저장 분리:
  - `invest/stages/stage6/outputs/results/test_history/`
  - `invest/stages/stage6/outputs/results/validated_history/`
  - `invest/stages/stage6/outputs/results/prod_history/`
- **공식/채택 가능 보고는 PRODUCTION만 허용**

## 4) Failure Policy

- Retryable failure: timeout/backoff 재시도 최대 3회
- Recompute 필요: 파라미터/데이터 갱신 재실행 최대 5회
- Data quality failure: quarantine 후 스코어링 제외
- Unknown critical failure: 즉시 중단, 원인 패치 후 재실행
- Deploy failure: 마지막 정상 버전으로 즉시 롤백

## 5) Reporting Rules

- 실행 중심 문장 사용(현재 진행/완료/다음 액션 명시)
- 완료 보고에는 canonical evidence card 경로 1개 이상 포함 (`runtime/tasks/evidence/cards/<ticket>.json`)
- proof index는 `runtime/tasks/evidence/proof-index.jsonl`를 기준으로 조회하며 `canonical_summary=true`가 기본 참조값이다.
- raw/tmp/log proof는 보존하되 기본 읽기층에서 제외하고, 필요 시에만 opt-in 조회한다.
- 보고 cadence/SLA canonical은 `docs/operations/governance/OPERATING_GOVERNANCE.md`를 따른다.

## 5.1) Evidence Runtime Tier

- L0 runtime pointer: current-task/context-handoff/TASKS-DIRECTIVES summary
- L1 canonical evidence: evidence card + proof index (`canonical_summary=true`)
- L2 cold raw artifacts: raw/log/tmp/stdout/stderr/full output (default non-load)
- hot layer 허용 경로는 `runtime/current-task.md`, `runtime/context-handoff.md`, `runtime/tasks/evidence/cards/*`, `runtime/tasks/evidence/proof-index.jsonl`만 쓴다.
- 탐색 기본값은 `python3 scripts/tasks/db.py evidence-search` canonical-only이며, `grep -R`로 raw/log/tmp 계층을 직접 뒤지지 않는다.
- ad-hoc 검색 검사는 `python3 scripts/tasks/canonical_search_guard.py -- <command...>`로 선검사할 수 있다.

## 6) Timezone Policy

- 원천/이벤트 저장: UTC
- 사용자 보고: KST(Asia/Seoul)
- 필요 시 `ts_utc`, `ts_kst` 병기

## 7) 실거래체결 일치 보장 모드 (Mandatory when enabled)

- 게이트 스크립트: `invest/stages/stage6/scripts/stage06_real_execution_parity_gate.py`
- 필수 입력(부재 시 즉시 FAIL-CLOSE)
  - `invest/stages/stage6/inputs/execution_ledger/model_trade_orders.csv`
  - `invest/stages/stage6/inputs/execution_ledger/broker_execution_ledger.csv`
- 표준 스키마(두 파일 공통)
  - `execution_id, order_id, timestamp, symbol, side, qty, fill_price, fee, tax`
  - 기준: `invest/stages/stage6/inputs/config/schemas/execution_ledger.schema.json`
- strict reconciliation 키 정책:
  - 1순위 `execution_id`
  - 2순위 `order_id`
  - 3순위 `date+symbol+side` (1:1 매칭)
- strict tolerance 기본값:
  - `qty=1e-9`, `fill_price=1e-6`, `fee=1e-6`, `tax=1e-6`
- fail-close 조건:
  - 원장 누락
  - 스키마/파싱 오류
  - `mismatch_count > mismatch_threshold`
