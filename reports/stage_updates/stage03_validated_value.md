status: IN_PROGRESS
updated_at: 2026-02-17 23:40 KST
policy_applied:
  - 스무딩 포함 밸류 산출: Momentum EMA(20), Flow Median(5)+EMA(10), Liquidity/Risk Winsor+EMA
  - 통합점수: z-score 가중합 후 최종 1회 스무딩
  - 누수방지: TimeSeries 분리 후 처리, 유동성/거래가능성 필터 선행
  - 이상치/누락: 즉시삭제 금지, PENDING 검증 후 반영
note: 3단계 적용 결과는 7단계(Purged CV+OOS) 검증 통과 전까지 확정 채택 금지
source:
  - scripts/calculate_stage3_values.py
  - reports/stage_updates/STAGE3_VALUE_RUN_20260217_233432.json