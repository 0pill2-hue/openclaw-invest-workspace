status: CANONICAL
updated_at: 2026-02-18 06:10 KST
stage: 02
name: data_cleaning
description: raw -> clean/quarantine 분리 및 정제 규칙 적용
inputs:
  raw_root: invest/data/raw/
  rulebook:
    - invest/docs/architecture/CONTAMINATION_RULEBOOK_V1.md
process:
  - 원천 raw를 오염 판정 규칙으로 clean/quarantine 분리
  - clean 우선 경로를 후속 단계 입력으로 고정
outputs:
  clean_root: invest/data/clean/
  quarantine_root: invest/data/quarantine/
  audit_manifest: invest/reports/data_quality/organize_existing_data_manifest_*.json
run_command:
  - python3 invest/scripts/onepass_refine_full.py --force

quality_gates:
  - id: QG-02-01 (Conservation)
    check: "count(raw) == count(clean) + count(quarantine)"
    path: "reports/logs/STAGE02_VALIDATE_REFINE_*.log"
  - id: QG-02-02 (Logical Invariant)
    check: "High >= Low and High >= Close and Low <= Close"
    path: "invest/data/clean/production/**/*.csv"
  - id: QG-02-03 (Temporal Monotonicity)
    check: "Date index must be strictly increasing per symbol"
    path: "invest/data/clean/production/**/*.csv"
  - id: QG-02-04 (Quarantine Rate Cap)
    check: "quarantine_count / total_count < 0.15"
    path: "reports/logs/STAGE02_VALIDATE_REFINE_*.log"

failure_policy:
  - action: STOP_PIPELINE
    condition: "QG-02-01 FAILED (Data Leakage/Loss detected)"
  - action: AUTO_QUARANTINE_AND_LOG
    condition: "QG-02-02 or QG-02-03 FAILED (Record-level corruption)"
  - action: NOTIFY_AND_REVISE_RULES
    condition: "QG-02-04 FAILED (Too much noise in raw data)"

repro_checklist:
  - script: "invest/scripts/onepass_refine_full.py --force"
  - validation: "Verify _processed_index.json signature matches raw input"
  - artifact_check: "Inspect invest/data/quarantine/production for reason tags"

next: stage03_cleaning_validation.md
