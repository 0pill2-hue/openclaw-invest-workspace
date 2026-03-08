# Stage3 Rulebook & Repro

## 범위
- 역할: Stage3에서 **4축 정성점수**를 산출해 Stage4 `QUALITATIVE_SIGNAL`로 전달
- 4축: `upside_score`, `downside_risk_score`, `bm_sector_fit_score`, `persistence_score`
- 원칙: 감성/주목도(attention/sentiment) 직접 점수축 사용 금지
- 역할 경계: 운영 철학, 편입/교체, 비중조절 규칙은 Stage6에서만 관리하며 Stage3에는 새 운영 축을 추가하지 않는다.

## 입력 (Inputs)
- `invest/stages/stage3/inputs/upstream_stage1/raw/qualitative/kr/dart/*.csv`
- `invest/stages/stage3/inputs/upstream_stage1/raw/qualitative/market/rss/*.json`
- `invest/stages/stage3/inputs/upstream_stage1/raw/signal/market/macro/macro_summary.json`
- `invest/stages/stage3/inputs/upstream_stage2_clean/qualitative/text/{telegram,blog,premium,image_map,images_ocr}`
  - 구(flat) 경로 `.../text/*`도 fallback 지원
- `invest/stages/stage3/inputs/stage2_text_meta_records.jsonl`

## 출력 (Outputs)
- 주 출력(4축):
  - `invest/stages/stage3/outputs/features/stage3_qualitative_axes_features.csv`
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
- 최종 연계:
  - `QUALITATIVE_SIGNAL`은 4축 합성 결과([-1,1])로 유지
  - Stage4 결합은 `VALUE_SCORE + QUALITATIVE_SIGNAL` baseline 구조를 유지하되, 세부 가중치는 고정 SSOT가 아니라 Stage4/ALGORITHM_SPEC 기준의 tuning 대상이다.

## 검증 (Validation)
- `STAGE3_LOCAL_BRAIN_RUN_latest.json`에서 확인:
  - `rows_output > 0` (부트스트랩 제외)
  - `axes` 정의 존재
  - `duplication_guard` 존재
- `dart_event_signal.csv` 생성 여부 확인

## 실패 정책
- remote/cloud endpoint/model 참조 시 fail-close
- 로컬 runtime 미가용 시 fail-close
