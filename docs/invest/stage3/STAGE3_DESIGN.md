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
1. DART: `upstream_stage1/raw/qualitative/kr/dart/*.csv`
2. RSS: `upstream_stage1/raw/qualitative/market/rss/*.json`
3. macro summary: `upstream_stage1/raw/signal/market/macro/macro_summary.json`
4. Stage2 clean qualitative text 전체:
   - `telegram`, `blog`, `premium`, `image_map`, `images_ocr`
   - `qualitative/text/*` 우선, 구(flat) `text/*` fallback

링크메타 전용 premium 문서(`STARTALE PREMIUM LINK`)는 제외.

---

## 3) 점수축 설계
모든 축은 0~100 점수.

- `upside_score`: 개선/성장/수주/가이던스 등 상승 근거 축
- `downside_risk_score`: 악화/희석/소송/리스크오프 등 하방 위험 축
- `bm_sector_fit_score`: 소스 신뢰/다원성/이벤트-시장 정합 축
- `persistence_score`: 신호 지속성(반복 언급/시간축 유지) 축

보조 정의:
- `risk_score = downside_risk_score`
- `net_edge_score = upside_score - downside_risk_score`

---

## 4) 이중카운팅 방지
1. 축 대표값 1개 원칙
2. 축간 상관 임계치: `|rho| > 0.7`이면 낮은 우선순위 축 제거
3. 단일축 가중치 cap: `<= 0.25`
4. 최종 합성:
   - `qualitative_signal` ([-1,1])
   - downside 축은 음(-) 기여로 반영

---

## 5) 출력 스키마
### 5.1 주 출력
- `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
- 핵심 컬럼:
  - `date,symbol,doc_count,mention_count`
  - `upside_score,downside_risk_score,risk_score,bm_sector_fit_score,persistence_score,net_edge_score`
  - `qualitative_signal`
  - `dup_guard_axis_weight_{upside,downside,bm,persistence}`

### 5.2 DART 신호 분리 출력
- `invest/stages/stage3/outputs/signal/dart_event_signal.csv`
- 컬럼:
  - `date,symbol,dart_doc_count,event_*_count,dart_event_signal`

### 5.3 요약
- `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`

---

## 6) Stage4 연계
- Stage4 조인키: `date + symbol`
- Stage4 결합 구조:
  - `VALUE_SCORE`와 `QUALITATIVE_SIGNAL`의 결합 구조를 유지한다.
  - 세부 가중치는 영구 고정 규칙이 아니라 baseline/candidate/tuning 대상이다.
- Stage4 입력 경로:
  - `upstream_stage3_outputs/features/stage3_qualitative_axes_features.csv`

---

## 7) 재현 명령
```bash
cd "$(git rev-parse --show-toplevel)"

python3 -m py_compile \
  invest/stages/stage3/scripts/stage03_build_input_jsonl.py \
  invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py

/usr/bin/python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py

/usr/bin/python3 invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py \
  --input-jsonl invest/stages/stage3/inputs/stage2_text_meta_records.jsonl \
  --output-csv invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv \
  --dart-signal-csv invest/stages/stage3/outputs/signal/dart_event_signal.csv \
  --summary-json invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json
```
