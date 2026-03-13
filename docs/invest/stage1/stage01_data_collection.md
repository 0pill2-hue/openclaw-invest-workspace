# stage01_data_collection

status: CANONICAL_COLLECTION_APPENDIX  
updated_at: 2026-03-12 KST

## 문서 역할
- 이 문서는 Stage1 collector ↔ output path/source map과 **DB archive 기준 최소 artifact 스키마**를 고정한다.
- Stage1 orchestration/gate 계약은 `STAGE1_RULEBOOK_AND_REPRO.md`를 따른다.
- 운영 명령/launchd/환경변수는 `RUNBOOK.md`를 따른다.

---

## 1) 책임 분리
- Stage1: 수집 + DB archive/master/runtime 기록
- Stage2: 정제(clean)·격리(quarantine)·품질 리포트
- Stage1은 `outputs/db/stage1_raw_archive.sqlite3`를 Stage2 입력 SSOT로 만든다.
- `outputs/raw/**`는 collector 호환성과 coverage 점검을 위한 파일 미러이며, 아래 경로 표기는 **DB `rel_path`와 동일한 논리 경로**로 해석한다.
- 따라서 이 문서의 스키마는 **Stage2가 읽을 수 있는 최소 DB artifact contract** 관점으로 적는다.

---

## 1.1) Stage1 raw DB archive contract
- archive path: `outputs/db/stage1_raw_archive.sqlite3`
- sync script: `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- authoritative row unit: `raw_artifacts.rel_path`
  - 예: `signal/kr/ohlcv/005930.csv`
  - 예: `qualitative/text/telegram/channel_a/msg_123.md`
- Stage2는 DB snapshot을 stage-local runtime mirror로 materialize한 뒤 기존 정제 로직을 수행한다.
- row-level 최소 메타:
  - `rel_path`
  - `content`
  - `size_bytes`
  - `mtime_ns`
  - `sha1`
  - `is_active`
  - `last_seen_sync_id`
- PDF structured index(운영 표준):
  - `pdf_documents` (`doc_key`, `channel_slug`, `message_id`, `message_date`, `meta_rel_path`, `original_rel_path`, `extract_rel_path`, `manifest_rel_path`, `bundle_rel_path`, `page_count`, `text_pages`, `rendered_pages`, `quality_grade`, `page_marked`, `page_marker_count`, `page_mapping_status`, `extract_format`)
  - `pdf_pages` (`doc_key`, `page_no`, `text_rel_path`, `render_rel_path`, `text_chars`, `width`, `height`)
- collector가 파일을 재기록하면 동일 `rel_path` row가 upsert되고, 사라진 파일은 `is_active=0`으로 비활성화된다. PDF structured index는 sync 시점 raw artifact를 다시 읽어 재구성한다.

---

## 2) Master artifact

### `outputs/master/kr_stock_list.csv`
최소 컬럼 계약:
- `Code` (6자리 종목코드, zero-pad 허용)
- `Name` (종목명)
- 아래 둘 중 하나는 있어야 함
  - `Market`
  - `MarketId`

Stage2 QC는 `Code`를 필수로 사용하고,
KR universe 필터는 `Market` 또는 `MarketId`로 수행한다.

---

## 3) Signal raw contracts

### 3.1 KR OHLCV
- script: `stage01_fetch_ohlcv.py`
- output: `outputs/raw/signal/kr/ohlcv/<CODE>.csv`
- 최소 컬럼:
  - `Date`
  - `Open`
  - `High`
  - `Low`
  - `Close`
  - `Volume`
- 구현 메모:
  - `Date`는 parse 가능한 날짜여야 한다.
  - `Volume >= 10` 미만은 Stage2 QC에서 invalid 가능.
  - duplicate `Date`는 Stage2 QC에서 quarantine 대상.

### 3.2 KR Supply
- script: `stage01_fetch_supply.py`
- output: `outputs/raw/signal/kr/supply/<CODE>_supply.csv`
- 최소 컬럼/순서:
  - `Date`
  - `Inst`
  - `Corp`
  - `Indiv`
  - `Foreign`
  - `Total`
- 구현 메모:
  - Stage2는 앞 6개 컬럼만 읽어 이 이름으로 재매핑한다.

### 3.3 US OHLCV
- script: `stage01_fetch_us_ohlcv.py`
- output: `outputs/raw/signal/us/ohlcv/<TICKER>.csv`
- 최소 컬럼:
  - `Date`, `Open`, `High`, `Low`, `Close`, `Volume`

### 3.4 Market macro
- scripts:
  - `stage01_fetch_macro_fred.py`
  - `stage01_fetch_global_macro.py`
- output:
  - `outputs/raw/signal/market/macro/*.csv`
  - `outputs/raw/signal/market/macro/macro_summary.json`
- `macro_summary.json` 최소 계약:
```json
{
  "latest": {
    "SPY": {"date": "YYYY-MM-DD", "change_1d": 0.0},
    "QQQ": {"date": "YYYY-MM-DD", "change_1d": 0.0}
  }
}
```
- Stage3는 `latest[*].date`, `latest[*].change_1d`를 사용한다.

---

## 4) Qualitative raw contracts

### 4.1 DART
- script: `stage01_fetch_dart_disclosures.py`
- output: `outputs/raw/qualitative/kr/dart/dart_list_*.csv`
- 최소 컬럼:
  - `corp_code`
  - `corp_name`
  - `report_nm`
  - `rcept_no`
  - `rcept_dt`
- 권장 추가 컬럼:
  - `stock_code`
- 구현 메모:
  - `rcept_dt`는 `YYYYMMDD` 파싱 가능해야 한다.
  - `rcept_no`는 문서 식별자다.

### 4.2 RSS
- script: `stage01_fetch_news_rss.py`
- output: `outputs/raw/qualitative/market/rss/*.json`
- 최소 JSON shape:
```json
{
  "feed_name": [
    {
      "title": "...",
      "summary": "...",
      "url": "https://...",
      "published": "ISO-8601 or parseable datetime",
      "published_date": "YYYY-MM-DD"
    }
  ]
}
```
- 구현 메모:
  - Stage2 validation의 최소 계약은 item-level `title + datetime/published + url`
  - Stage3 builder는 `title`, `summary`, `published`, `published_date`를 우선 사용한다.

### 4.3 News URL index
- script: `stage01_build_news_url_index.py`
- output: `outputs/raw/qualitative/market/news/url_index/*.jsonl`
- 최소 row contract:
  - `url`
  - `title` (권장)
  - `published_date` 또는 `published_at` (권장)
  - `source_domain` (권장)
- 구현 메모:
  - Stage2 canonical qualitative corpus 입력은 아님
  - Stage1 selected_articles 생성 보조 인덱스다

### 4.4 Selected articles
- canonical live writer: `stage01_collect_selected_news_articles_naver.py`
- helper collector: `stage01_collect_selected_news_articles.py` (`--input-index` 명시가 필요한 manual/debug helper; direct live write canonical 아님)
- output: `outputs/raw/qualitative/market/news/selected_articles/*.jsonl`
- 최소 row contract:
```json
{
  "url": "https://...",
  "title": "...",
  "published_date": "YYYY-MM-DD",
  "published_at": "optional ISO datetime",
  "summary": "optional",
  "body": "optional but one of summary/body should carry usable text",
  "source_domain": "optional",
  "source_kind": "optional but recommended for verified lanes"
}
```
- 구현 메모:
  - Stage2는 `url`, `title`, `published_date|published_at`, `summary/body`를 검증한다.
  - Stage3는 `title + summary + body`를 이어 붙여 본문으로 사용한다.
  - canonical corpus는 항상 `selected_articles_*.jsonl` live 파일셋이다.
  - `selected_articles_merged_summary.json`은 파생 directory summary이며, live 파일셋과 불일치하면 stale/invalid로 간주하고 소비자는 fail-close(요약 비신뢰)해야 한다.
  - `daily_full`과 `selected_articles_naver_only`는 `stage01_collect_selected_news_articles_naver.py`를 통해 live `selected_articles/`를 갱신한다. 이 wrapper는 검증된 Naver finance index를 먼저 만들고 generic collector를 explicit `--input-index`로 호출한다.
  - `news_backfill` / `stage01_backfill_10y.py`는 live `selected_articles/` writer가 아니다. 역할은 RSS 및 URL index coverage/backfill 쪽으로 제한한다.
  - 검증 가능한 selected_articles 갱신은 별도 verifiable lane에서만 수행해야 하며, 현재 documented canonical lane은 Naver-only다.
  - 따라서 현재 live corpus에서 `source_domain=n.news.naver.com`, `source_kind=naver_finance_list`가 아닌 값이 관찰되면 contamination 또는 새 lane 미문서화 상태로 본다.

### 4.5 Blog markdown
- script: `stage01_scrape_all_posts_v2.py`
- output: `outputs/raw/qualitative/text/blog/**/*.md`
- 최소 markdown metadata contract:
```text
# <title>
Date: <parseable date>
Source: https://...

