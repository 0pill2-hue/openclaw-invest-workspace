# Stage2 authoritative audit

- generated_at: 2026-03-08T18:58:34
- ticket_id: JB-20260308-STAGE2HANDOFF
- refine_verdict: PASS
- qc_validation_pass: True
- refine_report: invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260308_185110.json
- qc_report: invest/stages/stage2/outputs/reports/QC_REPORT_20260308_185535.json

## 핵심 판정
- Stage2 자체는 authoritative rebuild + validation 기준 PASS.
- 실제 데이터 이슈는 Stage1 raw signal 쪽 duplicate_date 누적이며, 특히 kr/ohlcv 에 집중되어 있음.
- Stage2 clean 출력은 중복 제거 후 정상적으로 생성됨.

## Stage1 raw duplicate audit
- kr_ohlcv: files=2882, total_rows=33539580, files_with_duplicate_dates=2879, total_duplicate_dates=27765798
- kr_supply: files=2882, total_rows=7214675, files_with_duplicate_dates=2790, total_duplicate_dates=1599137
- us_ohlcv: files=508, total_rows=1263071, files_with_duplicate_dates=0, total_duplicate_dates=0

## Stage2 signal quarantine reason counts
- duplicate_date: 28745689
- zero_candle: 94465
- basic_invalid_or_low_liquidity: 34688
- return_spike_gt_35pct: 131

## Stage2 qualitative quarantine top reasons by folder
- kr/dart: duplicate_rcept_no=33
- market/news: duplicate_canonical_url=19493, duplicate_title_date=1246, duplicate_content_fingerprint=165, empty_jsonl=3
- market/rss: empty_json=1

## Sample focus
- invest/stages/stage1/outputs/raw/signal/kr/ohlcv/000020.csv: rows=14921, duplicate_dates=12427, min_date=2016-01-04, max_date=2026-03-06
- invest/stages/stage2/outputs/clean/production/signal/kr/ohlcv/000020.csv: rows=2494, duplicate_dates=0, min_date=2016-01-04, max_date=2026-03-06
- invest/stages/stage2/outputs/quarantine/production/signal/kr/ohlcv/000020.csv: rows=12427, duplicate_dates=9934, min_date=2016-01-04, max_date=2026-03-05
  - reason_counts: duplicate_date=12427
- invest/stages/stage1/outputs/raw/signal/kr/supply/000020_supply.csv: rows=2472, duplicate_dates=6, min_date=2016-02-16, max_date=2026-03-06
- invest/stages/stage2/outputs/clean/production/signal/kr/supply/000020_supply.csv: rows=2466, duplicate_dates=0, min_date=2016-02-16, max_date=2026-03-06
- invest/stages/stage2/outputs/quarantine/production/signal/kr/supply/000020_supply.csv: rows=6, duplicate_dates=0, min_date=2026-02-19, max_date=2026-02-26
  - reason_counts: duplicate_date=6

## Report-only warning
- {'type': 'missing_input_folder', 'folder': 'market/google_trends', 'path': '/Users/jobiseu/.openclaw/workspace/invest/stages/stage2/inputs/upstream_stage1/raw/signal/market/google_trends', 'required': False, 'severity': 'warn'}
