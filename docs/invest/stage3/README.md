# Stage3 Qualitative Axes Docs

## Canonical 문서
- `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`

## 입력 (Inputs)
- `invest/stages/stage3/inputs/upstream_stage2_clean/production/`
  - qualitative kr: `qualitative/kr/dart/*.json`
  - qualitative market: `qualitative/market/{rss,news/selected_articles}/*`
  - signal market: `signal/market/macro/macro_summary.json`
  - qualitative text: `qualitative/text/{blog,telegram,premium}`
  - 구(flat) 경로 `text/*` fallback 지원
  - Telegram PDF는 Stage2 clean telegram 본문에 inline 승격된 `[ATTACHED_PDF]` 블록까지 함께 인입
- `invest/stages/stage3/inputs/reference/kr_stock_list.csv`
- `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`

원칙: Stage3는 Stage1 raw를 직접 읽지 않는다.

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
- `STAGE3_INPUT_BUILD_latest.json`의 `rows_from_market_selected_articles`, `selected_articles_stats`, `dropped_duplicate_fingerprint` 확인
- `STAGE3_LOCAL_BRAIN_RUN_latest.json`의 `rows_output > 0` (부트스트랩 모드 제외)
- `dart_event_signal.csv` 생성 확인

## 실패 정책
- remote/cloud 사용 시 fail-close
- local runtime 미가용 시 fail-close

## 비운영(legacy) 문서
- `STAGE3_DESIGN.md` (상세 설계 기록)
