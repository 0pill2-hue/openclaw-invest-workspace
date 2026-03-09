# Stage3 Rulebook & Repro

## 범위
- 역할: Stage3에서 **4축 정성점수**를 산출해 Stage4 `QUALITATIVE_SIGNAL`로 전달
- 4축: `upside_score`, `downside_risk_score`, `bm_sector_fit_score`, `persistence_score`
- 원칙: 감성/주목도(attention/sentiment) 직접 점수축 사용 금지
- 역할 경계: 운영 철학, 편입/교체, 비중조절 규칙은 Stage6에서만 관리하며 Stage3에는 새 운영 축을 추가하지 않는다.

## 입력 (Inputs)
- `invest/stages/stage3/inputs/upstream_stage2_clean/production/qualitative/kr/dart/*.json`
- `invest/stages/stage3/inputs/upstream_stage2_clean/production/qualitative/market/rss/*.json`
- `invest/stages/stage3/inputs/upstream_stage2_clean/production/signal/market/macro/macro_summary.json`
- `invest/stages/stage3/inputs/upstream_stage2_clean/production/qualitative/text/{telegram,blog,premium}`
  - 구(flat) 경로 `.../text/*`도 fallback 지원
  - Telegram PDF는 Stage2 clean telegram 본문에 inline 승격된 `[ATTACHED_PDF] ...` 블록까지 함께 인입한다
- `invest/stages/stage3/inputs/upstream_stage2_clean/production/qualitative/market/news/selected_articles/*.jsonl`
- `invest/stages/stage3/inputs/reference/kr_stock_list.csv`
- `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`

원칙: Stage3는 Stage1 raw를 직접 입력으로 사용하지 않는다.

## 평가 단위 (Local-model friendly)
- 저장 단위: `stage2_text_meta_records.jsonl`의 1 row
- 모델 평가 단위: `(record_id, chunk_id, focus_symbol)`
- 집계 단위: `(symbol, date, issue_cluster_id)` → `(symbol, date)`

구조 원칙:
- LLM(local)은 claim-card 추출기 역할만 수행한다.
- rule engine이 최종 4축 점수와 `QUALITATIVE_SIGNAL`을 집계한다.
- `__NOSYMBOL__`/`__MACRO__` placeholder는 종목 축 점수 집계에 직접 투입하지 않는다.

## 출력 (Outputs)
- 주 출력(4축):
  - `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
- claim-card 출력(증거/집계 중간 산출물):
  - `invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl`
- DART 분석 신호(별도 signal):
  - `invest/stages/stage3/outputs/signal/dart_event_signal.csv`
- 요약/매니페스트:
  - `invest/stages/stage3/outputs/STAGE3_INPUT_BUILD_latest.json`
  - `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`
  - `invest/stages/stage3/outputs/manifest_stage3_input_build_*.json`
  - `invest/stages/stage3/outputs/manifest_stage3_qual_axes_*.json`

## 실행 커맨드 (Run)
```bash
python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py
python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py \
  --input-jsonl invest/stages/stage3/inputs/stage2_text_meta_records.jsonl \
  --output-csv invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv \
  --claim-card-jsonl invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl \
  --dart-signal-csv invest/stages/stage3/outputs/signal/dart_event_signal.csv \
  --summary-json invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json
```

## 정제/점수 규칙 핵심
- 종류 추가가 아니라 축 재설계:
  - 감성/주목도 축 제거
  - 4축 정량 점수(0~100)로 통일
- 이중카운팅 방지:
  1) 축 대표값 1개
  2) 축간 `|rho| > 0.7`이면 낮은 우선순위 축 제거
  3) 단일축 가중치 cap `<= 0.25`
- source family 처리 우선순위:
  - DART: narrative 감상문 점수화보다 deterministic event extraction 우선
  - RSS: item 단위(`title+summary`) 처리, 길면 제한 chunk(1~2)
  - selected_articles: `market_selected_articles` 정식 family로 포함, symbol-focus chunk 기준 평가
  - macro-only 문서(`__MACRO__`)는 종목점수 직접 가산하지 않고 날짜 매크로 보정치로만 사용
- 최종 연계:
  - `QUALITATIVE_SIGNAL`은 4축 합성 결과([-1,1])로 유지
  - Stage4 결합은 `VALUE_SCORE + QUALITATIVE_SIGNAL` baseline 구조를 유지하되, 세부 가중치는 고정 SSOT가 아니라 Stage4/ALGORITHM_SPEC 기준의 tuning 대상이다.

## 검증 (Validation)
- `STAGE3_INPUT_BUILD_latest.json`에서 확인:
  - `rows_from_dart`, `rows_from_rss`, `rows_from_macro_summary`가 Stage2 clean 기준으로 채워지는지 확인
  - `rows_from_text_telegram`, `rows_from_text_blog`, `rows_from_text_premium`, `rows_from_market_selected_articles` 존재
  - `selected_articles_stats` 존재
  - `dropped_duplicate_fingerprint`가 존재해 Stage2/Stage3 중복 차단이 유지되는지 확인
- Telegram PDF 반영 확인:
  - Stage2 clean telegram 본문에서 `[ATTACHED_PDF]`가 있는 메시지가 `stage2_text_meta_records.jsonl`에도 `source=text/telegram:*`로 유지되는지 샘플 확인
- `STAGE3_LOCAL_BRAIN_RUN_latest.json`에서 확인:
  - `rows_output > 0`, `claim_cards_generated > 0` (부트스트랩 제외)
  - `records_skipped_nosymbol`가 집계되는지 확인
  - `axes` 정의 존재
  - `duplication_guard` 존재
- `stage3_claim_cards.jsonl`, `dart_event_signal.csv` 생성 여부 확인

## 실패 정책
- remote/cloud endpoint/model 참조 시 fail-close
- 로컬 runtime 미가용 시 fail-close
