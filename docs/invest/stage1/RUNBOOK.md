# RUNBOOK

status: CANONICAL (operations)  
updated_at: 2026-03-07 KST

## 문서 역할
- Stage1 일상 운영/재현/실행 절차의 단일 SSOT다.
- cross-stage 인덱스용 stage 계약 요약은 `STAGE1_RULEBOOK_AND_REPRO.md`가 맡는다.
- 이 문서와 다른 Stage1 문서가 실행 명령/환경변수/폴백/coverage 보고에서 충돌하면 본 문서를 우선한다.

## 목적
Stage1은 외부 원천 데이터를 수집해 Stage2 이후가 사용할 raw/master/runtime 기준선을 만든다.
운영 재현, 실행 명령, 출력 경로, 실패 시 처리 규칙은 본 문서가 단일 SSOT다.

## 입력 요약
- 설정 파일: `invest/stages/stage1/inputs/config/news_sources.json`
- 키 파일: `invest/stages/stage1/inputs/config/dart_api_key.txt`
- 허용 목록: `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
- 외부 원천: FDR, pykrx, yfinance, FRED, RSS, DART, Telegram, 웹 수집 대상

## 필수 환경변수 / 키
- `INVEST_PYTHON_BIN`: 선택. 유효한 실행 파일이면 하위 파이썬 호출에 사용하고, 없거나 무효면 기본 실행기(`sys.executable` 또는 `python3`)를 사용한다.
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`: Telegram 인증 수집 경로 사용 시 필요. 없으면 공개 fallback 경로로 전환된다.
- `DART_API_KEY`: DART 수집 스크립트가 파일 대신 환경변수로 읽을 때 사용 가능.
- `RUN_US_OHLCV_IN_DAILY=1|true|yes`: `daily_full` 프로필에 US OHLCV를 추가 포함할 때만 사용한다.
- `invest/stages/stage1/.env`: 현재 저장소 기준 파일 없음. 일부 스크립트에 optional load 경로는 남아 있으나 운영 표준은 환경변수/launchctl 주입이다.

