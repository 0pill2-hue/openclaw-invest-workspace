# TUNING_GUIDE

> canonical: 튜닝(How much) 전용  
> location: `invest/docs/`  
> scope: 가중치/임계값/필터 조정

## 1) 튜닝 원칙

- 하드룰은 고정, 튜닝만 변경
- 한 번에 1~2개 파라미터만 조정
- 모든 조정은 전/후 diff와 근거를 남김

## 2) 튜닝 대상

- 매력도 가중치 (상승여력/훼손위험/과열도)
- 매력도 스무딩 계수 (`alpha`: 예 0.2~0.4)
- 교체/비중조절 판단 임계값 (누적 매력도 기준)
- 섹터강도 반영 비율
- 후보 필터 문턱값

## 3) 금지 사항

- Strategy 변경을 튜닝으로 위장 금지
- Rulebook 하드룰 무단 변경 금지
- 근거 없는 동시 다중 튜닝 금지

## 4) 실험 포맷 (필수)

- inputs
- changed_params
- run_command
- outputs
- quality_gates
- failure_policy
- proof

## 5) 채택 기준

- 행동 로그가 전략 철학과 합치
- 과매매 지표 악화 없음
- 수익/리스크 중 최소 1개 개선 + 나머지 비악화

## 6) 롤백 기준

- 하드룰 위반
- 행동-전략 불일치 확대
- 가중치 변경으로 winner만 바뀌고 실행 행동은 개선 없음
