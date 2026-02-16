import FinanceDataReader as fdr
import pandas as pd
import os
import sys
import time
from datetime import datetime, timedelta

# pipeline_logger가 같은 디렉토리에 있을 때 경로 보정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from pipeline_logger import append_pipeline_event
except ImportError:
    def append_pipeline_event(*args, **kwargs):
        pass


def fetch_all_ohlcv():
    # 1. 종목 리스트 읽기
    stock_list_path = 'invest/data/master/kr_stock_list.csv'
    if not os.path.exists(stock_list_path):
        print("Stock list not found. Run fetch_stock_list.py first.")
        return

    df_stocks = pd.read_csv(stock_list_path)
    # 종목코드를 6자리 문자열로 맞춤
    df_stocks['Code'] = df_stocks['Code'].astype(str).str.zfill(6)
    
    output_dir = 'invest/data/ohlcv'
    os.makedirs(output_dir, exist_ok=True)

    # 10년 전부터 오늘까지 (기본 시작일)
    base_start_date = '2016-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"Starting OHLCV collection for {len(df_stocks)} stocks up to {end_date} (incremental enabled)...")

    success_count = 0
    fail_count = 0

    for idx, row in df_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        file_path = os.path.join(output_dir, f"{code}.csv")

        # 증분 수집: 기존 파일이 있으면 마지막 날짜 이후부터 수집
        start_date = base_start_date
        if os.path.exists(file_path):
            try:
                df_existing = pd.read_csv(file_path)
                if 'Date' in df_existing.columns:
                    last_date = pd.to_datetime(df_existing['Date']).max()
                else:
                    last_date = pd.to_datetime(df_existing.iloc[:, 0]).max()
                next_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                # 이미 최신이면 스킵
                if next_date > end_date:
                    continue
                start_date = next_date
            except Exception:
                # 기존 파일 파싱 실패 시 전체 재수집
                start_date = base_start_date

        try:
            # 주가 데이터 가져오기
            df = fdr.DataReader(code, start_date, end_date)
            if not df.empty:
                if os.path.exists(file_path):
                    df.to_csv(file_path, mode='a', header=False)
                else:
                    df.to_csv(file_path)
                success_count += 1
            else:
                fail_count += 1
            
            if success_count % 50 == 0:
                print(f"Progress: {idx+1}/{len(df_stocks)} (Success: {success_count}, Fail: {fail_count})")
            
            # API 부하 방지를 위한 미세 지연
            time.sleep(0.05)

        except Exception as e:
            print(f"Error fetching {code} ({name}): {e}")
            fail_count += 1
            time.sleep(1) # 에러 시 잠시 대기

    status = "OK" if fail_count == 0 else "WARN"
    append_pipeline_event(
        source="fetch_ohlcv",
        status=status,
        count=success_count,
        errors=[],
        note=f"KR OHLCV done. total={len(df_stocks)} ok={success_count} fail={fail_count}",
    )
    print(f"Collection completed. Total Success: {success_count}, Total Fail: {fail_count}")

if __name__ == "__main__":
    fetch_all_ohlcv()
