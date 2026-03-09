# Stage1 Rulebook & Repro

status: CANONICAL (stage contract / reproducible orchestration spec)  
updated_at: 2026-03-09 KST  
ops companion: `docs/invest/stage1/RUNBOOK.md`

## 문서 역할
- 이 문서는 **Stage1을 문서만 보고 재구현할 때 필요한 orchestration/gate/runtime 계약**을 고정한다.
- collector별 raw artifact 상세 포맷은 `stage01_data_collection.md`를 본다.
- 운영 명령/launchd/환경변수 절차는 `RUNBOOK.md`를 본다.

---

## 1) 범위
- 역할: 외부 원천 데이터 **수집(raw 적재)** + 수집 상태(runtime) + Stage1 게이트 수행
- 비범위:
  - clean/quarantine 생성
  - 정성 점수화/feature 계산
  - downstream stage의 해석/투자판단
- Stage 경계:
  - Stage1 책임: `invest/stages/stage1/outputs/{master,raw,runtime,logs,reports}`
  - Stage2 책임: `clean/quarantine` 정제·격리

---

## 2) 입력(Inputs)
- 설정 파일
  - `invest/stages/stage1/inputs/config/news_sources.json`
  - `invest/stages/stage1/inputs/config/dart_api_key.txt`
  - `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
  - `invest/stages/stage1/inputs/config/telegram_terminal_status.json`
  - `invest/stages/stage1/inputs/config/blog_terminal_status.json`
- 런타임 secret / 외부 원천
  - FDR / pykrx / yfinance / FRED / RSS / DART / Telethon
  - Telegram full collector secret은 파일 평문 저장 금지: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- Stage1의 외부 입력은 **모두 collector를 통해 raw/master/runtime로만 반영**한다.

---

## 3) 실행 진입점 / profile 계약

### 3.1 메인 진입점
- canonical orchestrator: `invest/stages/stage1/scripts/stage01_daily_update.py`
- 인자:
  - `--profile <profile>`
- 지원 profile:
  - `daily_full`
  - `rss_fast`
  - `telegram_fast`
  - `blog_fast`
  - `kr_ohlcv_intraday`
  - `kr_supply_intraday`
  - `us_ohlcv_daily`
  - `dart_fast`
  - `news_backfill`

### 3.2 profile별 정확한 실행 스크립트
| profile | ordered scripts |
| --- | --- |
| `daily_full` | `stage01_fetch_stock_list.py` → `stage01_fetch_ohlcv.py` → `stage01_fetch_supply.py` → `stage01_fetch_us_ohlcv.py` → `stage01_fetch_macro_fred.py` → `stage01_fetch_global_macro.py` → `stage01_fetch_news_rss.py` → `stage01_build_news_url_index.py` → `stage01_collect_selected_news_articles.py` → `stage01_fetch_dart_disclosures.py` → `stage01_collect_premium_startale_channel_auth.py` → `stage01_update_coverage_manifest.py` |
| `rss_fast` | `stage01_fetch_news_rss.py` |
| `telegram_fast` | `stage01_scrape_telegram_launchd.py` |
| `blog_fast` | `stage01_scrape_all_posts_v2.py` |
| `kr_ohlcv_intraday` | `stage01_fetch_ohlcv.py` |
| `kr_supply_intraday` | `stage01_fetch_supply.py` |
| `us_ohlcv_daily` | `stage01_fetch_us_ohlcv.py` |
| `dart_fast` | `stage01_fetch_dart_disclosures.py` |
| `news_backfill` | `stage01_fetch_news_rss.py` → `stage01_build_news_url_index.py` → `stage01_collect_selected_news_articles.py` → `stage01_update_coverage_manifest.py` |

### 3.3 fallback 계약
다음 스크립트는 primary 실패 시 fallback script를 순서대로 시도한다.

| primary | fallback |
| --- | --- |
| `stage01_fetch_ohlcv.py` | `stage01_full_fetch_ohlcv.py` |
| `stage01_fetch_supply.py` | `stage01_full_fetch_supply.py` |
| `stage01_fetch_us_ohlcv.py` | `stage01_full_fetch_us_ohlcv.py` |
| `stage01_fetch_dart_disclosures.py` | `stage01_full_fetch_dart_disclosures.py` |

### 3.4 `news_backfill` 고정 env 계약
`news_backfill` profile은 아래 env를 주입한 실행을 문서상 canonical로 본다.

- RSS backfill
  - `RSS_ENABLE_PAGED_BACKFILL=1`
  - `RSS_BACKFILL_TARGET_DATE=2016-01-01`
  - `RSS_BACKFILL_TARGET_YEARS=10`
  - `RSS_BACKFILL_MAX_PAGES` default `400`
  - `RSS_BACKFILL_MAX_EMPTY_PAGES` default `3`
  - `RSS_DISABLE_KEYWORD_FILTER=1`
- URL index
  - `NEWS_INDEX_TARGET_DATE=2016-01-01`
  - `NEWS_INDEX_RSS_MAX_PAGES` default `120`
  - `NEWS_INDEX_MAX_SITEMAPS` default `300`
  - `GUARDIAN_ENABLE` default `1`
  - `GUARDIAN_END_DATE` default `2019-12-31`
  - `GUARDIAN_MAX_MONTHS` default `48`
  - `GUARDIAN_MAX_PAGES_PER_SLICE` default `1`
  - `GUARDIAN_PAGE_SIZE` default `50`
- selected articles
  - `NEWS_SELECTED_TARGET_DATE=2016-01-01`
  - `NEWS_SELECTED_MIN_KEYWORD_HITS` default `0`
  - `NEWS_SELECTED_MAX_ARTICLES` default `600`
  - `NEWS_SELECTED_MAX_ATTEMPTS` default `5000`
  - `NEWS_SELECTED_YEARLY_QUOTA` default `50`
  - `NEWS_SELECTED_SKIP_EXISTING` default `1`
  - `NEWS_SELECTED_EXCLUDED_DOMAINS` default `bloomberg.com,wsj.com`
  - `NEWS_SELECTED_EXCLUDED_URL_PATTERNS` default `/graphics/,/video/`

---

## 4) 출력 경로(Outputs)

### 4.1 Master
- `invest/stages/stage1/outputs/master/kr_stock_list.csv`

### 4.2 Raw
- `invest/stages/stage1/outputs/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage1/outputs/raw/signal/kr/supply/*_supply.csv`
- `invest/stages/stage1/outputs/raw/signal/us/ohlcv/*.csv`
- `invest/stages/stage1/outputs/raw/signal/market/macro/*`
- `invest/stages/stage1/outputs/raw/qualitative/kr/dart/*.csv`
- `invest/stages/stage1/outputs/raw/qualitative/market/rss/*.json`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/url_index/*.jsonl`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/*.jsonl`
- `invest/stages/stage1/outputs/raw/qualitative/text/{telegram,blog,premium}/**/*`
- Telegram attachment artifact
  - `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/<channel_slug>/msg_<message_id>/{meta.json,original,extracted.txt?}`

### 4.3 Runtime / reports
- runtime
  - `invest/stages/stage1/outputs/runtime/daily_update_status.json` (`daily_full` alias)
  - `invest/stages/stage1/outputs/runtime/daily_update_<profile>_status.json`
  - `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
  - `invest/stages/stage1/outputs/runtime/telegram_collector_status.json`
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
  - `invest/stages/stage1/outputs/runtime/pipeline_events.jsonl`
