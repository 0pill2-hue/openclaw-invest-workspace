# Stage2 Rulebook & Repro

## 범위
- 역할: Stage1 산출 raw/master를 Stage2 clean/quarantine으로 정제
- 정제 대상: **ohlcv/supply + dart/news/text 전체**
- 원칙: Stage2는 `stage2/inputs/upstream_stage1` 경유 입력만 사용
- Change type: **Rule**
- Telegram PDF artifact 승격 canonical contract/implementation: `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`
- signal/qualitative 원칙:
  - `raw/signal/*`는 수치/시계열 신호 원천이다.
  - `raw/qualitative/*`는 비정형 원천이다.
  - Stage2의 책임은 **정제/격리/중복 제거**까지이며, qualitative에 대해 직접 점수화·라벨링·투자판단을 하지 않는다.
  - `stage02_qc_cleaning_full.py`는 `kr/ohlcv`, `kr/supply`, `us/ohlcv`의 canonical clean/quarantine writer이자 signal QC 단계다.
  - `stage02_onepass_refine_full.py`는 `market/* signal` + qualitative 전체 canonical clean/quarantine writer다.
  - 같은 output path는 한 스크립트만 쓰도록 folder ownership을 고정한다.

## 입력 (Inputs)
- config inputs: `invest/stages/stage2/inputs/config/stage2_runtime_config.json`, `invest/stages/stage2/inputs/config/stage2_reason_config.json`
- filter/dedup/link/runtime 값은 runtime config JSON을 canonical source로 사용하고, reason/taxonomy 이름은 reason config JSON을 canonical source로 사용한다.
- `invest/stages/stage2/inputs/upstream_stage1/master/kr_stock_list.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/kr/supply/*_supply.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/kr/dart/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/us/ohlcv/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/market/rss/*.json`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/market/news/selected_articles/*.jsonl`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/market/macro/*`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/{blog,telegram,premium/startale}/**/*`
- Telegram PDF auxiliary artifact: `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/attachments/telegram/**/{meta.json,*.pdf,extracted.txt}`
  - 주의: attachment tree는 standalone corpus/FOLDER가 아니라 telegram raw markdown과 message-sidecar join으로 소비한다. 승격 계약/경로 rewrite/출력 스키마는 `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`를 따른다.
- 제외 입력:
  - `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/market/news/url_index/*`
  - reason: Stage1 `selected_articles` 생성용 보조 인덱스이며 Stage2 canonical qualitative corpus 입력이 아니다.
  - image 계열(`image_map`, `images_ocr`)은 현행 Stage2 계약에서 제외한다.

## 정제 규칙(핵심)
- OHLCV/Supply: 기존 규칙 유지(행 단위 수치 정합성/결측 검증)
- DART CSV: 최소 `corp_code/corp_name/report_nm/rcept_no/rcept_dt`를 요구하고, `rcept_dt` 파싱 실패·핵심 키 결측·`rcept_no` 중복은 quarantine한다.
- Market RSS JSON: 비어있지 않음 + 엔트리 레벨 `title + datetime + url` 최소 1건 필수
- Selected Articles JSONL:
  - 각 row는 object여야 한다.
  - 최소 `url + title + published_date|published_at + 본문(summary/body 기반 유효 텍스트)` 계약을 만족해야 한다.
  - URL은 canonicalize 후 clean에 적재한다.
  - row-level invalid/duplicate는 quarantine JSONL로 분리한다.
- Text(blog): `Date/PublishedDate + Source` 메타 필수 + 유효 본문 길이(boilerplate/UI 라인 제거 후) 검증
- Text(telegram): `Date + Source + Post*` 메타 필수 + 유효 본문 길이 검증
- Telegram PDF auxiliary promotion: parent Telegram message + attachment `meta/original/extracted(optional)` pair를 입력 계약으로 삼고, Stage1 marker path(`outputs/raw/...`)는 Stage2 upstream root(`raw/...`)로 rewrite 해석한다. image/legacy OCR text는 계속 제외한다. canonical 출력은 별도 `telegram_pdf` corpus가 아니라 기존 `qualitative/text/telegram` clean 본문에 메시지 단위 inline 승격하는 방식이다. clean 본문에는 `[ATTACHED_PDF] <normalized_title>` 최소 표식만 허용하고, provenance/debug 정보는 report/diagnostics sidecar로 보낸다.
- Text(premium/startale): `URL + PublishedAt + Status` 메타 필수, `Status=SUCCESS|OK`만 통과, paywall/session reason 차단, boilerplate-only 본문 차단
- Link enrichment:
  - Stage2 기본 동작이 아니라 **명시적 opt-in(`STAGE2_ENABLE_LINK_ENRICHMENT=1`)**일 때만 수행한다.
  - 대상: `text/blog`, `text/telegram`, `text/premium/startale`
  - 조건: 본문이 너무 짧거나 URL 의존도가 높을 때만 시도한다.
  - 동작: 본문/`[ATTACH_TEXT]`에서 URL 추출 → canonicalize/dedup → 외부 본문 fetch → 본문 주입 → 재검증
  - image residue 정책: `ATTACH_*`, `MEDIA`, image attachment marker는 link-source 추출에는 참고할 수 있어도 **clean output에는 남기지 않는다**.
- Corpus-level qualitative dedup:
  - scope: `market/news/selected_articles`, `text/blog`, `text/telegram`, `text/premium/startale`
  - registry: incremental 실행에서도 기존 clean corpus를 bootstrap해 전역 중복 비교를 수행한다.
  - duplicate 판정 키(우선순위):
    1. canonical URL 일치
    2. normalized title + normalized date 일치
    3. content fingerprint 일치
  - content fingerprint는 유효 본문/기사 본문 기준으로 계산하며, link-enrichment로 주입된 본문과 selected_articles body 간 중복도 같은 registry에서 잡는다.

## Reason / Filter / Quarantine Taxonomy (canonical)

| Scope | Filter class | Canonical reason / pattern | Disposition |
| --- | --- | --- | --- |
| `stage02_qc_cleaning_full.py` signal QC | invalid | `basic_invalid_or_low_liquidity`, `zero_candle`, `return_spike_gt_35pct`, `invalid_date_or_nonnumeric` | quarantine row/file |
| `stage02_qc_cleaning_full.py` signal QC | duplicate | `duplicate_date` | quarantine row/file |
| `selected_articles/*.jsonl` | invalid | `selected_articles_missing_url`, `selected_articles_missing_title`, `selected_articles_missing_published_date`, `selected_articles_effective_body_too_short`, `jsonl_parse_error:<Exception>`, `jsonl_row_not_object`, `empty_jsonl` | quarantine JSONL row |
| `text/{blog,telegram,premium/startale}` | invalid | `text_too_short`, `blog_missing_required_metadata`, `telegram_missing_required_metadata`, `premium_missing_required_metadata`, `blog_effective_body_empty`, `blog_effective_body_too_short`, `telegram_effective_body_empty`, `telegram_effective_body_too_short`, `premium_effective_body_empty_or_boilerplate`, `premium_effective_body_too_short` | quarantine text |
| `text/{blog,telegram,premium/startale}` | fetch-fail | `blog_link_body_fetch_failed`, `telegram_link_body_fetch_failed`, `premium_link_body_fetch_failed` | quarantine text |
| `text/premium/startale` | terminal | `premium_bad_status_<STATUS>`, `premium_paywall_or_blocked_reason` | quarantine text |
| qualitative CSV / JSON | invalid | `missing_required_columns:<cols>`, `invalid_rcept_dt`, `invalid_<date_column>`, `missing_report_nm`, `missing_rcept_no`, `missing_corp_or_stock_code`, `missing_title_body_url`, `empty_after_strip`, `rss_no_entries`, `rss_missing_required_fields(title/datetime/url)`, `empty_json`, `invalid_json` | quarantine file/row |
| corpus-level qualitative dedup | duplicate | `duplicate_canonical_url`, `duplicate_title_date`, `duplicate_content_fingerprint`, `duplicate_rcept_no`, `duplicate_date_title`, `duplicate_<id_column>` | quarantine file/row |
| refine runtime | terminal | `exception:<ExceptionType>:<message>` | quarantine file |
| clean normalization | max-available | minimum contract 만족 + deterministic normalization 성공 시 clean 유지. **별도 `max_available` reason string은 emit하지 않는다.** | clean |
| refine report issue filter | warn/fail | warn=`missing_input_folder(optional)`, `zero_clean_optional_folder`; fail=`missing_input_folder(required)`, `folder_processing_exception`, `zero_clean_required_folder` | report-only / hard-fail |

정렬 원칙:
- `terminal`은 Stage2 quarantine 종착점(umbrella)이며, 실제 emitted reason은 주로 `invalid` / `duplicate` / `fetch-fail` / `premium status` / `exception` 패턴으로 기록한다.
- `max-available`는 clean 보존 정책 이름이며 quarantine reason이 아니다.
- canonical run 기준으로 보고/JSON에 노출되는 reason 명칭만 관리한다. helper 내부의 미도달 fallback wording은 taxonomy에 싣지 않는다.

## 출력 (Outputs)
- signal canonical writer (folder-owned)
  - `stage02_qc_cleaning_full.py` → `invest/stages/stage2/outputs/{clean,quarantine}/production/signal/{kr,us}/{ohlcv,supply}/...`
  - `stage02_onepass_refine_full.py` → `invest/stages/stage2/outputs/{clean,quarantine}/production/signal/market/{macro,google_trends}/...`
- qualitative canonical writer
  - `stage02_onepass_refine_full.py` → `invest/stages/stage2/outputs/{clean,quarantine}/production/qualitative/...`
  - Telegram PDF inline track(implemented): 별도 `telegram_pdf` corpus를 canonical output으로 만들지 않는다. 기존 `invest/stages/stage2/outputs/clean/production/qualitative/text/telegram/*.md`에 메시지 단위 inline 승격하고, attachment-specific 실패/통계는 report 또는 diagnostics sidecar로 추적한다.
  - alias policy (canonical 내부): `market/news/rss -> market/rss`
- 리포트/상태
  - `invest/stages/stage2/outputs/reports/QC_REPORT_*.{md,json}`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`
  - 각 report는 `runtime_config_path/reason_config_path`와 SHA1(bundle/runtime/reason)를 함께 남긴다.
  - refine incremental index: `invest/stages/stage2/outputs/clean/production/_processed_index.json`
- authoritative replacement policy:
  - 기존 outputs/reports에 image residue 또는 pre-dedup 설명이 남아 있어도 이번 턴에는 재생성하지 않는다.
  - 다음 `--force-rebuild` 결과물을 authoritative replacement로 본다.

## 실행 커맨드 (Run, canonical)
```bash
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
# 재현 가능한 full rerun / canonical rebuild
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild
# alias
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --full-rerun
# 비결정적 enrichment가 꼭 필요할 때만 opt-in
STAGE2_ENABLE_LINK_ENRICHMENT=1 python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
```

## 재현 규칙 (Repro)
- 기본 refine 실행은 incremental 모드다.
  - 기준: `_processed_index.json`의 파일 signature 일치 + 기존 clean/quarantine 산출물 존재 시 skip
- 재현 가능한 전체 재구축이 필요하면 `--force-rebuild`(=`--full-rerun`)를 사용한다.
  - 동작: processed index를 재사용하지 않고, Stage2 canonical clean/quarantine 트리를 비운 뒤 현재 `upstream_stage1/raw` 기준으로 다시 적재한다.
  - 목적: incremental skip 때문에 동일 입력 재실행이 부분 생략되는 갭을 없애고, 현재 입력 기준 전체 산출물을 다시 만든다.
- rule version / input contract / dedup 규칙이 바뀌면 signature salt가 달라져 동일 입력도 재정제 대상이 된다.
- Telegram PDF inline 승격 규칙처럼 qualitative 본문 자체가 바뀌는 변경은 `stage02_onepass_refine_full.py --force-rebuild`를 canonical rerun으로 본다. PDF-only 변경 검증에는 signal QC full rerun이 필수는 아니지만, Stage2 authoritative PASS 패키지를 새로 만들 때는 refine + QC를 함께 다시 도는 것을 권장한다.

## 검증 (Validation)
- QC 보고: `invest/stages/stage2/outputs/reports/QC_REPORT_*.{md,json}`
- refine 보고: `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`
- PASS 기준(현행 스크립트 기준):
  - refine 스크립트 rc=0
  - QC 스크립트 rc=0
  - 각 스크립트의 timestamped report 파일 생성
  - refine `quality_gate.verdict=PASS`
  - QC `validation.pass=true`
- refine hard fail:
  - required qualitative input folder 누락
  - required qualitative folder에서 `input_files>0`인데 `clean=0`
  - folder processing exception 발생
- QC hard fail:
  - `missing_target_file`, `processing_error`, `zero_clean_folder`
- report-only anomaly:
  - `full_quarantine`, `high_quarantine_ratio`, `empty_input_file`, optional folder의 `zero_clean_optional_folder`는 기본적으로 경고/리포트 대상이다.
- 운영 handoff 체크(스크립트 rc와 별도):
  - Stage3 입력으로 승격할 qualitative/text 배치는 `clean/production/qualitative/text/*`와 `clean/production/qualitative/market/news/selected_articles/*` 존재를 확인한다.

## Reason / Filter Taxonomy (authoritative names)
- 상태 구분:
  - `terminal_quarantine`: Stage2가 clean으로 승격하지 않고 quarantine에 남기는 최종 reason.
  - `normalizable_clean_transform`: URL/date/title 정규화, tracking query 제거, file-local URL dedup, opt-in link enrichment 성공처럼 **clean에 남기기 위한 보정**이다. 별도 quarantine reason을 쓰지 않는다.
  - `max_available`: 결정적 보정 후 최소 계약을 만족하면 clean에 유지한다. 현재 별도 reason string은 없다.
  - `warn`: report-only anomaly. 예: `full_quarantine`, `high_quarantine_ratio`, `empty_input_file`, `missing_input_folder(required=false)`, `zero_clean_optional_folder`.
  - `fail`: quality gate를 FAIL로 만드는 issue type. 예: `missing_input_folder(required=true)`, `folder_processing_exception`, `zero_clean_required_folder`, QC의 `missing_target_file|processing_error|zero_clean_folder`.
- text invalid metadata reason:
  - `blog_missing_required_metadata`
  - `telegram_missing_required_metadata`
  - `premium_missing_required_metadata`
- text body quality reason (invalid metadata와 분리):
  - `blog_effective_body_empty`, `blog_effective_body_too_short`
  - `telegram_effective_body_empty`, `telegram_effective_body_too_short`
  - `premium_effective_body_empty_or_boilerplate`, `premium_effective_body_too_short`
- link-body fetch failure reason (short/empty body와 분리):
  - `blog_link_body_fetch_failed`
  - `telegram_link_body_fetch_failed`
  - `premium_link_body_fetch_failed`
- premium blocked/status reason:
  - `premium_bad_status_<STATUS>`
  - `premium_paywall_or_blocked_reason`
- selected_articles invalid row reason:
  - `selected_articles_missing_url`
  - `selected_articles_missing_title`
  - `selected_articles_missing_published_date`
  - `selected_articles_effective_body_too_short`
  - `jsonl_parse_error:<Exception>` / `jsonl_row_not_object` / `empty_jsonl`
- qualitative csv/json invalid reason:
  - DART: `missing_required_columns:<cols>`, `invalid_rcept_dt`, `missing_report_nm`, `missing_rcept_no`, `missing_corp_or_stock_code`, `duplicate_rcept_no`
  - generic qualitative CSV: `missing_title_body_url`, `duplicate_<id_column>`, `duplicate_date_title`, `empty_after_strip`
  - RSS/JSON: `rss_no_entries`, `rss_missing_required_fields(title/datetime/url)`, `empty_json`, `invalid_json`
- corpus duplicate reason (실제 quarantine reason과 report 명칭 통일):
  - `duplicate_canonical_url`
  - `duplicate_title_date` ← **normalized title + normalized date** 매칭을 의미한다.
  - `duplicate_content_fingerprint`
- signal row quarantine reason (QC):
  - `basic_invalid_or_low_liquidity`, `zero_candle`, `return_spike_gt_35pct`, `duplicate_date`, `invalid_date_or_nonnumeric`

## incremental / 재현성
- processed index는 입력 파일의 `size + mtime + path`만 보지 않고 **Stage2 rule version + config bundle SHA1 + link enrichment flag**를 포함한 signature를 사용한다.
- qualitative dedup registry는 incremental 실행 시 기존 clean corpus를 bootstrap한다. 단, pre-change clean/output은 authoritative replacement가 아니며 다음 full rebuild 후 최종 상태를 확정한다.
- clean/quarantine row-level lineage 표준화는 추후 과제로 두고, 현재는 refine/QC report의 `config_provenance`, refine report JSON의 `stage2_rule_version`, `incremental_signature`, `corpus_dedup`를 기준으로 추적한다.

## 실패 정책
- QC 또는 refine 중 하나라도 실패하면 downstream 차단
- 같은 signal output path를 두 스크립트가 중복 작성하지 않는다.
- QC는 자신이 소유한 signal 폴더의 clean/quarantine writer이며, 동시에 hard-fail validation gate를 제공한다.
