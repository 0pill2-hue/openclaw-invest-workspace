# JB-20260313-STAGE12-PDF-MUSTFIX-RUNTIME

- ticket: JB-20260313-STAGE12-PDF-MUSTFIX-RUNTIME
- status: PARTIAL_DONE
- checked_at: 2026-03-13 14:57 KST

## Goal
Stage1/Stage2 PDF/backfill/runtime의 must-fix를 적용해 bounded stop, silent fallback, placeholder completeness로 인한 오판을 줄인다.

## Landed
1. Stage2 raw-files fallback 기본 hard-fail(기본 deny) + 명시 opt-in
- file: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- added: `STAGE2_ALLOW_RAW_FILES_FALLBACK`(default `0`)
- added: `STAGE2_INPUT_SOURCE_STATUS` (`ok` / `degraded_opt_in` / `blocked_raw_files_fallback_opt_in_required`)
- added: `_enforce_input_source_policy()`; blocked 상태면 처리 시작 전 `SystemExit`
- reporting/index 메타에 `input_source` + `input_source_status` + `raw_files_fallback_opt_in` 반영

2. Stage2 PDF status taxonomy 도입 + 진단 로직 분리
- file: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- added helpers:
  - `_telegram_pdf_manifest_diag`
  - `_pick_telegram_pdf_status`
  - `_collect_telegram_pdf_diag`
  - `_record_telegram_pdf_diag_stats`
- taxonomy wired:
  - `promoted`
  - `bounded_by_cap`
  - `recoverable_missing_artifact`
  - `extractor_unavailable`
  - `parse_failed`
  - `placeholder_only`
- per-message meta 및 aggregate report(json/md) 모두에 상태/카운터 반영
- multi-attachment aggregate 시 page/char counters가 중복 가산되지 않도록 합산 경로 보정

3. 페이지 카운터 분리 저장/보고 (declared/indexed/materialized/placeholder)
- files:
  - `invest/stages/common/stage_pdf_artifacts.py`
  - `invest/stages/common/stage_raw_db.py`
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- manifest(`stage_pdf_artifacts`)에 분리 필드 추가:
  - `declared_page_count`
  - `indexed_page_rows` (실제 indexed rows 유지, declared와 혼합하지 않음)
  - `materialized_text_pages`
  - `materialized_render_pages`
  - `placeholder_page_rows`
  - `bounded_by_cap`
- raw DB(`pdf_documents`) 스키마 확장:
  - same separated counters + `bounded_by_cap` + `pdf_status`
- Stage1 status payload/DB totals에 분리 카운터 + taxonomy 기반 카운터 반영

4. Stage1 canonical success 계약 정렬(original/raw PDF 비필수)
- file: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- added canonical readiness counter:
  - local/meta 기준: `pdf_local_canonical_ready_total`
  - db 기준: `pdf_db_canonical_ready_total`
  - final payload: `pdf_canonical_ready_total`
- missing original이어도 manifest/extract usable이면 canonical readiness 집계 가능하도록 보고 계약 강화

5. bounded validator/report 확장
- Stage1 status payload에 구분 필드 추가:
  - `pdf_bounded_by_cap_total`
  - `pdf_recoverable_missing_artifact_total`
  - `pdf_placeholder_only_total`
  - `pdf_extractor_unavailable_total`
  - `pdf_parse_failed_total`
- Stage2 report(json/md)에 PDF status 카운트 + 분리 page 카운터 집계 추가

6. monolith 책임 분리의 최소 착수
- Stage2에서 input-source policy 로직과 PDF diagnostic 로직을 별도 helper로 분리해 후속 split 기준선 확보.

## Remaining (bounded scope outside this patch)
1. Stage2 onepass 대규모 분해(파일/모듈 단위)는 미완료.
2. `pdf_documents` 신규 컬럼을 적극 소비하는 다운스트림 리포터/대시보드 전면 반영은 후속 필요.
3. live long-run 데이터 재처리 검증(대량 스캔)은 본 티켓의 bounded validation 범위 밖.

## Validation (bounded)
1. Required py_compile
```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile \
  invest/stages/stage2/scripts/stage02_onepass_refine_full.py \
  invest/stages/common/stage_pdf_artifacts.py \
  invest/stages/common/stage_raw_db.py \
  invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py
```
- result: PASS

