# STAGE3_EXTERNAL_WEB_PACKAGE_SPEC

status: DRAFT
updated_at: 2026-03-12 KST
change_type: Strategy
scope: Stage3 external/web comparison package for ChatGPT Pro manual web review
contract_version: stage3_external_web_v1

## 1) 목적
- 본 문서는 `external_review` lane용 **mixed 100 sample package contract**를 고정한다.
- 이 lane의 역할은 production truth writer가 아니라 **provisional oracle / comparison group**이다.
- 즉, external 결과는 내부 `local_brain / main_brain / subagent_brain`과 동일 schema로 비교·정렬하기 위한 참고 기준이며, 자동 채택 대상이 아니다.
- 본 패키지는 **ChatGPT Pro web 수동 첨부 방식**을 전제로 한다.

## 2) lane position
- lane name: `external_review`
- role: `provisional_oracle`
- primary use:
  1. 100-sample 품질 비교군
  2. 내부 lane disagreement adjudication 보조
  3. claim/evidence/final-axis 구조의 외부 독립 판독
- non-goal:
  - production 자동 반영
  - 포트폴리오 추천/매매 지시
  - deterministic-first source의 canonical override

## 3) 고정 100-sample mix
첫 external/web 패키지는 분기 수를 억제하기 위해 `stock / industry / macro` 3개 focus level만 사용한다.
`sector`는 차기 패키지에서 별도 추가한다.

### 3.1 focus level quota
| focus_level | count |
| --- | ---: |
| stock | 50 |
| industry | 30 |
| macro | 20 |
| total | 100 |

### 3.2 source family quota
| source_family | stock | industry | macro | total |
| --- | ---: | ---: | ---: | ---: |
| blog | 12 | 7 | 5 | 24 |
| telegram | 11 | 6 | 3 | 20 |
| pdf_analyst_report | 10 | 5 | 3 | 18 |
| premium | 5 | 4 | 3 | 12 |
| report | 3 | 3 | 2 | 8 |
| ir | 4 | 2 | 0 | 6 |
| earnings_call | 2 | 1 | 1 | 4 |
| conference_call | 1 | 1 | 1 | 3 |
| trade_publication | 1 | 1 | 1 | 3 |
| field_signal | 1 | 0 | 1 | 2 |
| total | 50 | 30 | 20 | 100 |

### 3.3 inclusion rules
- 한 `sample_id`는 하나의 주된 `focus_level`만 가진다.
- 한 `document_or_item_id`가 여러 level로 해석 가능하더라도 본 배치에서는 **대표 row 1개만** 뽑는다.
- `stock`은 종목 직접 thesis/catalyst/failure mode가 있는 문서만 포함한다.
- `industry`는 value chain/수급/가격결정력/정책/기술 변화가 산업 수준에서 읽히는 문서만 포함한다.
- `macro`는 rates/fx/liquidity/policy/regime transmission이 명시된 문서만 포함한다.
- 동일 저자/같은 날/거의 동일 주장 복제물은 제외한다.
- deterministic-first canonical source인 `dart`, `rss`, `macro` source_family는 **이번 mixed 100 core pack에서 제외**한다. 필요하면 별도 control pack으로 분리한다.

## 4) package layout
권장 패키지 디렉터리:

```txt
runtime/tmp/stage3_external_web_package/
  batch_manifest.json
  scoring_contract.md
  response_schema.json
  sample_index.csv
  attachment_inventory.csv
  documents/
    S001.md
    S002.md
    ...
    S100.md
```

### 4.1 required files
1. `batch_manifest.json`
   - package identity, baseline placeholders, quota proof, timing placeholders
2. `scoring_contract.md`
   - reviewer instruction + axis definitions + non-goals
3. `response_schema.json`
   - 반환 JSON schema
4. `sample_index.csv`
   - 100개 sample 메타데이터 일람
5. `attachment_inventory.csv`
   - 첨부 파일명, bytes, sha256, source locator
6. `documents/S###.md`
   - sample별 첨부 본문/발췌 단위

