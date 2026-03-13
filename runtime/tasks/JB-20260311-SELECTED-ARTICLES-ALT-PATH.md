# JB-20260311-SELECTED-ARTICLES-ALT-PATH

## scope
JB-20260311-OVERNIGHT-CLOSEOUT / Workstream B
- selected_articles live 경로가 실제로 Naver-only alternate path인지 검증
- DB 반영 여부와 consumer-facing summary/coverage artifact 정합성 검증
- stale summary artifact / consumer pointer가 남아 있으면 안전하게 fix-forward

## code path verification
### PASS — alternate path가 code에 적용되어 있음
1. `invest/stages/stage1/scripts/stage01_daily_update.py`
   - `selected_articles_naver_only` profile 존재
   - `daily_full`에도 `stage01_collect_selected_news_articles_naver.py`가 직접 연결됨
   - proof: line `85`, `92-93`
2. `invest/stages/stage1/scripts/stage01_collect_selected_news_articles_naver.py`
   - `stage01_fetch_naver_finance_news_index.py` 결과만 사용
   - `NEWS_SELECTED_MERGE_ALL_INDEXES=0` 강제
   - collector 호출도 `--input-index <naver_index>` 단일 전달
   - proof: line `16`, `21`, `121`, `144`
3. runtime status
   - `invest/stages/stage1/outputs/runtime/news_selected_articles_naver_status.json`
   - `input_index_path=.../url_index_naver_finance_20260311-103715.jsonl`
   - collector `output_file=.../selected_articles_20260311-103721.jsonl`
   - `status=PASS`

## live artifact verification
### PASS — 현재 live selected_articles는 Naver-only
live dir:
- `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/`

live files:
- `selected_articles_20260311-010827.jsonl` rows=`21`
- `selected_articles_20260311-013501.jsonl` rows=`22`
- `selected_articles_20260311-072254.jsonl` rows=`21`
- `selected_articles_20260311-103721.jsonl` rows=`14`

aggregates:
- live file_count=`4`
- total_rows=`78`
- `source_domain={'n.news.naver.com': 78}`
- `source_kind={'naver_finance_list': 78}`
- old mixed `selected_articles_merged.jsonl`는 live dir에 없고 DB에서도 inactive로만 남아 있음

## DB reflection verification
### PASS — DB는 현재 live selected_articles/summary 상태를 이미 반영함
DB:
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`

evidence (`raw_artifacts`):
- active live files 4개
  - `qualitative/market/news/selected_articles/selected_articles_20260311-010827.jsonl`
  - `qualitative/market/news/selected_articles/selected_articles_20260311-013501.jsonl`
  - `qualitative/market/news/selected_articles/selected_articles_20260311-072254.jsonl`
  - `qualitative/market/news/selected_articles/selected_articles_20260311-103721.jsonl`
- active derived summary 1개
  - `qualitative/market/news/selected_articles/selected_articles_merged_summary.json`
- 위 active rows 공통:
  - `last_seen_sync_id=20260311T135155Z`
  - `stage1_run_id=20260311T133937Z`
  - `stage1_profile=news_backfill`
  - `synced_at=2026-03-11T13:51:55.720833+00:00`
- old `qualitative/market/news/selected_articles/selected_articles_merged.jsonl`는 `is_active=0`

## consumer-facing artifact verification
### PASS — stale summary/pointer는 현재 기준 해소됨
1. live summary
   - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_merged_summary.json`
   - `generated_at_utc=2026-03-11T13:52:02.784268+00:00`
   - `source_files=4`
   - `merged_count=78`
   - `output_file=""`
   - `latest_file=.../selected_articles_20260311-103721.jsonl`
   - `source_domains={"n.news.naver.com": 78}`
   - `source_kinds={"naver_finance_list": 78}`
   - `contract_note="Canonical selected_articles corpus is the live selected_articles_*.jsonl set in this directory. This file is a directory summary only."`
