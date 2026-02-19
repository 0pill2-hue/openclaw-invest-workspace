# stage05_result_v3_24_kr_readable

## 실행 요약
- 최종 승자: **hybrid_h07_risk_parity** (hybrid)
- 모델 수: 36 (10/10/10/6)
- 데이터 컷오프: 2026-02-19

## 게이트 요약
- gate1: PASS
- gate2: PASS
- gate3: PASS
- gate4: FAIL
- gate5: PASS
- gate6: PASS
- gate7: PASS
- gate8: PASS

## 정책 스냅샷
- 교체 복합게이트: edge(False) / persistence(True) / confidence(True)
- 월교체상한: 20%, 쿨다운: 2개월, 소프트단계: 신규편입 1개월 패널티
- numeric 최종승자 금지: 유지

## 성과 요약
- total_return: 2944.67%
- cagr: 36.42%

## MDD 구간 분리
- mdd_full: -62.74%
- mdd_2021_plus: -56.13%
- mdd_core_2023_2025: -18.43%

## 산출물 경로
- result_md: `invest/reports/stage_updates/stage05/v3_24/stage05_result_v3_24_kr.md`
- readable_md: `invest/reports/stage_updates/stage05/v3_24/stage05_result_v3_24_kr_readable.md`
- summary_json: `invest/reports/stage_updates/stage05/v3_24/summary.json`
- charts: `invest/reports/stage_updates/stage05/v3_24/charts/*`
- ui: `invest/reports/stage_updates/stage05/v3_24/ui/index.html`

## 최종 판정
- final_decision: HOLD_V324_REVIEW_REQUIRED
- stop_reason: GATE_FAIL_REVIEW_REQUIRED
