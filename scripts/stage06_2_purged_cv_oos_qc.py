#!/usr/bin/env python3
"""
Role: Stage08 Purged CV/OOS QC
Input: --input stage06_2_purged_cv_oos.json [--promote]
Output: PASS/FAIL
Side effect: --promote 시 DRAFT->VALIDATED
Author: 조비스
Updated: 2026-02-18
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--promote', action='store_true')
    args = ap.parse_args()

    p = Path(args.input)
    if not p.exists():
        print('FAIL:input_missing')
        return 2

    d = json.loads(p.read_text())
    rows = d.get('results', [])
    if len(rows) < 3:
        print('FAIL:insufficient_rows')
        return 2

    pass_cnt = 0
    for r in rows:
        if r.get('leakage_flag'):
            print(f"FAIL:leakage:{r.get('candidate_id')}")
            return 2
        if r['cv_sharpe_mean'] < 0.80 or r['cv_sharpe_std'] > 0.60:
            continue
        if r['oos_sharpe'] < 0.70 or r['oos_mdd'] < -0.18:
            continue
        if r['stress_pnl_ratio_50'] < 0.60:
            continue
        pass_cnt += 1

    if pass_cnt < 3:
        print(f'FAIL:pass_ratio:{pass_cnt}')
        return 2

    if args.promote and d.get('grade') == 'DRAFT':
        d['grade'] = 'VALIDATED'
        d.pop('watermark', None)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        print(f'PASS:validated:pass_candidates={pass_cnt}')
        return 0

    print(f'PASS:pass_candidates={pass_cnt}:grade={d.get("grade")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
