# JB-20260311-PDF-PAGEMARK-DECOMP-VERIFY

- status: READY_FOR_REVIEW
- updated_at: 2026-03-11 23:30 KST
- close_recommendation: DONE

## goal
- Verify whether Stage1 PDF page-marker insertion and PDF page decomposition persistence are actually complete.
- If the large live gap is caused by stale/mislinked state rather than real decomposition, fix it safely and leave exact before/after proof.

## what I actually fixed
I did **not** try to inflate canonical decomposition from 608 to 59k by wiring unsafe artifacts.
Instead, I fixed the real live mismatch: **the page-marked side was overstated by shared legacy extract paths**.

### Safe fix-forward applied
Touched:
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`

Change:
- canonical bucketed PDF metas no longer trust shared bucket-level `extracted.txt`
- page-marked text is now reused only when it is backed by a valid original PDF or a valid manifest/page set
- otherwise the doc is reclassified to `missing_original` / `missing_original_and_page_artifacts`

Execution:
- held `raw_db_sync.lock`
- reran `stage01_telegram_attachment_extract_backfill.py`
- allowed it to reindex the live DB once under that guarded window

No raw artifacts were deleted.
This was a metadata/contract correction, not destructive cleanup.

## root cause
The previous gap was not “59,673 real page-marked PDFs vs only 608 persisted decompositions”.
The real issue was:
- only **608** docs had valid canonical decomposition artifacts
- but **59,065** additional docs were being counted as `page_marked=1` purely because they pointed to shared legacy bucket extracts
- those shared files were not per-document canonical extracts

Exact pre-fix evidence:
- `page_marked_total`: **59,673**
- `decomposed_total`: **608**
- `page_marked_without_manifest`: **59,065**
- `available_from_extract_text`: **59,065**
- bucketed canonical metas counted as page-marked while pointing to shared bucket extracts: **59,641** docs
- distinct shared bucket extract paths behind that: **301**
- trusted page-marked docs already backed by manifest: **608**

So the large gap was mainly a **false-positive page-marked population**, not a hidden 59k decomposition persistence miss.

## before -> after (live DB)
### Before
- `pdf_documents_total`: **63,735**
- `page_marked_total`: **59,673**
- `decomposed_total`: **608**
- `page_marked_without_manifest`: **59,065**
- `available_from_extract_text`: **59,065**
- `available_from_manifest_pages`: **548**
- `available_from_original`: **60**

### After
- `pdf_documents_total`: **63,735**
- `page_marked_total`: **608**
- `decomposed_total`: **608**
- `page_marked_without_manifest`: **0**
- `page_marked_and_decomposed`: **608**
- `available_from_extract_text`: **0**
- `available_from_manifest_pages`: **548**
- `available_from_original`: **60**
- `missing_original_and_page_artifacts`: **63,127**
- `text_ready_total`: **608**
- `render_ready_total`: **608**
- `pdf_pages_total`: **9,632**

### Net effect
- false page-marked surplus removed: **59,065** docs
- live page-marked count now exactly matches live canonical decomposition count: **608 == 608**
- the original discrepancy behind this ticket is resolved

## runtime backfill proof
Latest runtime file:
- `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`

Key outputs from the corrective run:
- `finished_at=2026-03-11T14:29:08.998677+00:00`
- `duration_sec=859.442`
- `pdf_shared_legacy_extract_ignored=61071`
- `pdf_page_marked_written=576`
- `pdf_page_marked_rebuilt_from_manifest=544`
- `pdf_page_manifests_written=60`
- `pdf_db_extract_ok_total=608`
- `pdf_db_decomposed_total=608`
- `pdf_db_page_marked_total=608`
- `pdf_db_page_mapping_missing_total=63127`
- dominant failure reason: `missing_original=63129`

Interpretation:
- the run did what we wanted: stop trusting shared legacy extracts, preserve only real page-marked/decomposed docs, and refresh DB to that corrected state.

## representative samples
### Former false extract-only sample after fix
- doc: `telegram:선진짱_주식공부방_1378197756:100096`
- now:
  - `extract_rel_path=''`
  - `manifest_rel_path=''`
  - `page_marked=0`
  - `page_mapping_status='missing_original_and_page_artifacts'`
  - `extraction_status='failed'`
  - `extraction_reason='missing_original'`

### Valid manifest-backed sample after fix
- doc: `telegram:Nihil_s_view_of_data_information_viewofdata:3008`
- now:
  - `extract_rel_path='outputs/raw/qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/msg_3008/extracted.txt'`
  - `manifest_rel_path='qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/bucket_064/msg_3008__pdf_manifest.json'`
  - `page_marked=1`
  - `page_mapping_status='available_from_manifest_pages'`
  - `extraction_status='ok'`

## what remains genuinely blocked
The corrected state also makes the real ceiling explicit:
- real decomposed docs remain **608**
- real text/render-ready docs remain **608**
- the rest are now honestly classified as missing original/page artifacts

Why I could not push real decomposition above 608 overnight:
1. Telegram redownload is blocked in this workspace
   - `~/.config/invest/invest_autocollect.env` has `TELEGRAM_API_ID=""` and `TELEGRAM_API_HASH=""`
2. Raw DB history does not contain recoverable original-file history for the non-manifest gap docs
   - recoverable original history for the corrected gap set: **0**

Therefore there is **no safe local-only path** here to manufacture new real canonical decompositions beyond the current 608.
That would require recovering originals from Telegram or another external source.

## final determination
### Resolved in this ticket
- Yes: the live **page-marked vs decomposition mismatch** was real, and it has now been corrected.
- The corpus no longer claims **59,673** page-marked docs when only **608** have real canonical decomposition support.

### Not resolved in this ticket
- No: the broader corpus is still not recoverably decomposed beyond **608** docs, because the missing originals are genuinely unavailable in the current workspace.

## ticket recommendation
- **DONE**

Reason:
- the discrepancy this ticket was supposed to verify/fix is now removed in the live DB
- the remaining limit is a separate upstream recovery problem (original recovery), not a stale canonical persistence mismatch anymore

## exact proof paths
- report: `runtime/tasks/JB-20260311-PDF-PAGEMARK-DECOMP-VERIFY.md`
- proof JSON: `runtime/tasks/proofs/JB-20260311-PDF-PAGEMARK-DECOMP-VERIFY.json`
- before snapshot: `runtime/tasks/proofs/JB-20260311-PDF-PAGEMARK-DECOMP-VERIFY.before_fix.json`
- live DB: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- runtime status: `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
