import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# what: 섹터별 자금유입 점수를 계산하는 v1 배치
# why: 선호 섹터가 아닌 실제 유입 섹터를 랭킹화하기 위해

IN_PATH = '/Users/jobiseu/.openclaw/workspace/invest/data/clean/market/sector_flow_input.csv'
OUT_DIR = '/Users/jobiseu/.openclaw/workspace/invest/reports/sector_flow'


def zscore(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors='coerce').fillna(0.0)
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series([0.0] * len(s), index=s.index)
    return (s - s.mean()) / std


def main():
    if not os.path.exists(IN_PATH):
        raise FileNotFoundError(f'input not found: {IN_PATH}')

    df = pd.read_csv(IN_PATH)

    required = ['date', 'sector', 'turnover_share_delta', 'net_buy_strength']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'missing required columns: {missing}')

    # optional metrics
    if 'etf_flow_proxy' not in df.columns:
        df['etf_flow_proxy'] = 0.0
    if 'news_momentum' not in df.columns:
        df['news_momentum'] = 0.0

    # what: 표준화 후 가중합
    # why: 단위가 다른 지표를 공정하게 합산하기 위해
    df['turnover_share_delta_z'] = zscore(df['turnover_share_delta'])
    df['net_buy_strength_z'] = zscore(df['net_buy_strength'])
    df['etf_flow_proxy_z'] = zscore(df['etf_flow_proxy'])
    df['news_momentum_z'] = zscore(df['news_momentum'])

    df['money_flow_score_v1'] = (
        0.45 * df['turnover_share_delta_z']
        + 0.35 * df['net_buy_strength_z']
        + 0.15 * df['etf_flow_proxy_z']
        + 0.05 * df['news_momentum_z']
    )

    df = df.sort_values(['date', 'money_flow_score_v1'], ascending=[True, False])

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_csv = os.path.join(OUT_DIR, f'money_flow_sector_score_v1_{ts}.csv')
    out_json = os.path.join(OUT_DIR, f'money_flow_sector_score_v1_{ts}.json')

    df.to_csv(out_csv, index=False)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'rows': int(len(df)),
            'input': IN_PATH,
            'output_csv': out_csv,
            'weights': {
                'turnover_share_delta_z': 0.45,
                'net_buy_strength_z': 0.35,
                'etf_flow_proxy_z': 0.15,
                'news_momentum_z': 0.05
            }
        }, f, ensure_ascii=False, indent=2)

    print('OUTPUT_CSV', out_csv)
    print('OUTPUT_JSON', out_json)
    print('TOP5')
    print(df[['date', 'sector', 'money_flow_score_v1']].head(5).to_string(index=False))


if __name__ == '__main__':
    main()
