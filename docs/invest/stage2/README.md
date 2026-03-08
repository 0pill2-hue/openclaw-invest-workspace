# Stage2 Docs

## Canonical 문서
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage2/inputs/upstream_stage1/`
  - signal 입력: `raw/signal/{kr,us,market}`
  - qualitative 입력: `raw/qualitative/{kr,market,text}`
  - Stage2 qualitative 확장 입력: `raw/qualitative/market/news/selected_articles/*.jsonl`
- qualitative canonical contract:
  - 포함: `kr/dart`, `market/rss`(raw alias: `market/news/rss`), `market/news/selected_articles`, `text/blog`, `text/telegram`, `text/premium/startale`
  - 제외: `market/news/url_index` (Stage1 내부 선택/수집 보조 산출, Stage2 본입력 아님)
- 책임 경계:
  - Stage2는 signal/qualitative를 **입력 계층 기준으로만 분리**해 clean/quarantine에 적재한다.
  - `signal`은 수치/시계열 정합성 검증 대상이다.
  - `qualitative`는 메타데이터/본문 유효성 검증 + corpus-level dedup 대상이며, 정성 점수화·해석·투자판단은 하지 않는다.
  - image 계열(`image_map`, `images_ocr`)은 현행 정책상 Stage1/Stage2 계약에서 제외한다.

## 출력 (Outputs)
- canonical only: `invest/stages/stage2/outputs/{clean,quarantine}/production/{signal,qualitative}/...`
- folder ownership:
  - `kr/us ohlcv + supply` → `stage02_qc_cleaning_full.py`
  - `market signal + qualitative` → `stage02_onepass_refine_full.py`
- qualitative dedup scope:
  - `market/news/selected_articles`
  - `text/blog`
  - `text/telegram`
  - `text/premium/startale`
- reports:
  - `invest/stages/stage2/outputs/reports/QC_REPORT_*.{md,json}`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`
- 주의:
  - 이번 변경 전 생성된 Stage2 outputs/reports에 image residue 또는 pre-dedup 계약 흔적이 남아 있을 수 있다.
  - authoritative replacement는 **다음 Stage2 full rebuild(`--force-rebuild`) 결과물**이다. 이번 작업은 코드/문서/정적검증만 수행한다.

## 실행 커맨드 (Run, canonical)
```bash
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
# 재현용 full rerun이 필요하면
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild
# 비결정적 enrichment가 꼭 필요할 때만 opt-in
STAGE2_ENABLE_LINK_ENRICHMENT=1 python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
```

## 검증 (Validation)
- QC 스크립트 범위: `kr/us ohlcv + supply` clean/quarantine 작성 + validation/report 생성
- refine 스크립트 범위: `market signal + qualitative` canonical clean/quarantine 산출 및 보고 생성
- refine 추가 규칙:
  - blog/telegram/premium은 본문이 너무 짧을 때만 opt-in link enrichment를 시도한다.
  - enrichment 시 본문/첨부에서 추출한 링크를 canonicalize하고, 외부 본문을 가져와 정제 본문에 주입한 뒤 재검증한다.
  - qualitative dedup은 corpus-level registry로 수행하며, canonical URL → normalized title+date → content fingerprint 순으로 교차 중복을 잡는다.
- PASS 기준(현행 스크립트 기준):
  - refine 스크립트 rc=0 + `FULL_REFINE_REPORT_*.{md,json}` 생성 + `quality_gate.verdict=PASS`
  - qc 스크립트 rc=0 + `QC_REPORT_*.{md,json}` 생성 + `validation.pass=true`
  - report-only anomaly는 리포트에 남기되 rc를 바로 실패로 바꾸지 않는다.
- 운영 handoff 확인:
  - Stage3에 넘길 qualitative/text 배치를 승격할 때는 `clean/production/qualitative/text/*`와 `clean/production/qualitative/market/news/selected_articles/*` 존재를 별도 확인한다.

## 실패 정책
- qc/refine 중 하나라도 실패하면 downstream 차단
