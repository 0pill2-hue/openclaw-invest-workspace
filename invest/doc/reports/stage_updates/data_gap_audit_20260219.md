# Data Gap Audit (2026-02-19)

- Generated: 2026-02-19 10:34 KST
- Scope: Stage01 원천데이터(우선순위: KRX DART, 텍스트 Blog/Telegram, 기타 Stage01 입력)
- Target horizon: 2016~2026 (10년)

## 1) Yearly Coverage Table

| Year | DART unique disclosures | DART months present | Blog posts | Telegram msgs | Gap Flag |
|---:|---:|---:|---:|---:|---|
| 2016 | 174,040 | 10/12 | 52 | 0 | DART_MONTH_GAP, BLOG_LOW_DENSITY, TELEGRAM_LOW_DENSITY |
| 2017 | 11,748 | 1/12 | 63 | 0 | DART_MONTH_GAP, BLOG_LOW_DENSITY, TELEGRAM_LOW_DENSITY |
| 2018 | 0 | 0/12 | 160 | 0 | DART_MONTH_GAP, BLOG_LOW_DENSITY, TELEGRAM_LOW_DENSITY |
| 2019 | 0 | 0/12 | 276 | 3,393 | DART_MONTH_GAP, BLOG_LOW_DENSITY, TELEGRAM_LOW_DENSITY |
| 2020 | 0 | 0/12 | 956 | 12,679 | DART_MONTH_GAP, TELEGRAM_LOW_DENSITY |
| 2021 | 155,507 | 9/12 | 2,038 | 18,418 | DART_MONTH_GAP |
| 2022 | 225,434 | 12/12 | 2,195 | 29,332 | OK |
| 2023 | 235,471 | 12/12 | 3,359 | 68,176 | OK |
| 2024 | 247,507 | 12/12 | 4,445 | 99,948 | OK |
| 2025 | 248,581 | 12/12 | 8,538 | 223,393 | OK |
| 2026 | 28,779 | 2/2 | 5,452 | 40,636 | OK |

## 2) Missing / Low-density List

- DART missing month windows: **52개**
  - 2016-11, 2016-12, 2017-02, 2017-03, 2017-04, 2017-05, 2017-06, 2017-07, 2017-08, 2017-09, 2017-10, 2017-11, 2017-12, 2018-01, 2018-02, 2018-03, 2018-04, 2018-05, 2018-06, 2018-07, 2018-08, 2018-09, 2018-10, 2018-11, 2018-12, 2019-01, 2019-02, 2019-03, 2019-04, 2019-05 ...
- Blog low-density 기준: < 40% of median (815.2)
  - Low years: 2016(52), 2017(63), 2018(160), 2019(276)
- Telegram low-density 기준: < 40% of non-zero median (13993.6)
  - Low years: 2016(0), 2017(0), 2018(0), 2019(3393), 2020(12679)
- Telegram undated channel files: 19개

## 3) Other Stage01 Input Health (missing/validation)

- KR stock list: 2882 symbols
- KR OHLCV files: 2883 (missing symbols=0, extra=['019440'])
- KR Supply files: 2882 (missing symbols=0)
- US OHLCV files: 508
- RSS/Macro/Trends/ImageMap/OCR: 84/12/8/4/20
- daily_update_status: ts=2026-02-14T02:27:52.008913 failed_count=1
  - latest failure sample: invest/scripts/fetch_us_ohlcv.py (stale status, 재실행 필요)
- post_collection_validate: ok=True failed_count=0 mode=hourly_freshness

## 4) Backfill Action Queue

1. DART: missing 52 month windows batch backfill (retry max 3, exp backoff)
2. Blog: 633 buddies full cycle(6 passes) backfill
3. Telegram: full 10Y mode backfill (global/per-channel timeout + retry)
4. Stage01 기타 소스 재수집: stock list / KR OHLCV / KR supply / US OHLCV / RSS / macro / trends / image harvester