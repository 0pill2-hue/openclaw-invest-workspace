# web-review

역할: **ChatGPT web review 운영 개요 문서**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

## Modes
1. `review_mode`
   - 코드/문서/변경사항 external review
   - baseline = pushed git commit
   - canonical runtime templates:
     - `runtime/templates/web_review_review_mode_prompt.txt`
     - `runtime/templates/web_review_review_mode_response_schema.json`
2. `batch_scoring_mode`
   - Stage3 external-primary mixed analysis item scoring
   - baseline = attached package + `batch_manifest.json`
   - canonical contract + runtime templates:
     - `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
     - `runtime/templates/stage3_external_review_prompt.txt`
     - `runtime/templates/stage3_response_schema.json`

## Canonical sources
- tracked source: `skills/web-review/SKILL.md`
- deployed runtime copy: `~/.agents/skills/web-review/SKILL.md`
- operator template index: `docs/operations/skills/web-review-templates.md`
- Stage3 operator flow: `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`

## 운영 메모
- fresh chat + direct attachment 우선
- headless 실행이 Cloudflare 사람확인(`잠시만 기다리십시오…`, `사람인지 확인하십시오`)에 걸리면 selector/auth 문제로 오진하지 말고 fail-closed 후 screenshot/JSON 증빙을 남긴 뒤 `--headful`로 재시도
- current UI 기준 fresh chat당 약 20파일 이하 유지, mixed-item batch는 **20-40 items**(default target 30) 범위에서 partition metadata와 함께 분할
- 기본 모델은 **Thinking 5.4**
- 응답은 JSON-only 회수
- watcher raw text save는 기본 OFF, forensic 필요 시에만 `--debug-save-raw`로 `runtime/watch/raw/` cold save
- watcher completion은 `runtime/watch/unreported_watch_events.json` 큐를 거친다
- callback/taskdb sync 없이 성공 처리하지 않는다
- prompt/schema는 `runtime/templates/` canonical 1벌만 유지하고 run별 full prompt/results_template copy는 기본 금지
- evidence 탐색은 `python3 scripts/tasks/db.py evidence-search` canonical-only 기본을 사용하고 raw 검색은 `--include-raw` 명시 opt-in으로만 수행

## Sync
- source -> runtime 동기화: `bash scripts/skills/sync_web_review_skill.sh`

## 문서 원칙
- 이 문서는 overview/link만 유지한다.
- full prompt/schema는 runtime templates만 canonical로 둔다.
- Stage3 package data contract 본문은 `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`만 수정한다.
