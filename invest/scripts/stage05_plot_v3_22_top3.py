#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
IN_JSON = BASE / 'invest/results/validated/stage05_baselines_v3_22_kr.json'
OUT_DIR = BASE / 'invest/reports/stage_updates/charts'
OUT_CUM = OUT_DIR / 'stage05_v3_22_cum_2021plus.png'
OUT_YEAR = OUT_DIR / 'stage05_v3_22_yearly_continuous_2021plus.png'


def import_stage05_module():
    mod_path = BASE / 'invest/scripts/stage05_3x3_v3_9_kr.py'
    name = 'stage05_3x3_v3_9_kr_mod_for_v322_top3'
    spec = importlib.util.spec_from_file_location(name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot import stage05_3x3_v3_9_kr.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def import_replay_module():
    mod_path = BASE / 'invest/scripts/stage05_generate_readable_detailed_v3_20_kr.py'
    name = 'stage05_readable_detail_mod_for_v322_top3'
    spec = importlib.util.spec_from_file_location(name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot import stage05_generate_readable_detailed_v3_20_kr.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _to_cum_pct(eq: pd.Series) -> pd.Series:
    return (eq / float(eq.iloc[0]) - 1.0) * 100.0


def main():
    obj = json.loads(IN_JSON.read_text(encoding='utf-8'))
    models = obj['models']
    ranked = sorted(models, key=lambda m: float(m['stats']['total_return']), reverse=True)[:3]

    stage05_mod = import_stage05_module()
    replay_mod = import_replay_module()

    replays = []
    for m in ranked:
        r = replay_mod.replay_with_events(stage05_mod, m)
        eq = r['eq']
        eq = eq[eq.index.year >= 2021]
        replays.append((m['model_id'], eq))

    common_idx = sorted(set().union(*[set(eq.index) for _, eq in replays]))
    common_idx = pd.DatetimeIndex(common_idx)

    # benchmark (jagged, same x-axis)
    start = common_idx.min().strftime('%Y-%m-%d')
    end = common_idx.max().strftime('%Y-%m-%d')
    kospi_close = replay_mod.fetch_benchmark_close('1001', start, end)
    kosdaq_close = replay_mod.fetch_benchmark_close('2001', start, end)
    kospi_eq = replay_mod.align_series_to_dates(kospi_close, common_idx)
    kosdaq_eq = replay_mod.align_series_to_dates(kosdaq_close, common_idx) if not kosdaq_close.empty else pd.Series(dtype=float)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Chart 1: cumulative with top3 + KOSPI/KOSDAQ
    plt.figure(figsize=(12, 6))
    for i, (mid, eq) in enumerate(replays, start=1):
        s = eq.reindex(common_idx).ffill().bfill()
        plt.plot(common_idx, _to_cum_pct(s), linewidth=2.0, label=f'{i}위 {mid}')
    plt.plot(common_idx, _to_cum_pct(kospi_eq), linewidth=1.8, linestyle='--', label='KOSPI')
    if not kosdaq_eq.empty:
        plt.plot(common_idx, _to_cum_pct(kosdaq_eq), linewidth=1.6, linestyle=':', label='KOSDAQ')
    plt.axhline(0, color='gray', linewidth=0.8)
    plt.title('Stage05 v3_22 Top3 Cumulative Return (2021+)')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return (%)')
    plt.grid(alpha=0.25)
    plt.legend(loc='best', fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_CUM, dpi=150)
    plt.close()

    # Chart 2: same jagged style, yearly visual guide without reset
    plt.figure(figsize=(12, 6))
    for i, (mid, eq) in enumerate(replays, start=1):
        s = eq.reindex(common_idx).ffill().bfill()
        plt.plot(common_idx, _to_cum_pct(s), linewidth=2.0, label=f'{i}위 {mid}')
    plt.plot(common_idx, _to_cum_pct(kospi_eq), linewidth=1.8, linestyle='--', label='KOSPI')
    if not kosdaq_eq.empty:
        plt.plot(common_idx, _to_cum_pct(kosdaq_eq), linewidth=1.6, linestyle=':', label='KOSDAQ')
    # yearly separators
    years = sorted(set(common_idx.year))
    for y in years:
        plt.axvline(pd.Timestamp(f'{y}-01-01'), color='lightgray', linewidth=0.7, alpha=0.6)
    plt.axhline(0, color='gray', linewidth=0.8)
    plt.title('Stage05 v3_22 Top3 Continuous Curve with Year Guides (No Reset)')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return (%)')
    plt.grid(alpha=0.20)
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
