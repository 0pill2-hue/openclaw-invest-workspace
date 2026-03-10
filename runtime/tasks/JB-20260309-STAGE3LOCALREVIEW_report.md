# JB-20260309-STAGE3LOCALREVIEW

- verdict: DONE

## changed_files
- invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py
- docs/invest/stage3/README.md
- docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md
- docs/invest/stage3/STAGE3_DESIGN.md
- memory/2026-03-09.md

## validation
- `python3 -m py_compile invest/stages/stage3/scripts/stage03_build_input_jsonl.py invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py` → PASS
- `python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py` → PASS
- `python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --bootstrap-empty-ok` → PASS
- outputs:
  - `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
  - `invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl`
  - `invest/stages/stage3/outputs/signal/dart_event_signal.csv`
  - `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`

## remaining_issues
- legacy manifest들(과거 생성본)에는 Stage1 입력 경로가 남아 있음. 현재 실행으로 생성된 최신 manifest는 Stage2 clean 경로를 사용하지만, repo hygiene 관점에서 legacy 정리 정책이 필요함.
- `stage03_build_input_jsonl.py`는 여전히 `include_nosymbol=True` 기본값으로 `__NOSYMBOL__` row를 생성함. 현재 Stage3 scoring에서는 제외되므로 기능 문제는 없지만, 입력 파일 크기/운영명확성 관점에서 추후 분리 가능.
