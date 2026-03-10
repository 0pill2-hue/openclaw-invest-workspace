# JB-20260309-STAGE3-LOCAL-APPLY
- run_id: `20260309141045`
- verdict: **PASS**

## 1) What was validated
- 기존 builder 산출물 `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d.jsonl`를 기준으로, `published_at`의 **Asia/Seoul 날짜** 기준 **엄격 31일(inclusive)** 필터를 다시 적용했습니다.
- 그 strict 입력으로 `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py`를 실제 실행했습니다.
- 산출물/요약/체인 라우팅을 함께 점검했습니다.

## 2) Strict 31-day filter proof
- input: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d.jsonl`
- strict input: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d_strict.jsonl`
- strict summary: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d_strict_summary.json`

핵심 수치:
- latest published_at (KST): `2026-03-08T21:05:13+09:00`
- cutoff date (inclusive): `2026-02-06`
- input rows: `44,454`
- strict rows: `44,449`
- dropped outside window: `5`
- strict min/max date: `2026-02-06` ~ `2026-03-08`
- strict distinct dates: `31`

판정:
- builder lookback 결과에 **윈도우 밖 5건이 실제로 섞여 있었음**.
- 따라서 이번 strict 재필터링은 **실검증에 필요했고**, 필터 후 31일 범위가 정확히 맞았습니다.

## 3) Stage3 actual run proof
- features csv: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_qualitative_axes_features.csv`
- claim cards jsonl: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_claim_cards.jsonl`
- dart signal csv: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_dart_signal.csv`
- macro forecast csv: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_macro_forecast.csv`
- summary json: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_summary.json`

핵심 수치:
- records_loaded: `44,449`
- claim_cards_generated: `321,376`
- feature rows: `6,128`
- feature dates: `2026-02-06` ~ `2026-03-08` (`31` dates)
- feature distinct symbols: `2,007`
- dart signal rows: `870` (`2026-03-03` ~ `2026-03-05`)
- macro forecast rows: `4` (`2026-02-27` ~ `2026-03-06`)

Sanity checks:
- 모든 주요 산출물 **비어있지 않음**
- summary row count와 실제 파일 row count **일치**
- `brain_backend = keyword_local` 확인
- feature의 `brain_backend` 값 = `keyword_local`만 존재
- feature의 `macro_to_stock_axes_applied` 값 = `on`만 존재
- summary의 `apply_macro_to_stock_axes = true` 확인
- feature 내 `(symbol, date)` duplicate = `0`
- 출력 심볼 수가 strict input보다 2개 적어 보이지만, 빠진 것은 실제 종목이 아니라 pseudo-symbol `__MACRO__`, `__NOSYMBOL__` 뿐이라 **이상 아님**
- obvious fail-close / empty-output / count mismatch 징후 없음

## 4) Is Stage3 already routed to local in stage1234 chain?
**예. 이미 local Stage3로 라우팅되어 있습니다. 추가 변경은 필요 없습니다.**

근거:
- 파일: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 체인은 이미 아래 스크립트를 직접 호출합니다:
  - `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py`
- output csv도 이미 아래 경로로 맞춰져 있습니다:
  - `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
- macro forecast도 이미 체인에서 명시 출력합니다:
  - `invest/stages/stage3/outputs/signal/stage3_macro_forecast.csv`

보충:
- 체인에서 `--apply-macro-to-stock-axes`를 명시적으로 넘기지는 않지만, 스크립트 기본값이 `on`이고 실제 검증 run에서도 `true/on`으로 적용됨을 확인했습니다.
- 따라서 **“Stage3를 local에 handoff” 하는 목적만 놓고 보면 추가 라우팅 수정은 불필요**합니다.

## 5) Safety decision
**PASS**

이유:
1. strict 31일 실데이터 run이 정상 완료됨
2. 새 산출물 `stage3_macro_forecast.csv`가 실제로 비어있지 않게 생성됨
3. `apply_macro_to_stock_axes`가 실제 feature/summary에 반영됨
4. local-only backend(`keyword_local`)로 동작했고, obvious failure가 없음
5. stage1234 chain이 이미 local Stage3 스크립트를 사용 중이며, output path도 이번 변경 의도와 일치함

## 6) Recommended git paths / exact commit suggestion
추천 tracked git paths:
- `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py`
- `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`

Exact suggestion:
```bash
git add invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh && git commit -m "stage3: emit macro forecast and align local chain outputs"
```

## 7) Bottom line
- verdict: **PASS**
- Stage3 already local in chain: **YES**
- extra change needed to “hand Stage3 to local”: **NO**