### 4.2 per-document attachment format
각 `documents/S###.md`는 아래 순서를 고정한다.

```md
# sample_id: S001
- document_or_item_id: <id>
- source_family: <blog|telegram|...>
- focus_level: <stock|industry|macro>
- focus_entity_or_context_id: <symbol|industry_id|macro_context_id>
- title: <title>
- published_at_utc: <timestamp>
- language: <ko|en|...>
- locator: <url/page/message/file reference>
- extraction_mode: full_text|curated_excerpt
- extraction_note: <why excerpted if excerpted>

## normalized_context
- entity_hint: ...
- prior_lane_outputs_attached: no
- confidential_redaction: none|minimal|applied

## source_text
<attached text or curated excerpt>

## minimal_operator_notes
- reason_for_selection: <one short line>
- duplication_check: pass
```

원칙:
- 외부 reviewer에게 내부 lane 점수는 주지 않는다.
- 필요 최소한의 normalization만 제공하고 해석은 reviewer에게 맡긴다.
- `curated_excerpt`를 쓸 경우 핵심 문맥이 끊기지 않도록 2개 이상 segment를 허용한다.

## 5) baseline discipline (web-review concept adapted)
web-review discipline를 데이터 패키지용으로 변형해 아래 baseline을 항상 명시한다.

### 5.1 baseline fields
- `repo_name`
- `repo_url`
- `branch_name`
- `commit_hash`
- `commit_url`
- `package_id`
- `package_manifest_sha256`
- `package_prepared_at_utc`
- `package_preparer`

### 5.2 hard instruction
- reviewer prompt에는 반드시 다음을 넣는다.
  - **Ignore all prior conversation/context/memory. Use only this package and attached files.**
  - package/attachments가 불충분하면 추측하지 말고 item을 `insufficient_context`로 표시
  - **Return ONLY one JSON object** matching the response contract
- fresh new chat 사용
- 응답 수집 후 internal review 없이 자동 적용 금지

## 6) scoring request scope
reviewer는 각 sample마다 아래만 수행한다.
1. `primary_claim` 1줄 요약
2. `evidence_summary`와 `evidence_refs`
3. `risk_summary`와 `counterpoint_summary`
4. `transmission_path`
5. 공통 sub-score
6. level-specific final axis 산출
7. `analysis_confidence`
8. `status` 판정 (`scored|ambiguous|insufficient_context|skipped`)

reviewer에게 금지되는 것:
- 포트폴리오 추천
- buy/sell call
- 내부 lane 비난/채점
- deterministic 사실값 재작성

## 7) level-specific final axes
### 7.1 stock
필수 keys:
- `upside_capture_score`
- `downside_risk_score`
- `catalyst_path_score`
- `thesis_confidence_score`
- `execution_resilience_score`
- `final_result_label`

### 7.2 industry
필수 keys:
- `structural_attractiveness_score`
- `cycle_advantage_score`
- `pricing_power_supply_score`
- `policy_technology_tailwind_score`
- `disruption_fragility_score`
- `industry_attractiveness_score`
- `final_result_label`

### 7.3 macro
필수 keys:
- `regime_support_score`
- `liquidity_stress_score`
- `policy_directionality_score`
- `transmission_clarity_score`
- `macro_confidence_score`
- `final_result_label`

## 8) common scoring scale
- 모든 점수는 `0..100` 정수
- `analysis_confidence`는 `0.0..1.0`
- high score guardrail:
  - evidence summary가 빈약하면 80+ 금지
  - risk/counterpoint가 비어 있으면 confidence 0.70 초과 금지
- `status != scored`면 final axis를 `null` 허용

## 9) JSON-only response contract
정식 schema는 `response_schema.json`을 따른다.
반환 top-level object는 아래 구조를 가져야 한다.

```json
{
  "contract_version": "stage3_external_web_v1",
  "baseline": {},
  "package_audit": {},
  "review_batch": {},
  "items": [],
  "summary": {}
}
```

