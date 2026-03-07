# Stage5 Docs

## Canonical 문서
- `docs/invest/stage5/STAGE5_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage5/inputs/upstream_stage2_clean/`
- `invest/stages/stage5/inputs/upstream_stage1_master/`

## 출력 (Outputs)
- `invest/stages/stage5/outputs/features/`
- `invest/stages/stage5/outputs/reports/`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage5/scripts/stage05_feature_engineer.py
```

## 검증 (Validation)
- `invest/stages/stage5/outputs/reports/STAGE5_FEATURE_RUN_*.json`
- PASS 기준: `errors == 0`

## 실패 정책
- 비정상 종료 또는 `errors > 0`이면 stage5 FAIL
- Stage3~6 중복연산 방지 정책과 상충되는 동일축 중복 증폭 피처는 운영 반영 금지

