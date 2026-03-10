# JB-20260309-STAGE3-LOCAL-APPLY — output hygiene check (2026-03-09 KST)

## 목적
Stage3 시작 전 output 선정/정리 필요성 점검.

## 확인 결과
### 1) 핵심 산출물 overwrite 여부
- `invest/stages/stage3/scripts/stage03_build_input_jsonl.py`
  - `inputs/stage2_text_meta_records.jsonl` → `open(..., "w")`
  - `outputs/STAGE3_INPUT_BUILD_latest.json` → `write_text(...)`
- `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py`
  - `outputs/features/stage3_qualitative_axes_features.csv` → `to_csv(...)`
  - `outputs/features/stage3_claim_cards.jsonl` → `open(..., "w")`
  - `outputs/signal/dart_event_signal.csv` → `to_csv(...)`
  - `outputs/signal/stage3_macro_forecast.csv` → `to_csv(...)`
  - `outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json` → `write_text(...)`
- 결론: canonical main outputs는 append가 아니라 overwrite.

### 2) stale manifest/log/보조산출물 혼선 위험
- legacy file 존재:
  - `invest/stages/stage3/outputs/features/attention_sentiment_features.csv` (mtime 2026-03-05 16:40:41 KST)
- legacy manifest 다수 존재:
  - `invest/stages/stage3/outputs/manifest_stage3_attention_*.json` 9개
  - 해당 manifest는 위 legacy csv를 output으로 가리킴.
- current docs/canonical contract는 attention/sentiment 축을 제외하고 `stage3_qualitative_axes_features.csv`를 표준으로 정의.
- live canonical output 불일치:
  - `invest/stages/stage3/outputs/signal/stage3_macro_forecast.csv` 현재 없음
  - `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`은 현재 live본 기준 `macro_forecast_csv`, `macro_forecast_rows`, `apply_macro_to_stock_axes` 필드가 없음
  - 반면 proof run 산출물 `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_stage3_summary.json`에는 위 필드와 `stage3_macro_forecast.csv`가 존재
- logs 상태:
  - `invest/stages/stage3/outputs/logs/runtime/` 아래 stale log file 없음
- 결론:
  - append/덮어쓰기 리스크는 낮음
  - 그러나 directory listing만 보고 산출물 선택하면 legacy attention 계열 + missing live macro output 때문에 혼선 위험이 높음

### 3) 삭제 필요성/범위 판정
- 삭제 후보(모두 generated output):
  1. `invest/stages/stage3/outputs/features/attention_sentiment_features.csv`
  2. `invest/stages/stage3/outputs/manifest_stage3_attention_*.json` 9개
- 삭제 비권장(현재 유지):
  - `manifest_stage3_input_build_*.json`, `manifest_stage3_qual_axes_*.json` : run history/evidence 성격
  - `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_*` : 현재 검증 증빙
- 선행 권고:
  1. live Stage3 canonical rerun 또는 proof 결과 승격으로 `outputs/signal/stage3_macro_forecast.csv`와 summary contract를 복구
  2. 그 다음 legacy attention 계열만 정리

## 최종 판정
- Stage3 시작 전에 전체 output 청소가 필수는 아님 (canonical outputs는 overwrite).
- 다만 `attention_sentiment_features.csv` + `manifest_stage3_attention_*.json`은 stale generated output으로 혼선 유발 가능성이 높아 targeted cleanup 후보.
- live canonical output에서 `stage3_macro_forecast.csv`가 비어 있는 점이 현재 가장 큰 운영 리스크.
