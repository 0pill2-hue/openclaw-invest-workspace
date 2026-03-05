# Stage2 Rulebook & Repro

## 범위
- 역할: Stage1 산출 raw/master를 Stage2 clean/quarantine으로 정제
- 정제 대상: **ohlcv/supply + dart/news/text 전체**
- 원칙: Stage2는 `stage2/inputs/upstream_stage1` 경유 입력만 사용
- signal/qualitative 원칙:
  - `raw/signal/*`는 수치/시계열 신호 원천
  - `raw/qualitative/*`는 비정형 원천(직접 점수식 입력 금지, 파생피처 경유)

## 입력 (Inputs)
- `invest/stages/stage2/inputs/upstream_stage1/master/kr_stock_list.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/kr/supply/*_supply.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/kr/dart/*.{csv,json}`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/us/ohlcv/*.csv`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/market/rss/*.json`
- `invest/stages/stage2/inputs/upstream_stage1/raw/signal/market/macro/*`
- `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/text/{blog,telegram,image_map,images_ocr,premium/startale}/**/*`

## 정제 규칙(핵심)
- OHLCV/Supply: 기존 규칙 유지(행 단위 수치 정합성/결측 검증)
- Text(blog): `Date/PublishedDate + Source` 메타 필수 + 유효 본문 길이(boilerplate/UI 라인 제거 후) 검증
- Text(telegram): `Date + Source + Post*` 메타 필수 + 유효 본문 길이 검증
- Text(premium/startale): `URL + PublishedAt + Status` 메타 필수, `Status=SUCCESS|OK`만 통과, paywall/session reason 차단, boilerplate-only 본문 차단
- Market RSS JSON: 비어있지 않음 + 엔트리 레벨 `title + datetime + url` 최소 1건 필수
- Image-map JSON: 비어있지 않음 + 아이템 구조(`url류 + source류`) 최소 1건 필수

## 출력 (Outputs)
- QC clean/quarantine
  - `invest/stages/stage2/outputs/clean/production/signal/{kr,us}/...`
  - `invest/stages/stage2/outputs/quarantine/production/signal/{kr,us}/...`
- Full refine clean/quarantine
  - canonical only: `invest/stages/stage2/outputs/{clean,quarantine}/production/{signal,qualitative}/...`
  - alias policy (canonical 내부): `market/news/rss -> market/rss`
- 리포트/상태
  - `invest/stages/stage2/outputs/reports/QC_REPORT_*.{md,json}`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`

## 실행 커맨드 (Run, canonical)
```bash
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
```

## 검증 (Validation)
- QC 보고: `invest/stages/stage2/outputs/reports/QC_REPORT_*.json`
- refine 보고: `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.md`
- PASS 기준:
  - QC 스크립트 rc=0
  - refine 스크립트 rc=0
  - Stage3 입력 의존 경로(`clean/production/qualitative/text/*`) 존재

## 실패 정책
- QC 또는 refine 중 하나라도 실패하면 downstream 차단
