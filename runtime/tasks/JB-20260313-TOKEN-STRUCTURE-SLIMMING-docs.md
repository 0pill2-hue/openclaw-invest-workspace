# JB-20260313-TOKEN-STRUCTURE-SLIMMING-docs

- ticket: JB-20260313-TOKEN-STRUCTURE-SLIMMING
- scope: docs/contract slimming
- checked_at: 2026-03-13 KST

## landed
1. Stage3 external batch scoring **package data contract canonical**을 `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md` 1곳으로 고정했다.
2. Stage3 spec에서 full prompt/schema 재게시를 제거하고, package는 `item_id`, `item_type`, `title`, `source_kind`, `published_at_utc`, `locator`, curated `source_text`, one-line `minimal_operator_notes` 중심의 compact 표현으로 재정렬했다.
3. `skills/web-review/SKILL.md`를 orchestration contract + canonical reference 중심으로 슬림화했고, 장문 prompt body / answer-format 본문을 제거했다.
4. `runtime/templates/`에 `review_mode` canonical prompt/schema를 새로 추가했다.
   - `runtime/templates/web_review_review_mode_prompt.txt`
   - `runtime/templates/web_review_review_mode_response_schema.json`
5. `runtime/templates/stage3_external_review_prompt.txt`를 compact item package 전제에 맞게 갱신했다.
6. `docs/operations/skills/web-review.md`와 `docs/operations/skills/web-review-templates.md`를 overview/link 문서로 축소했다.
7. `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`와 `docs/invest/stage3/README.md`를 canonical split(package spec vs runtime templates) 기준으로 정렬했다.
8. `bash scripts/skills/sync_web_review_skill.sh`를 실행해 `~/.agents/skills/web-review/` 배포본도 동기화했다.
9. `docs/operations/OPERATIONS_BOOK.md`는 현재 링크 드리프트가 없어 추가 수정 없이 유지했다.

## remaining
- docs/contract 축 기준 추가 필수 수정은 현재 없음.
- 다만 문서 밖 후속으로는, 실제 package builder/runtime code가 compact `source_kind` 중심 표현과 runtime-template-derived attachment copy를 일관되게 생성하는지 별도 점검할 수 있다.

## proof
- changed files:
  - `docs/invest/stage3/README.md`
  - `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`
  - `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
  - `docs/operations/skills/web-review.md`
  - `docs/operations/skills/web-review-templates.md`
  - `skills/web-review/SKILL.md`
  - `runtime/templates/stage3_external_review_prompt.txt`
  - `runtime/templates/web_review_review_mode_prompt.txt`
  - `runtime/templates/web_review_review_mode_response_schema.json`
- validation:
  - JSON parse ok: `runtime/templates/stage3_response_schema.json`, `runtime/templates/web_review_review_mode_response_schema.json`
  - skill sync ok: `synced: /Users/jobiseu/.openclaw/workspace/skills/web-review/ -> /Users/jobiseu/.agents/skills/web-review/`
  - duplicate prompt check: `Use ONLY this baseline` 본문은 `runtime/templates/web_review_review_mode_prompt.txt`에만 남음
