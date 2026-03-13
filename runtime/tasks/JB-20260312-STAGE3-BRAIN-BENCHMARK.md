# JB-20260312-STAGE3-BRAIN-BENCHMARK

- checked_at: 2026-03-12 05:25 KST
- status: BLOCKED

## Goal
Determine whether the Stage3 benchmark is executable now for three comparison lanes: main brain 1,000 docs, subagent 1,000 docs, and external-review lane using <=100 directly attached files, with score/grounding(reasoning evidence)/latency comparison.

## Prerequisite check
- Stage3 local-brain pipeline exists and has canonical input/output proofs: `invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py`, `invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json`.
- Current Stage3 run summary proves corpus availability (`records_loaded=47763`, `claim_cards_generated=361842`) and local-brain output generation, but it exposes no benchmark fields for per-doc latency, reasoning traces, or cross-lane score delta comparison.
- Planning note exists for `main 1,000 + subagent 1,000`, but it is estimate-only and explicitly says real latency must still be benchmarked: `runtime/tasks/JB-20260312-STAGE3-BENCHMARK-TIME-ESTIMATE.md`.
- The direct-brain scoring design ticket is still blocked and its expected design doc is missing: `runtime/tasks/JB-20260312-STAGE3-BRAIN-SCORING-DESIGN.md`, expected proof `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md` = missing.
- Web-review skill/tooling exists only for commit-based ChatGPT Pro review, not for <=100 attached data files with per-file Stage3 scoring outputs, so the required external-review lane contract is not implemented.

## Blocker
Not executable now because the Stage3 direct-brain scoring contract/output spec is still missing and there is no implemented external-review lane that accepts <=100 attached files and returns per-file scores, evidence, and latency comparable to main/subagent runs.

## Next action
Finish and land `docs/invest/stage3/STAGE3_BRAIN_SCORING_DESIGN.md`, then define/implement one benchmark harness and one external-review attachment schema that emit the same per-file output fields (score, evidence/reasoning, latency) for main, subagent, and external-review lanes before running the 1,000/1,000 benchmark.
