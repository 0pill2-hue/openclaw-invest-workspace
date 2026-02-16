import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
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


def fetch_supply_data():
    stock_list_path = 'invest/data/master/kr_stock_list.csv'
    if not os.path.exists(stock_list_path):
        print("Stock list not found.")
        return

    df_stocks = pd.read_csv(stock_list_path)
    df_stocks['Code'] = df_stocks['Code'].astype(str).str.zfill(6)
    
    output_dir = 'invest/data/supply'
    os.makedirs(output_dir, exist_ok=True)

    # Define timeframe: last 10 years (base) / incremental to today
    end_date = datetime.now().strftime('%Y%m%d')
    base_start_date = (datetime.now() - timedelta(days=365*10)).strftime('%Y%m%d')

    print(f"Starting Supply data collection for {len(df_stocks)} stocks up to {end_date} (incremental enabled)...")

    success_count = 0
    for idx, row in df_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        file_path = os.path.join(output_dir, f"{code}_supply.csv")

        # 증분 수집: 기존 파일이 있으면 마지막 날짜 이후부터 수집
        start_date = base_start_date
        if os.path.exists(file_path):
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
                if os.path.exists(file_path):
                    df.to_csv(file_path, mode='a', header=False)
                else:
                    df.to_csv(file_path)
                success_count += 1
                if success_count % 50 == 0:
                    print(f"Progress: {idx+1}/{len(df_stocks)} stocks collected.")
            
            time.sleep(0.05) 

        except Exception as e:
            print(f"Error fetching supply for {code} ({name}): {e}")
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
