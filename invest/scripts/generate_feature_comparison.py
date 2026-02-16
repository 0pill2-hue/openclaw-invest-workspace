import pandas as pd
import numpy as np
import os
from datetime import datetime

# Paths
BASE_DIR = '/Users/jobiseu/.openclaw/workspace/invest'
OHLCV_PATH = os.path.join(BASE_DIR, 'data/ohlcv/005930.csv')
SUPPLY_PATH = os.path.join(BASE_DIR, 'data/supply/005930_supply.csv')
TREND_PATH = os.path.join(BASE_DIR, 'data/alternative/trends/삼성전자_trends_10y.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'results/test')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'feature_score_comparison.csv')

os.makedirs(OUTPUT_DIR, exist_ok=True)

def calculate_scores():
    results = []
    asof_date = "N/A"
    
    # Load OHLCV
    if os.path.exists(OHLCV_PATH):
        df_ohlcv = pd.read_csv(OHLCV_PATH)
        df_ohlcv['Date'] = pd.to_datetime(df_ohlcv['Date'])
        df_ohlcv = df_ohlcv.sort_values('Date').set_index('Date')
        asof_date = df_ohlcv.index[-1].strftime('%Y-%m-%d')
    else:
        df_ohlcv = None

    # Load Supply
    if os.path.exists(SUPPLY_PATH):
        df_supply = pd.read_csv(SUPPLY_PATH)
        df_supply.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
        df_supply['Date'] = pd.to_datetime(df_supply['Date'])
        df_supply = df_supply.sort_values('Date').set_index('Date')
    else:
        df_supply = None

    # Load Trends
    if os.path.exists(TREND_PATH):
        df_trend = pd.read_csv(TREND_PATH)
        # Handle date, value, isPartial
        df_trend = df_trend.iloc[:, :2] # Take first two columns
        df_trend.columns = ['Date', 'TrendValue']
        df_trend['Date'] = pd.to_datetime(df_trend['Date'])
        df_trend = df_trend.sort_values('Date').set_index('Date')
    else:
        df_trend = None

    # 1. Trend (추세)
    if df_ohlcv is not None and len(df_ohlcv) >= 60:
        ma20 = df_ohlcv['Close'].rolling(20).mean()
        ma60 = df_ohlcv['Close'].rolling(60).mean()
        my_trend = (ma20.iloc[-1] / ma60.iloc[-1] - 1) * 100
        
        if df_supply is not None:
            # Neighbor trend: Consistent with backtest_compare logic
            # Use the supply_signal from there
            net_20 = (df_supply['Inst'] + df_supply['Foreign']).rolling(20).sum()
            supply_signal = net_20 / (df_ohlcv['Close'] * df_ohlcv['Volume'] + 1e-9)
            neighbor_trend = supply_signal.iloc[-1] * 1000000 # Scale to readable number
        else:
            neighbor_trend = None
        
        results.append({
            'feature': 'Trend (추세)',
            'my_score': round(my_trend, 2),
            'neighbor_score': round(neighbor_trend, 4) if neighbor_trend is not None else None,
            'reason': None if neighbor_trend is not None else "Supply data missing"
        })
    else:
        results.append({'feature': 'Trend (추세)', 'my_score': None, 'neighbor_score': None, 'reason': "OHLCV data insufficient"})

    # 2. Momentum (모멘텀)
    if df_ohlcv is not None and len(df_ohlcv) >= 20:
        my_mom = df_ohlcv['Close'].pct_change(20).iloc[-1] * 100
        
        if df_supply is not None:
            # Neighbor momentum: Supply signal intensity
            net_20 = (df_supply['Inst'] + df_supply['Foreign']).rolling(20).sum()
            supply_signal = net_20 / (df_ohlcv['Close'] * df_ohlcv['Volume'] + 1e-9)
            neighbor_mom = supply_signal.iloc[-1] * 1000000
        else:
            neighbor_mom = None
            
        results.append({
            'feature': 'Momentum (모멘텀)',
            'my_score': round(my_mom, 2),
            'neighbor_score': round(neighbor_mom, 4) if neighbor_mom is not None else None,
            'reason': None if neighbor_mom is not None else "Supply data missing"
        })
    else:
        results.append({'feature': 'Momentum (모멘텀)', 'my_score': None, 'neighbor_score': None, 'reason': "OHLCV data insufficient"})

    # 3. BM (Business Model)
    results.append({
        'feature': 'BM (Business Model)',
        'my_score': None,
        'neighbor_score': None,
        'reason': "Qualitative data requires manual analyst input (Not in automated pipeline)"
    })

    # 4. Liquidity (유동성)
    if df_ohlcv is not None and len(df_ohlcv) >= 20:
        avg_turnover_20 = (df_ohlcv['Close'] * df_ohlcv['Volume']).rolling(20).mean()
        curr_turnover = df_ohlcv['Close'].iloc[-1] * df_ohlcv['Volume'].iloc[-1]
        my_liq = (curr_turnover / (avg_turnover_20.iloc[-1] + 1e-9)) * 100
        
        if df_supply is not None:
            # Neighbor liquidity: Share of absolute Inst+Foreign net volume in total volume
            abs_net_20 = (df_supply['Inst'].abs() + df_supply['Foreign'].abs()).iloc[-20:].mean()
            vol_20 = df_ohlcv['Volume'].iloc[-20:].mean()
            neighbor_liq = (abs_net_20 / (vol_20 + 1e-9)) * 100
        else:
            neighbor_liq = None
            
        results.append({
            'feature': 'Liquidity (유동성)',
            'my_score': round(my_liq, 2),
            'neighbor_score': round(neighbor_liq, 2) if neighbor_liq is not None else None,
            'reason': None if neighbor_liq is not None else "Supply data missing"
        })
    else:
        results.append({'feature': 'Liquidity (유동성)', 'my_score': None, 'neighbor_score': None, 'reason': "OHLCV data insufficient"})

    # 5. Risk (리스크)
    if df_ohlcv is not None and len(df_ohlcv) >= 20:
        # My risk: Price volatility (20d std of returns)
        returns = df_ohlcv['Close'].pct_change()
        my_risk = returns.rolling(20).std().iloc[-1] * 100
        
        if df_supply is not None:
            # Neighbor risk: Supply signal volatility
            net_20 = (df_supply['Inst'] + df_supply['Foreign']).rolling(20).sum()
            supply_signal = net_20 / (df_ohlcv['Close'] * df_ohlcv['Volume'] + 1e-9)
            neighbor_risk = supply_signal.rolling(20).std().iloc[-1] * 1000000
        else:
            neighbor_risk = None
            
        results.append({
            'feature': 'Risk (리스크)',
            'my_score': round(my_risk, 2),
            'neighbor_score': round(neighbor_risk, 2) if neighbor_risk is not None else None,
            'reason': None if neighbor_risk is not None else "Supply data missing"
        })
    else:
        results.append({'feature': 'Risk (리스크)', 'my_score': None, 'neighbor_score': None, 'reason': "OHLCV data insufficient"})

    # 6. Sentiment (센티)
    if df_trend is not None:
        # My sentiment: Current Google Trend vs 20d Avg
        avg_trend_20 = df_trend['TrendValue'].rolling(20).mean()
        my_senti = (df_trend['TrendValue'].iloc[-1] / (avg_trend_20.iloc[-1] + 1)) * 100
    else:
        my_senti = None
        
    # Neighbor sentiment: Often comes from "Market Consensus" or social signals.
    # Since we have blog insights and telegram logs, but they are not strictly scored yet.
    # I'll mark as null for neighbor if no consensus engine found.
    results.append({
        'feature': 'Sentiment (센티)',
        'my_score': round(my_senti, 2) if my_senti is not None else None,
        'neighbor_score': None,
        'reason': "Neighbor sentiment (Consensus) requires NLP engine aggregation" if my_senti is not None else "Trend data missing"
    })

    # Convert to DataFrame
    final_df = pd.DataFrame(results)
    final_df['diff'] = final_df['my_score'] - final_df['neighbor_score']
    final_df['asof_date'] = asof_date
    
    # Reorder columns
    cols = ['feature', 'my_score', 'neighbor_score', 'diff', 'asof_date', 'reason']
    final_df = final_df[cols]
    
    # Add watermark/header
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig') as f:
        f.write("# [DRAFT / TEST ONLY] Feature Score Comparison Table\n")
        f.write(f"# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Target Stock: Samsung Electronics (005930)\n")
        final_df.to_csv(f, index=False)
    
    return final_df

if __name__ == "__main__":
    df = calculate_scores()
    print("File generated successfully at:", OUTPUT_FILE)
    print("\nTop 10 rows (or all if less):")
    print(df.head(10))
