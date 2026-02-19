# CLEAN/QUARANTINE Backfill Report — 2026-02-18

- Executed at (KST): 2026-02-18 01:05
- Command: `./.venv/bin/python3 invest/scripts/onepass_refine_full.py`
- Rules baseline: existing sanitize rules in `invest/scripts/onepass_refine_full.py` (OHLCV/supply/schema/text/json 분리 규칙)
- Source: `invest/data/raw/**`
- Target clean: `invest/data/clean/production/**`
- Target quarantine: `invest/data/quarantine/production/**`
- Upstream generated report: `reports/qc/FULL_REFINE_REPORT_20260218_010517.md`

## Summary

| Metric | Count |
|---|---:|
| Total scanned | 34,029 |
| Newly clean-written | 262 |
| Newly quarantine-written | 169 |
| Skipped (incremental unchanged) | 33,766 |

## Folder Highlights

- `us/ohlcv`: clean 168 / quarantine 169 (가장 큰 재분리 발생 구간)
- `kr/dart`: clean 88
- `text/blog`: clean 2 (대부분 incremental skip)
- `kr/ohlcv`, `kr/supply`: 이번 배치에서 모두 skip (기존 처리 결과 재사용)

## Notes

- 본 배치는 `clean/quarantine` 소급 재분리를 수행했으며, 기존 인덱스(`_processed_index.json`)를 이용한 incremental 실행으로 동일 시그니처 파일은 skip 처리됨.
- 재현용 근거 파일:
  - `reports/qc/FULL_REFINE_REPORT_20260218_010517.md`