2. coverage / consumer pointer
   - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
   - `sources.news_selected_articles.rows_seen=78`
   - `sources.news_selected_articles.files_scanned=4`
   - `sources.news_selected_articles.scope.latest_selected_articles_file=.../selected_articles_20260311-103721.jsonl`
   - `sources.news_selected_articles.scope.selected_articles_summary_file=.../selected_articles_merged_summary.json`
   - `sources.news_selected_articles.scope.selected_articles_summary_status=validated_live_directory_summary`
   - `sources.news_selected_articles.scope.selected_articles_contract=selected_articles_*.jsonl files are canonical; selected_articles_merged_summary.json is a derived directory summary.`
3. code-level consumer contract
   - `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
   - live file selection은 `selected_articles_*.jsonl`에서 `selected_articles_merged.jsonl`를 제외
   - summary는 live dir 기반으로 재계산 후 validation 통과 시만 pointer에 노출
   - proof: line `310-318`, `321-395`, `746-765`, `878-883`

## fix-forward result
- 이번 확인 시점에는 stale summary artifact / stale consumer pointer를 추가로 고칠 필요가 없었음.
- 현재 live summary와 coverage pointer는 모두 Naver-only live set 기준으로 일치함.
- destructive deletion 없음.

## writer lock note
### NOTE — live writer lock remains, but this verification 자체의 blocker는 아님
- active lock:
  - `invest/stages/stage1/outputs/runtime/raw_db_sync.lock`
  - `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- observed:
  - `status=RUNNING`
  - `stage1_profile=news_backfill`
  - `pid=97161`
  - `acquired_at=2026-03-11T22:51:55.703601`
  - `ps`: elapsed about `09:33`, state `U`
  - process holds `stage1_raw_archive.sqlite3`, `-wal`, `-shm`, and `raw_db_sync.lock`
- handling:
  - writer를 건드리지 않았고, 추가 sync/regen 강행도 하지 않았음.
  - 다만 selected_articles 관련 DB 반영 증거는 이미 직전 completed sync(`last_seen_sync_id=20260311T135155Z`)에서 확보되어 있음.

## decision
### recommended status: DONE
근거:
1. live selected_articles path는 실제로 Naver finance index 단일 경로만 사용함
2. live corpus 4개 jsonl 전부 Naver-only임
3. DB가 live corpus + derived summary를 active 상태로 이미 반영함
4. consumer-facing summary/coverage artifact가 현재 live corpus와 수치/계약 모두 일치함
5. stale mixed `selected_articles_merged.jsonl`는 live canon이 아니며 DB에서도 inactive 처리됨

단, 운영 메모:
- 현재 `stage01_sync_raw_to_db.py` writer lock은 살아 있으므로, 별도 write 작업이나 추가 full sync 재검증은 lock 해제 후 처리하는 편이 안전함.
- 그러나 본 Workstream B의 close 판단에는 필요한 read-side 증거가 충족됨.

## proof paths
- code
  - `invest/stages/stage1/scripts/stage01_daily_update.py`
  - `invest/stages/stage1/scripts/stage01_collect_selected_news_articles_naver.py`
  - `invest/stages/stage1/scripts/stage01_fetch_naver_finance_news_index.py`
  - `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
  - `invest/stages/stage1/scripts/selected_articles_live_summary.py`
- runtime
  - `invest/stages/stage1/outputs/runtime/news_selected_articles_naver_status.json`
  - `invest/stages/stage1/outputs/runtime/news_selected_articles_status.json`
  - `invest/stages/stage1/outputs/runtime/daily_update_selected_articles_naver_only_status.json`
  - `invest/stages/stage1/outputs/runtime/raw_db_sync.lock`
  - `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- live raw
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/url_index/url_index_naver_finance_20260311-103715.jsonl`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_20260311-010827.jsonl`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_20260311-013501.jsonl`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_20260311-072254.jsonl`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_20260311-103721.jsonl`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_merged_summary.json`
  - `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- archive/db
  - `invest/stages/stage1/outputs/archive/news/selected_articles_disabled/20260311-010819/`
  - `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
