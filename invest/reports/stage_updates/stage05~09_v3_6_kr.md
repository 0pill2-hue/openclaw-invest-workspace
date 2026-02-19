# stage05~09_v3_6_kr

- generated_at: 2026-02-19T05:17:57
- scope: KRX ONLY
- external_proxy_role: comparison_only

## RULEBOOK update before Stage05 (before/after)
- before: invest/docs/strategy/RULEBOOK_V3.md had no explicit low-turnover 3-rule + internal 3000% gate section
- after: invest/docs/strategy/RULEBOOK_V3.md updated to V3.4 with
  - minimum holding 20 trading days
  - replacement only at +15% edge
  - monthly replacement cap 30%
  - Stage05 internal 3000% hard gate (internal 3 baselines)
- sync: invest/docs/strategy/RULEBOOK_V1_20260218.md stage gate section updated with internal 3000% hard gate + external_proxy comparison-only

## proof paths
- invest/docs/strategy/RULEBOOK_V3.md
- invest/docs/strategy/RULEBOOK_V1_20260218.md
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_v3_6_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v3_6_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage07_candidates_cut_v3_6_kr.json

## Required policy fields
- baseline_internal_best_id: qualitative
- baseline_internal_best_return: 5.716009 (571.60%)
- internal_3000_gate_pass: fail
- 버려진 후보 수: 0
- 버려진 후보 사유 분해: {}
- 최종 챔피언이 internal baseline 최고를 이겼는지 여부: N/A

## Stage status
- Stage05: FAIL_STOP
- Stage06: NOT_RUN
- Stage07: NOT_RUN
- Stage08: NOT_RUN
- Stage09: NOT_RUN

## FAIL_STOP
- reason: FAIL_STOP: Stage05 internal 3000% hard gate not met

## Outputs
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage05_baselines_v3_6_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage06_candidates_v3_6_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/results/validated/stage07_candidates_cut_v3_6_kr.json
- /Users/jobiseu/.openclaw/workspace/invest/reports/stage_updates/stage05~09_v3_6_kr.md