<body>
```
- 허용 meta key:
  - `Date` 또는 `PublishedDate`
  - `Source`
- 구현 메모:
  - Stage2는 metadata line을 읽고 body에서 UI/boilerplate 라인을 제거한다.

### 4.6 Telegram markdown
- script: `stage01_scrape_telegram_launchd.py`
- output: `outputs/raw/qualitative/text/telegram/*.md`
- 최소 contract는 아래 둘 중 하나를 만족해야 한다.

#### A. message-style block
```text
---
Date: <parseable date>
Source: https://...
PostID: <id>

<body>
```

#### B. highspeed full-log style
```text
# Telegram Log: <channel>
Date: <parseable date>
MessageID: <id>
Source: https://...

<body>
```

- PDF / attachment marker 지원 필드
  - `[ATTACH_KIND] pdf|image|...`
  - `[ATTACH_ARTIFACT_DIR] ...`
  - `[ATTACH_ORIGINAL_PATH] ...`
  - `[ATTACH_META_PATH] ...`
  - `[ATTACH_TEXT_PATH] ...`
  - `[ATTACH_TEXT] ... [/ATTACH_TEXT]`
  - `[ATTACH_TEXT_STATUS] ...`
- 구현 메모:
  - Stage2는 `ATTACH_KIND=pdf`와 attachment sidecar를 조인해 clean telegram 본문에 inline 승격한다.

### 4.6.1 Link enrichment sidecar (Stage1-owned)
- script: `stage01_collect_link_sidecars.py`
- output: `outputs/raw/qualitative/link_enrichment/text/{blog,telegram,premium/startale}/**/*.json`
- source mapping:
  - source: `outputs/raw/qualitative/text/<folder>/<file>`
  - sidecar: `outputs/raw/qualitative/link_enrichment/<folder>/<file>.json`
- 최소 JSON 필드:
  - `generated_at`
  - `rule_version`
  - `source_rel_path`
  - `source_sha1`
  - `canonical_urls[]`
  - `body_validation_ok`
  - `body_validation_reason`
  - `body_enrichment_needed`
  - `blocks[]` (`canonical_url`, `text`)
  - `fetch_meta`
- 구현 메모:
  - 외부 링크 fetch ownership은 Stage1 sidecar 단계가 가진다.
  - Stage2는 sidecar canonical URL/blocks를 우선 소비하고, 필요 시에만 opt-in live fetch fallback을 쓴다.

### 4.7 Telegram attachment artifact
- root: `outputs/raw/qualitative/attachments/telegram/<channel_slug>/bucket_<nn>/`
- 저장 원칙: **message별 하위 폴더를 만들지 않고 bucket 안에 flat file로 적재**한다.
- canonical count/index 단위는 bucketed meta(`bucket_<nn>/msg_<id>__meta.json`) 1건이며, 레거시 `msg_<id>/meta.json`은 migration/shadow 용도만 가진다.
- PDF 예시 파일:
  - `msg_<id>__meta.json`
  - `msg_<id>__original__<safe_name>.pdf`
  - `msg_<id>__extracted.txt` (preferred durable form; PDF는 가능하면 `[PAGE 001]`, `[PAGE 002]` 같은 explicit marker를 포함)
  - `msg_<id>__pdf_manifest.json`
  - `msg_<id>__page_<NNN>.txt`
  - `msg_<id>__page_<NNN>.png`
  - `msg_<id>__bundle.zip`
- `meta.json` 최소 필드:
  - `channel_slug`
  - `message_id`
  - `kind`
  - `artifact_dir`
  - `meta_path`
  - `original_path`
  - `extraction_status`
  - `extract_path` (있을 때)
- PDF 추가 필드(권장/운영 표준):
  - `pdf_manifest_path`
  - `pdf_page_count`
  - `pdf_text_pages`
  - `pdf_render_pages`
  - `pdf_quality_grade`
  - `compressed_bundle_path`
  - `human_review_window_active`
  - `pdf_page_marked` (durable extracted text가 explicit page marker를 포함하는지)
  - `pdf_page_marker_format` (`[PAGE NNN]`)
  - `pdf_page_marker_count`
  - `pdf_page_mapping_status` (`available_from_original|available_from_manifest_pages|available_from_extract_text|missing_*`)
  - `extract_format` (`pdf_page_marked_text_v1|plain_text_legacy|''`)
- `msg_<id>__pdf_manifest.json` 최소 필드:
  - `source_original_rel_path`
  - `page_count`
  - `max_pages_applied`
  - `text_pages_written`
  - `rendered_pages_written`
  - `quality_grade`
  - `pages[]` (`page_no`, `text_rel_path`, `render_rel_path`, `text_chars`, `width`, `height`)
- 페이지 수 의미 계약:
  - `pdf_documents.page_count` / manifest `page_count` = **원본 PDF 전체 페이지 수**
  - `pdf_pages` row count / manifest `pages[]` 길이 = **실제로 추출·저장한 indexed page 수**
  - `max_pages_applied` cap이 걸린 문서는 두 값이 같지 않을 수 있으며, 이 경우만으로 손상으로 판단하지 않는다.
- page-marked extracted text / bounded backfill 계약:
  - 새 PDF 또는 rerun 시 원본 bytes가 있으면 `msg_<id>__extracted.txt`를 page-marked single text(`pdf_page_marked=true`, `extract_format=pdf_page_marked_text_v1`)로 저장한다.
  - original PDF를 영구 보관할 필요는 없다. 이미 `pdf_manifest/pages[]`가 있으면 original이 삭제된 뒤에도 manifest page text로 aggregate extracted text를 재구성할 수 있다.
  - original도 manifest page text도 없으면 기존 plain text를 유지하되 `pdf_page_marked=false`, `pdf_page_mapping_status=missing_*`로 명시한다. 이 경우 backfill scope는 여기서 종료되며 corpus를 삭제/실패 처리하지 않는다.

### 4.8 Premium markdown
- script: `stage01_collect_premium_startale_channel_auth.py`
- output: `outputs/raw/qualitative/text/premium/startale/*.md`
- 최소 markdown contract:
```text
# <title>
- URL: https://...
- PublishedAt: <parseable datetime>
- Status: SUCCESS
- Reason: optional

## 본문
<body>
```
- 구현 메모:
  - `Status`는 `SUCCESS|OK`만 Stage2 통과 가능
  - `Reason`에 paywall/session/blocked가 들어가면 Stage2에서 quarantine

---

## 5) Runtime / status artifacts
- `outputs/runtime/daily_update(_<profile>)_status.json`
- `outputs/runtime/telegram_collector_status.json`
- `outputs/runtime/telegram_last_run_status.json`
- `outputs/runtime/telegram_public_fallback_status.json`
- `outputs/runtime/telegram_attachment_extract_stats_latest.json`
- `outputs/runtime/link_enrich_sidecar_status.json`
- `outputs/runtime/blog_last_run_status.json`
- `outputs/runtime/kr_supply_status.json`
- `outputs/runtime/us_ohlcv_status.json`
- `outputs/runtime/raw_db_sync_status.json`

이 runtime 파일들은 Stage1 gate가 freshness waiver / collector selection / coverage 판단에 사용한다.
`raw_db_sync_status.json`은 Stage2 DB mirror의 최신 sync provenance를 제공하며, status contract는 `RUNNING|FAIL|PASS` + `status_mode` + `lock` lifecycle 메타를 포함한다.
락 없이 RUNNING 잔재가 남은 경우에는 stale cleanup 후 `status_only_from_sync_meta_after_stale_cleanup` 또는 `stale_lock_cleanup_no_sync_meta`로 정리한다.

---

## 6) 재현 구현 요약
Stage1 수집 계층을 재구현할 때 가장 중요한 것은 **Stage2가 기대하는 최소 형식과 DB `rel_path` 계약**을 맞추는 것이다.
- CSV는 최소 컬럼명 유지
- JSON/JSONL은 필수 key 유지
- markdown는 metadata line + body 구조 유지
- DB archive의 `rel_path`는 문서에 적힌 `outputs/raw/**` 논리 경로와 일치해야 한다.
- Telegram PDF는 markdown marker와 attachment sidecar가 함께 존재해야 한다.
