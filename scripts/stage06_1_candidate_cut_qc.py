#!/usr/bin/env python3
"""
Role: Stage07 컷 결과 QC
Input: --input stage06_1_candidates_cut.json [--promote]
Output: PASS/FAIL
Side effect: --promote 시 DRAFT->VALIDATED
Author: 조비스
Updated: 2026-02-18
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--promote',action='store_true'); args=ap.parse_args()
    p=Path(args.input)
    if not p.exists(): print('FAIL:input_missing'); return 2
    d=json.loads(p.read_text())
    sel=d.get('selected',[])
    if not (4 <= len(sel) <= 8): print(f'FAIL:selection_size:{len(sel)}'); return 2
    if not any(x.get('track')=='text' for x in sel): print('FAIL:champion_missing'); return 2
    req=['candidate_id','track','score','warning_points','metrics']
    for x in sel:
      for k in req:
        if k not in x: print(f"FAIL:missing_field:{x.get('candidate_id','unknown')}:{k}"); return 2
    if args.promote and d.get('grade')=='DRAFT':
      d['grade']='VALIDATED'; d.pop('watermark',None); p.write_text(json.dumps(d,ensure_ascii=False,indent=2)); print(f'PASS:validated:selected={len(sel)}'); return 0
    print(f'PASS:selected={len(sel)}:grade={d.get("grade")}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
