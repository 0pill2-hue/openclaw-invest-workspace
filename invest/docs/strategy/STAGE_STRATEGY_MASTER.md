# STAGE_STRATEGY_MASTER

> canonical: 스테이지별 운영전략 전용 단일 파일
> location: invest/docs/strategy/

## Stage01
- 증분 수집 + 누락 자동복구 + 백필 자동전환

## Stage02
- raw 불변, one-pass 정제, 격리 우선

## Stage03
- 독립 검증(보존법칙/품질게이트)

## Stage04
- 누수 차단 기반 VALIDATED 밸류 산출

## Stage05
- 12-baseline 비교/게이트/판정
- 보고 필수: 수익률/CAGR/MDD 한표 + 그래프2종(전략 vs KOSPI, 2021~) + CSV 2종

## Stage06
- 베이스라인 확장/선별(트랙별 후보 확대 + 최소 게이트)

## Stage07
- 단일모델(비혼합) 고도화
- 과교체 억제/보유우선 규칙 검증

## Stage08
- 복합모델 개발(앙상블/게이팅)
- Stage07 통과본만 결합 대상으로 사용

## Stage09
- Purged CV + OOS 검증

## Stage10
- 비용/턴오버/리스크 컷 + 교차리뷰

## Stage11
- 채택/보류/승격
