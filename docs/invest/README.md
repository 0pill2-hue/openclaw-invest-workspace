# INVEST README

역할: **투자 공통 SSOT와 stage 진입 문서 인덱스**.

## 공통 SSOT
- `STRATEGY_MASTER.md` — 공통 전략 원칙과 단계 흐름 SSOT
- `RULEBOOK_MASTER.md` — 공통 하드 룰/금지사항 SSOT
- `KPI_MASTER.md` — stage별 수치 게이트와 KPI 기준 SSOT
- `RESULT_GOVERNANCE.md` — 결과 등급/승격/차단/증빙 기준 SSOT
- `OPERATIONS_SOP.md` — 실행 절차/실패 정책/보고 기준 SSOT
- `INVEST_STRUCTURE_POLICY.md` — 구조/경로/산출물 위치 기준 SSOT

## 공통 보조 문서
- `ALGORITHM_SPEC.md`
- `TUNING_GUIDE.md`
- `BOOTSTRAP_REPRODUCTION.md`

## Stage 진입 인덱스
- canonical: `STAGE_EXECUTION_SPEC.md`

선택 이유:
- `STAGE_EXECUTION_SPEC.md`, `STAGE_EXECUTION_SPEC.md`, `STAGE_EXECUTION_SPEC.md` 세 문서는 실제 내용이 모두 stage 상세 문서 링크 인덱스로 사실상 동일했다.
- 그중 `STAGE_EXECUTION_SPEC.md`가 가장 중립적이고, stage 상세 문서가 실행/재현/룰을 함께 담는 현재 구조와 가장 잘 맞는다.
- 따라서 `STAGE_EXECUTION_SPEC.md`만 남기고 나머지 두 문서는 삭제한다.

## 우선순위
1. `RULEBOOK_MASTER.md`
2. `KPI_MASTER.md`
3. `STRATEGY_MASTER.md`
4. `RESULT_GOVERNANCE.md`
5. `OPERATIONS_SOP.md`
