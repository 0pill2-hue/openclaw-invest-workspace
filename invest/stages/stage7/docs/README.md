# Stage7 Docs

## Canonical 문서
- `invest/stages/stage7/docs/STAGE7_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage7/inputs/upstream_stage4_outputs/`

## 출력 (Outputs)
- `invest/stages/stage7/inputs/stage7_tuning_input_from_stage4_latest.json`
- `invest/stages/stage7/outputs/results/stage7_interface_build_latest.json`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage7/scripts/build_stage7_tuning_input_interface.py
```

## 검증 (Validation)
- 결과 JSON에 `source.stage4_*` 경로 존재 여부
- `stage7_input_contract.required_columns` 4개 포함 여부

## 실패 정책
- upstream(Stage4) 미탐지 시 `source.* = 미확인`으로 기록
- Stage7 자동 튜닝 실행은 정책상 금지(명시 지시 시만)

## 운영 보조 자산
- `invest/stages/stage7/docs/stage_updates/template/ui/index.html` (Stage6 UI 템플릿 소스)