- reports
  - `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`

---

## 5) Runtime provenance / status schema

### 5.1 `daily_update(_<profile>)_status.json`
Stage1 orchestrator status JSON은 아래 필드를 canonical로 가진다.

- `timestamp`
- `started_at`
- `finished_at`
- `duration_sec`
- `run_id`
- `profile`
- `scheduler_origin` (`manual|launchd|env-override` 성격)
- `launchd_job_label`
- `host`
- `python_bin`
- `repo_root`
- `status_path`
- `total_scripts`
- `executed_scripts[]`
  - `requested`
  - `executed`
  - `env_overrides`
  - `use_fallbacks`
- `failed_count`
- `failures[]`
- `fallbacks_used[]`
- `run_us_in_daily`

### 5.2 provenance 최소 보장값
Stage1 실행 provenance는 최소 아래가 남아야 한다.
- `run_id`
- `profile`
- `scheduler_origin`
- `host`
- `python_bin`
- `repo_root`
- fallback 사용 여부

---

## 6) 게이트 계약

### 6.1 Checkpoint gate
- 스크립트: `invest/stages/stage1/scripts/stage01_checkpoint_gate.py`
- 출력: `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
- 목적: raw tree 최소 커버리지와 DART 연속성의 **빠른 fail-close 점검**

#### 6.1.1 checkpoint 최소 개수 기준
| check | glob | min_count |
| --- | --- | ---: |
| `kr_ohlcv` | `raw/signal/kr/ohlcv/*.csv` | 2800 |
| `kr_supply` | `raw/signal/kr/supply/*_supply.csv` | 2800 |
| `us_ohlcv` | `raw/signal/us/ohlcv/*.csv` | 500 |
| `market_macro` | `raw/signal/market/macro/*` | 5 |
| `kr_dart` | `raw/qualitative/kr/dart/dart_list_*.csv` | 100 |
| `market_rss` | `raw/qualitative/market/rss/*.json` | 1 |
| `market_news_url_index` | `raw/qualitative/market/news/url_index/*.jsonl` | 1 |
| `market_news_selected_articles` | `raw/qualitative/market/news/selected_articles/*.jsonl` | 1 |
| `text_blog` | `raw/qualitative/text/blog/**/*.md` | 1000 |
| `text_telegram` | `raw/qualitative/text/telegram/**/*.md` | 10 |
| `text_premium` | `raw/qualitative/text/premium/**/*.md` | 1 |

#### 6.1.2 checkpoint 추가 검사
- DART continuity
  - `rcept_dt` 기준 unique day 집합 생성
  - 인접 day gap 중 `> 14일`이면 실패
- raw tree coverage
  - leaf dir별 file_count / latest_age_h 스냅샷 생성

#### 6.1.3 checkpoint 출력 schema
- `timestamp`
- `grade` (`VALIDATED|DRAFT`)
- `ok`
- `failed_count`
- `failures[]`
- `details`
  - 각 source별 `pattern/count/latest_age_h/min_count`
  - `dart_continuity`
  - `raw_tree_coverage`

### 6.2 Post-collection validation gate
- 스크립트: `invest/stages/stage1/scripts/stage01_post_collection_validate.py`
- 출력: `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- 목적: freshness / zero-byte / runtime status / full coverage를 함께 보는 **운영 게이트**

