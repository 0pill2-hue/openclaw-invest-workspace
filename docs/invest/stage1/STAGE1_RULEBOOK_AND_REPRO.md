# Stage1 Rulebook & Repro

status: CANONICAL (stage contract / stage index target)  
updated_at: 2026-03-07 KST
ops companion: `docs/invest/stage1/RUNBOOK.md`

## 문서 역할
- cross-stage 인덱스(`STAGE_EXECUTION_SPEC.md`, `RULEBOOK_MASTER.md`)가 참조하는 Stage1 대표 문서다.
- Stage1의 범위/입력/출력/검증 계약을 요약한다.
- day-2 운영 명령, 환경변수, fallback, coverage 보고 상세는 `RUNBOOK.md`를 우선한다.

## 1) 범위
- 역할: 외부 원천 데이터 **수집(raw 적재)** + 수집 상태 기록(runtime)
- 책임 경계:
  - Stage1: `invest/stages/stage1/outputs/{master,raw,runtime,logs,reports}` 작성
  - Stage2: `clean/quarantine` 정제·검역(Stage1 비책임)

## 2) 입력(Inputs)
- `invest/stages/stage1/inputs/config/news_sources.json`
- `invest/stages/stage1/inputs/config/dart_api_key.txt`
- `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
- terminal registry: `invest/stages/stage1/inputs/config/telegram_terminal_status.json`, `invest/stages/stage1/inputs/config/blog_terminal_status.json`
- 외부 원천 API/피드(FDR/pykrx/yfinance/FRED/RSS/DART/Telethon)

## 3) 실행 진입점(Scripts/Runtime)
- 메인 수집: `invest/stages/stage1/scripts/stage01_daily_update.py --profile <name>`
  - runtime 상태 파일은 저장소 루트 기준 `invest/stages/stage1/outputs/runtime/daily_update_<profile>_status.json`에 기록하고, `daily_full`은 canonical alias `daily_update_status.json`도 사용한다.
  - 하위 스크립트는 저장소 루트 `cwd`로 실행한다.
  - profile 분리:
    - `daily_full`: stage1 core 수집
    - `rss_fast`, `telegram_fast`, `blog_fast`, `kr_ohlcv_intraday`, `kr_supply_intraday`, `us_ohlcv_daily`, `dart_fast`: cadence 분리 프로필
    - `news_backfill`: `selected_articles` 2016 coverage 백필 전용 프로필
  - `news_backfill`은 이미 수집 성공한 selected article URL을 건너뛰고 미수집 backlog를 우선 처리한다.
- 체인 실행: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 게이트:
  - `invest/stages/stage1/scripts/stage01_checkpoint_gate.py`
  - `invest/stages/stage1/scripts/stage01_post_collection_validate.py`
- coverage/유지보수 보조:
  - `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
  - `invest/stages/stage1/scripts/stage01_rss_date_repair.py`
  - `invest/stages/stage1/scripts/stage01_telegram_undated_repair.py`
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- 보조 잡:
  - `invest/stages/stage1/scripts/launchd/launchd_stage01_profile.sh` (profile-based launchd wrapper)
  - `invest/ops/launchd/plists/com.jobiseu.invest.stage1.backfill.news.plist` (`news_backfill`, `StartInterval=1800`)
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
  - `invest/stages/stage1/outputs/runtime/telegram_collector_status.json`
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
  - `invest/stages/stage1/outputs/runtime/pipeline_events.jsonl`
- Coverage / reports
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
  - `invest/stages/stage1/outputs/reports/data_quality/`
  - `invest/stages/stage1/outputs/reports/stage_updates/`

## 5) 재현 커맨드
```bash
# Stage1 기본 수집
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile daily_full

# cadence 분리 프로필 예시
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile telegram_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile blog_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile rss_fast

# selected articles 2016 coverage 백필
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile news_backfill

# 뉴스 2단계(전수 URL 인덱스 -> 선별 본문)
python3 invest/stages/stage1/scripts/stage01_build_news_url_index.py
python3 invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py

# coverage/보정 보조
python3 invest/stages/stage1/scripts/stage01_update_coverage_manifest.py
python3 invest/stages/stage1/scripts/stage01_rss_date_repair.py
python3 invest/stages/stage1/scripts/stage01_telegram_undated_repair.py

# Stage1 게이트(체인 fail-close와 동일 순서)
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py

# 체인 실행(Stage1~4)
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

## 5.1) provenance / 추적성 원칙
- Stage1 실행 provenance의 canonical runtime 근거는 `daily_update_status.json`과 `pipeline_events.jsonl`이다.
- 최소 provenance는 `run_id`, `profile`, `scheduler_origin`, `host`, `python_bin`, `git commit` 수준에서 추적 가능해야 한다.
- structured JSON/JSONL 산출물은 가능하면 `published_at`, `collected_at`, `source identity`를 유지하되, 기존 markdown collector는 런타임 sidecar 상태 파일로 보강한다.
- 중복 제거는 기존 URL/ID 중심 로직을 우선 유지하고, 텍스트 fingerprint는 실제 필요가 확인된 경로에만 제한 도입한다.

## 6) 검증 기준
- `invest/stages/stage1/outputs/runtime/post_collection_validate.json` 의 `ok=true`
- `run_stage1234_chain.sh`는 Stage1 직후 아래 순서로 게이트 실행:
  - `stage01_checkpoint_gate.py`
  - `stage01_post_collection_validate.py`
- 두 게이트 중 하나라도 non-zero 또는 `ok=false`이면 즉시 fail-close 종료(`fail_close_exit`)하고 Stage2~4는 실행 금지
- `stage01_post_collection_validate.py`는 Stage1 core source(신호 5종 + 정성 5종)를 최소건수/0바이트/신선도 기준으로 검증하며 실패 시 `ok=false`, `failed_count>0`, exit code 1
- 핵심 컬렉터(telegram/rss)는 최소 성공 임계치 미달 시 exit code 1을 반환하며, 임계치는 env로 완화 가능
