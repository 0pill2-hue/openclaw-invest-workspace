# RULEBOOK_MASTER

> canonical: 규칙 전용 단일 파일
> location: invest/docs/strategy/

## 하드룰
- KRX only
- 보유 1~6
- 최소보유 20거래일
- 교체 +15% 우위
- 월교체 상한 30%
- 트레일링 스탑 -20%
- 왕복 비용 3~4%
- DRAFT/VALIDATED/PRODUCTION 등급 분리

## Stage05 강제 (v3_23 기준)
- 36-baseline: numeric10/qualitative10/hybrid10/external6
- `track_counts == 10/10/10/6` 아니면 FAIL_STOP
- 필수 JSON: `protocol_enforced=true`, `track_counts_assertion`
- high-density gate: +25%p / MDD 우위 / turnover <= 1.05x
- **v3_23 신규 규칙:**
  - numeric 모델은 최종 승자가 될 수 없음
  - 동적 가중치 제어 (상태 기반: NORMAL/CAUTION/AGGRESSIVE)
  - 강제 집중 트림 래더 미적용
  - 교체 규칙 +15% edge 유지
  - MDD 분할 평가: full/2021+/2023-2025

## 평가 윈도우
- official: 2021~현재
- core: 2023~2025
- reference: 2016~현재(참고/저가중)
