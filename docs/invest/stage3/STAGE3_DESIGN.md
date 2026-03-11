# STAGE3_DESIGN (2026-03-05 Refresh)

## 1) 목적 / 범위
- 목적: Stage3에서 4축 정성신호를 산출해 Stage4 `QUALITATIVE_SIGNAL`에 반영
- 4축: `upside`, `downside_risk`, `bm_sector_fit`, `persistence`
- 비범위: 감성/주목도(attention/sentiment) 직접 점수축 사용
- 역할 경계: 편입/교체/비중조절 같은 운영 규칙은 Stage6 범위이며, Stage3는 정성 신호 압축 구조만 유지한다.

---

## 2) 입력원
입력 JSONL: `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`

빌더(`stage03_build_input_jsonl.py`) 인입원:
1. Stage2 clean DART: `upstream_stage2_clean/production/qualitative/kr/dart/*.json`
2. Stage2 clean RSS: `upstream_stage2_clean/production/qualitative/market/rss/*.json`
3. Stage2 clean macro summary: `upstream_stage2_clean/production/signal/market/macro/macro_summary.json`
4. Stage2 clean qualitative text 전체:
   - `telegram`, `blog`, `premium`
   - `qualitative/text/*` 우선, 구(flat) `text/*` fallback
   - Telegram PDF는 Stage2에서 `[ATTACHED_PDF] ...` 형태로 inline 승격된 clean telegram 본문을 그대로 인입
5. Stage2 clean market qualitative corpus:
   - `market/news/selected_articles/*.jsonl`
6. Stage3 reference:
   - `inputs/reference/kr_stock_list.csv` (symbol/name mapping)

링크메타 전용 premium 문서(`STARTALE PREMIUM LINK`)는 제외.
원칙: Stage3 본입력은 Stage1 raw를 직접 읽지 않고, Stage2 clean/Stage3 reference만 사용한다.
또한 builder는 모든 입력 row에 아래 semantic contract를 공통 부여한다.
- `target_levels`
- `macro_tags`
- `industry_tags`
- `stock_tags`
- `event_tags`
- `impact_direction`
- `horizon`
- `region_tags`
계약 부여는 deterministic keyword/name-match 규칙으로 수행하고, 기존 `record_id/published_at/symbols/text/source/source_family/content_fingerprint`는 그대로 유지한다.

---

## 3) 평가 단위 / 내부 구조 (Local-model friendly)
3층 평가 단위:
1. 저장 단위: `stage2_text_meta_records.jsonl`의 row
2. 모델 평가 단위: `(record_id, chunk_id, focus_symbol)`
3. 집계 단위: `(symbol, date, issue_cluster_id)`

구조 분리:
- LLM(local) = claim-card 추출기(짧은 chunk + evidence)
- Rule engine = 점수기/집계기(축 점수 + 중복가드 + 최종 signal)

source family 권장 처리:
- DART: deterministic event extraction 우선(보조 판정만 로컬모델)
- RSS: item 단위(`title+summary`), 길면 1~2 chunk 제한
- selected_articles: `market_selected_articles` 정식 family로 symbol-focus chunk 평가
- macro-only(`__MACRO__`) 문서는 standalone `stage3_macro_forecast.csv`의 입력으로 우선 집계
- stock axis 반영은 선택 플래그(`--apply-macro-to-stock-axes on|off`)로 제어하고, 기본은 `on`으로 두어 backward-compat를 유지
- `__NOSYMBOL__`는 종목 점수 집계에서 제외(통계로만 유지)

---

## 4) 점수축 설계
모든 축은 0~100 점수.

- `upside_score`: 개선/성장/수주/가이던스 등 상승 근거 축
- `downside_risk_score`: 악화/희석/소송/리스크오프 등 하방 위험 축
- `bm_sector_fit_score`: 소스 신뢰/다원성/이벤트-시장 정합 축
- `persistence_score`: 신호 지속성(반복 언급/시간축 유지) 축

보조 정의:
- `risk_score = downside_risk_score`
- `net_edge_score = upside_score - downside_risk_score`

---

## 5) 이중카운팅 방지
1. 축 대표값 1개 원칙
2. 축간 상관 임계치: `|rho| > 0.7`이면 낮은 우선순위 축 제거
3. 단일축 가중치 cap: `<= 0.25`
4. 최종 합성:
   - `qualitative_signal` ([-1,1])
   - downside 축은 음(-) 기여로 반영

---

## 6) 출력 스키마
### 5.1 주 출력
- `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
- 핵심 컬럼:
  - `date,symbol,doc_count,mention_count`
  - `upside_score,downside_risk_score,risk_score,bm_sector_fit_score,persistence_score,net_edge_score`
  - `qualitative_signal`
  - `dup_guard_axis_weight_{upside,downside,bm,persistence}`

### 6.2 Claim-card 중간 출력
- `invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl`
- 핵심 필드:
  - `date,symbol,record_id,chunk_id,focus_symbol,issue_cluster_id`
  - `evidence_text,dominant_axis,claim_confidence,claim_weight`

### 6.3 DART 신호 분리 출력
- `invest/stages/stage3/outputs/signal/dart_event_signal.csv`
- 컬럼:
  - `date,symbol,dart_doc_count,event_*_count,dart_event_signal`

### 6.4 Macro forecast 분리 출력
- `invest/stages/stage3/outputs/signal/stage3_macro_forecast.csv`
- 핵심 컬럼:
  - `date,macro_doc_count,macro_risk_signal,macro_risk_on_ratio,macro_risk_off_ratio`
  - `macro_regime_label,macro_forecast_score,macro_confidence,macro_horizon`
  - `macro_evidence_summary,macro_source_mix,brain_backend`

### 6.5 요약
- `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`

---

## 7) Stage4 연계
- Stage4 조인키: `date + symbol`
- Stage4 결합 구조:
  - `VALUE_SCORE`와 `QUALITATIVE_SIGNAL`의 결합 구조를 유지한다.
  - 세부 가중치는 영구 고정 규칙이 아니라 baseline/candidate/tuning 대상이다.
- Stage4 입력 경로:
  - stock qualitative: `upstream_stage3_outputs/features/stage3_qualitative_axes_features.csv`
  - macro qualitative: `upstream_stage3_outputs/signal/stage3_macro_forecast.csv`
- 권장 결합 계약:
  - stock row는 `date + symbol`로 조인
  - macro row는 `date` 단위로 별도 조인 후 시장 regime 보정 입력으로 사용

---

## 8) 재현 명령
```bash
cd "$(git rev-parse --show-toplevel)"

python3 -m py_compile \
  invest/stages/stage3/scripts/stage03_build_input_jsonl.py \
  invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py

/usr/bin/python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py

/usr/bin/python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py \
  --input-jsonl invest/stages/stage3/inputs/stage2_text_meta_records.jsonl \
  --output-csv invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv \
  --claim-card-jsonl invest/stages/stage3/outputs/features/stage3_claim_cards.jsonl \
  --dart-signal-csv invest/stages/stage3/outputs/signal/dart_event_signal.csv \
  --macro-forecast-csv invest/stages/stage3/outputs/signal/stage3_macro_forecast.csv \
  --summary-json invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json
```