### 9.1 item-level required fields
- `sample_id`
- `document_or_item_id`
- `source_family`
- `focus_level`
- `focus_entity_or_context_id`
- `provisional_oracle`
- `status`
- `primary_claim`
- `evidence_summary`
- `evidence_refs`
- `risk_summary`
- `counterpoint_summary`
- `transmission_path`
- `common_scores`
- `final_result_axes`
- `final_result_label`
- `analysis_confidence`
- `timing`

## 10) time-metrics contract
외부 web lane의 시간값은 **model 내부 진실 추정이 아니라 관측/파생 값**으로 다룬다.

### 10.1 batch-level required timing fields
`review_batch`에 아래 필드를 고정한다.
- `package_prepared_at_utc`
- `prompt_submitted_at_utc`
- `response_completed_at_utc`
- `json_extracted_at_utc`
- `batch_wall_seconds_observed`
- `operator_active_seconds_observed`
- `attachment_bytes_total`
- `attachment_count`
- `reviewed_item_count`
- `normalized_item_wall_seconds`
- `timing_measurement_method`

정의:
- `batch_wall_seconds_observed = response_completed_at_utc - prompt_submitted_at_utc`
- `normalized_item_wall_seconds = batch_wall_seconds_observed / reviewed_item_count`
- `operator_active_seconds_observed`는 사람이 실제로 package 준비/전송/회수/정리한 시간 합계
- `timing_measurement_method` 기본값: `observed_batch_plus_derived_per_item`

### 10.2 item-level timing fields
각 item의 `timing` object는 아래를 가진다.
- `timing_source`: `derived_from_batch`
- `batch_wall_seconds_observed`
- `normalized_item_wall_seconds`
- `operator_active_seconds_share`
- `timing_comparability_note`

원칙:
- external lane item time은 lane-local true inference time이 아니라 **batch 배분값**이다.
- 따라서 main/subagent의 per-item processing time과 1:1 동일 의미가 아님을 `timing_comparability_note`에 명시한다.

## 11) summary fields
`summary`는 최소 아래를 포함한다.
- `scored_count`
- `ambiguous_count`
- `insufficient_context_count`
- `skipped_count`
- `focus_level_counts`
- `source_family_counts`
- `status_counts`
- `timing_rollup`
- `comparison_readiness`
- `recommended_follow_up`

`comparison_readiness` enum:
- `ready`
- `ready_with_gaps`
- `not_ready`

## 12) package acceptance checklist
배치 생성자는 전송 전 아래를 만족해야 한다.
1. sample count 정확히 100
2. focus level quota = 50/30/20
3. source family quota table 일치
4. 각 sample attachment 1개와 index row 1개 매칭
5. attachment inventory sha256 채움
6. baseline placeholders 채움 (`branch_name`, `commit_hash`, `package_manifest_sha256` 등)
7. reviewer prompt에 JSON-only 문구 포함
8. external lane가 provisional oracle임을 명시
9. 내부 lane score/output 미동봉
10. 민감/비공개 원문 승인 여부 확인

## 13) downstream comparison rules
- external 결과는 normalize 후 `lane=external_review`로 적재한다.
- 비교는 항상 `sample_id + focus_level + axis_name` 기준으로 한다.
- disagreement는 아래 중 하나면 발생한다.
  - label conflict
  - final axis abs diff >= 25
  - evidence mismatch severe
  - status disagreement (`scored` vs `insufficient_context`)
- disagreement가 커도 external 결과를 자동 우선하지 않는다.
- adjudication 기본 우선순위:
  1. evidence traceability
  2. focus-level correctness
  3. final-axis coherence
  4. timing/cost efficiency

## 14) next implementation handoff
이 spec 다음 단계는 아래 순서를 따른다.
1. `runtime/tmp/stage3_external_web_package/`에 실제 manifest/template 채우기
2. mixed 100 sample selection script 또는 수동 selection sheet 작성
3. ChatGPT Pro web fresh chat에 prompt 제출
4. JSON 응답 회수 후 normalize
5. internal lane와 동일 comparison table 생성
