# JB-20260312-STAGE3-EXTERNAL-WEB-PACKAGE

- ticket: JB-20260312-STAGE3-EXTERNAL-WEB-PACKAGE
- status: DONE (package spec drafted)
- checked_at: 2026-03-12 08:18 KST
- lane: external_review
- role: provisional_oracle

## Summary
- ChatGPT Pro web용 Stage3 external/web comparison package 계약을 문서화했다.
- mixed 100 sample의 **고정 quota**를 정의했다.
  - focus level: stock 50 / industry 30 / macro 20
  - source family: blog 24 / telegram 20 / pdf_analyst_report 18 / premium 12 / report 8 / ir 6 / earnings_call 4 / conference_call 3 / trade_publication 3 / field_signal 2
- external lane를 production truth가 아닌 **provisional oracle / comparison group**로 고정했다.
- JSON-only response schema와 batch/item time-metrics contract를 정의했다.
- web-review discipline를 데이터 패키지 맥락으로 변형해 baseline placeholders (`repo/branch/commit/package_manifest_sha256`)를 prompt/manifest에 반영했다.

## Touched paths
- `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- `runtime/tmp/stage3_external_web_package/reviewer_prompt_template.txt`
- `runtime/tmp/stage3_external_web_package/scoring_contract.md`
- `runtime/tmp/stage3_external_web_package/batch_manifest.template.json`
- `runtime/tmp/stage3_external_web_package/response_schema.json`

## Key contract points
1. first package는 sector를 제외하고 stock/industry/macro 3-level mix만 사용
2. deterministic-first source family (`dart`, `rss`, `macro`)는 core mixed100에서 제외하고 필요 시 control pack으로 분리
3. reviewer는 내부 lane output 없이 첨부 문서만 보고 JSON object 하나만 반환
4. timing은 hidden inference guess가 아니라 **observed batch + derived per-item** 방식으로 기록
5. item status는 `scored | ambiguous | insufficient_context | skipped`

## Next action
- `runtime/tmp/stage3_external_web_package/` 아래에 실제 `sample_index.csv`, `attachment_inventory.csv`, `documents/S001..S100.md`를 채워서 전송 가능한 첫 package instance를 만들고, fresh ChatGPT Pro web chat에서 `reviewer_prompt_template.txt` + attached schema/contract로 제출한다.
