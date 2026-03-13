# JB-20260311-WEB-REVIEW-STAGE12-IMPROVE

- status: REVIEWED
- updated_at: 2026-03-11 20:xx KST
- close_recommendation: DONE

## scope checked
- `docs/invest/stage1/stage01_data_collection.md`
- `docs/invest/stage1/RUNBOOK.md`
- `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- `invest/stages/common/stage_pdf_artifacts.py`
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`

## advisory web-review input inspected
### available Stage1/2 review artifacts in workspace
- prompt file: `runtime/tmp/web_review_stage12_prompt.txt`
- screenshots: `runtime/browser-profiles/web_review_stage12_send.png`, `runtime/browser-profiles/web_review_stage12_watch.png`

### what the review said
- **미확인 (workspace 내 가시 증빙 기준)**
- Stage1/2 전용 web-review의 로컬 증빙에서는 **프롬프트만 확인되고 assistant 응답 본문은 확인되지 않았다.**
- OCR/inspection result used for recovery:
  - `runtime/browser-profiles/web_review_stage12_watch.png` → `NO_RESPONSE_VISIBLE`
  - `runtime/browser-profiles/web_review_stage12_send.png` → prompt only
  - multi-screenshot inspection summary → `STAGE12_RESULT=NONE`
- 참고용 선행 티켓(`runtime/tasks/JB-20260311-WEB-REVIEW-FIRST-RUN.md`)에는 Stage1/2 전용 결과가 아니라 earlier first-run 결과만 있다.

## local state judgment
### 1) baseline parity
- requested review baseline commit: `e1c9384fa`
- current HEAD scoped diff vs baseline: **no diff in all scoped files**
- judgment: review 대상이었던 Stage1/2 scope는 현재도 같은 내용이라, 현재 판단은 baseline 그대로에 대해 유효하다.

### 2) docs/scripts consistency check
- Stage1 data appendix already states DB archive SSOT and Stage2 mirror contract:
  - proof: `docs/invest/stage1/stage01_data_collection.md`
- Stage1 runbook already documents bounded PDF backfill / canonical single-writer / Stage1→2 fail-close chain:
  - proof: `docs/invest/stage1/RUNBOOK.md`
- Stage1 PDF deliverable contract already distinguishes logical document success from physical `.pdf` retention and fixes page-marker/page-mapping fields:
  - proof: `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
- Stage2 rulebook already documents:
  - DB mirror input source
  - Telegram PDF inline promotion
  - link enrichment / live fetch opt-in
  - corpus-level dedup
  - processed index + report schema
  - proof: `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- Stage2 implementation already contains matching logic for:
  - `stage1_raw_db_mirror` input source
  - semantic tagging fields
  - Telegram PDF promotion
  - sidecar canonical URL usage
  - corpus dedup registry/report keys
  - proof: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- Stage1 PDF helper/backfill code already contains matching page-marker / manifest rebuild / bounded fallback logic:
  - proof: `invest/stages/common/stage_pdf_artifacts.py`
  - proof: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`

### 3) token-cost judgment
- judgment: **MEDIUM but acceptable / no must-fix**
- reason:
  - scope size is large in absolute lines, but the docs are already split by role (`appendix` / `runbook` / `deliverable contract` / `rulebook`) rather than collapsed into one mega-file.
  - most repeated PDF rules are intentional cross-document contract restatements for different audiences (collector schema vs operator runbook vs deliverable audit), not accidental contradictory duplication.
- therefore: no high-value token-cost-only rewrite is justified now.

## edits made
- none

## verification
- static compile passed:
  - `python3 -m py_compile invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py invest/stages/common/stage_pdf_artifacts.py invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- scoped git status before decision: clean/no scoped modifications
- scoped baseline comparison: no diff from `e1c9384fa`

## final judgment
- **No real change needed right now.**
- 이유:
  1. Stage1/2 web-review answer itself is not recoverable from accessible workspace artifacts, so there is no concrete advisory finding to apply.
  2. Independently, current scoped files are already consistent on the key contracts the review prompt asked about (must-fix, ambiguous wording, duplicated rules, token-cost risk).
  3. No doc/code mismatch or syntax-level breakage was found in the scoped files.
- Git sync: not performed, because no justified code/doc edit was made.

## proof paths
- `runtime/tmp/web_review_stage12_prompt.txt`
- `runtime/browser-profiles/web_review_stage12_send.png`
- `runtime/browser-profiles/web_review_stage12_watch.png`
- `runtime/tasks/JB-20260311-WEB-REVIEW-FIRST-RUN.md`
- `docs/invest/stage1/stage01_data_collection.md`
- `docs/invest/stage1/RUNBOOK.md`
- `docs/invest/stage1/PDF_DELIVERABLE_CONTRACT.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- `invest/stages/common/stage_pdf_artifacts.py`
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`

## close recommendation
DONE
