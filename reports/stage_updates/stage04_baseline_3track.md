status: FIXED
updated_at: 2026-02-18 00:34 KST
refactor_status: phase1_structure_safe_done

stage_goal:
  - 3개 baseline(Quant/Text/Hybrid)을 동일 조건으로 비교·유지
  - 단, 실매매 운영은 1개(Hybrid)만 집행하는 3검증 1운영 구조 적용

fixed_rules:
  strategy_structure:
    - 메인 신호: 이웃지표
    - 내지표: 점수화 금지(필터/가드 전용)
    - 동일 지표 정의/계산식/스케일 통일

  track_roles:
    - Quant: 검증/이상탐지 레퍼런스
    - Text: 검증/조기신호 레퍼런스
    - Hybrid: 운영 집행 엔진

  comparison_conditions:
    - 동일 기간
    - 동일 유니버스
    - 동일 비용/리스크 패널티
    - 동일 리밸런싱 주기

  turnover_rules:
    - 최소보유 20거래일
    - 리밸런싱 주 1회
    - 교체 임계치 +15%
    - 월간 교체 30% 캡
    - 분할교체 50%→100%

  cost_risk:
    - 왕복 비용 패널티 3~4%
    - 저유동성 단계 패널티
    - 보유 1~6개
    - 리스크 급증 시 현금화 허용

  conflict_resolution:
    - Hybrid 최종 우선
    - Quant/Text는 경고 플래그
    - 경고 누적 시 포지션 축소/보류

  governance:
    - 결과 등급: DRAFT/VALIDATED/PRODUCTION
    - DRAFT 학습/평가 입력 금지
    - 7단계(Purged CV+OOS) 전 채택 금지
    - 중요 산출물 교차리뷰 필수

outputs:
  - baseline 비교표(3트랙)
  - 운영(집행) 전략 1개 지정
  - 감시 레이어(2트랙) 경고 규칙

drop_criteria_v1:
  mode: conservative
  hard_drop:
    - governance violation (DRAFT 운영투입 / 7단계 미통과 채택 / 등급위반 보고)
    - Hybrid MDD > 25%
    - Quant/Text MDD > 30%
    - Rolling 3M Sharpe < -0.1(Hybrid) / < -0.2(Quant,Text)
    - Rolling 3M alpha < -15%(Hybrid) / < -18%(Quant,Text)
  soft_warning:
    score_window_weeks: 8
    drop_review_score: 3
    triggers:
      - Sharpe<0.2 2개월 연속
      - MDD 18~25% 구간 4주 지속(Hybrid)
      - 주간승률<42% 3주 연속
      - 변동성 1.5x 4주 지속
  switch_guard:
    - 기대개선효과 > 스위치 총비용(18~19%)일 때만 교체
    - 미충족 시 유지 + 포지션 축소/보류

reference:
  - invest/strategy/RULEBOOK_V1_20260218.md
