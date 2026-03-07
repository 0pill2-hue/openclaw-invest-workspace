# OPERATIONS_SOP

## 목적
- 투자 파이프라인 공통 실행 절차와 fail-close 기준을 정의한다.
- stage 상세 실행 규칙은 각 stage RULEBOOK이 담당한다.

## 재현 핵심 문서
- 부트스트랩: `docs/invest/BOOTSTRAP_REPRODUCTION.md`
- Stage 실행 인덱스: `docs/invest/STAGE_EXECUTION_SPEC.md`
- 구조 기준: `docs/invest/INVEST_STRUCTURE_POLICY.md`
- Stage1 상세: `invest/stages/stage1/docs/STAGE1_RULEBOOK_AND_REPRO.md`

## Pipeline Order (E2E, canonical)
1. Stage1 데이터 수집
2. Stage2 데이터 정제
3. Stage3 로컬뇌 정성 게이트
4. Stage4 정제 검증
5. Stage5 VALIDATED 피처 산출
6. Stage6 베이스라인 비교/선발

## Hard Gates
- 상위 단계 FAIL 시 하위 단계 실행 금지
- Stage1에서 raw 수집 실패가 있으면 non-zero exit와 상태 파일을 함께 남긴다.
- stage 상세 fail-close 기준은 각 RULEBOOK을 따른다.

## Result Governance
- 기본 등급: `DRAFT | VALIDATED | PRODUCTION`
- 공식/채택 가능 보고는 PRODUCTION만 허용

## Reporting Rules
- 실행 중심 문장 사용
- 완료 보고에는 proof 경로 포함
- cadence/SLA canonical은 `docs/operations/OPERATING_GOVERNANCE.md`
