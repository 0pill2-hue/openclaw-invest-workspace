# Stage2 Docs

## Canonical 문서
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage2/inputs/upstream_stage1/`
  - signal 입력: `raw/signal/{kr,us,market}`
  - qualitative 입력: `raw/qualitative/{kr,market,text}`

## 출력 (Outputs)
- canonical only: `invest/stages/stage2/outputs/{clean,quarantine}/production/{signal,qualitative}/...`
- reports: `invest/stages/stage2/outputs/reports/`

## 실행 커맨드 (Run, canonical)
```bash
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
```

## 검증 (Validation)
- `invest/stages/stage2/outputs/reports/QC_REPORT_*.json`
- `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_*.{md,json}`
- PASS 기준: qc + refine 모두 rc=0

## 실패 정책
- qc/refine 중 하나라도 실패하면 downstream 차단
