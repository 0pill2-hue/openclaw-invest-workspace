status: CANONICAL
updated_at: 2026-02-18 19:28 KST
stage: 04
name: validated_value
description: VALIDATED 밸류 산출(메인 신호 계산)
inputs:
  clean_root:
    - invest/data/clean/production/kr/ohlcv
    - invest/data/clean/production/kr/supply
  value_script: invest/scripts/calculate_stage3_values.py
outputs:
  value_report: reports/stage_updates/STAGE3_VALUE_RUN_*.json
  value_manifest: invest/reports/data_quality/manifest_stage3_value_*.json
run_command:
  - python3 invest/scripts/calculate_stage3_values.py
proof:
  - reports/stage_updates/STAGE3_VALUE_RUN_*.json
  - invest/reports/data_quality/manifest_stage3_value_*.json

quality_gates:
  - id: QG-04-01 (Z-Score Normalization)
    check: "|Mean| < 0.05 and |Std - 1.0| < 0.1 for factor scores"
    path: "reports/stage_updates/STAGE3_VALUE_RUN_*.json"
  - id: QG-04-02 (Finite Score Integrity)
    check: "NaN rate < 0.5% in VALUE_SCORE (excluding lead-in)"
    path: "invest/data/value/stage3/**/*.csv"
  - id: QG-04-03 (Liquidity Filter)
    check: "AvgVol < Threshold symbols must have null scores"
    path: "invest/data/value/stage3/**/*.csv"
  - id: QG-04-04 (Continuity)
    check: "continuity_flag == 'OK' or 'WARN' (Current Baseline: < 70% warn rate)"
    path: "reports/stage_updates/STAGE3_VALUE_RUN_*.json"

failure_policy:
  - action: USE_STALE_FALLBACK
    condition: "QG-04-01 or QG-04-02 FAILED (Numerical instability)"
  - action: ACCEPT_AS_DRAFT
    condition: "QG-04-04 == 'WARN' (Gaps present but within baseline)"
  - action: TRIGGER_RECOVERY_CHAIN
    condition: "value_script exit code != 0"

repro_checklist:
  - script: "invest/scripts/calculate_stage3_values.py"
  - baseline: "Ensure invest/data/clean/production state is locked"
  - verification: "Compare VALUE_SCORE_RAW with local calc for 1 asset"

next: stage05_baseline_3track.md
