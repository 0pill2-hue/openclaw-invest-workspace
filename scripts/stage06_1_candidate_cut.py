#!/usr/bin/env python3
"""
Role: Stage07 후보군 하드/소프트 컷 실행
Input: --input stage06_candidates.json
Output: stage06_1_candidates_cut.json, stage06_1_candidates_cut_table.csv
Side effect: validated 결과 파일 생성
Author: 조비스
Updated: 2026-02-18
"""
from __future__ import annotations
import argparse, json, csv
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def zscores(vals):
    m=sum(vals)/len(vals)
    v=sum((x-m)**2 for x in vals)/max(1,len(vals)-1)
    s=v**0.5 or 1.0
    return [(x-m)/s for x in vals]

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); args=ap.parse_args()
    p=Path(args.input)
    d=json.loads(p.read_text())
    cands=d.get('candidates',[])
    hard=[]; dropped=[]
    for c in cands:
        cid=c.get('candidate_id','unknown'); m=c.get('metrics',{})
        reason=[]
        if c.get('track') not in {'text','quant','hybrid'}: reason.append('[Stage07][Hard][HC01] track')
        if m.get('MDD',-1) < -0.15: reason.append('[Stage07][Hard][HC02] MDD')
        if m.get('rolling_sharpe_min_3m',-9) <= -0.20: reason.append('[Stage07][Hard][HC03] rolling_sharpe')
        if m.get('rolling_alpha_min_3m',-9) <= -0.18: reason.append('[Stage07][Hard][HC04] rolling_alpha')
        if c.get('turnover_cap',9) > 0.55 or c.get('cost_penalty_bps',9999) > 500: reason.append('[Stage07][Hard][HC05] turnover_cost')
        if c.get('governance_pass') is not True: reason.append('[Stage07][Hard][HC06] governance')
        if reason: dropped.append((c,reason)); continue
        hard.append(c)

    if not hard:
        print('FAIL:no_hardcut_pass'); return 2

    cagr=[x['metrics']['CAGR'] for x in hard]; shr=[x['metrics']['Sharpe'] for x in hard]
    risk=[-abs(x['metrics']['MDD']) for x in hard]; cost=[-(x['turnover_cap']+x['cost_penalty_bps']/1000.0) for x in hard]
    zc,zs,zr,zk=zscores(cagr),zscores(shr),zscores(risk),zscores(cost)

    scored=[]
    for i,c in enumerate(hard):
        wp=0
        if c['metrics']['rolling_sharpe_min_3m']<0: wp+=1
        if c['metrics']['rolling_alpha_min_3m']<-0.10: wp+=1
        if c['turnover_cap']>=0.50: wp+=1
        if c['cost_penalty_bps']>=420: wp+=1
        score=0.35*zc[i]+0.30*zs[i]+0.20*zr[i]+0.15*zk[i]
        scored.append((c,score,wp))

    survivors=[x for x in scored if x[2]<3]
    survivors.sort(key=lambda t:t[1],reverse=True)
    selected=survivors[:8]
    if len(selected)<4:
        selected=survivors

    out_json=BASE/'invest/results/validated/stage06_1_candidates_cut.json'
    out_csv=BASE/'invest/results/validated/stage06_1_candidates_cut_table.csv'
    payload={'stage':7,'grade':'DRAFT','watermark':'TEST ONLY','selected':[{'candidate_id':c['candidate_id'],'track':c['track'],'score':round(s,6),'warning_points':wp,'metrics':c['metrics'],'turnover_cap':c['turnover_cap'],'cost_penalty_bps':c['cost_penalty_bps']} for c,s,wp in selected], 'dropped':[{'candidate_id':c['candidate_id'],'reasons':r} for c,r in dropped]}
    out_json.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    with out_csv.open('w',newline='',encoding='utf-8') as f:
      w=csv.writer(f); w.writerow(['candidate_id','track','score','warning_points','decision'])
      sel={x[0]['candidate_id'] for x in selected}
      for c,s,wp in scored:
        w.writerow([c['candidate_id'],c['track'],round(s,6),wp,'SELECT' if c['candidate_id'] in sel else 'DROP'])
    print(f'PASS:selected={len(selected)} hard_pass={len(hard)} dropped={len(dropped)}')
    print(out_json)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
