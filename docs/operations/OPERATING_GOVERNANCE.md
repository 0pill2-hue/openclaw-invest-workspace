# OPERATING GOVERNANCE

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

게이트 운영의 고정 기준(실행 SOP, 보고 SLA, Git 규칙)을 관리한다.

투자 전략 canonical: `docs/invest/STRATEGY_MASTER.md`

## 실행 SOP
1. stage 실행
2. stage gate check
3. PASS면 다음 stage 진행
4. FAIL이면 gate_fail_protocol 복귀
5. 재실행 후 동일 gate 재검증

## Task 운영 규칙
- 남은 backlog가 있으면 추가 지시를 기다리지 말고 우선순위대로 자동 진행한다. 단, 승인 필요 작업/실제 blocker는 예외다.
- 태스크 착수 시에는 사용자에게 1줄 시작 보고를 먼저 한다.
- 외부 검토(web-review 등) 답변은 자동 실행 트리거가 아니다. 메인이 먼저 검토하고, 실제 개선 필요 판정일 때만 task/directive/proof 절차로 후속 작업을 연다.

## Git 운영 규칙
- 검증 후 커밋/푸시 우선
- Push 타이밍 SSOT: `docs/operations/CONTRIBUTING.md`

## 모델 운용 원칙
- 1번 뇌(GPT-5.4): 기본 실행/판단/검증/최종 결정
- 2번 뇌(로컬뇌): 폴백/요약/크롤링/배치/반복

## 서브에이전트 완료 처리
- 장시간 서브에이전트는 poll 대기 대신 완료 직전 `openclaw system event --mode now`로 메인을 호출한다.
- 메인은 완료 이벤트 수신 턴에서 proof 반영과 task 상태 전이까지 즉시 마무리한다.
