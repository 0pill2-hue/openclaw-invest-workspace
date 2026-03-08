import FinanceDataReader as fdr
import pandas as pd
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

# pipeline_logger가 같은 디렉토리에 있을 때 경로 보정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from pipeline_logger import append_pipeline_event
except ImportError:
    def append_pipeline_event(*args, **kwargs):
        """
        Role: append_pipeline_event 함수 역할 설명
        Input: 입력 타입/의미 명시
        Output: 반환 타입/의미 명시
        Side effect: 파일 저장/외부 호출/상태 변경 여부
        Author: 조비스
        Updated: 2026-02-18
        """
        pass


def _sanitize_ohlcv(code: str, df_new: pd.DataFrame, prev_close: float = None):
    """
    
        Role: 수집된 OHLCV 데이터의 무효값 및 급변치(35% 초과)를 필터링하여 정제 데이터와 오염 데이터를 분리한다.
        Input: code (종목코드), df_new (신규 수집 데이터), prev_close (전일 종가)
        Output: clean (정제 데이터프레임), bad_df (오염 데이터프레임)
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
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
    # Stage1은 수집/원천(raw)까지만 담당한다. 검역(quarantine) 파일 저장은 Stage2 단일 책임.
    clean = x[~x['Date'].isin(set(pd.to_datetime(bad_df['Date'], errors='coerce')))].copy() if not bad_df.empty else x
    clean = clean.set_index('Date').sort_index()[['Open', 'High', 'Low', 'Close', 'Volume']]
    return clean, bad_df


def _read_local_latest_date(file_path: str) -> Optional[datetime]:
    if not os.path.exists(file_path):
        return None
    try:
        df_existing = pd.read_csv(file_path)
        if 'Date' in df_existing.columns:
            last_date = pd.to_datetime(df_existing['Date'], errors='coerce').max()
        else:
            last_date = pd.to_datetime(df_existing.iloc[:, 0], errors='coerce').max()
        if pd.isna(last_date):
            return None
        return last_date.to_pydatetime() if hasattr(last_date, 'to_pydatetime') else last_date
    except Exception:
        return None



def _probe_market_latest_date(code: str, lookback_days: int = 14) -> Optional[datetime]:
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=max(lookback_days, 3))
    try:
        df = fdr.DataReader(code, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
    except Exception:
        return None
    if df is None or df.empty:
        return None
    idx = pd.to_datetime(df.index, errors='coerce')
    idx = idx[~pd.isna(idx)]
    if len(idx) == 0:
        return None
    latest = idx.max()
    return latest.to_pydatetime() if hasattr(latest, 'to_pydatetime') else latest



def fetch_all_ohlcv():
    """
    
        Role: 국장(KOSPI/KOSDAQ) 전체 종목의 OHLCV 데이터를 증분 또는 전체 수집한다.
        Input: None (환경변수 FULL_COLLECTION 참조)
        Output: None (파일 저장 및 로그 기록)
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
    full_collection = os.environ.get('FULL_COLLECTION', '0').strip().lower() in ('1', 'true', 'yes')
    # 1. 종목 리스트 읽기
    stock_list_path = 'invest/stages/stage1/outputs/master/kr_stock_list.csv'
    if not os.path.exists(stock_list_path):
        print("Stock list not found. Run fetch_stock_list.py first.")
        return

    df_stocks = pd.read_csv(stock_list_path)
    # 종목코드를 6자리 문자열로 맞춤
    df_stocks['Code'] = df_stocks['Code'].astype(str).str.zfill(6)
    
    raw_output_dir = 'invest/stages/stage1/outputs/raw/signal/kr/ohlcv'
    os.makedirs(raw_output_dir, exist_ok=True)

    # 10년 전부터 오늘까지 (기본 시작일)
    base_start_date = '2016-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')

    benchmark_code = '005930'
    benchmark_file = os.path.join(raw_output_dir, f"{benchmark_code}.csv")
    local_latest_dt = _read_local_latest_date(benchmark_file)
    live_latest_dt = None if full_collection else _probe_market_latest_date(benchmark_code)
    if (not full_collection) and local_latest_dt and live_latest_dt and live_latest_dt.date() <= local_latest_dt.date():
        note = (
            'KR OHLCV skipped. market_closed_or_no_new_trading_day '
            f'benchmark={benchmark_code} local_latest={local_latest_dt.date().isoformat()} '
            f'live_latest={live_latest_dt.date().isoformat()}'
        )
        append_pipeline_event(
            source="fetch_ohlcv",
            status="OK",
            count=0,
            errors=[],
            note=note,
        )
        print(note)
        return

    print(f"Starting OHLCV collection for {len(df_stocks)} stocks up to {end_date} (incremental enabled)...")

    success_count = 0
    fail_count = 0

    for idx, row in df_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        file_path = os.path.join(raw_output_dir, f"{code}.csv")

        # 증분 수집: 기존 파일이 있으면 마지막 날짜 이후부터 수집
        start_date = base_start_date
        if (not full_collection) and os.path.exists(file_path):
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
