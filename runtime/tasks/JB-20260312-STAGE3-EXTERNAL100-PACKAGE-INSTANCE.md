# JB-20260312-STAGE3-EXTERNAL100-PACKAGE-INSTANCE

- ticket: JB-20260312-STAGE3-EXTERNAL-WEB-PACKAGE
- status: DONE
- built_at_utc: 2026-03-12T01:25:00Z
- package_dir: `/Users/jobiseu/.openclaw/workspace/runtime/tmp/stage3_external_web_package`
- package_id: `JB-20260312-STAGE3-EXTERNAL-WEB-PACKAGE-mixed100-v1-instance1`

## What was built
- `sample_index.csv`
- `attachment_inventory.csv`
- `documents/S001.md` .. `documents/S100.md`
- `batch_manifest.json`
- `batch_01_prompt.txt` .. `batch_05_prompt.txt`

## Source basis
- primary selection corpus: `runtime/tasks/proofs/JB-20260309-STAGE3-LOCAL-APPLY_input_31d.jsonl`
- context/reference only: `runtime/stage3_calibration_sample100.jsonl` and `runtime/stage3_main_brain_package_sample100/local_benchmark_rows.jsonl`
- rationale: the reference sample100 package did not cover the spec's broader source-family mix, so the actual instance was drawn from the broader 31d workspace corpus while keeping the external package contract format.

## Output counts
- total_samples: 100
- focus_level_counts: {'macro': 20, 'stock': 50, 'industry': 30}
- source_family_counts: {'premium': 12, 'report': 8, 'telegram': 20, 'pdf_analyst_report': 18, 'ir': 6, 'conference_call': 3, 'earnings_call': 4, 'blog': 24, 'field_signal': 2, 'trade_publication': 3}
- attachment_count: 100
- attachment_bytes_total: 421367
- manifest_sha_preimage_method: `baseline.package_manifest_sha256` hashed from manifest JSON with that field empty

## Quota deviations
- none; target mix matched exactly under the implemented package heuristics
