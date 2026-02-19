import os
import pandas as pd
import numpy as np
from pathlib import Path

def fix_ohlcv(df, market='KR'):
    date_col = 'Date'
    if date_col not in df.columns:
        # Try to find a date-like column
        for col in df.columns:
            if 'Date' in col or '날짜' in col:
                df = df.rename(columns={col: date_col})
                break
    
    if date_col not in df.columns:
        return None

    # Drop empty dates
    df = df.dropna(subset=[date_col])
    
    # Parse date
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Sort
    df = df.sort_values(date_col)
    
    # Drop duplicates
    df = df.drop_duplicates(subset=[date_col], keep='last')
    
    # Basic Range fix: we can't really "fix" 0 prices unless we interpolate, 
    # but for now let's just ensure we have the right columns.
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    available_cols = [c for c in required_cols if c in df.columns]
    df = df[available_cols]
    
    return df

def fix_us_ohlcv(df):
    # Special handling for messy yfinance columns
    cols_to_keep = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close']
    
    # Flatten/Clean columns
    new_cols = []
    for c in df.columns:
        found = False
        for k in cols_to_keep:
            if k in c:
                new_cols.append(k)
                found = True
                break
        if not found:
            new_cols.append(c)
    
    df.columns = new_cols
    
    # Keep only the first occurrence of standard columns
    df = df.loc[:, ~df.columns.duplicated()]
    
    # Re-use generic fix
    return fix_ohlcv(df, 'US')

def fix_supply(df):
    date_col = '날짜'
    if date_col not in df.columns:
        return None
    
    df = df.dropna(subset=[date_col])
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)
    df = df.drop_duplicates(subset=[date_col], keep='last')
    
    return df

def run_refinement():
    raw_base = Path("invest/data/raw")
    clean_base = Path("invest/data/clean")
    
    # KR OHLCV
    print("Refining KR OHLCV...")
    src = raw_base / "kr/ohlcv"
    dst = clean_base / "kr/ohlcv"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.csv"):
        df = pd.read_csv(f)
        df_fixed = fix_ohlcv(df, 'KR')
        if df_fixed is not None:
            df_fixed.to_csv(dst / f.name, index=False)

    # US OHLCV
    print("Refining US OHLCV...")
    src = raw_base / "us/ohlcv"
    dst = clean_base / "us/ohlcv"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.csv"):
        df = pd.read_csv(f)
        df_fixed = fix_us_ohlcv(df)
        if df_fixed is not None:
            df_fixed.to_csv(dst / f.name, index=False)

    # KR SUPPLY
    print("Refining KR SUPPLY...")
    src = raw_base / "kr/supply"
    dst = clean_base / "kr/supply"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.csv"):
        df = pd.read_csv(f)
        df_fixed = fix_supply(df)
        if df_fixed is not None:
            df_fixed.to_csv(dst / f.name, index=False)

if __name__ == "__main__":
    run_refinement()
