status: CANONICAL
updated_at: 2026-02-18 06:10 KST
stage: 03
name: cleaning_validation
description: 정제 결과 검증(누락/중복/스키마/타임존/정합성)
inputs:
  clean_root: invest/data/clean/
  validation_script: invest/scripts/stage03_validate_refine_independent.py
outputs:
  validate_manifest: invest/reports/data_quality/manifest_stage2_validate_*.json
  validate_log: invest/logs/
run_command:
  - python3 invest/scripts/stage03_validate_refine_independent.py

quality_gates:
  - id: QG-03-01 (Independent Verdict)
    check: "verdict_*.json -> summary.FAIL <= 3"
    path: "reports/qc/verdict_*.json"
  - id: QG-03-02 (Schema Compliance)
    check: "Strict validation against invest/config/schemas/*.json"
    path: "reports/qc/VALIDATION_INDEPENDENT_*.md"
  - id: QG-03-03 (Outlier Justification)
    check: "Returns > 20% must be verified in OUTLIER_WEB_CROSSCHECK"
    path: "reports/qc/OUTLIER_WEB_CROSSCHECK_*.csv"
  - id: QG-03-04 (Sampling Audit)
    check: "Random 10% spot check error rate < 1%"
    path: "invest/scripts/stage02_qc_cleaning_10pct.py output"

failure_policy:
  - action: BLOCK_STAGE_04
    condition: "QG-03-01 status == 'FAIL' or any CRITICAL tags"
  - action: MARK_AS_DRAFT
    condition: "QG-03-03 FAILED (Unverified outliers present)"
  - action: RE-REFINE_TRIGGER
    condition: "QG-03-02 FAILED (Schema mismatch)"

repro_checklist:
  - script: "invest/scripts/stage03_validate_refine_independent.py"
  - evidence: "reports/qc/VALIDATION_INDEPENDENT_*.md"
  - verification: "Confirm verdict_*.json hash matches audit manifest"

next: stage04_validated_value.md
