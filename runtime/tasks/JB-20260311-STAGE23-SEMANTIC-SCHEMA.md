# JB-20260311-STAGE23-SEMANTIC-SCHEMA

## Status
- recommendation: DONE
- change_type: Rule

## What changed
1. **Stage3 canonical input schema unified**
   - `invest/stages/stage3/scripts/stage03_build_input_jsonl.py`
   - Added one deterministic semantic-enrichment pass at the canonical convergence point, applied to every built row before output/dedup.
   - Every Stage3 input row now carries the same semantic contract:
     - `target_levels`
     - `macro_tags`
     - `industry_tags`
     - `stock_tags`
     - `event_tags`
     - `impact_direction`
     - `horizon`
     - `region_tags`
   - Also normalizes `source_family` canonically and stamps `semantic_version=stage-semantic-20260311-r1`.

2. **Stage2 qualitative classification payload extended**
   - `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
   - Existing Stage2 text/selected-articles classification payloads now keep old compatibility fields (`primary_*`, `mentioned_*`) and additionally expose the same deterministic semantic fields above.
   - This keeps Stage2 sidecars/contracts aligned with the Stage3 canonical schema without introducing remote model dependency.

3. **Docs/contracts updated**
   - `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
   - `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`
   - `docs/invest/stage3/STAGE3_DESIGN.md`
   - Updated docs to reflect the new semantic contract boundary and field meanings.

## Deterministic implementation notes
- Semantic tagging is rule-based only.
- Tagging uses deterministic keyword/name-match heuristics for:
  - macro topics
  - industries
  - stock codes
  - event tags (`order|rights_issue|lawsuit|guidance`)
  - impact direction
  - horizon
  - region tags
- Existing downstream-required fields were preserved; new fields were only added.

## Files changed
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- `invest/stages/stage3/scripts/stage03_build_input_jsonl.py`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage3/STAGE3_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage3/STAGE3_DESIGN.md`
- `memory/2026-03-11.md`

## Verification
### 1) Syntax / import-level validation
```bash
python3 -m py_compile \
  invest/stages/stage2/scripts/stage02_onepass_refine_full.py \
  invest/stages/stage3/scripts/stage03_build_input_jsonl.py
```
- result: PASS

### 2) Targeted Stage3 builder run
```bash
python3 invest/stages/stage3/scripts/stage03_build_input_jsonl.py \
  --out-jsonl runtime/tmp/stage3_semantic_input_sample.jsonl \
  --summary-json runtime/tmp/stage3_semantic_input_sample.summary.json \
  --text-lookback-days 30 \
  --telegram-max-files 1 \
  --telegram-max-messages-per-file 5 \
  --blog-max-files 1 \
  --premium-max-files 1 \
  --selected-articles-max-files 1
```
- result: PASS
- proof paths:
  - `runtime/tmp/stage3_semantic_input_sample.jsonl`
  - `runtime/tmp/stage3_semantic_input_sample.summary.json`
  - `invest/stages/stage3/outputs/manifest_stage3_input_build_20260311_173632.json`

### 3) Semantic-field proof observed in output
Verified rows in `runtime/tmp/stage3_semantic_input_sample.jsonl` include the new fields for multiple source families:
- `dart`
- `news_rss`
- `news_rss_macro`
- `text_blog`
- `market_selected_articles`

Representative proof path:
- `runtime/tmp/stage3_semantic_input_sample.jsonl`

## Notes / caveats
- Stage2 runtime classification sidecar regeneration was not force-rerun globally in this task; the code path and contract are updated, and Stage3 canonical input verification was executed directly.
- Semantic tags are intentionally conservative deterministic heuristics for now; they provide one common schema without introducing model dependency.

## Close recommendation
- DONE