#### 6.2.1 source별 기본 기준
| source | min_count | freshness max_age_sec |
| --- | ---: | ---: |
| `raw/signal/kr/ohlcv` | 2800 | 172800 |
| `raw/signal/kr/supply` | 2800 | 345600 |
| `raw/signal/us/ohlcv` | 500 | 129600 |
| `raw/signal/market/macro` | 5 | 259200 |
| `raw/qualitative/kr/dart` | 100 | 259200 |
| `raw/qualitative/market/rss` | 1 | 259200 |
| `raw/qualitative/market/news/url_index` | 1 | 259200 |
| `raw/qualitative/market/news/selected_articles` | 1 | 259200 |
| `raw/qualitative/text/telegram` | 1 | 604800 |
| `raw/qualitative/text/blog` | 1 | 604800 |
| `raw/qualitative/text/premium` | 1 | 604800 |

#### 6.2.2 post-collection 특례
- `selected_articles`
  - zero-byte 파일이 있어도 **non-zero 파일이 하나 이상 있으면 zero-byte 실패로 보지 않음**
- `kr_ohlcv`
  - freshness 실패 시 market-closed probe가 `waive_freshness=true`면 freshness 오류 면제
- `kr_supply`
  - runtime status에서 `external_blocked_login_required=true` and `source=krx_supply`면 freshness 오류 면제
