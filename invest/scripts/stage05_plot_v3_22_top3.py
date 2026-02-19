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
OUT_DIR = BASE / 'invest/reports/stage_updates/stage05/v3_22/charts'
OUT_CUM = OUT_DIR / 'stage05_v3_22_cum_2021plus.png'
OUT_CONT = OUT_DIR / 'stage05_v3_22_yearly_continuous_2021plus.png'
OUT_YEAR = OUT_DIR / 'stage05_v3_22_yearly_reset_2021plus.png'
TRADE_EVENTS = BASE / 'invest/reports/stage_updates/stage05/v3_22/stage05_trade_events_v3_22_kr.csv'


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


def _year_segments(eq: pd.Series):
    segs = []
    years = sorted(set(eq.index.year))
    for y in years:
        s = eq[eq.index.year == y]
        if s.empty:
            continue
        base = float(s.iloc[0])
        yr = (s / base - 1.0) * 100.0
        segs.append((y, yr))
    return segs


def _load_event_dates():
    if not TRADE_EVENTS.exists():
        return [], []
    try:
        df = pd.read_csv(TRADE_EVENTS)
    except Exception:
        return [], []
    buys = pd.to_datetime(df.get('buy_date', pd.Series([], dtype=str)), errors='coerce').dropna().tolist()
    sells = pd.to_datetime(df.get('sell_date', pd.Series([], dtype=str)), errors='coerce').dropna().tolist()
    return buys, sells


def _series_value_at_or_before(s: pd.Series, d: pd.Timestamp):
    h = s.loc[:d]
    if h.empty:
        return None
    return float(h.iloc[-1])


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

    model_colors = {
        replays[0][0]: '#1f77b4',  # blue
        replays[1][0]: '#ff7f0e',  # orange
        replays[2][0]: '#2ca02c',  # green
    }
    kospi_color = '#d62728'  # red
    kosdaq_color = '#9467bd'  # purple

    buy_dates, sell_dates = _load_event_dates()

    # Chart 1: cumulative with top3 + KOSPI/KOSDAQ + trade events(top1)
    plt.figure(figsize=(12, 6))
    top1_series = None
    for i, (mid, eq) in enumerate(replays, start=1):
        s = eq.reindex(common_idx).ffill().bfill()
        cp = _to_cum_pct(s)
        if i == 1:
            top1_series = cp
        plt.plot(common_idx, cp, linewidth=2.0, color=model_colors[mid], label=f'{i}위 {mid}')
    plt.plot(common_idx, _to_cum_pct(kospi_eq), linewidth=1.8, linestyle='--', color=kospi_color, label='KOSPI')
    if not kosdaq_eq.empty:
        plt.plot(common_idx, _to_cum_pct(kosdaq_eq), linewidth=1.6, linestyle=':', color=kosdaq_color, label='KOSDAQ')

    if top1_series is not None:
        bx, by = [], []
        sx, sy = [], []
        for d in buy_dates:
            y = _series_value_at_or_before(top1_series, d)
            if y is not None:
                bx.append(d); by.append(y)
        for d in sell_dates:
            y = _series_value_at_or_before(top1_series, d)
            if y is not None:
                sx.append(d); sy.append(y)
        if bx:
            plt.scatter(bx, by, marker='^', s=16, color='#17becf', alpha=0.8, label='Top1 Buy Event')
        if sx:
            plt.scatter(sx, sy, marker='v', s=16, color='#8c564b', alpha=0.8, label='Top1 Sell Event')

    plt.axhline(0, color='gray', linewidth=0.8)
    plt.title('Stage05 v3_22 Top3 Cumulative Return (2021+)')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return (%)')
    plt.grid(alpha=0.25)
    plt.legend(loc='best', fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_CUM, dpi=150)
    plt.savefig(OUT_CONT, dpi=150)
    plt.close()

    # Chart 2: yearly reset (start each year at 0), jagged daily curves
    plt.figure(figsize=(12, 6))
    top1_yearly_segments = None
    for i, (mid, eq) in enumerate(replays, start=1):
        s = eq.reindex(common_idx).ffill().bfill()
        segs = _year_segments(s)
        if i == 1:
            top1_yearly_segments = segs
        for j, (_, yr) in enumerate(segs):
            plt.plot(
                yr.index,
                yr.values,
                linewidth=2.0,
                color=model_colors[mid],
                label=(f'{i}위 {mid}' if j == 0 else None),
            )

    kospi_segs = _year_segments(kospi_eq)
    for j, (_, yr) in enumerate(kospi_segs):
        plt.plot(
            yr.index,
            yr.values,
            linewidth=1.8,
            linestyle='--',
            color=kospi_color,
            label=('KOSPI' if j == 0 else None),
        )

    if not kosdaq_eq.empty:
        kosdaq_segs = _year_segments(kosdaq_eq)
        for j, (_, yr) in enumerate(kosdaq_segs):
            plt.plot(
                yr.index,
                yr.values,
                linewidth=1.6,
                linestyle=':',
                color=kosdaq_color,
                label=('KOSDAQ' if j == 0 else None),
            )

    if top1_yearly_segments is not None:
        by, sy = [], []
        bx, sx = [], []
        for d in buy_dates:
            year_seg = next((seg for y, seg in top1_yearly_segments if y == d.year), None)
            if year_seg is None:
                continue
            yv = _series_value_at_or_before(year_seg, d)
            if yv is not None:
                bx.append(d); by.append(yv)
        for d in sell_dates:
            year_seg = next((seg for y, seg in top1_yearly_segments if y == d.year), None)
            if year_seg is None:
                continue
            yv = _series_value_at_or_before(year_seg, d)
            if yv is not None:
                sx.append(d); sy.append(yv)
        if bx:
            plt.scatter(bx, by, marker='^', s=16, color='#17becf', alpha=0.8, label='Top1 Buy Event')
        if sx:
            plt.scatter(sx, sy, marker='v', s=16, color='#8c564b', alpha=0.8, label='Top1 Sell Event')

    years = sorted(set(common_idx.year))
    for y in years:
        plt.axvline(pd.Timestamp(f'{y}-01-01'), color='lightgray', linewidth=0.7, alpha=0.6)
    plt.axhline(0, color='gray', linewidth=0.8)
    plt.title('Stage05 v3_22 Top3 Yearly Reset Curve (Each Year Starts at 0)')
    plt.xlabel('Date')
    plt.ylabel('Yearly Return from Jan Start (%)')
    plt.grid(alpha=0.20)
    plt.legend(loc='best', fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_YEAR, dpi=150)
    plt.close()

    print(json.dumps({
        'status': 'ok',
        'top3': [m['model_id'] for m in ranked],
        'out_cum': str(OUT_CUM.relative_to(BASE)),
        'out_cont': str(OUT_CONT.relative_to(BASE)),
        'out_year': str(OUT_YEAR.relative_to(BASE)),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
