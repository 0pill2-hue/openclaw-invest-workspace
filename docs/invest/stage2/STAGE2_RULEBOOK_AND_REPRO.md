# Stage2 Rulebook & Repro

status: CANONICAL (contract/repro)
updated_at: 2026-03-13 KST
implementation spec: `docs/invest/stage2/STAGE2_IMPLEMENTATION_CURRENT_SPEC.md`

## 문서 역할
- 이 문서는 Stage2 재현에 필요한 **입력/출력/책임 경계/PASS-FAIL 계약**만 고정한다.
- 현재 구현값(정확한 threshold, runtime flag 기본값, report schema, 세부 동작 순서)은 구현 spec로 분리한다.

## 1) 범위 / 책임 경계
- 역할: Stage1 raw/master를 Stage2 `clean/quarantine`으로 정제
- 비범위:
  - 투자판단/정성 점수화
  - Stage1 원천 재수집
- writer ownership
  - `stage02_qc_cleaning_full.py`: `signal/{kr/ohlcv,kr/supply,us/ohlcv}`
  - `stage02_onepass_refine_full.py`: `signal/market/*`, `qualitative/**`

## 2) 입력 계약 (Inputs)
- config
  - `invest/stages/stage2/inputs/config/stage2_runtime_config.json`
  - `invest/stages/stage2/inputs/config/stage2_reason_config.json`
- master
  - `invest/stages/stage2/inputs/upstream_stage1/master/kr_stock_list.csv`
- Stage1 raw archive authoritative source
  - `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- Stage2 runtime mirror root (logical raw path)
  - `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/current/raw`
- DB archive 부재 시 fallback
  - `invest/stages/stage2/inputs/upstream_stage1/raw`

## 3) 입력 최소 스키마 계약
### signal
- KR/US OHLCV CSV: `Date,Open,High,Low,Close,Volume`
- KR supply CSV: `Date,Inst,Corp,Indiv,Foreign,Total`

### qualitative
- DART CSV: `corp_code,corp_name,report_nm,rcept_no,rcept_dt`
- RSS JSON: flatten 결과 최소 1개 entry가 `title + datetime/published + url`
- selected_articles JSONL: `url,title,published_date|published_at,summary|body`
- blog markdown: `Date|PublishedDate` + `Source`
- telegram markdown: `Date` + (`Source`+`Post*` 또는 `# Telegram Log`+`MessageID`)
- premium markdown: `- URL`, `- PublishedAt`, `- Status`

## 4) canonical 출력 경로
### clean
- `invest/stages/stage2/outputs/clean/production/signal/{kr,us,market}/...`
- `invest/stages/stage2/outputs/clean/production/qualitative/...`

### quarantine
- `invest/stages/stage2/outputs/quarantine/production/signal/{kr,us,market}/...`
- `invest/stages/stage2/outputs/quarantine/production/qualitative/...`

### classification sidecar
- text/blog, text/telegram, text/premium/startale clean 파일: `*.classification.json`
- selected_articles clean JSONL row: `stage2_classification` 필드 + 파일단위 summary sidecar

## 5) 핵심 계약
- raw/input alias: `market/news/rss`
- canonical output alias: `market/rss`
- Telegram PDF는 별도 corpus를 만들지 않고 `text/telegram` clean 본문에 inline 승격
- dedup은 corpus-level로 적용(대상 folder: selected_articles/blog/telegram/premium)
- processed index 기반 incremental을 기본으로 한다.

구현 세부(우선순위, exact reason taxonomy, threshold 값, signature 구성)는 구현 spec를 따른다.

## 6) 실행 / 재실행
- 기본 실행(incremental)
  - `python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- authoritative rebuild
  - `python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild`
  - `python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`
- subset/repair 실행과 flag 상세는 구현 spec를 따른다.

## 7) PASS / FAIL
- PASS 최소 조건
  - refine rc=0 + report 생성 + quality_gate PASS
  - QC rc=0 + validation.pass=true
- FAIL 조건
  - required 입력 누락
  - writer 충돌(동일 output path 이중 소유)
  - refine/QC 중 하나라도 hard failure
- Stage2 FAIL 시 downstream 실행 금지
