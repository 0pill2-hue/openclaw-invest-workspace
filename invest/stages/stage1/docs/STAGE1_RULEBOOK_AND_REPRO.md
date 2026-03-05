# Stage1 Rulebook & Repro

## 1) 범위
- 역할: 외부 원천 데이터 **수집(raw 적재)** + 수집 상태 기록(runtime).
- 책임 경계:
  - Stage1: `invest/stages/stage1/outputs/{master,raw,runtime,logs,reports}` 작성
  - Stage2: `clean/quarantine` 정제·검역(Stage1 비책임)

## 2) 입력(Inputs)
- `invest/stages/stage1/inputs/config/news_sources.json`
- `invest/stages/stage1/inputs/config/dart_api_key.txt`
- `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
- 외부 원천 API/피드(FDR/pykrx/yfinance/FRED/RSS/DART/Telethon)

## 3) 실행 진입점(Scripts/Runtime)
- 메인 수집: `invest/stages/stage1/scripts/stage01_daily_update.py`
- 체인 실행: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 보조 잡:
  - `invest/stages/stage1/scripts/launchd/launchd_dart_backfill_autopilot.sh`
  - `invest/stages/stage1/scripts/launchd/launchd_rss_telegram_date_fix.sh`
  - `invest/stages/stage1/scripts/launchd/launchd_supply_autorepair.sh`
  - launchd agent `com.jobiseu.openclaw.invest.stage01.blog` -> `stage01_scrape_all_posts_v2.py`
  - launchd agent `com.jobiseu.openclaw.invest.stage01.telegram` -> `stage01_scrape_telegram_launchd.py`

## 4) 출력 경로(Outputs)
- Master
  - `invest/stages/stage1/outputs/master/kr_stock_list.csv`
- Raw 루트
  - `invest/stages/stage1/outputs/raw/signal/`
  - `invest/stages/stage1/outputs/raw/qualitative/`
  - signal: `market/macro`, `kr/ohlcv`, `kr/supply`, `us/ohlcv`, 기타 수치/시계열
  - qualitative: `kr/dart`, `market/rss`, `market/news/url_index`, `market/news/selected_articles`, `text/*`, `images_ocr`, `image_map`, 기타 비정형
- Runtime
  - `invest/stages/stage1/outputs/runtime/daily_update_status.json`
  - `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- Reports
  - `invest/stages/stage1/outputs/reports/data_quality/`
  - `invest/stages/stage1/outputs/reports/stage_updates/`

## 5) 재현 커맨드
```bash
# Stage1 수집
python3 invest/stages/stage1/scripts/stage01_daily_update.py

# 뉴스 2단계(전수 URL 인덱스 -> 선별 본문)
python3 invest/stages/stage1/scripts/stage01_build_news_url_index.py
python3 invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py

# Stage1 게이트(체인 fail-close와 동일 순서)
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py

# 체인 실행(Stage1~4)
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

## 6) 검증 기준
- `invest/stages/stage1/outputs/runtime/post_collection_validate.json` 의 `ok=true`
- `run_stage1234_chain.sh`는 Stage1 직후 아래 순서로 게이트 실행:
  - `stage01_checkpoint_gate.py`
  - `stage01_post_collection_validate.py`
- 두 게이트 중 하나라도 non-zero 또는 `ok=false`이면 즉시 fail-close 종료(`fail_close_exit`)하고 Stage2~4는 실행 금지
- `stage01_post_collection_validate.py`는 Stage1 core source(신호 5종 + 정성 5종)를 최소건수/0바이트/신선도 기준으로 검증하며 실패 시 `ok=false`, `failed_count>0`, exit code 1
- 핵심 컬렉터(telegram/rss)는 최소 성공 임계치 미달 시 exit code 1을 반환하며, 임계치는 env로 완화 가능
