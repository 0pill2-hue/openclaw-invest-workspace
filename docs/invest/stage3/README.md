# Stage3 Qualitative Axes Docs

## Canonical 문서
- `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage3/inputs/upstream_stage1/`
  - qualitative: `raw/qualitative/{kr/dart,market/rss}`
  - signal: `raw/signal/market/macro/macro_summary.json`
- `invest/stages/stage3/inputs/upstream_stage2_clean/`
  - qualitative text: `qualitative/text/{blog,telegram,premium,image_map,images_ocr}`
  - 구(flat) 경로 `text/*` fallback 지원
- `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`

## 출력 (Outputs)
- `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
- `invest/stages/stage3/outputs/signal/dart_event_signal.csv`
- `invest/stages/stage3/outputs/STAGE3_INPUT_BUILD_latest.json`
- `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py
python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py --bootstrap-empty-ok
```

## 검증 (Validation)
- `STAGE3_LOCAL_BRAIN_RUN_latest.json`의 `rows_output > 0` (부트스트랩 모드 제외)
- `dart_event_signal.csv` 생성 확인

## 실패 정책
- remote/cloud 사용 시 fail-close
- local runtime 미가용 시 fail-close

## 비운영(legacy) 문서
- `STAGE3_DESIGN.md` (상세 설계 기록)
