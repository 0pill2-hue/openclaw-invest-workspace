# MONEY_FLOW_SECTOR_SCORE_V1

## 목적
"선호 섹터"가 아니라 **실제 돈이 몰리는 섹터**를 데이터 기반으로 랭킹화한다.

## 스코어 정의 (v1)
- `turnover_share_delta_z`: 섹터 거래대금 점유율 변화 Z-score
- `net_buy_strength_z`: 섹터 순매수 강도 Z-score
- `etf_flow_proxy_z`: 섹터 연관 ETF 유입 대용치 Z-score (없으면 0)
- `news_momentum_z`: 섹터 뉴스/언급량 모멘텀 Z-score (없으면 0)

### 최종 점수
`score = 0.45*turnover_share_delta_z + 0.35*net_buy_strength_z + 0.15*etf_flow_proxy_z + 0.05*news_momentum_z`

## 해석
- score 상위: 돈 유입 강한 섹터
- score 하위: 상대적 자금 이탈 섹터

## 운영 규칙
- 입력 데이터 없으면 해당 항목 0 처리(결측 안전)
- 점수 산출 실패 행은 quarantine 후보로 audit 기록
- 백테스트에는 clean 데이터만 연결
