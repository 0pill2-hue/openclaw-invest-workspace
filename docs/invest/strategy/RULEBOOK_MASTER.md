# RULEBOOK_MASTER

> canonical: 규칙 전용 단일 파일
> location: docs/invest/strategy/

## 하드룰
- KRX only
- 보유 1~6
- 최소보유 20거래일
- 교체 +15% 우위
- 월교체 상한 30%
- 트레일링 스탑 -20%
- 왕복 비용 3~4%
- DRAFT/VALIDATED/PRODUCTION 등급 분리

## Stage05 강제
- 12-baseline: numeric3/qualitative3/hybrid3/external3
- `track_counts == 3/3/3/3` 아니면 FAIL_STOP
- 필수 JSON: `protocol_enforced=true`, `track_counts_assertion`
- high-density gate: +25%p / MDD 우위 / turnover <= 1.05x

## 평가 윈도우
- official: 2021~현재
- core: 2023~2025
- reference: 2016~현재(참고/저가중)
