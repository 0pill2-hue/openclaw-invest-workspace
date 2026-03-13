# JB-20260308-STAGE1REMAIN

- generated_at: 2026-03-08T13:54:05
- minimal_interpretation: Stage1 카테고리는 `source_coverage_index.json` taxonomy/db/source 항목 + tree_only(image_map/images_ocr)로 보고, 잔여구간은 10년 범위/월 연속성/증분 필요/외부 blocker 기준으로 판단함.
- safe_execution_this_run:
  - `python3 invest/stages/stage1/scripts/stage01_backfill_10y_coverage_audit.py` 실행 -> 최신 10년 커버리지 audit 생성
  - `python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile us_ohlcv_daily` 실행 -> rc=0, 그러나 US OHLCV date lag 지속
  - `python3 invest/stages/stage1/scripts/stage01_update_coverage_manifest.py` 실행 -> source coverage SSOT 최신화

## 1) Actionable remaining task triage
- JB-20260307-005 | P0 | PARTIAL
  - why: KR supply 네이버 대체는 현재 동작하지만, selected articles 2016 coverage는 아직 미완
  - detail: KR supply=OK source=naver_finance_item_frgn success=2770/2770; selected_articles from/to=2019-10-07~2026-03-08, missing_months=75
  - next: selected articles는 별도 장시간 backfill/도메인 접근성 개선이 필요
  - evidence: invest/stages/stage1/outputs/runtime/kr_supply_status.json, invest/stages/stage1/outputs/raw/source_coverage_index.json
- JB-20260305-030 | P1 | BLOCKED_EXTERNAL
  - why: Telegram full coverage는 인증 자격정보 부재로 외부의존
  - detail: allowlist=44, covered=28, uncovered=16, auth_env_present=False
  - next: TELEGRAM_API_ID/HASH(+세션) 제공 전까지 public fallback 범위만 유지
  - evidence: invest/stages/stage1/outputs/reports/stage_updates/_telegram_coverage.json, invest/stages/stage1/outputs/raw/source_coverage_index.json
- JB-20260306-007 | P0 | BLOCKED_DEP
  - why: OCR 누락 보완은 현재 OCR unavailable 상태라 즉시 완료 불가
  - detail: attachments_total=1 extracted=0 failed=1 txt_file_count=0
  - next: OCR runtime/엔진 가용화 후 재실행 필요
  - evidence: invest/stages/stage1/outputs/runtime/telegram_attachment_extract_stats_latest.json, invest/stages/stage1/outputs/runtime/stage01_ocr_postprocess_validate.json
- US_OHLCV_INCREMENTAL | P1 | EXECUTED_BUT_REMAINS
  - why: 안전하게 재실행 가능해 이번 런에서 1회 실행했지만 date lag 지속
  - detail: rerun_rc=0, latest_date=2026-02-26, needs_incremental_update=True
  - next: fetch_us_ohlcv 소스/API 응답 기준으로 2026-02-26 고착 원인 확인 필요
  - evidence: invest/stages/stage1/outputs/runtime/daily_update_us_ohlcv_daily_status.json, invest/stages/stage1/outputs/raw/source_coverage_index.json

## 2) Stage1 category remaining-coverage report
- summary: PASS=6, remaining_or_blocked=7

| category | kind | from | to | current_state | remaining |
|---|---|---|---|---|---|
| dart | db | 2016-01-04 | 2026-03-06 | PASS | 잔여 없음 |
| kr_ohlcv | db | 2016-01-04 | 2026-03-06 | PASS | 잔여 없음 |
| kr_supply | db | 2016-02-16 | 2026-03-06 | PASS | 잔여 없음 |
| us_ohlcv | db | 2016-01-04 | 2026-02-26 | REMAIN | 증분 갱신 필요 |
| macro | db | 2016-03-08 | 2026-03-06 | PASS | 잔여 없음 |
| rss | source | 2025-01-25 | 2026-03-08 | REMAIN | 결손 12개월 |
| news_url_index | source | 2015-12-01 | 2026-03-08 | PASS | 잔여 없음 |
| news_selected_articles | source | 2019-10-07 | 2026-03-08 | REMAIN | 결손 75개월 |
| telegram | source | 2019-10-25 | 2026-03-08 | PASS | 잔여 없음 |
| blog | source | 2016-03-14 | 2026-03-08 | REMAIN | 결손 1개월 |
| premium | source | 미정의 | 미정의 | BLOCKED | date 필드 부재 |
| image_map | tree_only | 미정의 | 미정의 | TREE_ONLY | date semantics 없음 (파일 26개) |
| images_ocr | tree_only | 미정의 | 미정의 | BLOCKED | OCR 산출 0건, reason=ocr_unavailable |

## 3) Focus notes by category
- KR supply: `kr_supply_status.json` 기준 `status=OK`, `source=naver_finance_item_frgn`, `success_count=2770/2770`로 네이버 대체 수집 자체는 동작함. 다만 post-collection freshness는 KRX login required waiver가 함께 기록됨.
- News selected articles: `source_coverage_index.json` 기준 from=2019-10-07, to=2026-03-08, missing_months=75. 2016 coverage 완료 목표는 아직 미달.
- Telegram: allowlist 44 중 public/full artifact 기준 미커버 16개. `auth_env_present=False`라 인증기반 full 확장은 외부 blocker.
- RSS: 10년 audit 기준 `rss_provider_retention_limit`. rss file 자체는 2025-01-25~2026-03-08만 확보됨.
- Premium: markdown 971개가 있으나 publish timestamp 필드가 없어 date coverage를 정의하지 못함(`premium_linkmeta_no_original_publish_timestamp`).
- OCR/images: attachment extract latest stats상 `reason_counts={'ocr_unavailable': 1}`, postprocess validate `txt_file_count=0`로 실 OCR 텍스트 산출은 아직 0건.

## 4) Concrete proof paths
- `runtime/reports/JB-20260308-STAGE1REMAIN.md`
- `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- `invest/stages/stage1/outputs/reports/stage_updates/STAGE1_BACKFILL_10Y_COVERAGE_20260308_133917.json`
- `invest/stages/stage1/outputs/runtime/daily_update_us_ohlcv_daily_status.json`
- `invest/stages/stage1/outputs/runtime/kr_supply_status.json`
- `invest/stages/stage1/outputs/reports/stage_updates/_telegram_coverage.json`
- `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_stats_latest.json`
