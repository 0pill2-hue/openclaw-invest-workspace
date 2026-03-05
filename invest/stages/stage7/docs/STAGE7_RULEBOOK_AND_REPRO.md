# Stage7 Rulebook & Repro

## 범위
- 역할: Stage4 산출을 Stage7 튜닝 입력 인터페이스 JSON으로 고정
- 원칙: Stage7는 `stage7/inputs/upstream_stage4_outputs` 경유 입력만 사용

## 입력 (Inputs)
- `invest/stages/stage7/inputs/upstream_stage4_outputs/value/`
- `invest/stages/stage7/inputs/upstream_stage4_outputs/reports/STAGE4_VALUE_RUN_*.json`
- `invest/stages/stage7/inputs/upstream_stage4_outputs/manifest_stage4_value_*.json`

## 출력 (Outputs)
- `invest/stages/stage7/inputs/stage7_tuning_input_from_stage4_YYYYMMDD_HHMMSS.json`
- `invest/stages/stage7/inputs/stage7_tuning_input_from_stage4_latest.json`
- `invest/stages/stage7/outputs/results/stage7_interface_build_YYYYMMDD_HHMMSS.json`
- `invest/stages/stage7/outputs/results/stage7_interface_build_latest.json`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage7/scripts/build_stage7_tuning_input_interface.py
```

## 검증 (Validation)
- 결과 JSON에 다음 필드 존재:
  - `source.stage4_value_root`
  - `source.stage4_report`
  - `source.stage4_manifest`
  - `stage7_input_contract.required_columns`
- PASS 기준: 필수 필드 누락 없음

## 실패 정책
- Stage4 입력 미확인 시 `미확인`으로 기록하고 fail-close 유지
- Stage7 자동 튜닝 파이프라인은 미연결(False) 상태 유지
