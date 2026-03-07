# STRATEGY_MASTER

투자 파이프라인의 공통 전략 원칙과 단계 흐름만 정의하는 상위 SSOT다.
세부 실행 규칙, 재현 절차, 파일 링크는 각 stage 문서에서만 관리한다.

Stage 상세 설계/재현/파일 링크는 invest/stages/stageN/docs/*에서만 관리한다(SSOT).

## 공통 운영 원칙
- 단계는 순차 파이프라인으로 운영하며 upstream 실패 시 downstream 진입을 금지한다.
- 각 stage는 자신의 입력을 받아 검증된 출력만 다음 단계로 넘긴다.
- 결과 등급은 DRAFT, VALIDATED, PRODUCTION으로 관리하며 공식 채택은 승인 게이트를 거친다.
- 운영 판단은 산출물, 검증 로그, 증빙이 함께 있을 때만 승격할 수 있다.

## 파이프라인 개요
1. Stage1: 외부 원천 데이터를 수집하고 raw/master/runtime 기준선을 만든다.
2. Stage2: 수집 데이터를 정제하고 quarantine 분리를 통해 downstream 입력 품질을 고정한다.
3. Stage3: 비정형/정성 입력을 attention gate로 압축해 구조화 피처 입력을 만든다.
4. Stage4: 상위 입력을 결합해 가치 계산과 핵심 검증 산출물을 만든다.
5. Stage5: 검증 가능한 feature set을 산출해 선발/평가 단계 입력을 준비한다.
6. Stage6: 베이스라인 비교와 후보 선발을 수행해 운영 판단 직전 결과를 만든다.
7. Stage7~Stage12: 확장/심화 운영 슬롯으로 예약되어 있으며 현재는 RESERVED 상태다.
