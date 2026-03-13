# web-review template index

역할: **web-review runtime template 경로 안내 문서**.

상위 문서: `docs/operations/skills/web-review.md`

## review_mode canonical templates
- prompt: `runtime/templates/web_review_review_mode_prompt.txt`
- response schema: `runtime/templates/web_review_review_mode_response_schema.json`
- baseline: pushed git commit only
- expected answer: short JSON object 1개

## batch_scoring_mode canonical templates
- package data contract: `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- prompt: `runtime/templates/stage3_external_review_prompt.txt`
- response schema: `runtime/templates/stage3_response_schema.json`
- baseline: attached package + `batch_manifest.json`
- expected answer: schema-valid JSON object 1개

## operator reminders
- docs에는 full prompt/schema를 다시 붙이지 않는다.
- 실제 전송본은 항상 runtime template 최신본에서 채운다.
- canonical prompt/schema는 `runtime/templates/` 1벌만 유지하고 run별 full prompt copy / `results_template` copy는 기본 금지다.
- batch_scoring_mode item package는 compact 표현을 기본으로 하고, `source_text`는 curated excerpt 우선이다.
- mixed-item batches는 20-40 items(default 30) 범위와 `partition_index`/`partition_count`/`partial_failure` metadata를 유지한다.
- watcher 성공 판정은 verdict token보다 JSON integrity를 우선한다.
- raw watcher text save는 기본 OFF이며, 필요 시 `--debug-save-raw`로 cold layer(`runtime/watch/raw/`)에만 남긴다.
