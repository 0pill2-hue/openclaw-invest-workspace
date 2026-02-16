# WORKFLOW_PROCESS.md

## End-to-End 8-Stage Standard

1. 수집 (Collection)
- Input: 원천 API/크롤링 소스
- Output: raw data (parquet/csv)
- DoD: record_count>0, schema check pass

2. 정제 (Cleaning)
- Input: raw data
- Output: clean data
- DoD: null ratio < 1%, timezone normalized

3. 지표 생성 (Indicators)
- Input: clean data
- Output: indicators table
- DoD: required features complete, unit test pass

4. 전략 반영 (Strategy)
- Input: indicators + strategy rules
- Output: strategy config/code
- DoD: rule spec updated, dry-run pass

5. 백테스트 (Backtest)
- Input: strategy + history data
- Output: DRAFT results
- DoD: >=3y range, cost/slippage applied, OOS>=30%

6. 검증 (Validation)
- Input: DRAFT results
- Output: VALIDATED results
- DoD: walk-forward pass, OOS consistency pass

7. 보고 (Reporting)
- Input: validated metrics/charts
- Output: report package
- DoD: metrics+visuals included, owner-facing summary ready

8. 배포 (Production)
- Input: approved report
- Output: PRODUCTION result/package
- DoD: approval logged, monitoring/rollback ready

## Failure Branch Rules
- Retry: transient errors only, max 3
- Recompute: param/data refresh, max 5
- Quarantine: suspected bad data isolation
- Stop: critical unknown failure -> stop downstream immediately
- Rollback: failed deploy -> immediate restore

## Execution Style
- 즉시 실행: stage 완료 시 다음 stage 자동 트리거
- 즉시 검증: 각 stage 직후 검증 실행
- 즉시 보고: 시작/중간/종료 보고 고정
