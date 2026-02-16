import os
import glob
import json
import pandas as pd
import numpy as np
from datetime import datetime
from run_manifest import write_run_manifest

BASE = '/Users/jobiseu/.openclaw/workspace/invest/data'
RAW_OHLCV = os.path.join(BASE, 'ohlcv')
RAW_SUPPLY = os.path.join(BASE, 'supply')
CLEAN_OHLCV = os.path.join(BASE, 'clean/ohlcv')
CLEAN_SUPPLY = os.path.join(BASE, 'clean/supply')
Q_OHLCV = os.path.join(BASE, 'quarantine/ohlcv')
Q_SUPPLY = os.path.join(BASE, 'quarantine/supply')
REPORT_DIR = '/Users/jobiseu/.openclaw/workspace/invest/reports/data_quality'

MIN_VALID_VOLUME = 10
MAX_DAILY_RET_ABS = 0.35

os.makedirs(CLEAN_OHLCV, exist_ok=True)
os.makedirs(CLEAN_SUPPLY, exist_ok=True)
os.makedirs(Q_OHLCV, exist_ok=True)
os.makedirs(Q_SUPPLY, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


def sanitize_ohlcv(df: pd.DataFrame):
    x = df.copy()
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        x[c] = pd.to_numeric(x[c], errors='coerce')

    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    r1 = (
        x['Date'].isna() |
        x['Close'].isna() | (x['Close'] <= 0) |
        x['Open'].isna() | x['High'].isna() | x['Low'].isna() |
        x['Volume'].isna() | (x['Volume'] < MIN_VALID_VOLUME)
    )
    bad |= r1
    reason.loc[r1] = reason.loc[r1].mask(reason.loc[r1] == '', 'basic_invalid_or_low_liquidity').fillna('basic_invalid_or_low_liquidity')

    r2 = ((x['Open'] <= 0) & (x['High'] <= 0) & (x['Low'] <= 0) & (x['Close'] > 0) & (x['Volume'] == 0))
    bad |= r2
    reason.loc[r2] = reason.loc[r2].mask(reason.loc[r2] == '', 'zero_candle').fillna('zero_candle')

    ret = x['Close'].pct_change().abs() > MAX_DAILY_RET_ABS
    bad |= ret.fillna(False)
    reason.loc[ret.fillna(False)] = reason.loc[ret.fillna(False)].mask(reason.loc[ret.fillna(False)] == '', 'return_spike_gt_35pct').fillna('return_spike_gt_35pct')

    # duplicate dates: keep first
    dup = x['Date'].duplicated(keep='first')
    bad |= dup
    reason.loc[dup] = reason.loc[dup].mask(reason.loc[dup] == '', 'duplicate_date').fillna('duplicate_date')

    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values

    clean_df = x[~bad].copy()
    clean_df = clean_df.dropna(subset=['Date']).sort_values('Date')
    clean_df = clean_df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]

    return clean_df, bad_df


def sanitize_supply(df: pd.DataFrame):
    x = df.copy()
    x = x.iloc[:, :6]
    x.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']:
        x[c] = pd.to_numeric(x[c], errors='coerce')

    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    r1 = x['Date'].isna() | x[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']].isna().any(axis=1)
    bad |= r1
    reason.loc[r1] = reason.loc[r1].mask(reason.loc[r1] == '', 'invalid_date_or_nonnumeric').fillna('invalid_date_or_nonnumeric')

    dup = x['Date'].duplicated(keep='first')
    bad |= dup
    reason.loc[dup] = reason.loc[dup].mask(reason.loc[dup] == '', 'duplicate_date').fillna('duplicate_date')

    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values

    clean_df = x[~bad].copy().dropna(subset=['Date']).sort_values('Date')
    clean_df = clean_df[['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']]

    return clean_df, bad_df


def main():
    stats = {
        'ohlcv_files': 0,
        'supply_files': 0,
        'ohlcv_rows_total': 0,
        'supply_rows_total': 0,
        'ohlcv_rows_quarantined': 0,
        'supply_rows_quarantined': 0,
    }

    # OHLCV
    for f in glob.glob(os.path.join(RAW_OHLCV, '*.csv')):
        code = os.path.basename(f).replace('.csv', '')
        if not (code.isdigit() and len(code) == 6):
            continue
        try:
            df = pd.read_csv(f)
            if 'Date' not in df.columns:
                continue
            stats['ohlcv_files'] += 1
            stats['ohlcv_rows_total'] += len(df)
            clean_df, bad_df = sanitize_ohlcv(df)
            clean_df.to_csv(os.path.join(CLEAN_OHLCV, f'{code}.csv'), index=False)
            if not bad_df.empty:
                stats['ohlcv_rows_quarantined'] += len(bad_df)
                bad_df.to_csv(os.path.join(Q_OHLCV, f'{code}.csv'), index=False)
        except Exception:
            continue

    # SUPPLY
    for f in glob.glob(os.path.join(RAW_SUPPLY, '*_supply.csv')):
        code = os.path.basename(f).replace('_supply.csv', '')
        if not (code.isdigit() and len(code) == 6):
            continue
        try:
            df = pd.read_csv(f)
            if df.shape[1] < 6:
                continue
            stats['supply_files'] += 1
            stats['supply_rows_total'] += len(df)
            clean_df, bad_df = sanitize_supply(df)
            clean_df.to_csv(os.path.join(CLEAN_SUPPLY, f'{code}_supply.csv'), index=False)
            if not bad_df.empty:
                stats['supply_rows_quarantined'] += len(bad_df)
                bad_df.to_csv(os.path.join(Q_SUPPLY, f'{code}_supply.csv'), index=False)
        except Exception:
            continue

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(REPORT_DIR, f'organize_existing_data_summary_{ts}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    manifest_path = os.path.join(REPORT_DIR, f'organize_existing_data_manifest_{ts}.json')
    write_run_manifest(
        run_type='organize_existing_data',
        params={'min_valid_volume': MIN_VALID_VOLUME, 'max_daily_ret_abs': MAX_DAILY_RET_ABS},
        inputs=[RAW_OHLCV, RAW_SUPPLY],
        outputs=[out, CLEAN_OHLCV, CLEAN_SUPPLY, Q_OHLCV, Q_SUPPLY],
        out_path=manifest_path,
        workdir='/Users/jobiseu/.openclaw/workspace'
    )

    print('SUMMARY_FILE', out)
    print('MANIFEST_FILE', manifest_path)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
