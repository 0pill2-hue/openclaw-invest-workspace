# JB-20260312-STAGE3-ACTUAL-CALIBRATION-RUN

- ticket: JB-20260312-STAGE3-ACTUAL-CALIBRATION-RUN
- status: IN_PROGRESS
- checked_at: 2026-03-12 05:28 KST

## Actual runs executed
### 20-doc smoke run
- sample file: `runtime/stage3_calibration_sample20.jsonl`
- mix: blog 10 / telegram 5 / premium 5
- command backend: `llama_local`
- wall time: `0.53s`
- outputs:
  - `runtime/stage3_calibration_sample20_features.csv`
  - `runtime/stage3_calibration_sample20_claim_cards.jsonl`
  - `runtime/stage3_calibration_sample20_summary.json`
- result summary:
  - records_loaded=20
  - claim_cards_generated=125
  - rows_output=41

### 100-doc calibration run
- sample file: `runtime/stage3_calibration_sample100.jsonl`
- mix: blog 50 / telegram 25 / premium 25
- command backend: `llama_local`
- wall time: `0.88s`
- outputs:
  - `runtime/stage3_calibration_sample100_features.csv`
  - `runtime/stage3_calibration_sample100_claim_cards.jsonl`
  - `runtime/stage3_calibration_sample100_summary.json`
- result summary:
  - records_loaded=100
  - claim_cards_generated=611
  - rows_output=158
  - unique_symbols=73
  - dominant_axes: bm=562, persistence=31, upside=12, downside=6

## Notes
- This is an actual executed run, not an estimate.
- Current implementation is the existing Stage3 script path; it does not yet prove the future expanded direct-brain design quality by itself.
- Current pipeline latency is very low, so next comparison should focus on quality deltas and whether `llama_local` path is genuinely using richer reasoning vs lightweight local heuristics.

## Next action
- Compare same sample against main-brain/subagent/external-review lanes.
- Validate whether current `llama_local` backend behavior is semantically rich enough for the intended direct-brain design.
