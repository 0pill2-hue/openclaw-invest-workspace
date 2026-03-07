# INVEST README

## 역할
- 투자 파이프라인의 공통 SSOT와 stage 진입 인덱스를 제공한다.
- stage별 운영 상세는 상위 문서가 아니라 stage RULEBOOK을 본다.

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
- canonical index: `STAGE_EXECUTION_SPEC.md`

## Stage 상세 문서 정책
- stage 운영 상세의 canonical 위치는 `invest/stages/stageN/docs/STAGE{N}_RULEBOOK_AND_REPRO.md`다.
- 상위 문서는 공통 정책/링크 허브만 담당한다.
- Stage1은 이 정책을 적용했다.

## 우선순위
1. `RULEBOOK_MASTER.md`
2. `KPI_MASTER.md`
3. `STRATEGY_MASTER.md`
4. `RESULT_GOVERNANCE.md`
5. `OPERATIONS_SOP.md`
