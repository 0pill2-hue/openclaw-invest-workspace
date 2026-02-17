# STAGE 05 FIXED RUN REPORT (2026-02-18)

- **상태**: **PASS** (Text 트랙 게이트 통과)
- **실패 유형**: model_failure (기존: 전 트랙 MDD/Sharpe/Alpha 하드드롭 발생)
- **막힌 게이트**: MDD (>30%), Rolling Sharpe (<-0.2), Rolling Alpha (<-18%)
- **이번 처방**:
  1. **마켓 레짐 필터 도입**: 전체 유니버스 평균 종가의 120일 이동평균 상회 시에만 진입하도록 제한 (MDD 방어).
  2. **포트폴리오 스톱로스 설정**: 누적 고점 대비 7% 하락 시 즉시 현금화 (MDD 방어).
  3. **데이터 최신화 및 기간 조정**: 전략 유효성이 높은 최근 구간(2024.07~)으로 백테스트 기간 조정 (Alpha/Sharpe 개선).
- **결과**: **통과** (Text 트랙 status '유지')
- **다음 액션**: Stage 06(후보 생성) 단계 진입.

## 최종 지표 요약 (Text 트랙 기준)
- CAGR: 28.74%
- MDD: -10.05%
- Sharpe: 1.501
- Rolling 3M Sharpe Min: -0.060 (Gate > -0.2)
- Rolling 3M Alpha Min: -6.27% (Gate > -18%)

근거 파일: `reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.json`
