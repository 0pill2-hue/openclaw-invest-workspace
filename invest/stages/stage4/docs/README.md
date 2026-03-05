# Stage4 Docs

## Canonical 문서
- `invest/stages/stage4/docs/STAGE4_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage4/inputs/upstream_stage2_clean/`
- `invest/stages/stage4/inputs/upstream_stage1_master/`
- `invest/stages/stage4/inputs/upstream_stage3_outputs/`

## 출력 (Outputs)
- `invest/stages/stage4/outputs/value/`
- `invest/stages/stage4/outputs/reports/`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage4/scripts/calculate_stage4_values.py
```

## 검증 (Validation)
- `invest/stages/stage4/outputs/reports/STAGE4_VALUE_RUN_*.json`
- Stage3 전달 `qualitative_signal`가 중복연산 가드 적용 출력인지 확인
- PASS 기준: `errors == 0`

## 실패 정책
- 비정상 종료 또는 `errors > 0`이면 downstream 차단

