# stage05_effective_window_policy_v3_18_kr

## inputs
- 기준 Rulebook: `invest/docs/strategy/RULEBOOK_V1_20260218.md`
- 기반 Stage05: `invest/scripts/stage05_rerun_v3_16_kr.py`
- 사용자 확정 지시: "Stage05부터 재시작, 평가 로직만 유효구간 기준 적용"

## policy_patch_scope (평가 한정)
- **입력 데이터(Stage04 산출/원천 시계열)는 변경하지 않는다.**
- Stage05 내부의 **평가/게이트/최종판정**에만 유효구간 마스크를 적용한다.
- 전체 10년 성과는 **참고치(reference)** 로 유지하고,
  최종 판정은 **유효구간 공식치(official)** 기준으로 수행한다.

## 유효구간 정의 (density + sample)
- 월 단위 평가 인덱스 기준
- `combined_density(year) >= 0.35` 인 연도만 후보
- 후보 연도 중 `연도별 유효 월수 >= 6` 인 연도만 최종 유효 연도로 인정
- 공식 판정 사용 조건:
  - `effective_samples >= 36 months`
  - `effective_years >= 3`

이번 v3_18 실행에서 유효구간:
- 유효 연도: `2023, 2024, 2025`
- 유효 샘플: `36 months`

## 공식/참고 지표 분리
- 참고치(full period): 누적수익률/CAGR/MDD/turnover (10년 전체)
- 공식치(effective window): 누적수익률/CAGR/MDD/turnover (유효구간)
- Gate2~Gate4, high-density advantage gate, final_decision은 **공식치** 사용

## 하드룰/고정원칙 유지
1) KRX only 유지
2) Rulebook 하드룰 유지(보유1~6, 최소보유20, 교체+15%, 월교체30)
3) 전략 임의 삽입 금지(기존 합의 항목만)
4) external_proxy 비교군 전용 유지
5) high-density 강화 게이트(+25%p, MDD 우위, turnover<=1.05x) 유지

## failure_policy
- 유효구간 샘플 조건 미달 시: `non_numeric_top_valid=false` 강제
- 공식치/참고치 구분 누락 시: 결과 무효
- Gate 표기(`gate1~gate4`, `high_density_advantage_pass`) 누락 시: 결과 무효

## proof
- 설정 반영: `invest/config/stage05_auto_capture_v3_18_kr.yaml`
- 코드 반영: `invest/scripts/stage05_rerun_v3_18_kr.py`
- 실행 결과: `invest/results/validated/stage05_baselines_v3_18_kr.json`
