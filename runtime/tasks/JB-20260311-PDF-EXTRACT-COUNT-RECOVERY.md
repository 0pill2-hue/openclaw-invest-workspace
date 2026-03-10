# JB-20260311-PDF-EXTRACT-COUNT-RECOVERY

## Result
- Status: PARTIAL
- Safe code fix applied for the real bottleneck/counting bug.
- No DB writer/indexer path changed. Single-writer safety preserved.
- Runtime status JSONs were audited, but not regenerated in this turn, so their on-disk counters remain pre-fix snapshots.

## Requested Audit Targets
### 1) `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- Audited and patched.
- Actual failure mode was in original-path inference for legacy `meta.json` entries, not a genuine 63k-scale Swift/PDFKit inability to open valid PDFs.

### 2) `invest/stages/common/stage_pdf_artifacts.py`
- Audited only, unchanged.
- Relevant because manifest/page-text/render generation is here.

### 3) `invest/stages/common/stage_raw_db.py`
- Audited only, unchanged.
- Relevant because DB/pdf-index reflected counts come from here.

### 4) `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- Audited.
- Snapshot shows:
  - `meta_scanned=64140`
  - `supported_candidates=63737`
  - `attempted=63349`
  - `reused_existing=388`
  - `extracted_ok=0`
  - `failed=63349`
  - `skipped_missing_original=0`
  - `reason_counts.swift_pdf_open_failed=63346`
- Proof path: `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`

### 5) `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- Audited.
- Snapshot shows DB/pdf-index reflection already sees:
  - `pdf_index.indexed_documents=127467`
  - `pdf_index.documents_with_text=1197`
  - `pdf_index.documents_with_renders=1197`
  - `pdf_index.indexed_pages=18765`
- Proof path: `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`

## Exact Evidence Counts (filesystem + status)
### A. Raw PDF/meta population
- PDF meta files on disk: `127467`
- Unique `(channel_slug, message_id)` PDF docs: `63735`
- Duplicate/meta split:
  - bucketed `*__meta.json`: `63732`
  - legacy `meta.json`: `63735`
- Meaning: the apparent ~127k PDF population is roughly two metadata layers over ~63.7k unique Telegram PDF messages.
- Proof root: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram`

### B. Actual artifact-bearing counts
- Original PDF-like files physically present: `1213`
  - derived from both metadata layers combined
- Non-empty extracted text docs (`extracted.txt` or `*__extracted.txt`): `635`
- Manifest-backed docs with text pages: `1197`
- Manifest-backed docs with rendered pages: `1197`
- Page text files present: `11102`
- Rendered page files present: `11449`
- Proof roots:
  - originals/text/meta/manifests: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram`
  - DB/index reflection: `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`

### C. Why 60k+ candidates collapse to ~600-1200 effective items
- Unique PDF docs available in metadata: `63735`
- Unique docs with a real original file still present: `608`
- Unique docs with extracted text present: `607`
- DB/pdf-index reflected docs with text/renders: `1197`
- Conclusion: the ceiling is not “63k valid PDFs waiting to extract”; it is “~63.7k metadata rows, but only ~608 unique docs still have real originals on disk, while ~607-1197 already have downstream text/render reflection”.

## Actual Bottleneck / Failure Mode
### 1) Mass `swift_pdf_open_failed` was mostly a path-inference bug
In `stage01_telegram_attachment_extract_backfill.py`, `_infer_original_path(...)` previously did this pattern:
- resolve `original_path` with fallback `Path("")`
- return it if `.exists()`

When `original_path` was blank, `Path("")` resolved to the current working directory, which **does exist** but is **not a file**.
That caused thousands of legacy entries with no original PDF to be treated as if they had an original path, so the extractor attempted to open a directory as a PDF and surfaced `swift_pdf_open_failed`.

This exactly matches the observed split:
- bucketed layer already shows `missing_original=63127`
- legacy layer shows `swift_pdf_open_failed=63127`
- legacy real original files found: only `608`
- legacy directory-bug candidates: `63127`

So the 63k Swift failures were overwhelmingly a **directory-as-PDF false positive**, not 63k real PDFs that Swift/PDFKit could not open.

### 2) Counting disconnect
- Backfill status snapshot says `skipped_missing_original=0`, which is contradicted by the filesystem reality above.
- Raw DB/pdf index snapshot already reflects `1197` docs with text/renders.
- Therefore the operational confusion came from mixing:
  1. raw metadata candidate counts,
  2. backfill run-local failure counts distorted by the directory bug,
  3. downstream manifest/render/index counts that reflect actual decomposed artifacts.

## Code Changes Applied
### Touched path
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`

### Why
To stop missing-original legacy entries from being treated as valid original PDFs, and to make future status counts reflect `missing_original` instead of bogus `swift_pdf_open_failed`.

### Minimal safe edits
1. `_infer_original_path(...)`
   - stopped accepting empty-path fallback as a valid original
   - now requires the resolved path to exist **and be a file**
2. legacy reconcile branch
   - when no canonical original file exists and extraction is not already `ok`, it now forces `extraction_reason="missing_original"`
3. main extraction loop
   - missing-original guard now requires `original_path.is_file()` as well as `exists()`

## Verification
- Syntax check passed:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py invest/stages/common/stage_pdf_artifacts.py invest/stages/common/stage_raw_db.py`

