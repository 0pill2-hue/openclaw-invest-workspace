import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from pipeline_logger import append_pipeline_event
except ImportError:
    def append_pipeline_event(*args, **kwargs):
        pass


def _quarantine_supply_rows(code: str, bad_df: pd.DataFrame):
    if bad_df is None or bad_df.empty:
        return
    qdir = 'invest/data/quarantine/kr/supply'
    os.makedirs(qdir, exist_ok=True)
    qpath = os.path.join(qdir, f"{code}_supply.csv")
    cols = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total', 'reason']
    out = bad_df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out[cols].to_csv(qpath, mode='a', header=not os.path.exists(qpath), index=False)


def _sanitize_supply(code: str, df_new: pd.DataFrame):
    if df_new is None or df_new.empty:
        return df_new, pd.DataFrame()

    x = df_new.copy().reset_index().rename(columns={'index': 'Date'})
    # pykrx index name could be 날짜
    if '날짜' in x.columns and 'Date' not in x.columns:
        x = x.rename(columns={'날짜': 'Date'})
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')

    # 표준 컬럼 매핑
    cols = list(x.columns)
    # 기대: Date + [기관합계,기타법인,개인,외국인합계,전체]
    if len(cols) >= 6:
        x = x.iloc[:, :6]
        x.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']

    for c in ['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']:
        x[c] = pd.to_numeric(x[c], errors='coerce')

    bad = x[x['Date'].isna() | x[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']].isna().any(axis=1)].copy()
    if not bad.empty:
        bad['reason'] = 'invalid_date_or_nonnumeric'
        _quarantine_supply_rows(code, bad)

    clean = x[~x.index.isin(bad.index)].copy()
    clean = clean.set_index('Date').sort_index()[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']]
    return clean, bad


def fetch_supply_data():
    full_collection = os.environ.get('FULL_COLLECTION', '0').strip().lower() in ('1', 'true', 'yes')
    stock_list_path = 'invest/data/master/kr_stock_list.csv'
    if not os.path.exists(stock_list_path):
        print("Stock list not found.")
        return

    df_stocks = pd.read_csv(stock_list_path)
    df_stocks['Code'] = df_stocks['Code'].astype(str).str.zfill(6)
    
    raw_output_dir = 'invest/data/raw/kr/supply'
    legacy_output_dir = 'invest/data/raw/kr/supply'  # backward-compat mirror
    os.makedirs(raw_output_dir, exist_ok=True)
    os.makedirs(legacy_output_dir, exist_ok=True)

    # Define timeframe: last 10 years (base) / incremental to today
    end_date = datetime.now().strftime('%Y%m%d')
    base_start_date = (datetime.now() - timedelta(days=365*10)).strftime('%Y%m%d')

    print(f"Starting Supply data collection for {len(df_stocks)} stocks up to {end_date} (incremental enabled)...")

    success_count = 0
    fail_count = 0
    for idx, row in df_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        file_path = os.path.join(raw_output_dir, f"{code}_supply.csv")
        legacy_file_path = os.path.join(legacy_output_dir, f"{code}_supply.csv")

        # 증분 수집: 기존 파일이 있으면 마지막 날짜 이후부터 수집
        start_date = base_start_date
        if (not full_collection) and os.path.exists(file_path):
            try:
                df_existing = pd.read_csv(file_path)
                if '날짜' in df_existing.columns:
                    last_date = pd.to_datetime(df_existing['날짜']).max()
                else:
                    last_date = pd.to_datetime(df_existing.iloc[:, 0]).max()
                next_date = (last_date + timedelta(days=1)).strftime('%Y%m%d')
                if next_date > end_date:
                    continue
                start_date = next_date
            except Exception:
                start_date = base_start_date

        try:
            # 순매수(수급) 데이터: 날짜별 순매수
            df = stock.get_market_trading_value_by_date(start_date, end_date, code, on='순매수')
            if not df.empty:
                clean_df, bad_df = _sanitize_supply(code, df)
                if clean_df is not None and not clean_df.empty:
                    if os.path.exists(file_path):
                        clean_df.to_csv(file_path, mode='a', header=False)
                    else:
                        clean_df.to_csv(file_path)

                    # backward-compat mirror (legacy path)
                    if os.path.exists(legacy_file_path):
                        clean_df.to_csv(legacy_file_path, mode='a', header=False)
                    else:
                        clean_df.to_csv(legacy_file_path)
                    success_count += 1
                    if success_count % 50 == 0:
                        print(f"Progress: {idx+1}/{len(df_stocks)} stocks collected.")
                else:
                    fail_count += 1
            else:
                fail_count += 1

            time.sleep(0.05)

        except Exception as e:
            print(f"Error fetching supply for {code} ({name}): {e}")
            fail_count += 1
            time.sleep(0.5)

    status = "OK" if fail_count == 0 else "WARN"
    append_pipeline_event(
        source="fetch_supply",
        status=status,
        count=success_count,
        errors=[],
        note=f"KR supply done. total={len(df_stocks)} ok={success_count} fail={fail_count}",
    )
    print("Supply data collection completed.")

if __name__ == "__main__":
    fetch_supply_data()
