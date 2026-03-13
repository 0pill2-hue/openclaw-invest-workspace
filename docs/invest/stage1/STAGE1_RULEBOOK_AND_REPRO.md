# Stage1 Rulebook & Repro

status: CANONICAL (stage contract / reproducible spec)
updated_at: 2026-03-13 KST
ops companion: `docs/invest/stage1/RUNBOOK.md`

## 문서 역할
- 이 문서는 Stage1의 **계약(범위/입출력/게이트/판정)**만 정의한다.
- 실행 절차/운영 커맨드/스케줄/장애 대응은 `RUNBOOK.md`에서만 관리한다.

## 1) 범위
- 역할: 외부 원천 수집(raw 적재), runtime 상태 기록, Stage1 게이트 수행
- 비범위:
  - clean/quarantine 생성
  - 정성 점수화/투자판단

## 2) 입력 계약
### 설정 파일
- `invest/stages/stage1/inputs/config/news_sources.json`
- `invest/stages/stage1/inputs/config/dart_api_key.txt`
- `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
- `invest/stages/stage1/inputs/config/telegram_terminal_status.json`
- `invest/stages/stage1/inputs/config/blog_terminal_status.json`

### 외부 입력
- FDR / pykrx / yfinance / FRED / RSS / DART / Telethon
- Telegram 인증 수집은 `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` 필요

## 3) orchestration/profile 계약
### canonical orchestrator
- `invest/stages/stage1/scripts/stage01_daily_update.py --profile <profile>`

### 지원 profile
- `daily_full`
- `selected_articles_naver_only`
- `rss_fast`
- `telegram_fast`
- `blog_fast`
- `kr_ohlcv_intraday`
- `kr_supply_intraday`
- `us_ohlcv_daily`
- `dart_fast`
- `news_backfill`

### fallback 계약
| primary | fallback |
| --- | --- |
| `stage01_fetch_ohlcv.py` | `stage01_full_fetch_ohlcv.py` |
| `stage01_fetch_supply.py` | `stage01_full_fetch_supply.py` |
| `stage01_fetch_us_ohlcv.py` | `stage01_full_fetch_us_ohlcv.py` |
| `stage01_fetch_dart_disclosures.py` | `stage01_full_fetch_dart_disclosures.py` |

## 4) 출력 경로 계약
### master
- `invest/stages/stage1/outputs/master/kr_stock_list.csv`

### raw
- `invest/stages/stage1/outputs/raw/signal/{kr,us,market}/...`
- `invest/stages/stage1/outputs/raw/qualitative/...`
- Telegram attachment artifact canonical
  - `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/<channel_slug>/bucket_<nn>/msg_<id>__{meta,original,extracted,pdf_manifest,page_XXX,bundle}.<ext>`

### runtime / reports
- runtime
  - `invest/stages/stage1/outputs/runtime/daily_update_status.json`
  - `invest/stages/stage1/outputs/runtime/daily_update_<profile>_status.json`
  - `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
  - `invest/stages/stage1/outputs/runtime/pipeline_events.jsonl`
- reports
  - `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`

## 5) status/provenance 최소 schema
### daily_update status
필수 필드:
- `run_id`, `profile`, `scheduler_origin`, `host`, `python_bin`, `repo_root`
- `started_at`, `finished_at`, `duration_sec`
- `executed_scripts[]`, `failed_count`, `failures[]`, `fallbacks_used[]`

## 6) 게이트 계약
### checkpoint gate
- script: `stage01_checkpoint_gate.py`
- output: `stage01_checkpoint_status.json`
- 최소 기준: raw tree source별 min_count + DART continuity + raw_tree_coverage

### post-collection gate
- script: `stage01_post_collection_validate.py`
- output: `post_collection_validate.json`
- 기준: source별 min_count/freshness/zero-byte/runtime status/full coverage

## 7) PASS / FAIL
- 아래 중 하나면 Stage1 FAIL
  - `stage01_checkpoint_gate.py` non-zero 또는 `ok=false`
  - `stage01_post_collection_validate.py` non-zero 또는 `ok=false`
- 체인(`run_stage1234_chain.sh`)은 Stage1 FAIL 시 Stage2~4를 실행하지 않는다.

## 8) raw artifact 최소 스키마 appendix
- collector별 최소 artifact 스키마는 `stage01_data_collection.md`가 canonical appendix다.
