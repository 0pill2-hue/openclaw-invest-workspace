# RUNBOOK

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
- `.env`: 미확인. 저장소 내 Stage1 전용 `.env` 사용 여부는 확인되지 않았다.

## 실행 커맨드
```bash
python3 invest/stages/stage1/scripts/stage01_daily_update.py
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
python3 invest/stages/stage1/scripts/stage01_build_news_url_index.py
python3 invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py
python3 invest/stages/stage1/scripts/stage01_backfill_10y.py --years 10
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
- coverage 인덱스: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- 리포트/로그: `invest/stages/stage1/outputs/reports/data_quality/`, `invest/stages/stage1/outputs/reports/stage_updates/`, `invest/stages/stage1/outputs/logs/runtime/`

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

## 실패 / 폴백 규칙
- 메인 오케스트레이터 위치: `invest/stages/stage1/scripts/stage01_daily_update.py`
- `run_with_fallbacks()`는 아래 primary 실패 시 full fetch fallback을 시도한다.
  - `stage01_fetch_ohlcv.py` → `stage01_full_fetch_ohlcv.py`
  - `stage01_fetch_supply.py` → `stage01_full_fetch_supply.py`
  - `stage01_fetch_us_ohlcv.py` → `stage01_full_fetch_us_ohlcv.py`
  - `stage01_fetch_dart_disclosures.py` → `stage01_full_fetch_dart_disclosures.py`
- Telegram launchd 엔트리 위치: `invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py`
  - 인증 환경변수가 있으면 `stage01_scrape_telegram_highspeed.py` 우선 실행
  - 실패하거나 인증 정보가 없으면 `stage01_scrape_telegram_public_fallback.py`로 전환
  - 실행 결과/실사용 collector는 `invest/stages/stage1/outputs/runtime/telegram_collector_status.json`에 기록
- 체인 fail-close 위치: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
  - `stage01_checkpoint_gate.py` 또는 `stage01_post_collection_validate.py`가 실패하면 Stage2 이후를 막고 종료한다.

## 운영 주기 / 스케줄
- 일일 메인 수집 진입점은 `stage01_daily_update.py`다.
- Stage1~4 연쇄 자동화 진입점은 `run_stage1234_chain.sh`다.
- `RUN_US_OHLCV_IN_DAILY=1|true|yes`일 때만 US OHLCV를 일일 통합 수집에 포함한다.
- launchd 보조 잡 존재는 확인되었으나 실제 스케줄 값은 본 저장소 문서 기준 미확인이다.
