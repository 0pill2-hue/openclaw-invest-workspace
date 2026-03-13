# Stage2 Rulebook & Repro

status: CANONICAL (reproducible refine/QC contract)  
updated_at: 2026-03-11 KST

## 문서 역할
- 이 문서는 **문서만 보고 현재 Stage2를 재구현할 수 있도록** input/output, rule, threshold, dedup, incremental, report schema를 고정한다.
- Telegram PDF 승격은 `STAGE2_PDF_REFINEMENT_DESIGN.md`의 세부 설계를 따른다.

---

## 1) 범위 / 책임 경계
- 역할: Stage1 DB archive/master를 Stage2 `clean/quarantine`으로 정제
- 원칙:
  - 입력은 **오직** `invest/stages/stage2/inputs/upstream_stage1/**` + `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
  - raw 파일 트리는 canonical 입력이 아니라 Stage2 runtime mirror의 논리 경로다
  - Stage2는 정제/정규화/격리/중복 제거를 담당하고, qualitative clean 산출물에 대해 **deterministic semantic tagging**(`target_levels/macro_tags/industry_tags/stock_tags/event_tags/impact_direction/horizon/region_tags`)을 추가할 수 있다.
  - 정성 점수화/해석/투자판단은 하지 않음
- writer ownership:
  - `stage02_qc_cleaning_full.py`
    - 소유 출력: `signal/{kr/ohlcv,kr/supply,us/ohlcv}`
  - `stage02_onepass_refine_full.py`
    - 소유 출력: `signal/market/*` + `qualitative/**`

---

## 2) 입력 (Inputs)
- config
  - `invest/stages/stage2/inputs/config/stage2_runtime_config.json`
  - `invest/stages/stage2/inputs/config/stage2_reason_config.json`
- master
  - `invest/stages/stage2/inputs/upstream_stage1/master/kr_stock_list.csv`
- Stage1 raw DB archive (authoritative)
  - `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
  - `raw_artifacts.rel_path` 기준으로 Stage2 runtime mirror를 구성
  - 기본 mirror root: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/current/raw`
- raw signal (DB mirror logical path)
  - `raw/signal/kr/ohlcv/*.csv`
  - `raw/signal/kr/supply/*_supply.csv`
  - `raw/signal/us/ohlcv/*.csv`
  - `raw/signal/market/macro/*`
- raw qualitative (DB mirror logical path)
  - `raw/qualitative/kr/dart/*.csv`
  - `raw/qualitative/market/rss/*.json`
  - `raw/qualitative/market/news/selected_articles/*.jsonl`
  - `raw/qualitative/text/{blog,telegram,premium/startale}/**/*`
  - `raw/qualitative/link_enrichment/text/{blog,telegram,premium/startale}/**/*.json`
  - Telegram attachment artifact canonical path: `raw/qualitative/attachments/telegram/<channel_slug>/bucket_<nn>/msg_<id>__{meta,original,extracted,pdf_manifest,page_XXX,bundle}.<ext>`
  - legacy compatibility shadow: `raw/qualitative/attachments/telegram/<channel_slug>/msg_<id>/meta.json` (fallback only, non-canonical)
- 제외 입력
  - `raw/qualitative/market/news/url_index/*`
  - image 계열 (`image_map`, `images_ocr`)
- input materialization 정책
  - DB sync id 단위 snapshot 디렉터리를 만들고 `current` symlink 경로를 고정한다.
  - Stage2 incremental signature는 stable mirror path + 원본 `mtime` 기준을 유지한다.
  - DB archive가 없으면 기존 `inputs/upstream_stage1/raw` 파일 트리로 fallback 한다.
- PDF page-count handoff 계약
  - `pdf_documents.page_count` 및 PDF manifest `page_count`는 **원본 전체 페이지 수**다.
  - `pdf_pages` row count 및 manifest `pages[]` 길이는 **cap 적용 후 실제 indexed/stored page 수**다.
  - `max_pages_applied`가 설정된 문서는 두 값이 달라도 정상일 수 있으므로, Stage2는 이를 손상/누락으로 단정하지 않는다.

---

## 3) 현재 구현 값(Current exact thresholds)
아래 값은 현재 구현 기준이며, 문서만 보고 재현할 때도 동일 값으로 본다.

### 3.1 refine text validation thresholds
| key | value |
| --- | ---: |
| `blog_min_effective_len` | 80 |
| `telegram_min_effective_len` | 60 |
| `premium_min_effective_len` | 100 |
| `selected_articles_min_text_len` | 80 |
| `short_meaningful_min_len` | 45 |
| `dedup.min_fingerprint_text_len` | 80 |

### 3.2 refine target folders
- corpus dedup target folders
  - `market/news/selected_articles`
  - `text/blog`
  - `text/telegram`
  - `text/premium/startale`
- link enrichment target folders
  - `text/blog`
  - `text/telegram`
  - `text/premium/startale`

### 3.3 link enrichment runtime values
| key | value |
| --- | ---: |
| `allow_all_domains_default` | `true` |
| `fetch_timeout_sec` | 6 |
| `fetch_max_retries` | 3 |
| `fetch_backoff_base_sec` | 0.7 |
| `fetch_max_bytes` | 350000 |
| `fetch_max_text_chars` | 3000 |
| `max_urls_per_file` | 12 |
| `max_total_chars` | 4000 |
| `min_effective_add` | 50 |

### 3.4 QC thresholds
| key | value |
| --- | ---: |
| included KR markets | `KOSPI`, `KOSDAQ`, `KOSDAQ GLOBAL` |
| included MarketId | `STK`, `KSQ` |
| `min_valid_volume` | 10 |
| `max_daily_ret_abs` | 0.35 |

---

## 4) 입력 파일 최소 계약

### 4.1 signal
- KR/US OHLCV CSV
  - `Date, Open, High, Low, Close, Volume`
- KR supply CSV
  - 첫 6개 컬럼이 `Date, Inst, Corp, Indiv, Foreign, Total`로 해석 가능해야 함
- market macro
  - 파일 존재 자체가 Stage2 계약
  - Stage2는 market macro를 canonical signal로 복사/정제하고 Stage3는 `macro_summary.json`을 소비

### 4.2 qualitative
- DART CSV
  - `corp_code, corp_name, report_nm, rcept_no, rcept_dt` 필수
- RSS JSON
  - flatten 결과에서 최소 한 entry 이상이 `title + datetime/published + url`를 가져야 함
- selected_articles JSONL row
  - object row
  - `url + title + published_date|published_at + summary/body 유효 텍스트`
- blog markdown
  - `Date|PublishedDate` + `Source`
- telegram markdown
  - `Date` + (`Source`+`Post*` 또는 `# Telegram Log`+`MessageID`)
- premium markdown
  - `- URL`, `- PublishedAt`, `- Status` 필수
  - `Status=SUCCESS|OK`만 통과 가능

---

## 5) canonical 출력 경로

### 5.1 clean
- `invest/stages/stage2/outputs/clean/production/signal/{kr,us,market}/...`
- `invest/stages/stage2/outputs/clean/production/qualitative/...`

### 5.2 quarantine
- `invest/stages/stage2/outputs/quarantine/production/signal/{kr,us,market}/...`
- `invest/stages/stage2/outputs/quarantine/production/qualitative/...`

### 5.2-b classification sidecar
- text/blog, text/telegram, text/premium/startale clean 파일은 같은 경로에 `*.classification.json` sidecar를 둔다.
- selected_articles clean JSONL row는 `stage2_classification` 필드를 포함하고, 파일 단위 `*.classification.json` summary를 함께 둔다.
- incremental skip은 qualitative clean 산출물에 필요한 classification sidecar/row payload가 이미 존재할 때만 허용된다. sidecar가 비어 있거나 빠졌으면 raw signature가 같아도 다시 물질화한다.
- selected_articles는 body가 충분히 있으면 title+body를 우선 분류 입력으로 사용하고, summary는 body가 짧을 때만 보조 입력으로 사용한다. (요약 snippet 오염으로 인한 오탐 축소 목적)
- classification은 deterministic 규칙 기반이며, Stage1 raw/page split을 바꾸지 않는다.
- classification payload는 기존 `primary_* / mentioned_*` 필드를 유지하면서 아래 semantic contract를 추가한다.
  - `semantic_version`
  - `target_levels`
  - `macro_tags`
  - `industry_tags`
  - `stock_tags`
  - `event_tags`
  - `impact_direction`
  - `horizon`
  - `region_tags`

### 5.3 canonical alias policy
- raw/input alias: `market/news/rss`
- canonical internal/output alias: `market/rss`

### 5.4 output file behavior
- signal clean: same basename CSV
- signal quarantine: same basename CSV + row-level `reason`
- text clean: cleaned markdown/text 그대로 저장
- text quarantine: markdown-like payload with header fields
  - `reason`
  - `folder`
  - `source_file`
  - `sanitized_at`
  - `stage2_rule_version`
  - optional extra meta
  - `meta_lines`
  - `preview`
- selected_articles clean/quarantine: JSONL row 단위 분리
- JSON clean: validated canonical JSON 저장

---

## 6) refine exact behavior

### 6.1 text/blog validation
필수 metadata:
- `Date` 또는 `PublishedDate`
- `Source: https://...`

정제 규칙:
- heading / metadata line / `---` 제거
- blog UI marker 제거
- URL 제거 후 effective text 계산
- effective 길이 `< 80` 이고 meaningful short text가 아니면 quarantine

### 6.2 text/telegram validation
필수 metadata:
- `Date`
- 아래 둘 중 하나
  - `Source` + `PostID|PostDate|PostDateTime`
  - `# Telegram Log` + `MessageID`

정제 규칙:
- metadata line 및 forwarded residue 제거
- URL 제거 후 effective text 계산
- effective 길이 `< 60` 이고 meaningful short text가 아니면 quarantine
- Telegram PDF artifact가 있으면 clean body에 inline 승격 후 validation 수행

### 6.3 text/premium/startale validation
필수 metadata:
- `- URL`
- `- PublishedAt`
- `- Status`

판정 규칙:
- `Status`는 `SUCCESS|OK`만 허용
- `Reason`에 `paywall|subscription|session|blocked` 포함 시 quarantine
- `## 본문` 이후 텍스트에서 boilerplate 제거
- effective 길이 `< 100` 이고 meaningful short text가 아니면 quarantine

### 6.4 selected_articles row validation
- row must be object
- `url` canonicalize
- `title` strip
- `published_date|published_at`를 `YYYY-MM-DD`로 normalize
- `summary + body`의 effective text 길이 `< 80` 이고 meaningful short text가 아니면 quarantine

### 6.5 RSS validation
- flatten result가 비어 있으면 `rss_no_entries`
- item-level로 `title + datetime/published + url`를 만족하는 entry가 1개도 없으면 `rss_missing_required_fields(title/datetime/url)`

### 6.6 DART validation
- 최소 컬럼 불충족 → `missing_required_columns:<cols>`
- `rcept_dt` invalid → `invalid_rcept_dt`
- `report_nm` 결측 → `missing_report_nm`
- `rcept_no` 결측 → `missing_rcept_no`
- `corp/stock code` 결측 → `missing_corp_or_stock_code`
- `rcept_no` 중복 → `duplicate_rcept_no`

---

## 7) link enrichment 계약
- 기본값
  - enrichment ON: `link_enrichment.enabled_default=true` (필요 시 `STAGE2_ENABLE_LINK_ENRICHMENT=0`)
  - Stage2 live fetch fallback OFF: `STAGE2_ENABLE_LIVE_LINK_FETCH=0` (opt-in)
- 적용 조건
  - folder가 `text/blog|text/telegram|text/premium/startale`
  - 기본 validation이 short-body 사유로 실패
  - URL candidate가 존재
- 동작 순서(ownership 이동 이후)
  1. Stage1 sidecar(`raw/qualitative/link_enrichment/...`) 로드
  2. sidecar `canonical_urls` + `blocks`를 우선 적용
  3. 재검증
  4. still short이고 `STAGE2_ENABLE_LIVE_LINK_FETCH=1`인 경우에만 live fetch fallback
- dedup 계약(텍스트 교차 코퍼스)
  - `text/blog` / `text/telegram`은 clean 본문 canonical URL에 더해 sidecar `canonical_urls`를 corpus dedup 신호로 사용한다.
- fetch 전용 실패 reason
  - `blog_link_body_fetch_failed`
  - `telegram_link_body_fetch_failed`
  - `premium_link_body_fetch_failed`
- clean output에는 attachment residue (`ATTACH_*`, `MEDIA`, `MIME`, `FILE_SIZE`)를 남기지 않는다.

---

## 8) Telegram PDF inline promotion 계약
- 입력 단위: **parent telegram message + attachment artifact pair**
- canonical output: 별도 `telegram_pdf` corpus를 만들지 않고 기존 `text/telegram` clean 본문에 inline 승격
- clean 본문 표식:
```text
[ATTACHED_PDF] <normalized_title>
<pdf_body_text>
```
- path resolution
  - marker path 우선
  - 실패 시 bucketed flat canonical fallback (`<channel_slug>/bucket_<nn>/msg_<message_id>__meta.json` 계열)
  - 그 다음에만 legacy dir fallback (`<channel_slug>/msg_<message_id>/meta.json`)
- text source precedence
  - `stage1 extracted.txt` 우선
  - 실패 시 Stage2 local PDF extraction (`pypdf` → `pdfminer`)
- recovery boundary
  - Stage2 recovery는 **로컬 artifact path resolution + local extract fallback** 까지만 포함한다.
  - missing original 재다운로드/credentialed Telegram recovery는 Stage1 범위다.
- attachment-specific 실패는 report/diagnostics에 집계한다.
- 세부 설계/diagnostics 이름은 `STAGE2_PDF_REFINEMENT_DESIGN.md`를 따른다.

---

## 9) corpus-level qualitative dedup 계약
대상 folder:
- `market/news/selected_articles`
- `text/blog`
- `text/telegram`
- `text/premium/startale`

우선순위:
1. canonical URL exact match → `duplicate_canonical_url`
2. normalized title + normalized date exact match → `duplicate_title_date`
3. normalized effective body fingerprint match → `duplicate_content_fingerprint`

세부 규칙:
- incremental 실행에서도 기존 clean corpus를 bootstrap해 전역 dedup registry를 만든다.
- content fingerprint는 normalize 후 길이 `>= 80` 텍스트에 대해서만 생성한다.
- telegram의 generic log title 같은 약한 제목은 title-date key에서 제외할 수 있다.

---

## 10) processed index / incremental signature
- path: `invest/stages/stage2/outputs/clean/production/_processed_index.json`
- top-level schema:
```json
{
  "__meta__": {
    "stage2_rule_version": "stage2-refine-20260308-r4",
    "stage2_config_sha1": "...",
    "link_enrichment_enabled": false,
    "live_link_fetch_enabled": false,
    "input_source": "stage1_raw_db_mirror",
    "folders": ["..."]
  },
  "entries": {
    "<folder>/<rel_path>": "<sha1-signature>"
  }
}
```
- entry key: `"<folder>/<rel_path>"`
- signature 구성:
  - `stage2_rule_version`
  - `config_bundle_sha1`
  - `link_enrichment_enabled`
  - `live_link_fetch_enabled`
  - `size`
  - `mtime`
  - `path`
  - telegram markdown이면 **attachment subtree signature 추가**
  - text target(`blog|telegram|premium`)이면 Stage1 sidecar file(`link_enrichment/...`)의 `rel_path:size:mtime` signature 추가

telegram attachment subtree signature는 같은 channel slug 아래 file들의
`relative_path:size:mtime` 목록의 SHA1이다.

---

## 11) refine report schema
`stage02_onepass_refine_full.py`는 아래를 만든다.
- markdown: `outputs/reports/qc/FULL_REFINE_REPORT_<ts>.md`
- json: `outputs/reports/qc/FULL_REFINE_REPORT_<ts>.json`

JSON top-level keys:
- `generated_at`
- `stage2_rule_version`
- `run_mode`
- `processed_index_policy`
- `incremental_signature`
- `config_provenance`
- `clean_base`
- `quarantine_base`
- `writer_policy`
- `output_policy`
- `quality_gate`
- `results`
- `totals`
- `link_enrichment`
- `telegram_pdf`
- `reason_taxonomy`
- `corpus_dedup`

PASS 기준:
- process rc=0
- report json/md 생성
- `quality_gate.verdict = PASS`

hard fail:
- `missing_input_folder(required=true)`
- `folder_processing_exception`
- `zero_clean_required_folder`

report-only anomaly:
- `missing_input_folder(required=false)`
- `zero_clean_optional_folder`

---

## 12) QC exact behavior (`stage02_qc_cleaning_full.py`)

### 12.1 KR universe
- `kr_stock_list.csv`의 `Code`를 6자리 zero-pad
- `Market`가 있으면 `KOSPI|KOSDAQ|KOSDAQ GLOBAL`만 포함
- 아니면 `MarketId`가 `STK|KSQ`인 것만 포함

### 12.2 OHLCV invalid conditions
- `Date` parse 실패
- `Close <= 0`
- `Open/High/Low` 결측
- `Volume < 10`
- all-zero-ish candle (`Open<=0 and High<=0 and Low<=0 and Close>0 and Volume==0`) → `zero_candle`
- `abs(Close.pct_change()) > 0.35` → `return_spike_gt_35pct`
- duplicate `Date` → `duplicate_date`

### 12.3 supply invalid conditions
- `Date` parse 실패
- `Inst/Corp/Indiv/Foreign/Total` 중 하나라도 numeric 실패
- duplicate `Date`

### 12.4 QC report schema
- markdown: `outputs/reports/QC_REPORT_<ts>.md`
- json: `outputs/reports/QC_REPORT_<ts>.json`

JSON top-level keys:
- `executed_at`
- `qc_version`
- `mode`
- `writer_policy`
- `universe_policy`
- `anomaly_taxonomy`
- `config_provenance`
- `groups`
- `totals`
- `validation`
- `anomalies`
- `hard_failures`
- `report_only_anomalies`

PASS 기준:
- rc=0
- `validation.pass = true`

QC hard fail types:
- `missing_target_file`
- `processing_error`
- `zero_clean_folder`

QC warn types:
- `full_quarantine`
- `high_quarantine_ratio`
- `empty_input_file`

---

## 13) 실행 커맨드
```bash
# refine (incremental)
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py

# refine authoritative rebuild
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild
# alias
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --full-rerun

# folder subset only
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --folders market/news/selected_articles

# backfill existing clean selected_articles classification/sidecars without upstream raw replay
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --repair-selected-articles-clean

# signal QC
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py

# opt-in link enrichment
STAGE2_ENABLE_LINK_ENRICHMENT=1 python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
```

---

## 14) rerun policy
- 기본 실행은 incremental
- selected_articles historical backlog처럼 upstream raw가 이미 축약/교체된 경우에는 `--repair-selected-articles-clean`로 clean JSONL row + summary sidecar를 재물질화할 수 있다.
- 다음 조건이면 authoritative rebuild를 권장/요구한다.
  - rule version 변경
  - config bundle SHA1 변경
  - link enrichment flag 변경
  - Telegram attachment subtree 변경
  - Telegram PDF inline 승격 규칙 변경
- authoritative rebuild 기준:
  1. `stage02_onepass_refine_full.py --force-rebuild`
  2. 이어서 `stage02_qc_cleaning_full.py`

---

## 15) 실패 정책
- refine 또는 QC 중 하나라도 실패하면 downstream 차단
- 같은 output path를 두 writer가 동시에 소유하면 안 된다
- canonical output은 `production/(signal|qualitative)/*` only