## Why this is PARTIAL, not FIXED
- The core bug causing false `swift_pdf_open_failed` counts is fixed.
- But I did **not** rerun the long backfill in this turn, so:
  - `telegram_attachment_extract_backfill_status.json` is still the stale pre-fix snapshot
  - DB/pdf-index counts were audited, not regenerated
- Also, the deeper reality remains: most of the 63k+ metadata candidates do not have recoverable original PDFs on disk anymore, so no code-only change can turn that into 63k extracted documents.

## Recommended Next Step
1. Rerun only `stage01_telegram_attachment_extract_backfill.py` after this patch.
   - Expected immediate effect: most legacy `swift_pdf_open_failed` noise should shift to `missing_original`, and wasted attempts should collapse.
2. After that, rerun the raw DB sync/index reflection step once (single writer only) to refresh:
   - `telegram_attachment_extract_backfill_status.json`
   - `raw_db_sync_status.json`
3. Judge success using these four numbers, separately:
   - original PDFs physically present
   - non-empty extracted text docs
   - rendered/page-text artifact counts
   - DB/pdf-index reflected docs with text/renders

## Proof Paths
- Code fix: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- Manifest/render logic audited: `invest/stages/common/stage_pdf_artifacts.py`
- DB/index logic audited: `invest/stages/common/stage_raw_db.py`
- Backfill status snapshot: `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- DB/pdf-index snapshot: `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- Artifact tree audited: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram`

## 2026-03-11 Live accumulation check
### Latest completed backfill snapshot
- `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json` now shows a completed post-fix run:
  - `attempted=304`
  - `extracted_ok=301`
  - `failed=80259`
  - `skipped_missing_original=80256`
  - `pdf_meta_total=63735`
  - `pdf_extract_ok_total=46607`
  - `finished_at=2026-03-10T23:01:22.076464+00:00`
- This is materially different from the stale pre-fix snapshot (`extracted_ok=0`, `swift_pdf_open_failed≈63k`) and confirms the path bug fix is taking effect in the runtime status layer.

### Direct filesystem reality after the completed run
Canonical unique-PDF audit over `outputs/raw/qualitative/attachments/telegram` shows:
- unique PDF docs: `63735`
- unique docs with recoverable original file: `608`
- unique docs with extracted text file present: `46607`
- unique docs with manifest present: `608`
- unique docs with text pages: `608`
- unique docs with render pages: `608`
- page text files: `5665`
- page render files: `5840`

Interpretation:
- The post-fix run clearly created/normalized many `extract_path`/text artifacts (`46607` docs now have extracted text files), but **real decomposed PDF support artifacts** (manifest + per-page text/render based on an actual original PDF) remain capped at `608` docs, because recoverable originals on disk still cap out at `608`.

### Manifest census proves stale failure noise still dominates
Direct manifest census shows:
- manifest files on disk: `41980`
- manifests with `page_count>0`: `608`
- manifests with written text pages: `608`
- manifests with written render pages: `608`
- dominant stale manifest state: `41372 × (text_status=failed, render_status=failed, reason=swift_pdf_open_failed)`

This means a large amount of old failed manifest noise still exists on disk from pre-fix runs, but those files do **not** represent newly decomposed PDFs.

### Short live-growth sample while a backfill PID was still active
- Active PID observed: `30641` (`stage01_telegram_attachment_extract_backfill.py`)
- 15-second on-disk delta sample during that active PID:
  - `extracted_files`: `936 -> 936` (`Δ 0`)
  - `manifest_files`: `41980 -> 41980` (`Δ 0`)
  - `page_text_files`: `5665 -> 5665` (`Δ 0`)
  - `page_render_files`: `5840 -> 5840` (`Δ 0`)
- 20-second status-file sample:
  - `telegram_attachment_extract_backfill_status.json` mtime delta: `0`

### Conclusion after live verification
- **Yes**, the fix is real enough that a completed rerun no longer reports the old bogus `swift_pdf_open_failed≈63k` pattern and it did record `301` actual extraction successes plus `missing_original` reclassification.
- **No**, there is still no evidence of meaningful ongoing growth in *real decomposed PDF throughput* beyond the ~`608` docs that still have recoverable originals. A short live sample stayed flat even while a backfill PID remained active.
- Hard ceiling/blocker remains: most of the `63735` PDF candidates do not have recoverable original PDFs on disk anymore; reruns can normalize metadata/text sidecars, but they cannot manufacture new per-page manifests/renders without those originals.

### Concrete next action
- Wait for the current backfill PID to exit, then run the single-writer DB reflection step once (`invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`) to refresh `raw_db_sync_status.json` from the now-post-fix artifact state.
- If count clarity matters, separately plan cleanup/rebuild of stale failed `*__pdf_manifest.json` artifacts so manifest counts stop mixing old pre-fix failures with current live state.
