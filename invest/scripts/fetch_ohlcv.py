import FinanceDataReader as fdr
import pandas as pd
import numpy as np
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


def _quarantine_ohlcv_rows(code: str, bad_df: pd.DataFrame):
    if bad_df is None or bad_df.empty:
        return
    qdir = 'invest/data/quarantine/kr/ohlcv'
    os.makedirs(qdir, exist_ok=True)
    qpath = os.path.join(qdir, f"{code}.csv")
    cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'reason']
    out = bad_df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out[cols].to_csv(qpath, mode='a', header=not os.path.exists(qpath), index=False)


def _sanitize_ohlcv(code: str, df_new: pd.DataFrame, prev_close: float = None):
    if df_new is None or df_new.empty:
        return df_new, pd.DataFrame()

    x = df_new.copy().reset_index().rename(columns={'index': 'Date'})
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        x[c] = pd.to_numeric(x[c], errors='coerce')

    bad_parts = []

    # 규칙 1: 기본 무효값
    bad_basic = (
        x['Date'].isna() |
        x['Close'].isna() | (x['Close'] <= 0) |
        x['Volume'].isna() | (x['Volume'] < 10) |
        x['Open'].isna() | x['High'].isna() | x['Low'].isna() |
        ((x['Open'] <= 0) & (x['High'] <= 0) & (x['Low'] <= 0) & (x['Close'] > 0))
    )
    if bad_basic.any():
        b = x[bad_basic].copy()
        b['reason'] = 'basic_invalid_or_low_liquidity'
        bad_parts.append(b)

    # 규칙 2: 비상식 급변값(전일대비)
    ret_base = x['Close'].pct_change()
    if prev_close and prev_close > 0 and not x.empty and pd.notna(x.loc[0, 'Close']):
        ret_base.iloc[0] = (x.loc[0, 'Close'] / prev_close) - 1.0
    bad_ret = ret_base.abs() > 0.35
    if bad_ret.any():
        b = x[bad_ret].copy()
        b['reason'] = 'return_spike_gt_35pct'
        bad_parts.append(b)

    bad_df = pd.concat(bad_parts, ignore_index=True).drop_duplicates(subset=['Date']) if bad_parts else pd.DataFrame()
    if not bad_df.empty:
        _quarantine_ohlcv_rows(code, bad_df)

    clean = x[~x['Date'].isin(set(pd.to_datetime(bad_df['Date'], errors='coerce')))].copy() if not bad_df.empty else x
    clean = clean.set_index('Date').sort_index()[['Open', 'High', 'Low', 'Close', 'Volume']]
    return clean, bad_df


def fetch_all_ohlcv():
    # 1. 종목 리스트 읽기
    stock_list_path = 'invest/data/master/kr_stock_list.csv'
    if not os.path.exists(stock_list_path):
        print("Stock list not found. Run fetch_stock_list.py first.")
        return

    df_stocks = pd.read_csv(stock_list_path)
    # 종목코드를 6자리 문자열로 맞춤
    df_stocks['Code'] = df_stocks['Code'].astype(str).str.zfill(6)
    
    raw_output_dir = 'invest/data/raw/kr/ohlcv'
    legacy_output_dir = 'invest/data/ohlcv'  # backward-compat mirror
    os.makedirs(raw_output_dir, exist_ok=True)
    os.makedirs(legacy_output_dir, exist_ok=True)

    # 10년 전부터 오늘까지 (기본 시작일)
    base_start_date = '2016-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"Starting OHLCV collection for {len(df_stocks)} stocks up to {end_date} (incremental enabled)...")

    success_count = 0
    fail_count = 0

    for idx, row in df_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        file_path = os.path.join(raw_output_dir, f"{code}.csv")
        legacy_file_path = os.path.join(legacy_output_dir, f"{code}.csv")

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
                prev_close = None
                if os.path.exists(file_path):
                    try:
                        prev = pd.read_csv(file_path)
                        prev_close = pd.to_numeric(prev['Close'], errors='coerce').dropna().iloc[-1]
                    except Exception:
                        prev_close = None

                clean_df, bad_df = _sanitize_ohlcv(code, df, prev_close=prev_close)
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
                else:
                    fail_count += 1
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
