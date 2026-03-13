# STAGE3_EXTERNAL_PRIMARY_OPERATIONS

status: CANONICAL
updated_at: 2026-03-13 KST
scope: Stage3 external-primary operator workflow

## 1) 목적
- 본 문서는 Stage3 external-primary의 **실행 절차**만 고정한다.
- package data contract의 canonical은 `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`다.
- full prompt/schema의 canonical은 runtime templates다.

## 2) preflight
1. package를 `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md` 기준으로 준비한다.
2. mixed / chatter / opinion / no-symbol item 누락이 없는지 본다.
3. 아래 최신 runtime templates를 사용한다.
   - `runtime/templates/stage3_external_review_prompt.txt`
   - `runtime/templates/stage3_response_schema.json`
4. fresh chat를 사용한다.
5. 모델이 Thinking 5.4인지 확인한다.

## 3) send
1. `runtime/templates/stage3_external_review_prompt.txt`를 채운다.
2. canonical template는 `runtime/templates/` 1벌만 유지하고, package는 compact metadata + item payload 위주로 첨부한다. per-run full prompt copy / `results_template` copy / `actual` dump는 기본 금지다.
3. mixed-item batch는 **20-40 items**(default target 30) 범위에서 partition하고 `partition_index`, `partition_count`, `partial_failure.failed_item_ids` metadata를 담는다.
4. composer에 attachment chip/list가 보이는지 확인한다.
5. fresh chat 기준 총 첨부 수를 약 20 files 이하로 유지한다.
6. 전송이 막히면 `Enter -> Meta+Enter` 순으로 본다.
7. send 후 conversation URL을 기록한다.

## 4) capture / validation
1. watcher 또는 수동 회수로 JSON response를 받는다.
2. watcher raw text save는 기본 OFF로 두고, forensic이 필요할 때만 `--debug-save-raw`로 `runtime/watch/raw/` cold save를 남긴다.
3. markdown/code fence 없이 JSON object 1개인지 본다.
4. `runtime/templates/stage3_response_schema.json`으로 validation한다.
5. expected item count와 received item count를 대조한다.
6. malformed / partial / schema-mismatch batch는 failed subset만 재분할 가능한 metadata를 남기고 adjudication path로 보낸다.
7. run 종료 후 `python3 scripts/stage3/compact_runtime_outputs.py <run_dir>`로 intermediates를 cold archive/delete 한다.

## 5) normalization
- validated JSON object 자체가 Stage3 canonical normalized output이다.
- local support metadata는 provenance append만 가능하다.
- `merge_candidate` / `needs_adjudication` / malformed batch만 별도 queue로 보낸다.
- `insufficient_context` item도 보관한다.

## 6) references
- package spec: `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- prompt template: `runtime/templates/stage3_external_review_prompt.txt`
- response schema: `runtime/templates/stage3_response_schema.json`
- runtime policy helpers: `scripts/stage3/external_primary_runtime.py`
- runtime compactor: `scripts/stage3/compact_runtime_outputs.py`
- rulebook: `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`
- adjudication: `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`
- web-review skill: `skills/web-review/SKILL.md`
