# MASTER STRATEGY RUNBOOK V1 (2026-02-18)

> 목적: 이 문서 **하나만** 보고 동일 전략을 재현/운영할 수 있도록 고정.

## 1) 운영 원칙(고정)
- 운영 구조: 3검증 1운영 (운영 1개, 감시 2개)
- 메인 신호: 이웃지표
- 내지표: 점수화 금지, 필터/가드 전용
- 저회전: 최소보유 20일, 주1회 리밸런싱, 교체 +15%, 월간 교체 30% 캡
- 비용: 왕복 3~4% 보수 패널티
- 거버넌스: DRAFT/VALIDATED/PRODUCTION, 7단계 전 채택 금지

## 2) 11단계 절차(고정)
1. 수집
2. 정제
3. 정제검증
4. VALIDATED 밸류 산출
5. 베이스라인 3트랙 고정
6. 후보군 1차 생성
7. 후보군 단계 컷
8. Purged CV + OOS
9. 비용/턴오버/리스크
10. 교차리뷰 반영
11. 채택/보류/승격

## 3) 데이터/경로(고정)
- raw: `invest/data/raw/**` (불변)
- validated snapshot(현재): `invest/data/validated/snapshots/20260217_231426/production`
- 주요 전략 문서:
  - `invest/strategy/RULEBOOK_V1_20260218.md`
  - `reports/stage_updates/stage04/stage04_validated_value.md`

## 4) 실행 순서(최소 명령)
```bash
cd /Users/jobiseu/.openclaw/workspace
source .venv/bin/activate

# 정제
.venv/bin/python3 invest/scripts/onepass_refine_full.py

# 정제검증
.venv/bin/python3 invest/scripts/validate_refine_independent.py

# 밸류 산출
.venv/bin/python3 invest/scripts/calculate_stage3_values.py
```

## 5) 탈락기준 v1(보수형 요약)
### Hard Drop
- 거버넌스 위반(DRAFT 운영투입, 7단계 미통과 채택 시도)
- Hybrid MDD > 25%, Quant/Text MDD > 30%
- 3M Sharpe < -0.1(Hybrid), < -0.2(Quant/Text)
- 3M alpha < -15%(Hybrid), < -18%(Quant/Text)

### Soft Warning
- 8주 창에서 3점 누적 시 탈락 검토
- 교체는 기대개선효과 > 스위치 비용(18~19%)일 때만

## 6) 5단계 산출물 규격
- 비교표: 수익/MDD/Sharpe/Turnover/비용잠식률
- 상태판정: 유지/보류/탈락 + hard/soft 근거
- 운영1/감시2 지정 근거
- 결과 등급: DRAFT (TEST ONLY)

## 7) 최신 보강 반영
- 롤링 연속성 경고 플래그
- NaN 편중(시장/섹터/시총) 점검
- KR/US 혼합 분포 정합성 경고
- 보고서: `reports/qc/STAGE4_HARDENING_3ITEMS_20260218.md`

## 8) 변경관리 규칙
룰/파라미터 수정 시 동시 업데이트:
1) 본 문서
2) `invest/strategy/RULEBOOK_V1_20260218.md`
3) `reports/stage_updates/stage04/stage04_validated_value.md`
4) `memory/YYYY-MM-DD.md`
