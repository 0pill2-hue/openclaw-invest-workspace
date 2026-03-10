# JB-20260311-STAGE1-LINK-DEDUP-REPORT proof

- generated_at_kst: 2026-03-11 07:55:17
- code_verification: py_compile ok + synthetic sidecar/dedup check passed
- stage1_sidecar_files: 41980
- stage1_sidecar_blocks_written_files: 904
- stage1_sidecar_canonical_urls_total: 291843
- raw_db_sync_id: 20260310T224733Z
- raw_db_inserted_files: 1
- raw_db_updated_files: 6536

## Prefix range/count report

| prefix | active_db_rows | raw_output_files | stage2_mirror_files | min_date | max_date |
| --- | ---: | ---: | ---: | --- | --- |
| qualitative/text/blog/ | 40939 | 40939 | 40939 | 2026-03-05 | 2026-03-11 |
| qualitative/text/telegram/ | 73 | 73 | 73 | 2021-10-12 | 2026-03-11 |
| qualitative/text/premium/startale/ | 972 | 972 | 972 |  |  |
| qualitative/link_enrichment/text/blog/ | 40939 | 40939 | 40939 | 2026-03-10 | 2026-03-10 |
| qualitative/link_enrichment/text/telegram/ | 69 | 69 | 69 | 2026-03-10 | 2026-03-10 |
| qualitative/link_enrichment/text/premium/startale/ | 972 | 972 | 972 | 2026-03-10 | 2026-03-10 |

## PDF index summary

- pdf_documents.count=63735
- pdf_documents.message_date_range=20191029..20260309
- pdf_pages.count=9469

## Git scoped status

- ` M docs/invest/stage1/README.md`
- ` M docs/invest/stage1/RUNBOOK.md`
- ` M docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
- ` M docs/invest/stage1/stage01_data_collection.md`
- ` M docs/invest/stage2/README.md`
- ` M docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- ` M invest/stages/stage1/scripts/stage01_daily_update.py`
- ` M invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- `?? invest/stages/common/stage_raw_db.py`
- `?? invest/stages/stage1/scripts/stage01_collect_link_sidecars.py`
- `?? runtime/tasks/JB-20260311-STAGE1-LINK-DEDUP-REPORT.md`
- `?? runtime/tasks/proofs/JB-20260311-STAGE1-LINK-DEDUP-REPORT.proof.json`
- `?? runtime/tasks/proofs/JB-20260311-STAGE1-LINK-DEDUP-REPORT.proof.md`

## Suggested commit

- stage1/stage2: move link sidecars into raw-db dedup flow
