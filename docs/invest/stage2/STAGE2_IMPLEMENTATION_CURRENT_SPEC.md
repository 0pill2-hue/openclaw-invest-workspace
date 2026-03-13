# STAGE2_IMPLEMENTATION_CURRENT_SPEC

status: CANONICAL (implementation-detail/current-values)
updated_at: 2026-03-13 KST
contract source: `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`

## 1) 현재 구현값 (Current exact thresholds)
### 1.1 refine text validation thresholds
| key | value |
| --- | ---: |
| `blog_min_effective_len` | 80 |
| `telegram_min_effective_len` | 60 |
| `premium_min_effective_len` | 100 |
| `selected_articles_min_text_len` | 80 |
| `short_meaningful_min_len` | 45 |
| `dedup.min_fingerprint_text_len` | 80 |

### 1.2 refine target folders
- corpus dedup target
  - `market/news/selected_articles`
  - `text/blog`
  - `text/telegram`
  - `text/premium/startale`
- link enrichment target
  - `text/blog`
  - `text/telegram`
  - `text/premium/startale`

### 1.3 link enrichment runtime values
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

### 1.4 QC thresholds
| key | value |
| --- | ---: |
| included KR markets | `KOSPI`, `KOSDAQ`, `KOSDAQ GLOBAL` |
| included MarketId | `STK`, `KSQ` |
| `min_valid_volume` | 10 |
| `max_daily_ret_abs` | 0.35 |

## 2) refine 세부 동작 (implementation)
### 2.1 text/blog
- metadata: `Date|PublishedDate`, `Source`
- heading/metadata line/`---`/URL 제거 후 effective text 길이 판정

### 2.2 text/telegram
- metadata: `Date` + (`Source`+`Post*` 또는 `# Telegram Log`+`MessageID`)
- forwarded residue 제거, URL 제거, 길이 판정
- PDF artifact가 있으면 inline 승격 후 validation

### 2.3 text/premium/startale
- metadata: `- URL`, `- PublishedAt`, `- Status`
- `Status=SUCCESS|OK`만 통과
- paywall/subscription/session/blocked reason은 quarantine

### 2.4 selected_articles row
- object row
- URL canonicalize
- date normalize(`YYYY-MM-DD`)
- summary/body effective text 길이 판정

### 2.5 dedup 우선순위
1. canonical URL exact match
2. normalized title + normalized date
3. normalized body fingerprint

## 3) Telegram PDF inline promotion (implementation)
- clean 본문 표식
```text
[ATTACHED_PDF] <normalized_title>
<pdf_body_text>
```
- path resolution order
  1. marker path
  2. bucketed flat canonical (`bucket_<nn>/msg_<id>__meta.json` 계열)
  3. legacy `msg_<id>/meta.json`
- text source precedence
  1. Stage1 `extracted.txt`
  2. Stage2 local extraction (`pypdf` -> `pdfminer`)

## 4) processed index / incremental signature
- path: `invest/stages/stage2/outputs/clean/production/_processed_index.json`
- top-level keys
  - `__meta__.stage2_rule_version`
  - `__meta__.stage2_config_sha1`
  - `__meta__.link_enrichment_enabled`
  - `__meta__.live_link_fetch_enabled`
  - `__meta__.input_source`
  - `entries`
- entry key: `"<folder>/<rel_path>"`
- signature material
  - `rule_version`, `config_sha1`, flags, `size`, `mtime`, `path`
  - telegram attachment subtree signature
  - link_enrichment sidecar signature

## 5) report schema (current)
### refine
- files
  - `outputs/reports/qc/FULL_REFINE_REPORT_<ts>.md`
  - `outputs/reports/qc/FULL_REFINE_REPORT_<ts>.json`
- JSON keys
  - `generated_at`, `stage2_rule_version`, `run_mode`, `processed_index_policy`
  - `incremental_signature`, `config_provenance`, `clean_base`, `quarantine_base`
  - `writer_policy`, `output_policy`, `quality_gate`, `results`, `totals`
  - `link_enrichment`, `telegram_pdf`, `reason_taxonomy`, `corpus_dedup`

### QC
- files
  - `outputs/reports/QC_REPORT_<ts>.md`
  - `outputs/reports/QC_REPORT_<ts>.json`
- JSON keys
  - `executed_at`, `qc_version`, `mode`, `writer_policy`, `universe_policy`
  - `anomaly_taxonomy`, `config_provenance`, `groups`, `totals`
  - `validation`, `anomalies`, `hard_failures`, `report_only_anomalies`

## 6) 실행 옵션 (current)
```bash
# incremental refine
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py

# authoritative rebuild (alias 포함)
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --full-rerun

# subset
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --folders market/news/selected_articles

# selected_articles clean repair
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --repair-selected-articles-clean

# signal QC
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py

# opt-in link enrichment
STAGE2_ENABLE_LINK_ENRICHMENT=1 python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
```
