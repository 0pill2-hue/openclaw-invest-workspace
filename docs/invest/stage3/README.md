# Stage3 Qualitative Axes Docs

Stage3 문서는 **문서만 보고도 현재 Stage3를 재구현할 수 있는 수준**을 목표로 유지한다.

## Canonical 문서
- `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`

## Supporting 문서
- `docs/invest/stage3/STAGE3_DESIGN.md`
  - 상세 설계 기록 / 배경 설명
  - canonical 구현 계약은 `STAGE3_RULEBOOK_AND_REPRO.md` 우선

## 한 줄 요약
- Stage3는 Stage2 clean 기반 intermediate corpus를 만들고,
- `(record_id, chunk_id, focus_symbol)` 단위 claim-card를 생성한 뒤,
- `(symbol, date, issue_cluster_id)` → `(symbol, date)`로 집계해
- 4축 정성 feature + `QUALITATIVE_SIGNAL`을 만든다.
