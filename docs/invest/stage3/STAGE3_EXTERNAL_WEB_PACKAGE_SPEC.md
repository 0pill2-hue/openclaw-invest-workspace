# STAGE3_EXTERNAL_WEB_PACKAGE_SPEC

status: CANONICAL
updated_at: 2026-03-13 KST
change_type: Strategy
contract_version: stage3_external_primary_v2
lane: external_review_primary
review_mode: batch_scoring_mode

## 1) 목적
- 본 문서는 Stage3 `external_review_primary`의 **package data contract**를 고정한다.
- input unit은 stock sample이 아니라 **analysis item**이다.
- mixed item, chatter, opinion, no-symbol item도 package 대상에 포함될 수 있다.
- full prompt/schema의 canonical은 docs가 아니라 runtime templates다.

## 2) canonical split
- package data contract: `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- prompt template: `runtime/templates/stage3_external_review_prompt.txt`
- response schema: `runtime/templates/stage3_response_schema.json`
- operator flow: `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`

## 3) lane position
- lane name: `external_review_primary`
- role: `primary_scoring`
- local lane role: `prefilter_routing_support_only`
- default model target: **ChatGPT Thinking 5.4**
- execution mode: `batch_scoring_mode`

## 4) preserve-and-label-first
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

원칙:
- `chatter`, `opinion`, `unknown`도 package에서 제외하지 않는다.
- symbol이 없어도 item으로 인정한다.
- 하나의 문서가 여러 레벨/자산을 섞으면 `mixed` 또는 `multi_asset`을 허용한다.
- local support는 item_type hint를 줄 수 있지만, 강제 축소/왜곡하면 안 된다.

## 5) batch sizing and attachment discipline
- direct attachment를 기본으로 한다.
- fresh chat 기준 current UI attachment ceiling 안에서 batch를 분할한다.
- attachment 수는 실무 기본 **20 files 이하 / fresh chat**를 유지한다.
- mixed-item batch는 **20-40 items**를 기본 범위로 하고, 기본 target은 `30 items`다.
- batch split이 생겨도 `package_id + batch_id + item_id` lineage를 유지한다.
- partial failure는 전체 재실행이 아니라 failed subset 재분할이 가능해야 하므로 `partition_index`, `partition_count`, `partial_failure.failed_item_ids` 메타데이터를 유지한다.

## 6) package files
### package core
1. `batch_manifest.json`
2. `item_index.csv`
3. `items/I###.md`

### send-time template attachments
아래는 전송 시 함께 붙일 수 있는 compact package metadata다.
- `scoring_contract.md` -> `runtime/templates/stage3_external_review_prompt.txt`의 compact instruction projection
- `attachment_inventory.csv` -> 선택이지만 권장

규칙:
- canonical prompt/schema는 `runtime/templates/` 1벌만 유지한다.
- run별 full prompt copy, `results_template` copy, `actual` dump는 기본 생성 금지다.
- docs에 prompt/schema 본문을 다시 붙여 넣지 않는다.

## 7) batch manifest minimum fields
- `contract_version`
- `review_mode`
- `lane`
- `package_id`
- `batch_id`
- `package_manifest_sha256`
- `package_prepared_at_utc`
- `package_preparer`
- `model_target_default`
- `expected_item_count`
- `item_type_counts`
- `source_kind_counts`
- `repo_name`
- `repo_url`
- `branch_name`
- `commit_hash`
- `commit_url`

원칙:
- repo commit은 provenance다.
- scorer baseline은 **repo diff가 아니라 attached package**다.

### partition metadata (required when split occurs)
- `partition_index`
- `partition_count`
- `batch_item_policy.min_items`
- `batch_item_policy.max_items`
- `batch_item_policy.default_target`
- `partial_failure.failed_item_ids`
- `partial_failure.repartition_recommended`

원칙:
- split batch는 failed subset만 재분할/재전송 가능해야 한다.
- partition metadata 없이 partial failure를 whole-package ambiguity로 남기지 않는다.

## 8) compact item expression
### item_index core columns
- `item_id`
- `document_or_item_id` (`stable upstream id`가 없으면 `item_id` fallback 사용)
- `item_type`
- `title`
- `source_kind`
- `published_at_utc`
- `locator`
- `attachment_file`
- `minimal_operator_notes`

### optional columns
- `dedup_group_id`

### per-item attachment shape
각 `items/I###.md`는 아래처럼 **compact 표현**을 기본으로 한다.

```md
# item_id: I001
- item_type: mixed
- title: <title or null>
- source_kind: <raw source kind>
- published_at_utc: <timestamp or null>
- locator: <url/page/message/file reference>
- document_or_item_id: <stable upstream id or item_id fallback>
- minimal_operator_notes: <one short line>
- source_text_mode: curated_excerpt|full_text

## source_text
<curated excerpt preferred>
```

원칙:
- `source_text`는 **curated excerpt 우선**이다.
- extra metadata는 꼭 필요할 때만 넣는다.
- `focus_entities` / `symbol_hints`는 disambiguation에 실제로 필요할 때만 추가한다.
- local lane final score/output은 동봉하지 않는다.
- item_type이 `chatter|opinion|mixed|unknown`이어도 동일 형식으로 첨부한다.

## 9) response contract summary
정식 schema는 `runtime/templates/stage3_response_schema.json`이 canonical이다.

문서에는 field summary만 남긴다.
- top-level sections: `baseline`, `package_audit`, `review_batch`, `items`, `summary`
- each item must emit: identity, normalized `source_family`, `focus_entities`, claim/evidence/risk/counterpoint/transmission, `common_scores`, `normalized_judgement`, `status`, `preservation_decision`, `final_result_label`, `analysis_confidence`, `timing`
- `source_kind`는 compact package input label이고, response의 `source_family`는 reviewer가 정규화한 concise family label이다.

## 10) operator acceptance checklist
1. package manifest hash와 expected item count를 채운다.
2. mixed/chatter/opinion/no-symbol item 누락이 없는지 본다.
3. item file은 compact 표현 + curated excerpt 중심인지 본다.
4. prompt/schema attached copy가 runtime template 최신본과 일치하는지 본다.
5. JSON-only response 요구를 포함한다.

## 11) downstream normalization rules
- external response는 schema validation 후 canonical normalized JSON으로 보관한다.
- local support metadata는 provenance로 append 가능하지만 final qualitative fields를 대체하지 못한다.
- `merge_candidate` 또는 `needs_adjudication` item만 별도 exception queue로 보낸다.
- `insufficient_context`도 item record 자체는 남긴다.

## 12) runtime output compaction
- run 종료 후 hot keep set은 `manifest/result/summary/card/proof-index`만 유지한다.
- `actual/tmp/prompt/result_template/comparison/per-run metrics/stdout/stderr/log` 성격의 intermediates는 cold archive 이동 또는 삭제한다.
- runtime run metrics는 `wall_seconds`, `item_count`, `parse_integrity`, `completeness`, `cost_estimate(optional)`만 남긴다.
- canonical compactor는 `scripts/stage3/compact_runtime_outputs.py`다.
