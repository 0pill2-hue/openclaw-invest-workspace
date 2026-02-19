#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
import re
import sys
from pathlib import Path
import pandas as pd
from pykrx import stock

BASE = Path(__file__).resolve().parents[2]
V322_JSON = BASE / 'invest/results/validated/stage05_baselines_v3_22_kr.json'
TIMELINE_CSV = BASE / 'invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_timeline_v3_22_kr.csv'
OUT_STRUCTURED = BASE / 'invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_v3_22_kr.csv'
OUT_SUMMARY = BASE / 'invest/reports/stage_updates/stage05/v3_22/stage05_portfolio_weights_summary_v3_22_kr.json'


def _import(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _to_code6(v: str) -> str:
    s = str(v).strip()
    if s.isdigit():
        return s.zfill(6)
    return s


def _name_with_code(label: str) -> tuple[str, str]:
    code6 = _to_code6(label)
    name = ''
    try:
        name = stock.get_market_ticker_name(code6) or ''
    except Exception:
        name = ''
    if name:
        return code6, f"{name}({code6})"
    return code6, f"{label}({code6})"


def _parse_weights(desc: str, date: str):
    if not isinstance(desc, str) or desc.strip() in {'', '-'}:
        return []
    out = []
    parts = [x.strip() for x in desc.split(';') if x.strip()]
    for p in parts:
        m = re.match(r'^(.*?)\(([-0-9.]+)%\s*,\s*([0-9]+)d\)$', p)
        if not m:
            continue
        raw_label = m.group(1).strip()
        code6, name_code = _name_with_code(raw_label)
        out.append({
            'date': date,
            'stock_code': code6,
            'stock_name': name_code,
            'weight_pct': float(m.group(2)),
            'holding_days': int(m.group(3)),
        })
    return out


def main():
    stage05_mod = _import(BASE / 'invest/scripts/stage05_3x3_v3_9_kr.py', 'stage05mod_v322w')
    replay_mod = _import(BASE / 'invest/scripts/stage05_generate_readable_detailed_v3_20_kr.py', 'stage05replay_v322w')

    obj = json.loads(V322_JSON.read_text(encoding='utf-8'))
    best = max(obj['models'], key=lambda x: float(x['stats']['total_return']))

    rep = replay_mod.replay_with_events(stage05_mod, best)
    monthly_df = pd.DataFrame(rep['monthly_rows'])

    rows = []
    for _, r in monthly_df.iterrows():
        rows.extend(_parse_weights(str(r.get('holdings_weights_days', '-')), str(r.get('month_end', ''))))

    wdf = pd.DataFrame(rows)
    if not wdf.empty:
        # 0%는 미보유로 간주하여 UI/평가에서 제외
        wdf = wdf[wdf['weight_pct'] > 0].copy()

    snapshot_map = {}
    if not wdf.empty:
        for d, g in wdf.groupby('date'):
            g = g.sort_values('weight_pct', ascending=False)
            snapshot_map[d] = '; '.join(
                f"{row.stock_name} {row.weight_pct:.1f}%, {int(row.holding_days)}d" for row in g.itertuples()
            )

    if TIMELINE_CSV.exists():
        tl = pd.read_csv(TIMELINE_CSV)
        tl['weights_snapshot'] = tl['rebalance_date'].map(snapshot_map).fillna('-')
        tl.to_csv(TIMELINE_CSV, index=False, encoding='utf-8-sig')
    if not wdf.empty:
        wdf.sort_values(['date', 'weight_pct'], ascending=[True, False], inplace=True)
    wdf.to_csv(OUT_STRUCTURED, index=False, encoding='utf-8-sig')

    summary = {'model_id': best['model_id'], 'rows': int(len(wdf))}
    if not wdf.empty:
        g = wdf.groupby('date')['weight_pct']
        top1 = g.max()
        hhi = wdf.assign(w=(wdf['weight_pct'] / 100.0) ** 2).groupby('date')['w'].sum()
        summary.update({
            'top1_weight_pct_max': float(top1.max()),
            'top1_weight_pct_avg': float(top1.mean()),
            'hhi_max': float(hhi.max()),
            'hhi_avg': float(hhi.mean()),
        })

    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'ok', 'model_id': best['model_id'], 'out': str(OUT_STRUCTURED.relative_to(BASE)), 'summary': summary}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
