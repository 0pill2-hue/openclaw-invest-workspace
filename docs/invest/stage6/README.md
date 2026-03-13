# Stage6 Docs

## Canonical 문서
- `docs/invest/stage6/STAGE6_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage6/STAGE6_KPI_RUNTIME_SPEC.md` (KPI 현재값/UI/버전별 구현 상세)

## 입력 (Inputs)
- `invest/stages/stage6/inputs/upstream_stage1/`
- `invest/stages/stage6/inputs/upstream_stage2_clean/`
- `invest/stages/stage6/inputs/config/`
- `invest/stages/stage6/inputs/reference_cache/`
- `invest/stages/stage6/inputs/execution_ledger/`

## 출력 (Outputs)
- `invest/stages/stage6/outputs/results/`
- `invest/stages/stage6/outputs/reports/`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py
```

## 검증 (Validation)
- `invest/stages/stage6/scripts/stage06_validate_v4_6.py` 실행 결과
- `invest/stages/stage6/outputs/reports/stage06_real_execution_parity_latest.json`
- duplication guard(중복연산 방지 4규칙) 메타/임계치/cap 검증 포함

## 실패 정책
- validation/parity FAIL 시 결과는 운영 불가(DRAFT 유지)
