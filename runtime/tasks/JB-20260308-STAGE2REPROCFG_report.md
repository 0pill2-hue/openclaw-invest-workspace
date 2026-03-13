# JB-20260308-STAGE2REPROCFG completion report

## summary of changes
- `docs/invest/STRATEGY_MASTER.md` 확인 후 이번 작업 change type을 **Rule**로 선언했다.
- Stage2 filter/reason 설정을 코드 하드코딩에서 JSON으로 외부화했다.
  - runtime/filter/tuning/QC universe: `invest/stages/stage2/inputs/config/stage2_runtime_config.json`
  - reason taxonomy/QC anomaly taxonomy: `invest/stages/stage2/inputs/config/stage2_reason_config.json`
- Stage2 스크립트 공통 loader `invest/stages/stage2/scripts/stage2_config.py`를 추가했다.
- refine/QC가 config bundle SHA1(runtime/reason/bundle)을 report에 기록하도록 보강했고, refine incremental signature에도 config bundle SHA1을 포함시켰다.
- Stage2 문서를 config canonical source와 repro 기준(config SHA1 포함)에 맞게 동기화했다.
- `.gitignore`에 Stage2 config JSON 2개만 예외 추가해 Git 추적 가능 상태로 맞췄다.
- Stage2를 scratch에서 다시 실행했다.
  - refine: `--force-rebuild`
  - qc: full run

## change type declaration
- checked: `docs/invest/STRATEGY_MASTER.md`
- declared change type: **Rule**
- rationale: Stage2 reason/filter taxonomy와 incremental repro contract(config SHA1 포함)이 운영 규칙/검증 계약에 직접 영향한다.

## exact files changed
- `.gitignore`
- `docs/invest/stage2/README.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `invest/stages/stage2/inputs/config/stage2_runtime_config.json`
- `invest/stages/stage2/inputs/config/stage2_reason_config.json`
- `invest/stages/stage2/scripts/stage2_config.py`
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- `invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`
- `memory/2026-03-08.md`
- `runtime/tasks/JB-20260308-STAGE2REPROCFG_report.md`

## exact commands run
```bash
python3 -m py_compile \
  invest/stages/stage2/scripts/stage2_config.py \
  invest/stages/stage2/scripts/stage02_onepass_refine_full.py \
  invest/stages/stage2/scripts/stage02_qc_cleaning_full.py

python3 - <<'PY'
import importlib.util, sys
from pathlib import Path
repo = Path('/Users/jobiseu/.openclaw/workspace')
sys.path.insert(0, str(repo / 'invest/stages/stage2/scripts'))
for name in ['stage02_onepass_refine_full.py', 'stage02_qc_cleaning_full.py']:
    mod_path = repo / 'invest/stages/stage2/scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('.py',''), mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if 'refine' in name:
        tax = mod._reason_taxonomy_snapshot()
        assert tax['report_issue_filters']['fail'] == ['missing_input_folder(required=true)', 'folder_processing_exception', 'zero_clean_required_folder']
        assert mod.STAGE2_CONFIG_PROVENANCE['bundle_sha1']
        assert mod._current_index_meta()['stage2_config_sha1'] == mod.STAGE2_CONFIG_PROVENANCE['bundle_sha1']
        print('REFINE_OK', mod.STAGE2_RULE_VERSION, mod.STAGE2_CONFIG_PROVENANCE['bundle_sha1'])
    else:
        assert sorted(mod.HARD_FAIL_TYPES) == ['missing_target_file', 'processing_error', 'zero_clean_folder']
        print('QC_OK', mod.STAGE2_QC_VERSION, mod.STAGE2_CONFIG_PROVENANCE['bundle_sha1'])
PY

mkdir -p runtime/tasks/proofs && \
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild \
  > runtime/tasks/proofs/JB-20260308-STAGE2REPROCFG_refine.log 2>&1

python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py \
  > runtime/tasks/proofs/JB-20260308-STAGE2REPROCFG_qc.log 2>&1
# 위 1회는 SIGTERM/empty log로 종료

python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py

python3 - <<'PY'
import json
from pathlib import Path
repo = Path('/Users/jobiseu/.openclaw/workspace')
refine_json = repo/'invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260308_172430.json'
qc_json = repo/'invest/stages/stage2/outputs/reports/QC_REPORT_20260308_172557.json'
refine = json.loads(refine_json.read_text(encoding='utf-8'))
qc = json.loads(qc_json.read_text(encoding='utf-8'))
print('REFINE_VERDICT', refine['quality_gate']['verdict'])
print('REFINE_HARD_FAILS', refine['quality_gate']['hard_fail_count'])
print('REFINE_TOTALS', refine['totals']['total_input_files'], refine['totals']['total_clean_files'], refine['totals']['total_quarantine_files'])
print('REFINE_CONFIG_BUNDLE', refine['config_provenance']['bundle_sha1'])
print('REFINE_TEXT_TELEGRAM', [r for r in refine['results'] if r['folder']=='text/telegram'][0])
print('REFINE_TEXT_PREMIUM', [r for r in refine['results'] if r['folder']=='text/premium/startale'][0])
print('REFINE_SELECTED_ARTICLES', [r for r in refine['results'] if r['folder']=='market/news/selected_articles'][0])
print('QC_PASS', qc['validation']['pass'])
print('QC_HARD_FAILS', qc['totals']['hard_failures'])
print('QC_CONFIG_BUNDLE', qc['config_provenance']['bundle_sha1'])
PY

