# STRATEGY_MASTER

> canonical: 투자 알고리즘 전략/개발단계 단일 기준  
> location: `invest/docs/`  
> status: ACTIVE

## L0) 요약

- 운영 기준 단계는 **Stage1~Stage6**이다.
- 단계 우회는 금지하며 이전 단계 FAIL 시 다음 단계 진입 금지다.
- 공식 판정 구간은 2021~현재, 2016~2020은 참고 전용이다.
- 세부 실행 규칙은 `RULEBOOK_MASTER.md`, 단계별 규칙은 stage별 RULEBOOK 문서를 따른다.
- 공통 알고리즘 스펙 참조는 [`ALGORITHM_SPEC.md`](./ALGORITHM_SPEC.md)를 따른다.

## L1) 실행 최소 절차

1. 단계 정의 확인: 본 문서의 canonical 순서 사용
2. 하드룰 확인: `RULEBOOK_MASTER.md`
3. 단계별 의도/실행룰 확인: `STAGE_STRATEGY_MASTER.md`, `STAGE_RULEBOOK_MASTER.md`
4. 충돌 시 우선순위: `STRATEGY_MASTER` > 보조 문서

## 운영 canonical 순서

1. Stage1 데이터 수집
2. Stage2 데이터 정제
3. Stage3 로컬뇌 정성 게이트
4. Stage4 정제 검증/값 계산
5. Stage5 VALIDATED 피처 산출
6. Stage6 베이스라인 비교/선발

## 7~12 확장 단계(재번호 반영)

- Stage7: 튜닝 입력 인터페이스/튜닝 준비
- Stage8: 컷오프
- Stage9: 가치평가
- Stage10: 교차검토
- Stage11: 최종 승인 준비
- Stage12: 채택/보류/승격

## 운영 원칙

- 단계 우회 금지: 이전 단계 FAIL이면 다음 단계 진입 금지
- 증거 기반 승격: 산출물 + 검증 로그 + 실패정책(proof) 필수
- Stage6는 운영 룰 확정/검증 중심 단계
- 결과 등급은 `DRAFT | VALIDATED | PRODUCTION`을 따른다
