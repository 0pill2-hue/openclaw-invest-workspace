# Stage3 Rulebook & Repro

status: CANONICAL
updated_at: 2026-03-13 KST
change_type: Strategy
contract_version: stage3_external_primary_v2

## 문서 역할
- 이 문서는 현재 Stage3의 **재현 가능한 구현 계약**이다.
- Stage3의 canonical qualitative writer는 `external_review_primary` lane이며, 실행 모델 기본값은 **ChatGPT Thinking 5.4**다.
- local lane은 ingest / prefilter / routing / dedup / grouping / priority / sanity-check support만 담당한다.
- chatter / opinion / no-symbol item은 low-confidence일 수 있어도 **보존 우선**이며, 무기계적으로 폐기하지 않는다.

---

## 1) 범위
### 포함
1. Stage2 clean 기반 analysis item 정규화
2. local support lane의 package 준비 계약
3. external primary batch scoring 계약
4. external 응답의 normalized JSON 계약
5. adjudication / exception review 진입 조건

### 비포함
- 최종 포트폴리오 판단
- 실매매 지시
- external 응답 없이 local lane만으로 canonical final score를 쓰는 운영

---

## 2) Stage3 canonical pipeline

### Step A — local support ingest
입력원은 Stage2 clean artifacts다. Stage3는 Stage1 raw를 직접 읽지 않는다.

local support가 수행하는 일:
- source normalization
- document/item fingerprinting
- near-duplicate grouping
- entity hinting / symbol hinting
- item priority / batching
- attachment sanity-check
- package manifest 작성

local support가 **하지 않는 일**:
- canonical final qualitative score 작성
- noisy chatter/opinion/no-symbol item의 기계적 discard
- external primary 결과를 local heuristic으로 덮어쓰기

### Step B — analysis item package build
local support는 mixed analysis item을 batch package로 묶는다.
상세 계약은 `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`를 따른다.

### Step C — external primary scoring
- lane name: `external_review_primary`
- mode: `batch_scoring_mode`
- default model target: **ChatGPT Thinking 5.4**
- baseline: attached package + `batch_manifest.json`
- prompt template: `runtime/templates/stage3_external_review_prompt.txt`
- response schema: `runtime/templates/stage3_response_schema.json`

external scorer는 analysis item 단위로 아래를 반환한다.
- primary claim
- evidence / risk / counterpoint / transmission path
- generic common scores
- normalized judgement
- status / preservation decision
- final result label
- analysis confidence

### Step D — normalized JSON + exception handling
canonical Stage3 output은 **validated external response object**다.
local support는 아래만 후처리 가능하다.
- schema validation
- package provenance attach
- item count / attachment count reconciliation
- duplicate ledger sync
- adjudication queue routing

malformed / ambiguous / missing-context exception은 `STAGE3_BRAIN_SCORING_DESIGN.md`의 adjudication flow로 보낸다.

---

## 3) canonical analysis item contract
analysis item은 종목 샘플이 아니라 **분석 대상 item**이다.

최소 필드:
```json
{
  "item_id": "string",
  "document_or_item_id": "string",
  "item_type": "stock|industry|sector|macro|policy|commodity|rates_fx|theme|event|multi_asset|chatter|opinion|mixed|unknown",
  "published_at": "ISO-8601 datetime or null",
  "source_family": "string",
  "title": "string or null",
  "text": "string",
  "focus_entities": [
    {
      "entity_type": "string",
      "entity_id": "string or null",
      "label": "string or null"
    }
  ],
  "symbol_hints": ["005930"],
  "source_tier_hint": "official|professional|independent|field_signal|unknown",
  "dedup_group_id": "string or null",
  "packaging_note": "string or null"
}
```

원칙:
- `item_type`는 stock-only로 강제하지 않는다.
- symbol이 없어도 item 생성 가능하다.
- noisy chatter / opinion은 `item_type=chatter|opinion|unknown|mixed`로 보존 가능하다.
- mixed item은 local에서 억지 분해하지 못하면 `mixed`로 둔다.
- text가 실질적으로 비어 있거나 attachment가 깨졌을 때만 hard fail 대상으로 본다.

