# RESULT_GOVERNANCE

역할: 결과 등급/승격/저장 경로 정책의 단일 SSOT.

## Grade Model
- `DRAFT`: 탐색/실험 결과. 공식 보고/채택 불가.
- `VALIDATED`: 데이터·규칙·검증 기준 통과.
- `PRODUCTION`: 공식 보고/채택 승인 완료.

## Mandatory Rules
1. 등급 미표기 결과는 `DRAFT`로 간주한다.
2. `DRAFT` 산출물은 `TEST ONLY` 표기를 포함한다.
3. 결과 이력은 등급별 물리 경로를 반드시 분리한다.
4. 공식 보고/채택은 `PRODUCTION`만 허용한다.

## Canonical Result Paths (Stage6)
- `invest/stages/stage6/outputs/results/test_history/`
- `invest/stages/stage6/outputs/results/validated_history/`
- `invest/stages/stage6/outputs/results/prod_history/`

경로 drift 금지:
- `validated_history`를 생략하거나 `test/prod` 2분할로 축약하지 않는다.
- 신규 writer/배치/리포트는 위 3개 canonical 경로만 사용한다.

## Promotion Minimum Checks
### `DRAFT -> VALIDATED`
- 데이터 기간 3년 이상
- 비용/슬리피지 반영 명시
- OOS split 30% 이상
- rule spec 문서화

### `VALIDATED -> PRODUCTION`
- walk-forward 또는 paper verification 완료
- reviewer 승인 기록
