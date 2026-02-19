# stage05_patch_diff_v3_24_kr

## 핵심 정책 변경 (v3_23 → v3_24)
- 교체 게이트 단일(+15% edge) → **복합게이트**(edge + persistence(3중2) + confidence>=0.60)
- 교체 전 **소프트 단계** 추가: 신규 편입 1개월 비중 패널티(hold-first)
- 교체 후 **쿨다운 2개월** 추가: 즉시 재스위칭 차단
- 월교체 상한 **30% → 20%** 강화 (턴오버/슬리피지/실행 노이즈 억제)
- numeric 최종승자 금지 규칙 유지

## 산출물 확장
- trade/timeline/weights CSV 재생성(v3_24)
- charts 2종 생성(v3_24 연속/연도리셋)
- UI 템플릿 parity 유지(index.html)
- summary.json에 replacement_policy 세부 필드 추가