---

## 4) allowed item types and preservation policy
허용 item type:
- `stock`
- `industry`
- `sector`
- `macro`
- `policy`
- `commodity`
- `rates_fx`
- `theme`
- `event`
- `multi_asset`
- `chatter`
- `opinion`
- `mixed`
- `unknown`

보존 정책:
- chatter/opinion/no-symbol item은 **drop-by-default 금지**
- 근거가 약하면 `status=ambiguous|insufficient_context` 또는 `preservation_decision=preserve_low_confidence`로 남긴다
- duplicate 정리는 local support가 하되, drop 대신 dedup ledger에 남긴다
- external scorer는 item을 stock/industry/macro 셋 중 하나로 강제 재분류하지 않는다

---

## 5) external primary response contract
정식 schema는 `runtime/templates/stage3_response_schema.json`을 따른다.

Top-level required fields:
- `contract_version`
- `review_mode`
- `baseline`
- `package_audit`
- `review_batch`
- `items`
- `summary`

item-level required fields:
- `item_id`
- `document_or_item_id`
- `item_type`
- `source_family`
- `focus_entities`
- `status`
- `preservation_decision`
- `primary_claim`
- `evidence_summary`
- `evidence_refs`
- `risk_summary`
- `counterpoint_summary`
- `transmission_path`
- `common_scores`
- `normalized_judgement`
- `final_result_label`
- `analysis_confidence`
- `timing`

Stage3 canonical output은 위 JSON object 전체다. local support summary나 임시 score CSV는 canonical output을 대체하지 못한다.

---

## 6) local support lane contract
local lane 책임은 아래로 고정한다.

### 6.1 허용
- prefilter
- routing
- dedup / grouping
- attachment assembly
- batch priority
- source/metadata sanity-check
- invalid attachment or broken text detection
- external response validation

### 6.2 금지
- local provisional score를 production final처럼 쓰기
- external primary가 반환한 `status`, `preservation_decision`, `final_result_label`, `analysis_confidence`를 임의 overwrite
- chatter/opinion/no-symbol item을 “쓸모없다”는 이유만으로 discard

---

## 7) adjudication / exception review
아래면 adjudication path로 보낸다.
- response JSON schema mismatch
- expected item count 불일치
- attachment 누락/훼손
- item_type가 package와 응답에서 강하게 충돌
- duplicate/merge 판단이 high-impact인 경우
- focus entity mapping이 불명확한 경우
- 외부 응답이 `ambiguous` / `insufficient_context` 비율 과다인 경우

adjudication 문서는 `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`를 따른다.

---

## 8) PASS / FAIL 기준
### PASS
- batch package가 mixed analysis item을 누락 없이 담음
- response JSON이 schema-valid임
- 모든 item이 `status` 또는 `preservation_decision`으로 account됨
- chatter/opinion/no-symbol item이 mechanical discard 없이 처리됨

### FAIL
- local lane이 external primary를 우회해 canonical final score를 작성함
- response schema가 stock-only 가정을 강제함
- mixed/chatter/opinion/no-symbol item이 ledger 없이 사라짐
- item count mismatch가 unexplained 상태로 남음

---

## 9) reproducible operator checklist
1. Stage2 clean 기반으로 analysis item을 만든다.
2. local support로 dedup / grouping / priority / attachment sanity-check를 수행한다.
3. package를 `batch_scoring_mode`로 묶는다.
4. Thinking 5.4 fresh chat에서 package + prompt template + response schema를 사용한다.
5. 정확히 1개의 JSON object를 회수한다.
6. schema validation 후 normalized JSON을 canonical Stage3 output으로 저장한다.
7. 예외만 adjudication path로 보낸다.

---

## 10) implementation note
현재 repo에는 과거 local-brain 중심 산출물/실험 흔적이 남아 있을 수 있다.
그 경우에도 운영상 canonical truth는 본 문서와 runtime templates 기준의 **external-primary normalized JSON**이다.
