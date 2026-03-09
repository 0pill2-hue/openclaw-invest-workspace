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

## 평가 단위 (Canonical Units)
- 저장 단위: `stage2_text_meta_records.jsonl`의 1 row
- 모델 평가 단위: `(record_id, chunk_id, focus_symbol)`
- 집계 단위: `(symbol, date, issue_cluster_id)` → `(symbol, date)`

로컬모델은 짧은 chunk + 한 종목 focus claim-card만 추출하고,
최종 점수는 rule engine이 집계한다.

## 출력 (Outputs)
- `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
- `invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl`
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
- `STAGE3_LOCAL_BRAIN_RUN_latest.json`의 `rows_output > 0`, `claim_cards_generated > 0` (부트스트랩 모드 제외)
- `records_skipped_nosymbol`가 집계되고 `__NOSYMBOL__`가 종목 축으로 반영되지 않는지 확인
- `stage3_claim_cards.jsonl`, `dart_event_signal.csv` 생성 확인

## 실패 정책
- remote/cloud 사용 시 fail-close
- local runtime 미가용 시 fail-close

## 비운영(legacy) 문서
- `STAGE3_DESIGN.md` (상세 설계 기록)
