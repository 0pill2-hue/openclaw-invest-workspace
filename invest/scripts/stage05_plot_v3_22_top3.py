#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
IN_JSON = BASE / 'invest/results/validated/stage05_baselines_v3_22_kr.json'
OUT_DIR = BASE / 'invest/reports/stage_updates/charts'
OUT_CUM = OUT_DIR / 'stage05_v3_22_cum_2021plus.png'
OUT_YEAR = OUT_DIR / 'stage05_v3_22_yearly_continuous_2021plus.png'


def annual_to_cum(annual: dict, start_year: int = 2021):
    pts = []
    eq = 1.0
    for y in sorted(int(k) for k in annual.keys() if int(k) >= start_year):
        eq *= (1.0 + float(annual[str(y)]))
        pts.append((pd.Timestamp(f'{y}-12-31'), eq - 1.0))
    return pd.DataFrame(pts, columns=['date', 'cum'])


def main():
    obj = json.loads(IN_JSON.read_text(encoding='utf-8'))
    models = obj['models']

    ranked = sorted(models, key=lambda m: float(m['stats']['total_return']), reverse=True)[:3]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Top3 cumulative(2021+) on one axis
    plt.figure(figsize=(11, 5))
    for i, m in enumerate(ranked, start=1):
        df = annual_to_cum(m.get('annual_returns', {}), start_year=2021)
        if df.empty:
            continue
        plt.plot(df['date'], df['cum'] * 100.0, marker='o', linewidth=2.0, label=f"{i}위 {m['model_id']}")
    plt.axhline(0, color='gray', linewidth=0.8)
    plt.title('Stage05 v3_22 Top3 누적수익률 (2021+)')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return (%)')
    plt.grid(alpha=0.25)
    plt.legend(loc='best', fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_CUM, dpi=150)
    plt.close()

    # 2) Yearly returns with continuous x-axis (no year reset mixing)
    plt.figure(figsize=(11, 5))
    for i, m in enumerate(ranked, start=1):
        annual = {int(k): float(v) for k, v in m.get('annual_returns', {}).items() if int(k) >= 2021}
        xs = [pd.Timestamp(f'{y}-12-31') for y in sorted(annual)]
        ys = [annual[y] * 100.0 for y in sorted(annual)]
        if not xs:
            continue
        plt.plot(xs, ys, marker='o', linewidth=2.0, label=f"{i}위 {m['model_id']}")
    plt.axhline(0, color='gray', linewidth=0.8)
    plt.title('Stage05 v3_22 Top3 연도별 수익률 (연속 가로축)')
    plt.xlabel('Date')
    plt.ylabel('Yearly Return (%)')
    plt.grid(alpha=0.25)
    plt.legend(loc='best', fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_YEAR, dpi=150)
    plt.close()

    print(json.dumps({
        'status': 'ok',
        'top3': [m['model_id'] for m in ranked],
        'out_cum': str(OUT_CUM.relative_to(BASE)),
        'out_year': str(OUT_YEAR.relative_to(BASE)),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
