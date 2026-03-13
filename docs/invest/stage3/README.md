# Stage3 Docs

Stage3 문서는 **external-primary qualitative scoring** 기준으로 정렬한다.

## Canonical 문서
- `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`

## Canonical runtime templates
- `runtime/templates/stage3_external_review_prompt.txt`
- `runtime/templates/stage3_response_schema.json`

## Canonical runtime helpers
- `scripts/stage3/external_primary_runtime.py`
- `scripts/stage3/compact_runtime_outputs.py`

## Supporting 문서
- `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`
  - adjudication / exception review 역할
- `docs/invest/stage3/STAGE3_DESIGN.md`
  - historical/local-support background
- `docs/invest/stage3/STAGE3_DEEP_ANALYSIS_EXTRACTION_RUBRIC.md`
  - supporting draft rubric

## 한 줄 요약
- Stage3 primary lane = external ChatGPT Thinking 5.4 review
- local lane = prefilter / routing / dedup / grouping / priority / sanity-check support only
- input unit = analysis item
- mixed/chatter/opinion/no-symbol item도 preserve-first
- package data contract는 spec 문서 1곳에, full prompt/schema는 runtime templates 1곳에 둔다
- canonical output = external primary normalized JSON