python3 - <<'PY'
from pathlib import Path
root = Path('/Users/jobiseu/.openclaw/workspace/invest/stages/stage2/outputs')
checks = {
    'clean_text_telegram': root/'clean/production/qualitative/text/telegram',
    'clean_text_premium': root/'clean/production/qualitative/text/premium/startale',
    'clean_selected_articles': root/'clean/production/qualitative/market/news/selected_articles',
    'q_text_telegram': root/'quarantine/production/qualitative/text/telegram',
    'q_text_premium': root/'quarantine/production/qualitative/text/premium/startale',
}
for name, path in checks.items():
    files = sorted(p for p in path.rglob('*') if p.is_file())
    print(name, len(files), files[0].relative_to(root) if files else 'NONE')
PY

find invest/stages/stage2/outputs/clean/production -type f | wc -l
find invest/stages/stage2/outputs/quarantine/production -type f | wc -l
```

## verification / proof outputs / paths
### primary proof outputs
- refine report md: `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260308_172430.md`
- refine report json: `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260308_172430.json`
- qc report md: `invest/stages/stage2/outputs/reports/QC_REPORT_20260308_172557.md`
- qc report json: `invest/stages/stage2/outputs/reports/QC_REPORT_20260308_172557.json`
- refine stdout log: `runtime/tasks/proofs/JB-20260308-STAGE2REPROCFG_refine.log`
- qc first-attempt log: `runtime/tasks/proofs/JB-20260308-STAGE2REPROCFG_qc.log`

### key verification results
- config loader smoke:
  - `REFINE_OK stage2-refine-20260308-r3 0601d3803c3eca6eb5b3bf382d870bf913d251e3`
  - `QC_OK 2026-03-08-stage2-qc-r3 0601d3803c3eca6eb5b3bf382d870bf913d251e3`
- refine report:
  - `quality_gate.verdict=PASS`
  - `hard_fail_count=0`
  - `totals(total_input_files,total_clean_files,total_quarantine_files)=(42318, 39826, 2518)`
  - `config_provenance.bundle_sha1=0601d3803c3eca6eb5b3bf382d870bf913d251e3`
- qualitative folder proof:
  - `text/telegram`: `total=67 clean=51 quarantine=16 skipped=0 exceptions=0`
  - `text/premium/startale`: `total=972 clean=427 quarantine=545 skipped=0 exceptions=0`
  - `market/news/selected_articles`: `total=33 clean=11 quarantine=29 skipped=0 exceptions=0`
- qc report:
  - `validation.pass=true`
  - `totals.hard_failures=0`
  - `config_provenance.bundle_sha1=0601d3803c3eca6eb5b3bf382d870bf913d251e3`
- final canonical output file counts:
  - clean files: `45875`
  - quarantine files: `8025`
- existence samples:
  - `clean_text_telegram 51 clean/production/qualitative/text/telegram/Nihils_view_of_data__information_viewofdata_full.md`
  - `clean_text_premium 427 clean/production/qualitative/text/premium/startale/241214013439941bp_138a6e1c5c5e.md`
  - `clean_selected_articles 11 clean/production/qualitative/market/news/selected_articles/selected_articles_20260306-011114.jsonl`
  - `q_text_telegram 16 quarantine/production/qualitative/text/telegram/Stock_Trip_stocktrip_full.md`
  - `q_text_premium 545 quarantine/production/qualitative/text/premium/startale/250313094649591mw_30c34c078651.md`

## open issues / 미확인
- `python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py > runtime/tasks/proofs/JB-20260308-STAGE2REPROCFG_qc.log 2>&1` 1회 실행은 SIGTERM으로 종료했고 로그가 비어 있었다. 원인은 **미확인**. 동일 커맨드를 즉시 foreground로 재실행했을 때는 정상 종료 및 report 생성 확인.
- `runtime/tasks/proofs/JB-20260308-STAGE2REPROCFG_refine.log`에는 `FULL_REFINE_REPORT_20260308_172103.*` 경로가 출력되지만, 현재 canonical report는 `FULL_REFINE_REPORT_20260308_172430.*`가 존재한다. 이 타임스탬프 차이의 원인은 **미확인**. 다만 실제 존재 파일의 JSON/MD와 PASS 결과는 확인했다.

## recommended close status
- **DONE**
- reason: ticket scope(이미지 residue/taxonomy gap 정리 연장선의 taxonomy/repro 보강, filter/reason config JSON 외부화, 관련 docs sync, Stage2 scratch rerun, grounded proof report)가 완료되었고, authoritative Stage2 rerun 결과도 refine/QC 모두 PASS로 확인됨.
