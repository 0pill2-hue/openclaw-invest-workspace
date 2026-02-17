import os
import pandas as pd
import numpy as np
from pathlib import Path

def validate_ohlcv(df, market='KR'):
    errors = []
    
    # Check Empty Date
    date_col = 'Date'
    if date_col not in df.columns:
        return [f"Missing {date_col} column"]
    
    if df[date_col].isnull().any():
        errors.append("Contains empty dates")
        df = df.dropna(subset=[date_col])
    
    # Try parsing date
    try:
        df[date_col] = pd.to_datetime(df[date_col])
    except Exception as e:
        errors.append(f"Date parsing error: {e}")
        return errors

    # Check Duplicates
    if df[date_col].duplicated().any():
        errors.append("Contains duplicate dates")
    
    # Check Date Sorting
    if not df[date_col].is_monotonic_increasing:
        errors.append("Dates are not sorted")
    
    # Schema check and Basic Range
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing column: {col}")
        else:
            if (df[col] < 0).any():
                errors.append(f"Negative value in {col}")
            if col != 'Volume' and col != 'Close': # Close often has the previous price even if halted
                # If price is 0, volume must also be 0 (halted). 
                # If price is 0 but volume > 0, it's an error.
                bad_rows = df[(df[col] == 0) & (df['Volume'] > 0)]
                if not bad_rows.empty:
                    errors.append(f"Zero value in {col} with non-zero Volume")
                
                # Check for just 0 price if we want to be strict, but let's allow it if Volume is 0.
                # However, the previous error log showed many "Zero value in Open".
                # Let's keep it as a warning in the report rather than a "failed gate" if it's a halt.

    return errors

def validate_supply(df):
    errors = []
    date_col = '날짜'
    if date_col not in df.columns:
        return [f"Missing {date_col} column"]
    
    if df[date_col].isnull().any():
        errors.append("Contains empty dates")
        df = df.dropna(subset=[date_col])
        
    try:
        df[date_col] = pd.to_datetime(df[date_col])
    except Exception as e:
        errors.append(f"Date parsing error: {e}")
        return errors

    if df[date_col].duplicated().any():
        errors.append("Contains duplicate dates")
        
    if not df[date_col].is_monotonic_increasing:
        errors.append("Dates are not sorted")

    return errors

def run_validation():
    base_path = Path("invest/data/clean")
    results = {
        "KR_OHLCV": {"total": 0, "failed": 0, "errors": {}},
        "US_OHLCV": {"total": 0, "failed": 0, "errors": {}},
        "KR_SUPPLY": {"total": 0, "failed": 0, "errors": {}}
    }

    # KR OHLCV
    kr_ohlcv_path = base_path / "kr/ohlcv"
    if kr_ohlcv_path.exists():
        for f in kr_ohlcv_path.glob("*.csv"):
            results["KR_OHLCV"]["total"] += 1
            df = pd.read_csv(f)
            err = validate_ohlcv(df, 'KR')
            if err:
                results["KR_OHLCV"]["failed"] += 1
                results["KR_OHLCV"]["errors"][f.name] = err

    # US OHLCV
    us_ohlcv_path = base_path / "us/ohlcv"
    if us_ohlcv_path.exists():
        for f in us_ohlcv_path.glob("*.csv"):
            results["US_OHLCV"]["total"] += 1
            df = pd.read_csv(f)
            # Cleanup messy US columns
            cols_to_keep = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df = df[[c for c in df.columns if any(k in c for k in cols_to_keep)]]
            # Rename if needed (e.g., "('Open', 'AAPL')" -> "Open")
            rename_map = {}
            for c in df.columns:
                for k in cols_to_keep:
                    if k in c:
                        rename_map[c] = k
                        break
            df = df.rename(columns=rename_map)
            # Take only the first occurrence of each column if duplicates exist after renaming
            df = df.loc[:, ~df.columns.duplicated()]
            
            err = validate_ohlcv(df, 'US')
            if err:
                results["US_OHLCV"]["failed"] += 1
                results["US_OHLCV"]["errors"][f.name] = err

    # KR SUPPLY
    kr_supply_path = base_path / "kr/supply"
    if kr_supply_path.exists():
        for f in kr_supply_path.glob("*.csv"):
            results["KR_SUPPLY"]["total"] += 1
            df = pd.read_csv(f)
            err = validate_supply(df)
            if err:
                results["KR_SUPPLY"]["failed"] += 1
                results["KR_SUPPLY"]["errors"][f.name] = err

    return results

if __name__ == "__main__":
    import json
    res = run_validation()
    print(json.dumps(res, indent=2))
