# stage01_data_collection

status: CANONICAL_RAW_APPENDIX  
updated_at: 2026-03-09 KST

## 문서 역할
- 이 문서는 Stage1 collector ↔ output path/source map과 **raw artifact 최소 스키마**를 고정한다.
- Stage1 orchestration/gate 계약은 `STAGE1_RULEBOOK_AND_REPRO.md`를 따른다.
- 운영 명령/launchd/환경변수는 `RUNBOOK.md`를 따른다.

---

## 1) 책임 분리
- Stage1: 수집 + raw/master/runtime 기록
- Stage2: 정제(clean)·격리(quarantine)·품질 리포트
- 따라서 이 문서의 스키마는 **Stage2가 읽을 수 있는 최소 raw contract** 관점으로 적는다.

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
- script: `stage01_collect_selected_news_articles.py`
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
  "source_domain": "optional"
}
```
- 구현 메모:
  - Stage2는 `url`, `title`, `published_date|published_at`, `summary/body`를 검증한다.
  - Stage3는 `title + summary + body`를 이어 붙여 본문으로 사용한다.

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

### 4.7 Telegram attachment artifact
- root: `outputs/raw/qualitative/attachments/telegram/<channel_slug>/msg_<message_id>/`
- 최소 파일:
  - `meta.json`
  - original attachment file
  - `extracted.txt`는 optional
- `meta.json` 최소 필드:
  - `channel_slug`
  - `message_id`
  - `kind`
  - `artifact_dir`
  - `meta_path`
  - `original_path`
  - `extraction_status`
  - `extract_path` (있을 때)

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
- `outputs/runtime/blog_last_run_status.json`
- `outputs/runtime/kr_supply_status.json`
- `outputs/runtime/us_ohlcv_status.json`

이 runtime 파일들은 Stage1 gate가 freshness waiver / collector selection / coverage 판단에 사용한다.

---

## 6) 재현 구현 요약
Stage1 raw를 재구현할 때 가장 중요한 것은 **Stage2가 기대하는 최소 형식**을 맞추는 것이다.
- CSV는 최소 컬럼명 유지
- JSON/JSONL은 필수 key 유지
- markdown는 metadata line + body 구조 유지
- Telegram PDF는 raw markdown marker와 attachment sidecar가 함께 존재해야 한다.
