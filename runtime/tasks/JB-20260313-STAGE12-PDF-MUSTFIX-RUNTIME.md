# JB-20260313-STAGE12-PDF-MUSTFIX-RUNTIME

- ticket: JB-20260313-STAGE12-PDF-MUSTFIX-RUNTIME
- status: PARTIAL_DONE
- checked_at: 2026-03-13 15:28 KST

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

3. 페이지 카운터 분리 저장/보고 (declared/indexed/materialized/placeholder)
- files:
  - `invest/stages/common/stage_pdf_artifacts.py`
  - `invest/stages/common/stage_raw_db.py`
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- manifest(`stage_pdf_artifacts`)에 분리 필드 추가:
  - `declared_page_count`
  - `indexed_page_rows`
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

2. Focused check: Stage2 input-source policy gate + PDF diag/page-counter behavior
```bash
python3 - <<'PY'
import json, tempfile, importlib.util, sys
from pathlib import Path
root = Path('/private/tmp/stage12-pdf-fix.vLRGBn')
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
    assert d['declared_page_count'] == 5 and d['indexed_page_rows'] == 5 and d['placeholder_page_rows'] == 4
print('OK stage2_input_policy_and_pdf_diag_checks')
PY
```
- result: PASS (`OK stage2_input_policy_and_pdf_diag_checks`)

3. Focused check: Stage raw DB summary fields include separated counters
```bash
python3 - <<'PY'
import tempfile
from pathlib import Path
from invest.stages.common.stage_raw_db import index_pdf_artifacts_from_raw
with tempfile.TemporaryDirectory() as td:
    root = Path(td); (root/'raw').mkdir(parents=True)
    s = index_pdf_artifacts_from_raw(raw_root=root/'raw', db_path=root/'stage1.sqlite3').as_dict()
    for k in ['declared_pages','indexed_page_rows','materialized_text_pages','materialized_render_pages','placeholder_page_rows']:
        assert k in s, k
print('OK stage_raw_db_pdf_index_summary_check')
PY
```
- result: PASS (`OK stage_raw_db_pdf_index_summary_check`)

## Files changed
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- `invest/stages/common/stage_pdf_artifacts.py`
- `invest/stages/common/stage_raw_db.py`
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
