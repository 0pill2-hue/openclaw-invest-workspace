# RUNBOOK

status: CANONICAL (operations)
updated_at: 2026-03-13 KST
contract source: `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`

## 문서 역할
- Stage1 실행 절차/명령/환경변수/스케줄/장애 대응의 단일 SSOT.
- Stage 계약(범위/입출력/게이트 판정)을 여기서 중복 정의하지 않는다.

## 필수 환경변수
- `INVEST_PYTHON_BIN` (선택)
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` (Telegram 인증 수집)
- `DART_API_KEY` (선택)
- `RUN_US_OHLCV_IN_DAILY=1|true|yes` (daily_full에서 US OHLCV 포함)

## 실행 명령
```bash
# 기본 프로필
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile daily_full

# cadence 분리 프로필
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile selected_articles_naver_only
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile rss_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile telegram_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile blog_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile kr_ohlcv_intraday
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile kr_supply_intraday
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile us_ohlcv_daily
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile dart_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile news_backfill

# 게이트/보조
python3 invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
python3 invest/stages/stage1/scripts/stage01_collect_link_sidecars.py

# 체인 실행(Stage1~4)
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

## 운영 절차
1. profile 실행
2. Telegram 수집 lane이면 attachment recovery/backfill lane(`stage01_telegram_attachment_extract_backfill.py`)을 같은 cadence의 기본 후속 단계로 본다. `stage01_scrape_telegram_launchd.py`는 이 lane을 자동 호출한다.
3. checkpoint gate 실행
4. post-collection gate 실행
5. gate PASS 시에만 Stage2 이상 진행

## 스케줄/용도
- `daily_full`: Stage1 기본 수집
- `telegram_fast`: Telegram markdown 수집 + attachment recovery/backfill lane까지 같은 기본 cadence로 본다
- `selected_articles_naver_only`: live selected_articles 단독 갱신
- `news_backfill`: RSS/URL-index backlog 보강
- `launchd/run_stage1234_chain.sh`: Stage1~4 연쇄 자동화

## 장애 대응
- orchestrator 실패: 해당 profile 재실행 후 gate 재검증
- fallback 사용 발생: `daily_update_<profile>_status.json`의 `fallbacks_used[]` 확인
- Telegram 인증 경로 실패/미설정: 공개 fallback collector 경로로 전환 여부 확인
- attachment recovery 품질 점검: `stage1_attachment_recovery_summary.json`에서 `stage_status`와 `completeness_status`를 분리해서 본다. `retry_visibility.retry_count/last_retry_at/last_error`와 `recovery_lane.selected_candidates/failed`로 재시도 visibility를 확인한다.
- gate FAIL: Stage2~4 중단 후 원인(source freshness/zero-byte/coverage/runtime status) 수정

## 운영 보고 필수 항목
- 실행 profile / run_id
- gate 결과(`ok`, `failed_count`, `stage_status`, `completeness_status`)
- 핵심 proof 경로
  - `invest/stages/stage1/outputs/runtime/daily_update_<profile>_status.json`
  - `invest/stages/stage1/outputs/runtime/stage1_attachment_recovery_summary.json`
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
  - `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
  - `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
