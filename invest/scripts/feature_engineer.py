import pandas as pd
import numpy as np
import os
from datetime import datetime

def generate_features(stock_code):
    """
    Summarizes 10-year data into features for the strategist brain.
    """
    ohlcv_path = f'invest/data/ohlcv/{stock_code}.csv'
    supply_path = f'invest/data/supply/{stock_code}_supply.csv'
    
    if not os.path.exists(ohlcv_path):
        return None
    
    df = pd.read_csv(ohlcv_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    # 1. Price Momentum
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['Disparity20'] = (df['Close'] / df['MA20']) * 100
    
    # 2. Volatility
    df['Returns'] = df['Close'].pct_change()
    df['Volat_20'] = df['Returns'].rolling(window=20).std()
    
    # 3. Supply Features (if available)
    if os.path.exists(supply_path):
        sdf = pd.read_csv(supply_path)
        # Assuming columns: 날짜, 기관합계, 기타법인, 개인, 외국인합계
        sdf.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
        sdf['Date'] = pd.to_datetime(sdf['Date'])
        sdf.set_index('Date', inplace=True)
        
        # Merge supply into price df
        df = df.join(sdf[['Inst', 'Foreign']], how='left').fillna(0)
        
        # Cumulative supply momentum (20 days)
        df['Net_Foreign_20'] = df['Foreign'].rolling(window=20).sum()
        df['Net_Inst_20'] = df['Inst'].rolling(window=20).sum()
        
    return df

if __name__ == "__main__":
    # Test with Samsung Electronics
    sample = generate_features('005930')
    if sample is not None:
        print("Feature Engineering Sample (Latest 5 rows):")
        print(sample[['Close', 'MA20', 'Disparity20', 'Net_Foreign_20']].tail())
