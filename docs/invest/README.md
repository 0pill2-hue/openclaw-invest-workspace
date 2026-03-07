# invest/docs

투자 공통 정책·거버넌스 문서의 인덱스입니다.

이 디렉터리에는 공통 SSOT만 유지합니다. Stage별 상세 구현·재현 절차는 stage docs에서 관리합니다.

## Canonical SSOT

- [`STRATEGY_MASTER.md`](./STRATEGY_MASTER.md): 운영 기준 Stage 순서와 공통 전략 원칙의 SSOT
- [`RULEBOOK_MASTER.md`](./RULEBOOK_MASTER.md): 전 단계 공통 하드 룰과 금지사항의 SSOT
- [`KPI_MASTER.md`](./KPI_MASTER.md): Stage별 수치 게이트와 KPI 기준의 SSOT
- [`RESULT_GOVERNANCE.md`](./RESULT_GOVERNANCE.md): 결과 등급, 승격, 차단, 증빙 거버넌스의 SSOT
- [`OPERATIONS_SOP.md`](./OPERATIONS_SOP.md): 운영 절차, 실패 정책, 보고 규칙의 SSOT
- [`INVEST_STRUCTURE_POLICY.md`](./INVEST_STRUCTURE_POLICY.md): 경로, 산출물 위치, 구조 정책의 SSOT
- [`ALGORITHM_SPEC.md`](./ALGORITHM_SPEC.md): 공통 알고리즘 스펙 템플릿 및 확정 항목의 SSOT
- [`TUNING_GUIDE.md`](./TUNING_GUIDE.md): 튜닝 범위와 실험 포맷 가이드
- [`BOOTSTRAP_REPRODUCTION.md`](./BOOTSTRAP_REPRODUCTION.md): Stage1~6 최소 재현 부트스트랩

## Stage details live here

- [`STAGE_RULEBOOK_MASTER.md`](./STAGE_RULEBOOK_MASTER.md): stage별 룰북 링크 인덱스
- [`STAGE_STRATEGY_MASTER.md`](./STAGE_STRATEGY_MASTER.md): stage별 전략/재현 문서 링크 인덱스
- [`STAGE_EXECUTION_SPEC.md`](./STAGE_EXECUTION_SPEC.md): stage별 실행/재현 문서 링크 인덱스

## Precedence / conflict rules

1. 공통 문서 간 충돌 시 기본 우선순위는 `RULEBOOK_MASTER.md` > `KPI_MASTER.md` > `STRATEGY_MASTER.md` > 기타 보조 문서입니다.
2. 공통 하드 룰과 stage 문서가 충돌하면 공통 하드 룰을 우선합니다.
3. Stage별 상세 구현·재현 절차는 stage 문서가 담당하되, 공통 정책·거버넌스 의미는 이 디렉터리의 공통 문서를 따릅니다.
4. Stage 상세 문서는 stage 경로에서 관리하며, 이 디렉터리에는 상세 룰을 중복 기술하지 않습니다.

## Quick links

- [`STRATEGY_MASTER.md`](./STRATEGY_MASTER.md)
- [`RULEBOOK_MASTER.md`](./RULEBOOK_MASTER.md)
- [`KPI_MASTER.md`](./KPI_MASTER.md)
- [`RESULT_GOVERNANCE.md`](./RESULT_GOVERNANCE.md)
- [`OPERATIONS_SOP.md`](./OPERATIONS_SOP.md)
