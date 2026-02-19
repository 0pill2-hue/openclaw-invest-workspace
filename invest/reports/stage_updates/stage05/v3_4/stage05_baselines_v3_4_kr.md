# stage05_baselines_v3_4_kr

## inputs
- invest/data/raw/kr/ohlcv/*.csv
- invest/data/raw/kr/supply/*_supply.csv

## run_command(or process)
- `python3 invest/scripts/run_stage05_09_v3_4_kr.py`

## outputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_v3_4_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage05/stage05_baselines_v3_4_kr.md

## quality_gates
- KRX ONLY hard guard PASS
- 보유 1~6 적용
- 수치=JSON 일치

## failure_policy
- US 경로/티커 감지 시 즉시 FAIL 종료

## proof
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_v3_4_kr.json

## baseline summary
- numeric: total=488.97%, multiple=5.89x, mdd=-40.93%
- qualitative: total=416.07%, multiple=5.16x, mdd=-19.52%
- hybrid: total=99.96%, multiple=2.00x, mdd=-17.10%
- external_proxy: total=4558.75%, multiple=46.59x, mdd=-8.77%
