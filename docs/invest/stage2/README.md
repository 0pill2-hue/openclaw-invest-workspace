# Stage2 Docs

## Canonical 문서
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage2/inputs/upstream_stage1/`
  - signal 입력: `raw/signal/{kr,us,market}`
  - qualitative 입력: `raw/qualitative/{kr,market,text}`
- 책임 경계:
  - Stage2는 signal/qualitative를 **입력 계층 기준으로만 분리**해 clean/quarantine에 적재한다.
  - `signal`은 수치/시계열 정합성 검증 대상이다.
  - `qualitative`는 메타데이터/본문 유효성 검증 대상이며, Stage2에서 정성 점수화·해석·투자판단을 하지 않는다.

## 출력 (Outputs)
- canonical only: `invest/stages/stage2/outputs/{clean,quarantine}/production/{signal,qualitative}/...`
- folder ownership:
  - `kr/us ohlcv + supply` → `stage02_qc_cleaning_full.py`
  - `market signal + qualitative` → `stage02_onepass_refine_full.py`
- reports:
  - `invest/stages/stage2/outputs/reports/QC_REPORT_*.{md,json}`
  - `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`

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
- PASS 기준(현행 스크립트 기준):
  - refine 스크립트 rc=0 + `FULL_REFINE_REPORT_*.{md,json}` 생성 + `quality_gate.verdict=PASS`
  - qc 스크립트 rc=0 + `QC_REPORT_*.{md,json}` 생성 + `validation.pass=true`
  - report-only anomaly는 리포트에 남기되 rc를 바로 실패로 바꾸지 않는다.
- 운영 handoff 확인:
  - Stage3에 넘길 qualitative/text 배치를 승격할 때는 `clean/production/qualitative/text/*` 존재를 별도 확인한다.

## 실패 정책
- qc/refine 중 하나라도 실패하면 downstream 차단
