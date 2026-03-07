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

## Git 운영 규칙
- 검증 후 커밋/푸시 우선
- Push 타이밍 SSOT: `docs/operations/CONTRIBUTING.md`

## 모델 운용 원칙
- 1번 뇌(GPT-5.4): 기본 실행/판단/검증/최종 결정
- 2번 뇌(로컬뇌): 폴백/요약/크롤링/배치/반복
