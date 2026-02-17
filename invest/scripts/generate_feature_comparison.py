import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

try:
    from invest.scripts.run_manifest import write_run_manifest
except ModuleNotFoundError:
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from run_manifest import write_run_manifest

BASE_DIR = '/Users/jobiseu/.openclaw/workspace/invest'
OHLCV_PATH = os.path.join(BASE_DIR, 'data/clean/production/kr/ohlcv/005930.csv')
SUPPLY_PATH = os.path.join(BASE_DIR, 'data/clean/production/kr/supply/005930_supply.csv')
TREND_PATH = os.path.join(BASE_DIR, 'data/clean/production/market/google_trends/삼성전자_trends_10y.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'results/test')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'feature_score_comparison.csv')
MANIFEST_DIR = os.path.join(BASE_DIR, 'reports', 'data_quality')

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MANIFEST_DIR, exist_ok=True)


def _safe_num(s):
    return pd.to_numeric(s, errors='coerce')


def calculate_scores():
    results = []
    asof_date = 'N/A'

    df_ohlcv = pd.read_csv(OHLCV_PATH) if os.path.exists(OHLCV_PATH) else None
    if df_ohlcv is not None:
        df_ohlcv['Date'] = pd.to_datetime(df_ohlcv['Date'])
        df_ohlcv = df_ohlcv.sort_values('Date').set_index('Date')
        asof_date = df_ohlcv.index[-1].strftime('%Y-%m-%d')

    df_supply = pd.read_csv(SUPPLY_PATH) if os.path.exists(SUPPLY_PATH) else None
    if df_supply is not None:
        df_supply.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
        df_supply['Date'] = pd.to_datetime(df_supply['Date'])
        df_supply = df_supply.sort_values('Date').set_index('Date')

    df_trend = pd.read_csv(TREND_PATH) if os.path.exists(TREND_PATH) else None
    if df_trend is not None:
        df_trend = df_trend.iloc[:, :2]
        df_trend.columns = ['Date', 'TrendValue']
        df_trend['Date'] = pd.to_datetime(df_trend['Date'])
        df_trend = df_trend.sort_values('Date').set_index('Date')

    if df_ohlcv is not None and len(df_ohlcv) >= 60:
        ma20 = _safe_num(df_ohlcv['Close']).rolling(20).mean()
        ma60 = _safe_num(df_ohlcv['Close']).rolling(60).mean()
        my_trend = (ma20.iloc[-1] / (ma60.iloc[-1] + 1e-9) - 1) * 100

        if df_supply is not None:
            net_20 = (_safe_num(df_supply['Inst']) + _safe_num(df_supply['Foreign'])).rolling(20).sum()
            supply_signal = net_20 / ((_safe_num(df_ohlcv['Close']) * _safe_num(df_ohlcv['Volume'])).replace(0, np.nan))
            neighbor_trend = supply_signal.iloc[-1] * 1_000_000
        else:
            neighbor_trend = None

        results.append({'feature': 'Trend (추세)', 'my_score': round(my_trend, 2), 'neighbor_score': round(neighbor_trend, 4) if neighbor_trend is not None else None, 'reason': None if neighbor_trend is not None else 'Supply data missing'})
    else:
        results.append({'feature': 'Trend (추세)', 'my_score': None, 'neighbor_score': None, 'reason': 'OHLCV data insufficient'})

    if df_ohlcv is not None and len(df_ohlcv) >= 20:
        my_mom = _safe_num(df_ohlcv['Close']).pct_change(20).iloc[-1] * 100
        if df_supply is not None:
            net_20 = (_safe_num(df_supply['Inst']) + _safe_num(df_supply['Foreign'])).rolling(20).sum()
            supply_signal = net_20 / ((_safe_num(df_ohlcv['Close']) * _safe_num(df_ohlcv['Volume'])).replace(0, np.nan))
            neighbor_mom = supply_signal.iloc[-1] * 1_000_000
        else:
            neighbor_mom = None
        results.append({'feature': 'Momentum (모멘텀)', 'my_score': round(my_mom, 2), 'neighbor_score': round(neighbor_mom, 4) if neighbor_mom is not None else None, 'reason': None if neighbor_mom is not None else 'Supply data missing'})
    else:
        results.append({'feature': 'Momentum (모멘텀)', 'my_score': None, 'neighbor_score': None, 'reason': 'OHLCV data insufficient'})

    results.append({'feature': 'BM (Business Model)', 'my_score': None, 'neighbor_score': None, 'reason': 'Qualitative data requires manual analyst input'})

    final_df = pd.DataFrame(results)
    final_df['diff'] = final_df['my_score'] - final_df['neighbor_score']
    final_df['asof_date'] = asof_date
    final_df = final_df[['feature', 'my_score', 'neighbor_score', 'diff', 'asof_date', 'reason']]

    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig') as f:
        f.write('# [DRAFT / TEST ONLY] Feature Score Comparison Table\n')
        f.write(f"# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write('# 7단계(Purged CV/OOS) 이전 채택 금지\n')
        final_df.to_csv(f, index=False)

    manifest_path = os.path.join(MANIFEST_DIR, f"manifest_feature_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    write_run_manifest(
        run_type='feature_comparison',
        params={'symbol': '005930', 'grade': 'DRAFT'},
        inputs=[OHLCV_PATH, SUPPLY_PATH, TREND_PATH],
        outputs=[OUTPUT_FILE],
        out_path=manifest_path,
        workdir=BASE_DIR,
    )

    return final_df, manifest_path


if __name__ == '__main__':
    df, mf = calculate_scores()
    print('File generated successfully at:', OUTPUT_FILE)
    print('Manifest:', mf)
    print(df.head(10))