## 실행 커맨드
```bash
# 기본 일일 수집 프로필
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile daily_full

# 개별 cadence 프로필
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile rss_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile telegram_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile blog_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile kr_ohlcv_intraday
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile kr_supply_intraday
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile us_ohlcv_daily
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile dart_fast

# selected articles 2016 coverage 백필 cadence
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile news_backfill

# 게이트/보조
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
python3 invest/stages/stage1/scripts/stage01_build_news_url_index.py
python3 invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py
python3 invest/stages/stage1/scripts/stage01_backfill_10y.py --years 10
python3 invest/stages/stage1/scripts/stage01_update_coverage_manifest.py
python3 invest/stages/stage1/scripts/stage01_rss_date_repair.py
python3 invest/stages/stage1/scripts/stage01_telegram_undated_repair.py
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

## 출력 경로
- 마스터: `invest/stages/stage1/outputs/master/kr_stock_list.csv`
- 신호 raw: `invest/stages/stage1/outputs/raw/signal/`
  - KR OHLCV: `invest/stages/stage1/outputs/raw/signal/kr/ohlcv/*.csv`
  - KR 수급: `invest/stages/stage1/outputs/raw/signal/kr/supply/*_supply.csv`
  - US OHLCV: `invest/stages/stage1/outputs/raw/signal/us/ohlcv/*.csv`
  - 매크로: `invest/stages/stage1/outputs/raw/signal/market/macro/*.csv`
- 정성 raw: `invest/stages/stage1/outputs/raw/qualitative/`
  - RSS: `invest/stages/stage1/outputs/raw/qualitative/market/rss/*.json`
  - 뉴스 URL 인덱스: `invest/stages/stage1/outputs/raw/qualitative/market/news/url_index/*.jsonl`
  - 선별 뉴스 본문: `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/*.jsonl`
  - DART: `invest/stages/stage1/outputs/raw/qualitative/kr/dart/*.csv`
  - DART coverage SSOT: `invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json`
  - 텍스트/텔레그램/프리미엄/OCR: `invest/stages/stage1/outputs/raw/qualitative/text/`
- 런타임 상태: `invest/stages/stage1/outputs/runtime/daily_update_status.json`, `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- 실행 이벤트 로그: `invest/stages/stage1/outputs/runtime/pipeline_events.jsonl`
- coverage 인덱스: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- 리포트/로그: `invest/stages/stage1/outputs/reports/data_quality/`, `invest/stages/stage1/outputs/reports/stage_updates/`, `invest/stages/stage1/outputs/logs/runtime/`

## provenance / 추적성 SSOT
- Stage1 실행 provenance는 `daily_update_status.json` + `pipeline_events.jsonl` 조합으로 본다.
- `daily_update_status.json`은 최소 `run_id`, `profile`, `scheduler_origin`, `host`, `python_bin`, `repo_root`, `started_at/finished_at`를 남긴다.
- `pipeline_events.jsonl`은 collector 단위 이벤트와 함께 `failure_kind` 및 실행 provenance를 남겨 후속 디버깅 기준으로 사용한다.
- markdown 기반 telegram/blog raw는 원문 보존을 우선하고, provenance/실행 상태는 runtime sidecar에서 먼저 관리한다.

## coverage / 보고 SSOT
- DB/source별 수집 범위 판단은 raw 파일 직접 육안 확인이 아니라 `coverage_summary.json` 기준으로 한다.
- 현재 DART SSOT는 `invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json` 이다.
- 전체 인덱스는 `invest/stages/stage1/outputs/raw/source_coverage_index.json` 이다.
- 데이터가 추가로 모이면 해당 수집 스크립트가 coverage manifest를 즉시 갱신해야 한다.
- 운영 보고 시에는 반드시 manifest 기준으로 아래를 같이 보고한다.
  - earliest_date
  - latest_date
  - missing_months_between_range
  - needs_incremental_update
  - blog: `active_from=20160101`, `all_buddies_satisfied`
  - telegram: `all_channels_satisfied`, `missing_allowlist_entries`
- blog raw/backfill 기준 시작일은 rolling 10y가 아니라 `2016-01-01` 고정이다.

## 실패 / 폴백 규칙
- 메인 오케스트레이터 위치: `invest/stages/stage1/scripts/stage01_daily_update.py`
- `stage01_daily_update.py`는 runtime 상태 파일을 저장소 루트 기준 `invest/stages/stage1/outputs/runtime/daily_update_<profile>_status.json`에 쓰고, `daily_full` 프로필은 canonical alias `daily_update_status.json`을 함께 사용한다.
- `stage01_daily_update.py`가 하위 스크립트를 실행할 때는 저장소 루트(`cwd=$REPO_ROOT`)로 고정한다. 별도 per-script timeout은 두지 않고, 상위 체인 `run_stage1234_chain.sh`의 stage-level timeout을 권위 기준으로 사용한다.
- `run_with_fallbacks()`는 아래 primary 실패 시 full fetch fallback을 시도한다.
  - `stage01_fetch_ohlcv.py` → `stage01_full_fetch_ohlcv.py`
  - `stage01_fetch_supply.py` → `stage01_full_fetch_supply.py`
  - `stage01_fetch_us_ohlcv.py` → `stage01_full_fetch_us_ohlcv.py`
  - `stage01_fetch_dart_disclosures.py` → `stage01_full_fetch_dart_disclosures.py`
- Telegram collector 진입 스크립트: `invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py`
  - 인증 환경변수가 있으면 `stage01_scrape_telegram_highspeed.py` 우선 실행
  - 실패하거나 인증 정보가 없으면 `stage01_scrape_telegram_public_fallback.py`로 전환
  - 실행 결과/실사용 collector는 `invest/stages/stage1/outputs/runtime/telegram_collector_status.json`에 기록
- 체인 fail-close 위치: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
  - 체인은 `stage01_daily_update.py --profile daily_full` 뒤에 `stage01_checkpoint_gate.py`, `stage01_post_collection_validate.py`를 실행한다.
  - 둘 중 하나라도 실패하면 Stage2 이후를 막고 종료한다.

## 운영 주기 / 스케줄
- Stage1 단일 진입점은 `stage01_daily_update.py --profile <name>` 이다.
- Stage1~4 연쇄 자동화 진입점은 `run_stage1234_chain.sh`다.
- `daily_full`은 stage1 core 수집(시장/뉴스/DART/프리미엄/OCR)용 기본 프로필이다.
- `rss_fast`, `telegram_fast`, `blog_fast`, `kr_ohlcv_intraday`, `kr_supply_intraday`, `us_ohlcv_daily`, `dart_fast`는 cadence 분리를 위한 개별 프로필이다.
- `news_backfill`은 `selected_articles`를 2016 coverage까지 끌어내리기 위한 전용 프로필이며, 완료 전까지 짧은 interval(권장 30분~60분)로 유지한다.
- `news_backfill`은 `NEWS_SELECTED_SKIP_EXISTING=1`을 기본으로 사용해 이미 수집 성공한 URL은 건너뛰고 미수집 URL에 집중한다.
- `news_backfill`의 무료 보강 경로는 Guardian Open Platform(search api + Guardian business RSS)와 공식기관 RSS(Fed/ECB/SEC)다. 기본 backfill 범위는 `NEWS_INDEX_TARGET_DATE=2016-01-01`, `GUARDIAN_END_DATE=2019-12-31`이다.
- `invest/stages/stage1/scripts/launchd/launchd_stage01_profile.sh`가 launchd용 canonical profile wrapper다.
- `invest/ops/launchd/plists/com.jobiseu.invest.stage1.backfill.news.plist`는 `news_backfill`을 `StartInterval=1800`(30분) cadence로 실행한다.
- `RUN_US_OHLCV_IN_DAILY=1|true|yes`일 때만 US OHLCV를 `daily_full`에 추가 포함한다.
- blog/telegram 전용 cadence도 이제 동일 orchestrator의 profile 호출로 정리하며, 개별 raw collector 직접 호출은 canonical이 아니다.
