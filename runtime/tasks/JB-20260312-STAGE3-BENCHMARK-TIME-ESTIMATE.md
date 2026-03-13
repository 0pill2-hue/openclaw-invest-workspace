# JB-20260312-STAGE3-BENCHMARK-TIME-ESTIMATE

- checked_at: 2026-03-12 05:33 KST
- corpus_proof: `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`
- calibration_proof: `runtime/tasks/JB-20260312-STAGE3-ACTUAL-CALIBRATION-RUN.md`

## Verified corpus counts used
From `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`:
- total_stage3_records: 47,763
- source_docs: blog 38,467 / telegram 2,140 / premium 426 / selected_articles 5,231 / dart 1,457 / rss 24 / macro_rss 18
- core_direct_brain_docs (blog + telegram + premium): 41,033
- expanded_direct_brain_plus_selected_articles: 46,264
- current_feature_rows: 14,560
- current_claim_cards: 361,842

## Current baseline benchmark scope
Latest baseline decision is now:
- compare `local 100 docs` vs `main 100 docs`
- use the same sample set: `runtime/stage3_calibration_sample100.jsonl`
- sample composition: 100 input records = blog 50 / telegram 25 / premium 25

Actual local calibration already executed on that same 100-doc sample:
- backend: `llama_local`
- wall time: `0.88s`
- output proof: `runtime/stage3_calibration_sample100_summary.json`

## Rough ETA (planning only)
### Baseline: local 100 vs main 100 on same sample
- local 100 is already measured at `0.88s`
- practical planning ETA for the full baseline pair is:
  - `0.88s + main_100_measured_time`
- so the remaining unknown is only the first measured `main 100` run on the same file

### Full core direct-brain corpus (41,033 docs)
Using the observed local calibration only as a lower-bound scaling reference:
- local-rate lower bound: about `6.0 min` for 41,033 docs (`41,033 / 100 * 0.88s`)

For main-brain planning, use the first measured same-sample result as the multiplier:
- full_main_eta ~= `410.33 x main_100_measured_time`
- quick examples:
  - if `main 100 = 1 min` -> full corpus about `6.84 h`
  - if `main 100 = 5 min` -> full corpus about `34.19 h`
  - if `main 100 = 10 min` -> full corpus about `68.39 h`

## Practical note
- This note is a planning estimate, not the final runtime truth.
- The old `main 1,000 + subagent 1,000` estimate is obsolete for the current baseline decision.
- Replace the planning ETA immediately after the first measured `main 100` run on `runtime/stage3_calibration_sample100.jsonl`.
