# RULEBOOK_MASTER

> canonical: 규칙 전용 단일 파일
> location: invest/docs/strategy/

## 하드룰
- KRX only
- 보유 1~6
- 최소보유 20거래일
- 교체 +15% 우위
- 월교체 상한 20% (v3_24: over-switching 억제/hold 우선)
- 교체 후 쿨다운 2개월 (즉시 재교체 금지)
- 교체 전 소프트 단계 1개월(신규 비중 패널티)
- 트레일링 스탑 -20%
- 왕복 비용 3~4%
- DRAFT/VALIDATED/PRODUCTION 등급 분리

## Stage05 강제 (v3_24 기준)
- 36-baseline: numeric10/qualitative10/hybrid10/external6
- `track_counts == 10/10/10/6` 아니면 FAIL_STOP
- 필수 JSON: `protocol_enforced=true`, `track_counts_assertion`
- high-density gate: +25%p / MDD 우위 / turnover <= 1.05x
- **v3_24 신규 규칙(과잉교체 억제 / hold 우선):**
  - numeric 모델은 최종 승자가 될 수 없음
  - 교체는 `+15% edge` 단독이 아니라 `edge + persistence(3중 2) + confidence>=0.60` 모두 충족 시만 허용
  - 교체 전 소프트 단계: 1개월 신규편입 비중 패널티 후 전면교체
  - 교체 후 쿨다운 2개월 적용 (즉시 재스위칭 금지)
  - 월교체 상한 20%로 강화 (턴오버/슬리피지/실행노이즈 억제)
  - MDD 분할 평가: full/2021+/2023-2025

## 평가 윈도우
- official: 2021~현재
- core: 2023~2025
- reference: 2016~현재(참고/저가중)
