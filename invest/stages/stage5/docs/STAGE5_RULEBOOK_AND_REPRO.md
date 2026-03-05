# Stage5 Rulebook & Repro

## 범위
- 역할: Stage2 clean 기반 피처 엔지니어링
- 원칙: Stage5 입력은 `upstream_stage1_master`, `upstream_stage2_clean`로 고정
- Stage3/4 중복연산 방지 정책과 충돌하는 중복 피처 증폭 금지(동일축 중복 가중 금지)

## 입력 (Inputs)
- `invest/stages/stage5/inputs/upstream_stage2_clean/kr/ohlcv/*.csv`
- `invest/stages/stage5/inputs/upstream_stage2_clean/kr/supply/*_supply.csv`
- `invest/stages/stage5/inputs/upstream_stage1_master/kr_stock_list.csv`
- `invest/stages/stage5/inputs/upstream_stage2_clean/kr/{ohlcv,supply}/`

## 출력 (Outputs)
- `invest/stages/stage5/outputs/features/kr/*.csv`
- `invest/stages/stage5/outputs/reports/STAGE5_FEATURE_RUN_*.json`
- `invest/stages/stage5/outputs/manifest_stage5_feature_*.json`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage5/scripts/stage05_feature_engineer.py
```

## 검증 (Validation)
- 검증 파일: `invest/stages/stage5/outputs/reports/STAGE5_FEATURE_RUN_*.json`
- PASS 기준: `errors == 0`

## 실패 정책
- 스크립트 비정상 종료 또는 report.errors>0이면 stage5 FAIL
