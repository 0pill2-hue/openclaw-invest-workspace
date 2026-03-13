# JB-20260312-STAGE123-DEEP-WEB-REVIEW

- ticket: JB-20260312-STAGE123-DEEP-WEB-REVIEW
- checked_at: 2026-03-12 05:56 KST
- repo: `openclaw-invest-workspace`
- branch: `main`
- origin: `git@github.com:0pill2-hue/openclaw-invest-workspace.git`
- ready_now: `false`

## Goal
Stage1/2/3 설계·전략·코드를 GitHub 기준 commit/push baseline으로 고정한 뒤, 폴더 단위 deep web-review 준비 가능 여부를 판정한다.

## Exact review scope
### Root stage docs
- `docs/invest/STAGE123_REDESIGN_DECISIONS.md`
- `docs/invest/STAGE_EXECUTION_SPEC.md`
- `docs/invest/STAGES_OVERVIEW.md`

### Stage1 docset / code touchpoints
- `docs/invest/stage1/**`
- `invest/stages/common/stage_raw_db.py`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`

### Stage2 docset / code
- `docs/invest/stage2/**`
- `invest/stages/stage2/scripts/**`

### Stage3 docset / code
- `docs/invest/stage3/**`
- `invest/stages/stage3/scripts/**`

## Grounded working-tree facts
Relevant local deltas in current tree:
- modified: `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- modified: `invest/stages/common/stage_raw_db.py`
- modified: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- modified: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- untracked: `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`

Non-review runtime/untracked noise is large, but it is separable with path-scoped staging; it is not the primary blocker by itself.

## Assessment
- Folder-level review scope is clear: root Stage1/2/3 docs + Stage1/2/3 implementation folders above.
- A selective commit can exclude unrelated runtime artifacts.
- However, the current Stage1 code delta that belongs to the requested Stage1/2/3 review scope is `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`, and that file is the active Telegram PDF recovery implementation path.
- This ticket was explicitly scoped to avoid working that implementation.
- Therefore a full Stage1/2/3 code baseline cannot be made safely right now without one of two bad outcomes:
  1. omit the latest local Stage1 code delta from the GitHub review baseline, or
  2. sweep an in-flight Telegram PDF recovery fix into the review baseline before it is intentionally separated/stabilized.

## Blocker
Latest Stage1 in-scope code is still mixed into the Telegram PDF recovery fix path (`invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`). Until that delta is either separated/finished or intentionally excluded by decision, the requested full Stage1/2/3 GitHub reflection baseline is not clean.

## Prepared artifact
- prompt draft path: `runtime/tmp/web_review_stage123_prompt.txt`
- status: drafted with commit placeholders only; do not send before scoped commit+push exists.

## Next action
1. Separate or finish the Stage1 Telegram PDF recovery delta so the Stage1 review scope is intentional.
2. Then create a path-scoped commit/push containing only approved Stage1/2/3 design/strategy/code files.
3. Fill the prompt draft with the actual commit hash/URL and start the deep web-review from a fresh chat.