- `us_ohlcv`
  - runtime status의 `stale_ticker_count_after != 0`이면 실패

#### 6.2.3 blog full coverage 검사
`runtime/blog_full_coverage` detail을 별도로 추가한다.
- 검증 포인트
  - `blog_last_run_status.json` 존재
  - `naver_buddies_full.json`에서 buddy 총수 확인
  - buddy별 파일 존재 여부
  - terminal blog 상태(`empty-posts`, `404`, `page1-links-0`)는 결측 면제 가능
  - `PublishedDate < 2016-01-01` 파일 수는 0이어야 함

#### 6.2.4 telegram full coverage 검사
`runtime/telegram_full_coverage` detail을 별도로 추가한다.
- 검증 포인트
  - allowlist 총수 존재
  - collector/run status 존재
  - allowlist channel과 raw markdown channel key 정합
  - terminal channel(`bot`, `contact`, `join-only`, `non-channel`)은 결측 면제 가능
  - attachment stats 및 attachment artifact contract 포함

#### 6.2.5 post-collection 출력 schema
- `timestamp`
- `ok`
- `message`
- `failed_count`
- `mode` = `stage1_raw_full_coverage`
- `failures[]`
- `details[]`
  - 각 source별
    - `source`, `script`, `ok`, `failed_count`, `count`, `min_count`, `zero_byte_count`, `freshness_applied`, `latest`, `latest_age_sec`, `max_age_sec`, `errors[]`
    - optional: `runtime_status`, `collector_used`, `ignored_zero_byte_files`, `freshness_probe`, `freshness_waived_reason`
  - blog coverage detail
  - telegram coverage detail
- `raw_tree_coverage`

---

## 7) raw artifact 계약
- Stage1 raw artifact의 **최소 파일 스키마**는 `stage01_data_collection.md`가 canonical appendix다.
- 재구현 시 Stage2가 읽는 최소 계약을 반드시 만족해야 한다.
- 핵심 원칙
  - OHLCV: `Date/Open/High/Low/Close/Volume`
  - supply: `Date/Inst/Corp/Indiv/Foreign/Total`
  - DART: `corp_code/corp_name/report_nm/rcept_no/rcept_dt` (+ 가능하면 `stock_code`)
  - RSS: item-level `title + datetime/published + url`
  - selected_articles: `url + title + published_date|published_at + body/summary`
  - telegram/blog/premium markdown는 metadata line + body 구조를 유지

---

## 8) 실행 커맨드
```bash
# Stage1 기본 수집
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile daily_full

# cadence 분리 profile
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile rss_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile telegram_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile blog_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile kr_ohlcv_intraday
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile kr_supply_intraday
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile us_ohlcv_daily
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile dart_fast
python3 invest/stages/stage1/scripts/stage01_daily_update.py --profile news_backfill

# Gate
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py

# 체인 실행(Stage1~4)
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

---

## 9) PASS / FAIL 기준
- `stage01_checkpoint_gate.py` 또는 `stage01_post_collection_validate.py` 둘 중 하나라도
  - exit code non-zero 이거나
  - output JSON의 `ok=false`
  이면 Stage1은 FAIL로 본다.
- `run_stage1234_chain.sh`는 위 두 gate를 Stage1 직후 순서대로 실행하며, 실패 시 즉시 fail-close 종료하고 Stage2~4를 실행하지 않는다.

---

## 10) 재현 구현 요약
Stage1을 문서만 보고 재현하려면 아래 4개를 동일하게 맞추면 된다.
1. `stage01_daily_update.py`의 **profile별 ordered scripts + fallback map**
2. raw/master/runtime 출력 경로
3. checkpoint/post-collection gate의 **min_count/freshness/full-coverage 규칙**
4. `daily_update_status.json`, `post_collection_validate.json`, `stage01_checkpoint_status.json`의 schema
