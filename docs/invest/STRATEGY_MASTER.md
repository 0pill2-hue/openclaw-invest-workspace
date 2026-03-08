# STRATEGY_MASTER

역할: **공통 SSOT**.

투자 파이프라인의 공통 전략 원칙과 단계 흐름만 정의하는 상위 SSOT다.
세부 실행 규칙, 재현 절차, 파일 링크는 각 stage 문서에서만 관리한다.

Stage 상세 설계/재현/파일 링크 canonical:
- `docs/invest/stage1/` ~ `docs/invest/stage12/`
- stage 진입 인덱스: `docs/invest/STAGE_EXECUTION_SPEC.md`

## 공통 운영 원칙
- 단계는 순차 파이프라인으로 운영하며 upstream 실패 시 downstream 진입을 금지한다.
- 각 stage는 자신의 입력을 받아 검증된 출력만 다음 단계로 넘긴다.
- 결과 등급은 DRAFT, VALIDATED, PRODUCTION으로 관리하며 공식 채택은 승인 게이트를 거친다.
- 운영 판단은 산출물, 검증 로그, 증빙이 함께 있을 때만 승격할 수 있다.
- 후보군 검토 우선순위는 산업 리더십, 구조적 경쟁우위, 지속가능한 사업 우위를 우선 보되, 별도 독립 점수축으로 승격하지 않는다.

## 파이프라인 개요
1. Stage1: 외부 원천 데이터를 수집하고 raw/master/runtime 기준선을 만든다.
2. Stage2: 수집 데이터를 정제하고 quarantine 분리를 통해 downstream 입력 품질을 고정한다.
3. Stage3: 비정형/정성 입력을 4축 정성신호로 압축해 Stage4 결합 입력을 만든다.
4. Stage4: 상위 입력을 결합해 value/composite 후보 산출물을 만든다.
5. Stage5: 검증 가능한 feature set을 산출해 선발/평가 단계 입력을 준비한다.
6. Stage6: 실제 선택·교체·비중조절·분기 리뷰 규칙을 적용해 운영 판단 결과를 만든다.
7. Stage7: 튜닝 입력 인터페이스를 생성하는 활성 단계다.
8. Stage8~Stage12: RESERVED/HISTORICAL/GOVERNANCE 슬롯이며 README 상태를 우선 확인한다.
