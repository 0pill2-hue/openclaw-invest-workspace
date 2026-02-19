# MODEL_FAILOVER_POLICY.md

Last updated: 2026-02-19 20:03 KST

## 목적
Opus 계열 레이트리밋/일시 오류 발생 시 작업 중단 없이 자동 대체한다.

## 자동 교체 규칙 (양방향)
1. 기본 대상 모델이 `opus45`(Claude Opus 4.5)일 때
   - 레이트리밋(429) 또는 provider transient error 발생 시 즉시 `opus`(Claude Opus 4.1)로 재시도
2. 기본 대상 모델이 `opus`(Claude Opus 4.1)일 때
   - 동일 조건 발생 시 즉시 `opus45`(Claude Opus 4.5)로 재시도
3. 재시도는 최대 1회 교차 전환까지 허용
4. 교차 전환도 실패하면
   - `sonnet`(Claude Sonnet 4.6)으로 최종 1회 대체 실행
5. 보고 원칙
   - 시작/종료 보고만 유지
   - 실패 원인은 한 줄로만 명시 (`rate_limit`, `provider_transient`)

## 적용 범위
- subagent 실행
- 중요 검증(교차검토) 작업
- 장시간 배치 작업

## 고정 모델 매핑
- opus45 = anthropic/claude-opus-4-5
- opus = anthropic/claude-opus-4-1
- sonnet = anthropic/claude-sonnet-4-6

## 운영 체크
- model failover 발생 시 결과 리포트에 `model_failover` 필드 기록
- 예: `model_failover: opus45->opus (reason=rate_limit)`
