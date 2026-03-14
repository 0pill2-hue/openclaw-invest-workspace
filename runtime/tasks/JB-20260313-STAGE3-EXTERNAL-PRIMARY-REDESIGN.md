# JB-20260313-STAGE3-EXTERNAL-PRIMARY-REDESIGN

- ticket: JB-20260313-STAGE3-EXTERNAL-PRIMARY-REDESIGN
- status: IN_PROGRESS
- checked_at: 2026-03-13 14:29 KST

## Goal
Stage3를 external ChatGPT Thinking 5.4 본선 + local prefilter/router 보조 구조로 재설계하고, analysis item 일반화와 chatter/opinion 보존 정책을 문서/스킬/코드에 반영한다.

## Reviewed targets to apply
- primary lane = external_review_primary
- local lane = prefilter / routing / dedup / grouping / priority / sanity-check support only
- input unit = analysis item (not stock sample)
- allowed item types include stock / industry / sector / macro / policy / commodity / rates-fx / theme / event / multi_asset / chatter / opinion / mixed / unknown
- noisy chatter/opinion/no-symbol item도 discard보다 low-confidence preserved item으로 처리
- Stage3 canonical output = external review normalized JSON
- Stage3 docs + web-review skill/template + package flow를 새 운영 목표에 맞게 재작성

## Next action
- Stage3 rulebook/rule docs와 web-review skill/template의 stock-sample/benchmark 중심 전제를 제거
- analysis item package builder + external qualitative scoring flow를 canonical로 문서화/구현 정렬
- proof와 landed-vs-remaining summary를 남긴다

## Landed
- `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`
  - Stage3 canonical pipeline을 analysis item package -> external primary scoring -> normalized JSON로 재정의
- `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
  - external lane를 primary scoring contract로 승격
  - batch_scoring_mode, mixed item types, chatter/opinion/no-symbol preserve policy 반영
- `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`
  - primary scoring 문서에서 adjudication / exception review 문서로 재정의
- `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`
  - Thinking 5.4 external-primary 운영 절차 신설
- `runtime/templates/stage3_external_review_prompt.txt`
  - batch_scoring_mode canonical prompt template 신설
- `runtime/templates/stage3_response_schema.json`
  - stock-only assumption 없는 mixed analysis item response schema 신설
- `skills/web-review/SKILL.md`
  - review_mode vs batch_scoring_mode 분리, Stage3 external-primary mixed item 처리 규칙 반영
- `docs/operations/skills/web-review.md`
- `docs/operations/skills/web-review-templates.md`
- `docs/invest/stage3/README.md`
  - 운영/인덱스 문서 정렬

## Remaining integration (explicit)
- core orchestrator connection은 `runtime/tmp/stage3_external_chatgpt_batch_runner.py`에 landed; 남은 것은 full browser e2e 실주행 확인뿐이다
- 기존 local-brain 산출물/benchmark temp artifacts(`runtime/tmp/stage3_external_web_package/*` 등)는 historical proof로 남아 있으며, 이번 티켓에서 일괄 정리/마이그레이션하지는 않음
- 기존 Stage3 supporting draft 문서(`STAGE3_DESIGN.md`, `STAGE3_DEEP_ANALYSIS_EXTRACTION_RUBRIC.md`)의 전면 개편은 이번 티켓 범위 밖이며, README에서 canonical/supporting 역할만 재정렬함

## Bounded validation
- `python3 -m py_compile runtime/tmp/stage3_external_chatgpt_batch_runner.py`
- `.venv/bin/python` import probe로 `prepare_stage3_runtime_batch(...)` 실행 확인
- generated runtime package에서 `response_schema.json`이 `runtime/templates/stage3_response_schema.json`와 byte-equal 확인
- generated prompt에서 `external_review_primary`, `batch_scoring_mode`, `item_index.csv` marker 확인

## Integration append (2026-03-13 KST)

### landed
- `runtime/tmp/stage3_external_chatgpt_batch_runner.py`
  - 실행 직전에 `runtime/tmp/stage3_external_primary_runtime/<batch_id>/` canonical package를 staging하도록 연결
  - `runtime/templates/stage3_external_review_prompt.txt`를 실제 batch prompt source로 사용
  - `runtime/templates/stage3_response_schema.json`를 runtime package에 복사하고, `batch_manifest.json` / `item_index.csv` / `attachment_inventory.csv` / `scoring_contract.md`를 external-primary contract 기준으로 재구성
  - 응답 JSON parse 후 runtime schema validation을 수행하고, schema mismatch면 `ok=false`로 남기도록 강화

### remaining
- historical `runtime/tmp/stage3_external_web_package/*`는 upstream proof/input provenance로만 남겨두고, 파일 자체를 일괄 마이그레이션하지는 않음
- ChatGPT UI full send/receive round-trip은 이번 subtask에서 미실행이므로 실제 browser E2E 성공 여부는 미확인

### proof
- `runtime/tasks/proofs/JB-20260313-STAGE3-EXTERNAL-PRIMARY-REDESIGN/runtime_integration_check_20260313.txt`
- probe runtime dir: `runtime/tmp/stage3_external_primary_runtime/batch_01_probe2/`
- generated runtime files:
  - `runtime/tmp/stage3_external_primary_runtime/batch_01_probe2/batch_manifest.json`
  - `runtime/tmp/stage3_external_primary_runtime/batch_01_probe2/response_schema.json`
  - `runtime/tmp/stage3_external_primary_runtime/batch_01_probe2/item_index.csv`
  - `runtime/tmp/stage3_external_primary_runtime/batch_01_probe2/batch_01_probe2_prompt.txt`

## Integration append (2026-03-14 KST)

### browser E2E status
- Stage3 external-primary `project/ChatGPT` full browser send/receive round-trip: **success 확인**
- validated path: runtime package generation -> project sender attach/model guard -> ChatGPT response watch -> JSON parse/schema/integrity audit

### landed in this subtask
- `skills/web-review/scripts/send_chatgpt_project_prompt.py`
  - project mode attachment upload + model guard + attachment visibility handling 연결
- `runtime/tmp/stage3_external_chatgpt_batch_runner.py`
  - watch 후 success 판정 경로(`complete`) 오류 수정

### success proof
- proof summary: `runtime/tasks/proofs/JB-20260313-STAGE3-EXTERNAL-PRIMARY-REDESIGN/project_e2e_20260314.md`
- successful runtime batch: `runtime/tmp/stage3_external_primary_runtime/batch_project_e2e_20260314b/`
- wrapper/send/watch:
  - `runtime/tmp/stage3_external_batch_project_e2e_20260314b_wrapper_result.json`
  - `runtime/tmp/stage3_external_batch_project_e2e_20260314b_send_result.json`
  - `runtime/tmp/stage3_external_batch_project_e2e_20260314b_watch_result.json`
- canonical outputs:
  - `runtime/tmp/stage3_external_primary_runtime/batch_project_e2e_20260314b/canonical_audit.json`
  - `runtime/tmp/stage3_external_primary_runtime/batch_project_e2e_20260314b/normalized_score_table.jsonl`

### remaining / residual
- project conversation generic `delete-after`는 아직 project-internal chat에서 안정적으로 동작하지 않아, 이번 검증 채팅 자체 자동삭제는 미완료
- ad-hoc probe에서도 watcher fallback task가 생성될 수 있어, non-ticket validation 모드 분리가 후속 개선 포인트
