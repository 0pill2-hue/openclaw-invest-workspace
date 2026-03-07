# Stage4 Rulebook & Repro

## 범위
- 역할: Stage2 clean + Stage3 정성신호를 결합해 Value 산출
- 원칙: Stage4 입력은 `upstream_stage1_master`, `upstream_stage2_clean`, `upstream_stage3_outputs`로 고정
- Stage3 전달 규칙: 중복연산 방지 가드가 적용된 `qualitative_signal`만 결합 대상으로 사용

## 입력 (Inputs)
- `invest/stages/stage4/inputs/upstream_stage2_clean/{kr,us}/ohlcv/*.csv`
- `invest/stages/stage4/inputs/upstream_stage1_master/kr_stock_list.csv`
- `invest/stages/stage4/inputs/upstream_stage3_outputs/features/stage3_qualitative_axes_features.csv`

## 출력 (Outputs)
- `invest/stages/stage4/outputs/value/{kr,us}/ohlcv/*.csv`
- `invest/stages/stage4/outputs/reports/STAGE4_VALUE_RUN_*.json`
- `invest/stages/stage4/outputs/manifest_stage4_value_*.json`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage4/scripts/calculate_stage4_values.py
```

## 검증 (Validation)
- 검증 파일: `invest/stages/stage4/outputs/reports/STAGE4_VALUE_RUN_*.json`
- PASS 기준: `errors == 0`

## 실패 정책
- 스크립트 비정상 종료 또는 report.errors>0이면 downstream 차단
