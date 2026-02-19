# stage05_cross_review_v3_4_kr

## inputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_v3_4_kr.json

## run_command(or process)
- `python3 invest/scripts/run_stage05_09_v3_4_kr.py`

## outputs
- /Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage05/stage05_cross_review_v3_4_kr.md

## quality_gates
- Opus/Sonnet/AgPro 역할 분리
- 교차검증 기록

## failure_policy
- 중대한 누수/정합성 이슈 시 FAIL

## proof
- /Users/jobiseu/.openclaw/workspace/reports/stage_updates/stage05/stage05_cross_review_v3_4_kr.md

## review
- Opus(논리 타당성): PASS - Rulebook 제약(보유 1~6, KRX 전용)과 리밸런싱 논리 일관.
- Sonnet(데이터/누수/정합성): PASS - 입력 경로가 raw/kr로 제한, 미래 데이터 참조 없음.
- AgPro(리스크/실행성): PASS - 거래비용 반영(0.3%), 월말 리밸런싱으로 실행 가능성 확보.
