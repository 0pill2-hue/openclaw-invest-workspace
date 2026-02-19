#!/usr/bin/env python3
import glob, json, os, sys
from pathlib import Path

ROOT = Path('/Users/jobiseu/.openclaw/workspace')


def latest(pattern):
    files = sorted(glob.glob(str(ROOT / pattern)))
    return files[-1] if files else None


def check_stage1():
    checks = []
    checks.append(("raw_root_exists", (ROOT / 'invest/data/raw').exists()))
    hs = ROOT / 'memory/health-state.json'
    checks.append(("health_state_exists", hs.exists()))
    mf = latest('invest/reports/data_quality/manifest_*.json')
    checks.append(("lineage_manifest_exists", mf is not None))
    return checks


def check_stage2():
    checks = []
    checks.append(("clean_root_exists", (ROOT / 'invest/data/clean').exists()))
    checks.append(("quarantine_root_exists", (ROOT / 'invest/data/quarantine').exists()))
    mf = latest('invest/reports/data_quality/organize_existing_data_manifest_*.json')
    checks.append(("organize_manifest_exists", mf is not None))
    return checks


def check_stage3():
    checks = []
    mf = latest('invest/reports/data_quality/manifest_stage2_validate_*.json')
    checks.append(("validate_manifest_exists", mf is not None))
    if mf:
        try:
            data = json.load(open(mf, 'r', encoding='utf-8'))
            failed = int(data.get('failed_count', 0) or 0)
            checks.append(("failed_count_zero", failed == 0))
        except Exception:
            checks.append(("failed_count_zero", False))
    else:
        checks.append(("failed_count_zero", False))
    return checks


def check_stage4():
    checks = []
    vr = latest('reports/invest/stage_updates/STAGE3_VALUE_RUN_*.json')
    mf = latest('invest/reports/data_quality/manifest_stage3_value_*.json')
    checks.append(("value_report_exists", vr is not None))
    checks.append(("value_manifest_exists", mf is not None))
    if vr:
        try:
            data = json.load(open(vr, 'r', encoding='utf-8'))
            checks.append(("grade_present", str(data.get('grade', '')).strip() != ''))
        except Exception:
            checks.append(("grade_present", False))
    else:
        checks.append(("grade_present", False))
    return checks


def main():
    all_checks = {
        'stage01': check_stage1(),
        'stage02': check_stage2(),
        'stage03': check_stage3(),
        'stage04': check_stage4(),
    }
    ok = True
    for stage, checks in all_checks.items():
        for name, passed in checks:
            print(f"{stage}:{name}:{'PASS' if passed else 'FAIL'}")
            ok = ok and passed
    print('SUMMARY:' + ('PASS' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