2. Focused check: Stage2 input-source policy gate + PDF diag/page-counter behavior + aggregate counter semantics
```bash
STAGE1_RAW_DB_PATH='' python3 - <<'PY'
import json, tempfile, importlib.util, sys
from pathlib import Path
root = Path('/Users/jobiseu/.openclaw/workspace')
script = root / 'invest/stages/stage2/scripts/stage02_onepass_refine_full.py'
sys.path.insert(0, str(script.parent)); sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location('stage2_onepass', script)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
orig = m.STAGE2_INPUT_SOURCE_STATUS
try:
    m.STAGE2_INPUT_SOURCE_STATUS = 'blocked_raw_files_fallback_opt_in_required'
    try: m._enforce_input_source_policy(); raise AssertionError('must block')
    except SystemExit: pass
    m.STAGE2_INPUT_SOURCE_STATUS = 'degraded_opt_in'; m._enforce_input_source_policy()
finally:
    m.STAGE2_INPUT_SOURCE_STATUS = orig
with tempfile.TemporaryDirectory() as td:
    p = Path(td)
    (p/'manifest.json').write_text(json.dumps({
        'declared_page_count': 5, 'page_count': 5, 'max_pages_applied': 2,
        'pages': [{'page_no':1,'text_rel_path':'a.txt','render_rel_path':''},{'page_no':2,'text_rel_path':'','render_rel_path':''}],
        'materialized_text_pages': 1, 'materialized_render_pages': 0
    }), encoding='utf-8')
    (p/'meta.json').write_text('{}', encoding='utf-8')
    d = m._collect_telegram_pdf_diag(
        meta={'pdf_manifest_path': str(p/'manifest.json'), 'extraction_reason': 'missing_original'},
        meta_path=str(p/'meta.json'), original_path='', extract_path='',
        extract_failure_reason='telegram_pdf_extract_failed:original_missing',
        promoted=False, text_source='', cleaned_pdf=''
    )
    assert d['pdf_status'] == 'bounded_by_cap'
    assert d['declared_page_count'] == 5 and d['indexed_page_rows'] == 2 and d['placeholder_page_rows'] == 1
orig_resolve = m._resolve_telegram_pdf_artifact
try:
    def fake_resolve(block, path):
        idx = 1 if 'one' in block else 2
        return ({'promoted_block': f'PROMOTED-{idx}'}, {
            'pdf_promoted': True, 'pdf_status': 'promoted', 'pdf_source': f'source-{idx}',
            'pdf_chars_added': idx, 'pdf_nonempty_lines_added': idx,
            'declared_page_count': idx, 'indexed_page_rows': idx,
            'materialized_text_pages': idx, 'materialized_render_pages': 0,
            'placeholder_page_rows': 0, 'bounded_by_cap': False,
        })
    m._resolve_telegram_pdf_artifact = fake_resolve
    merged, meta = m._promote_telegram_pdf_content('[ATTACH_KIND] pdf\none\n---\n[ATTACH_KIND] pdf\ntwo\n', 'dummy')
    assert meta['pdf_chars_added'] == 3 and meta['declared_page_count'] == 3 and meta['indexed_page_rows'] == 3
    assert merged.count('PROMOTED-') == 2
finally:
    m._resolve_telegram_pdf_artifact = orig_resolve
print('OK stage2_input_policy_pdf_diag_and_aggregate_checks')
PY
```
- result: PASS (`OK stage2_input_policy_pdf_diag_and_aggregate_checks`)
- note: default import path attempted to materialize stage1 DB mirror and hit local `ENOSPC`, so bounded helper validation was rerun with `STAGE1_RAW_DB_PATH=''` to avoid any live snapshot write.

3. Focused check: Stage raw DB summary/document semantics keep declared vs indexed vs placeholder separated
```bash
python3 - <<'PY'
import json, sqlite3, tempfile
from pathlib import Path
from invest.stages.common.stage_raw_db import index_pdf_artifacts_from_raw
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    raw = root/'raw'
    attach = raw/'qualitative/attachments/telegram/bucket_0001'
    attach.mkdir(parents=True)
    manifest_rel = 'qualitative/attachments/telegram/bucket_0001/msg_1__pdf_manifest.json'
    extract_rel = 'qualitative/attachments/telegram/bucket_0001/msg_1__extracted.txt'
    (raw/extract_rel).write_text('[PAGE 001]\nhello\n', encoding='utf-8')
    (raw/manifest_rel).write_text(json.dumps({
        'declared_page_count': 5, 'page_count': 5, 'max_pages_applied': 2, 'bounded_by_cap': True,
        'materialized_text_pages': 1, 'materialized_render_pages': 0,
        'pages': [
            {'page_no': 1, 'text_rel_path': extract_rel, 'render_rel_path': '', 'text_chars': 5},
            {'page_no': 2, 'text_rel_path': '', 'render_rel_path': '', 'text_chars': 0},
        ],
    }), encoding='utf-8')
    (attach/'msg_1__meta.json').write_text(json.dumps({
        'kind': 'pdf', 'channel_slug': 'chan', 'message_id': 1, 'message_date': '20260313',
        'pdf_manifest_path': manifest_rel, 'extract_path': extract_rel, 'original_path': '',
        'extraction_status': 'ok', 'extraction_reason': 'ok',
        'pdf_page_marked': True, 'pdf_page_marker_count': 1,
        'pdf_page_mapping_status': 'available_from_manifest_pages',
    }), encoding='utf-8')
    db_path = root/'stage1.sqlite3'
    s = index_pdf_artifacts_from_raw(raw_root=raw, db_path=db_path).as_dict()
    assert s['declared_pages'] == 5 and s['indexed_page_rows'] == 2 and s['materialized_text_pages'] == 1 and s['placeholder_page_rows'] == 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT declared_page_count, indexed_page_rows, materialized_text_pages, placeholder_page_rows, bounded_by_cap, pdf_status FROM pdf_documents").fetchone()
        assert row == (5, 2, 1, 1, 1, 'promoted')
        assert conn.execute("SELECT COUNT(*) FROM pdf_pages").fetchone()[0] == 5
print('OK stage_raw_db_pdf_index_semantics_check')
PY
```
- result: PASS (`OK stage_raw_db_pdf_index_semantics_check`)

## Files changed
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- `invest/stages/common/stage_pdf_artifacts.py`
- `invest/stages/common/stage_raw_db.py`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
