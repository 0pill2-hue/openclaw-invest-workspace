# stage01_data_collection

status: REFERENCE_APPENDIX  
updated_at: 2026-03-07 KST

## 문서 역할
- Stage1 collector ↔ output path/source map 보조 카탈로그다.
- Stage1 운영 명령/환경변수/폴백 SSOT는 `RUNBOOK.md`를 따른다.
- Stage1 범위/입출력/검증 계약 요약은 `STAGE1_RULEBOOK_AND_REPRO.md`를 따른다.

## 목적
- 외부 원천 데이터를 Stage1 raw에 수집/보존한다.
- Stage2 정제·검역 입력의 원천(raw lineage)을 고정한다.

## 책임 분리
- Stage1: 수집 + raw/master/runtime 기록
- Stage2: 정제(clean)·격리(quarantine)·품질 리포트
- raw 분리 원칙:
  - signal: 수치/시계열 원천(`raw/signal/...`)만 직접 점수식 입력 허용
  - qualitative: 비정형 원천(`raw/qualitative/...`)은 중간 추출/피처화 경유만 허용

## 입력 경로
- `invest/stages/stage1/inputs/config/news_sources.json`
- `invest/stages/stage1/inputs/config/dart_api_key.txt`
- `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
- Telegram full 수집 secret(평문 파일 저장 금지):
  - `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` (launchctl setenv 또는 안전한 런타임 주입)

## 수집 스크립트 ↔ 산출 경로(1:1)

### KR
- `invest/stages/stage1/scripts/stage01_fetch_stock_list.py`
  - `invest/stages/stage1/outputs/master/kr_stock_list.csv`
- `invest/stages/stage1/scripts/stage01_fetch_ohlcv.py`
  - `invest/stages/stage1/outputs/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage1/scripts/stage01_fetch_supply.py`
  - `invest/stages/stage1/outputs/raw/signal/kr/supply/*_supply.csv`
- `invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py`
  - `invest/stages/stage1/outputs/raw/qualitative/kr/dart/*.csv`

### US
- `invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py`
  - `invest/stages/stage1/outputs/raw/signal/us/ohlcv/*.csv`

### Market
- `invest/stages/stage1/scripts/stage01_fetch_macro_fred.py`
  - `invest/stages/stage1/outputs/raw/signal/market/macro/*.csv`
- `invest/stages/stage1/scripts/stage01_fetch_global_macro.py`
  - `invest/stages/stage1/outputs/raw/signal/market/macro/*.csv`
  - 추가 지표: `BUFFETT_INDICATOR.csv`, `CREDIT_OSCILLATOR.csv`, `macro_summary.json`
- `invest/stages/stage1/scripts/stage01_fetch_news_rss.py`
  - `invest/stages/stage1/outputs/raw/qualitative/market/rss/*.json`
- `invest/stages/stage1/scripts/stage01_build_news_url_index.py` *(뉴스 1단계: 전수 URL 인덱스)*
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/url_index/*.jsonl`
  - 입력: `news_sources.json` 피드 도메인 기준 sitemap/rss archive
- `invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py` *(뉴스 2단계: 선별 본문 수집)*
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/*.jsonl`
  - 입력: `url_index` + keyword 우선순위

### Text
- `invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py` *(launchd: com.jobiseu.openclaw.invest.stage01.blog)*
  - `invest/stages/stage1/outputs/raw/qualitative/text/blog/**.md`
- `invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py` *(launchd 엔트리 / canonical wrapper)*
  - secret env 존재 시: `stage01_scrape_telegram_highspeed.py` 실행
  - secret env 미존재/실패 시: `stage01_scrape_telegram_public_fallback.py` 실행
  - 출력: `invest/stages/stage1/outputs/raw/qualitative/text/telegram/*.md`
  - runtime status: `invest/stages/stage1/outputs/runtime/telegram_collector_status.json`
- `invest/stages/stage1/scripts/stage01_collect_premium_startale_channel_auth.py`
  - `invest/stages/stage1/outputs/raw/qualitative/text/premium/startale/*.md`
  - `invest/stages/stage1/outputs/raw/qualitative/text/premium/startale/_index.json`
  - `invest/stages/stage1/outputs/raw/qualitative/text/premium/startale_channel_direct/_discovery.json`
  - 로그인 세션 기반 직접열람 수집(`isLogin=true` 경로)
- Telegram image attachment는 메시지 메타데이터만 기록하며 별도 `image_map`/`images_ocr` raw는 생성하지 않는다.

## 실행 프로필
- 메인(증분):
  - `python3 invest/stages/stage1/scripts/stage01_daily_update.py`
- 뉴스 2단계 단독 실행:
  - `python3 invest/stages/stage1/scripts/stage01_build_news_url_index.py`
  - `python3 invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py`
- 풀 백필(개별):
  - `python3 invest/stages/stage1/scripts/stage01_full_fetch_ohlcv.py`
  - `python3 invest/stages/stage1/scripts/stage01_full_fetch_supply.py`
  - `python3 invest/stages/stage1/scripts/stage01_full_fetch_us_ohlcv.py`
  - `python3 invest/stages/stage1/scripts/stage01_full_fetch_dart_disclosures.py`

## 런타임/리포트
- runtime:
  - `invest/stages/stage1/outputs/runtime/daily_update_status.json`
  - `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- logs:
  - `invest/stages/stage1/outputs/logs/runtime/`
- reports:
  - `invest/stages/stage1/outputs/reports/data_quality/`
  - `invest/stages/stage1/outputs/reports/stage_updates/`

## 체크포인트 게이트
- run: `python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py`
- output: `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
- PASS: `ok=true`
