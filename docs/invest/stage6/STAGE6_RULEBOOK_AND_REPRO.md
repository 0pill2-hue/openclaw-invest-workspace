# Stage6 Rulebook & Repro

## 범위
- 역할: Stage6 모델 재계산/검증 및 리포트 산출
- 원칙: Stage6 입력은 `upstream_stage1`, `upstream_stage2_clean`, `reference_cache`, `execution_ledger`, `config`로 고정
- 결합 가드: winner score 결합 시 중복연산 방지 4규칙(축대표1/축내합성1/|rho|>0.7 제거/축기여 cap 25%) 적용

## 입력 (Inputs)
- `invest/stages/stage6/inputs/upstream_stage1/master/kr_stock_list.csv`
- `invest/stages/stage6/inputs/upstream_stage1/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage6/inputs/upstream_stage2_clean/kr/ohlcv/*.csv`
- `invest/stages/stage6/inputs/reference_cache/highlander_sector_map_cache.csv`
- `invest/stages/stage6/inputs/execution_ledger/{model_trade_orders.csv,broker_execution_ledger.csv}`

## 출력 (Outputs)
- `invest/stages/stage6/outputs/results/validated/stage06_baselines_v4_6_kr.json`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/summary.json`
- `invest/stages/stage6/outputs/reports/stage06_real_execution_parity_latest.json`
- `invest/stages/stage6/outputs/reports/stage06_real_execution_mismatches_latest.csv`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py
```

## 검증 (Validation)
- `python3 invest/stages/stage6/scripts/stage06_validate_v4_6.py`
- PASS 기준:
  - validation verdict = PASS
  - parity gate = PASS
  - duplication guard 메타 존재 + `axis_cap<=0.25` + `corr_threshold=0.7` + post-corr 위험 비증가

## 실패 정책
- 검증 실패 또는 parity FAIL이면 fail-close
- 결과 라벨은 `DRAFT` 유지, downstream 운영 반영 금지
