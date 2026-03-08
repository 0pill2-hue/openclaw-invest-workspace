# Stage6 Rulebook & Repro

## 범위
- 역할: Stage6 모델 재계산/검증, 실제 선발/교체 판단, 운영 리포트 산출
- 원칙: Stage6 입력은 `upstream_stage1`, `upstream_stage2_clean`, `reference_cache`, `execution_ledger`, `config`로 고정
- 결합 가드: winner score 결합 시 중복연산 방지 4규칙(축대표1/축내합성1/|rho|>0.7 제거/축기여 cap 25%) 적용
- 역할 경계: Stage6는 실제 선택·교체·비중조절·리뷰 규칙을 담당하며, 새 정성축 추가는 Stage3 범위에서만 다룬다.

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

## 운영 규칙 핵심
- 신규 편입은 작은 초기 비중으로 시작한다.
- 추가 증액은 확인된 강세와 상대 우위 유지가 검증된 종목에 한해 허용한다.
- 손실 종목에 대한 자동 추매/물타기는 기본 금지다.
- 교체는 단순 가격 흔들림이 아니라 기존 thesis 훼손, 점수 붕괴, 더 우수한 대체 후보의 검증된 우위 출현이 확인될 때만 수행한다.
- 가격목표 기반 기계적 매도보다 thesis 훼손, 점수 붕괴, 대체 후보 우위 출현을 우선한다.
- 쿨다운과 turnover 관리는 불필요한 churn 억제를 우선 원칙으로 두며 단기 변동만으로 잦은 교체를 허용하지 않는다.
- 포트폴리오 상태, thesis, 상대 우위, 교체 필요성은 분기 단위 정기 리뷰를 기본으로 점검한다.

## 검증 (Validation)
- `python3 invest/stages/stage6/scripts/stage06_validate_v4_6.py`
- PASS 기준:
  - validation verdict = PASS
  - parity gate = PASS
  - duplication guard 메타 존재 + `axis_cap<=0.25` + `corr_threshold=0.7` + post-corr 위험 비증가

## 실패 정책
- 검증 실패 또는 parity FAIL이면 fail-close
- 결과 라벨은 `DRAFT` 유지, downstream 운영 반영 금지
