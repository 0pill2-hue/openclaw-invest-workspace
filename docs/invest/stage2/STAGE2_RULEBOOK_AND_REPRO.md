# Stage2 Rulebook & Repro

## 범위
- 역할: Stage1 산출 raw/master를 Stage2 clean/quarantine으로 정제
- 정제 대상: **ohlcv/supply + dart/news/text 전체**
- 원칙: Stage2는 `stage2/inputs/upstream_stage1` 경유 입력만 사용
- Change type: **Rule** (전략 로직 확장 아님)
- signal/qualitative 원칙:
  - `raw/signal/*`는 수치/시계열 신호 원천이다.
  - `raw/qualitative/*`는 비정형 원천이다.
  - Stage2의 책임은 **정제/격리**까지이며, qualitative에 대해 직접 점수화·라벨링·투자판단을 하지 않는다.
  - 정성 해석/압축은 Stage3 이후 책임이다.
  - `stage02_qc_cleaning_full.py`는 `kr/ohlcv`, `kr/supply`, `us/ohlcv`의 canonical clean/quarantine writer이자 signal QC 단계다.
  - `stage02_onepass_refine_full.py`는 `market/* signal` + qualitative 전체 canonical clean/quarantine writer다.
  - 같은 output path는 한 스크립트만 쓰도록 folder ownership을 고정한다.

## 입력 (Inputs)
- `invest/stages/stage2/inputs/upstream_stage1/master/kr_stock_list.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/kr/supply/*_supply.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/kr/dart/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/us/ohlcv/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/market/rss/*.json`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/market/macro/*`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/{blog,telegram,image_map,images_ocr,premium/startale}/**/*`

## 정제 규칙(핵심)
- OHLCV/Supply: 기존 규칙 유지(행 단위 수치 정합성/결측 검증)
- DART CSV: 최소 `corp_code/corp_name/report_nm/rcept_no/rcept_dt`를 요구하고, `rcept_dt` 파싱 실패·핵심 키 결측·`rcept_no` 중복은 quarantine한다. `stock_code`가 있으면 identity 보조키로 사용하되, Stage2는 공시 의미 해석까지 확장하지 않는다.
- Generic qualitative CSV: qualitative bucket CSV는 비어 있는 pass-through로 넘기지 않고, 가능한 범위에서 날짜/제목/URL 또는 identity 중 최소 계약을 확인한다.
- Text(blog): `Date/PublishedDate + Source` 메타 필수 + 유효 본문 길이(boilerplate/UI 라인 제거 후) 검증
- Text(telegram): `Date + Source + Post*` 메타 필수 + 유효 본문 길이 검증
- Text(premium/startale): `URL + PublishedAt + Status` 메타 필수, `Status=SUCCESS|OK`만 통과, paywall/session reason 차단, boilerplate-only 본문 차단
- Market RSS JSON: 비어있지 않음 + 엔트리 레벨 `title + datetime + url` 최소 1건 필수
- Image-map JSON: 비어있지 않음 + 아이템 구조(`url류 + source류`) 최소 1건 필수
- Link enrichment: Stage2 기본 동작이 아니라 **명시적 opt-in(`STAGE2_ENABLE_LINK_ENRICHMENT=1`)**일 때만 수행한다.

## 출력 (Outputs)
- signal canonical writer (folder-owned)
  - `stage02_qc_cleaning_full.py` → `invest/stages/stage2/outputs/{clean,quarantine}/production/signal/{kr,us}/{ohlcv,supply}/...`
  - `stage02_onepass_refine_full.py` → `invest/stages/stage2/outputs/{clean,quarantine}/production/signal/market/{macro,google_trends}/...`
- qualitative canonical writer
  - `stage02_onepass_refine_full.py` → `invest/stages/stage2/outputs/{clean,quarantine}/production/qualitative/...`
  - alias policy (canonical 내부): `market/news/rss -> market/rss`
- 리포트/상태
  - `invest/stages/stage2/outputs/reports/QC_REPORT_*.{md,json}`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`
  - refine incremental index: `invest/stages/stage2/outputs/clean/production/_processed_index.json`

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
  - Stage3 입력으로 승격할 qualitative/text 배치는 `clean/production/qualitative/text/*` 존재를 확인한다.

## incremental / 재현성
- processed index는 입력 파일의 `size + mtime + path`만 보지 않고 **Stage2 rule version + link enrichment flag**를 포함한 signature를 사용한다.
- 정제 규칙이 바뀌면 동일 입력이라도 재정제되도록 설계한다.
- clean/quarantine row-level lineage 표준화는 추후 과제로 두고, 현재는 refine report JSON의 `stage2_rule_version`과 `incremental_signature`를 기준으로 추적한다.

## 실패 정책
- QC 또는 refine 중 하나라도 실패하면 downstream 차단
- 같은 signal output path를 두 스크립트가 중복 작성하지 않는다.
- QC는 자신이 소유한 signal 폴더의 clean/quarantine writer이며, 동시에 hard-fail validation gate를 제공한다.
