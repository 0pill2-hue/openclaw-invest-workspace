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
  - `__meta__.input_source_status`
  - `__meta__.fallback_reason`
  - `__meta__.fallback_scope`
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
  - `outputs/runtime/stage2_integrity_summary.json`
- JSON keys
  - `generated_at`, `stage2_rule_version`, `run_mode`, `processed_index_policy`
  - `incremental_signature`, `config_provenance`
  - `input_source`, `input_source_status`, `fallback_reason`, `fallback_scope`, `input_source_policy`
  - `origin_of_degradation`, `stage3_ready_status`
  - `pdf_status_buckets`, `bounded_stop_visibility`, `legacy_join_visibility`, `handoff_completeness`
  - `clean_base`, `quarantine_base`
  - `writer_policy`, `output_policy`, `quality_gate`, `results`, `totals`
  - `link_enrichment`, `telegram_pdf`, `reason_taxonomy`, `corpus_dedup`
- `stage2_integrity_summary.json` 필수 key
  - `input_source_status`
  - `total_records_seen`, `total_records_clean`, `total_records_quarantine`
  - `pdf_docs_seen`, `pdf_promoted_docs`, `pdf_bounded_docs`, `pdf_missing_docs`, `pdf_placeholder_only_docs`
  - `lineage_unresolved_docs`
  - `stage3_ready_status`

### QC
- files
  - `outputs/reports/QC_REPORT_<ts>.md`
  - `outputs/reports/QC_REPORT_<ts>.json`
- JSON keys
  - `executed_at`, `qc_version`, `mode`, `writer_policy`, `universe_policy`
  - `anomaly_taxonomy`, `config_provenance`, `groups`, `totals`
  - `validation`, `anomalies`, `hard_failures`, `report_only_anomalies`

## 6) retention / residue policy (current)
| class | path | current role | retention |
| --- | --- | --- | --- |
| hot | `outputs/clean/production/**` | downstream canonical clean corpus | current 10y rolling corpus 유지 |
| hot | `outputs/quarantine/production/**` | quarantine evidence corpus | current 10y rolling corpus 유지 |
| hot | `outputs/runtime/upstream_stage1_db_mirror/current/raw/**` | Stage1 raw DB의 stage-local compact mirror | current snapshot 1개 + fallback latest 1개 |
| warm | `outputs/reports/qc/*` | refine/QC run report | 운영 증빙용, compact JSON/MD만 유지 |
| warm | `outputs/logs/runtime/*` | launchd/runtime log | 저용량 관찰 로그, 필요 시만 확장 |
| cold-delete-first | `outputs/runtime/upstream_stage1_db_mirror/snapshots/*` (non-current) | historical mirror copies | keep latest only, overflow snapshot 제거 |
| cold-delete-first | `outputs/runtime/upstream_stage1_db_mirror/snapshots/.*__building__*` | interrupted/incomplete staging residue | stale > 12h cleanup |
| cold-delete-first | mirror 내 `qualitative/attachments/telegram/**/*__page_*.png` | human-review render residue | compact mirror materialization에서 제외 |
| cold-delete-first | mirror 내 `qualitative/attachments/telegram/**/*__bundle.zip` | convenience bundle residue | compact mirror materialization에서 제외 |

### current implementation note
- `prepare_stage2_raw_input_root()`는 `stage2_compact_v1` profile로 snapshot을 materialize한다.
- compact profile은 Telegram attachment mirror에서 Stage2 refine에 필요 없는 `__page_*.png`, `__bundle.zip`을 제외한다.
- snapshot retention env:
  - `STAGE2_DB_MIRROR_KEEP_LATEST` (default `2`)
  - `STAGE2_DB_MIRROR_INCOMPLETE_MAX_AGE_HOURS` (default `12`)
- prune audit trail: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/retention_status.json`

## 7) 실행 옵션 (current)
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
