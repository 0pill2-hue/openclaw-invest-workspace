import os
from pathlib import Path
import pandas as pd

BASE_DIR = Path('/Users/jobiseu/.openclaw/workspace/invest/data')
CLEAN_PROD_DIR = BASE_DIR / 'clean' / 'production'
OHLCV_DIR = CLEAN_PROD_DIR / 'kr' / 'ohlcv'
SUPPLY_DIR = CLEAN_PROD_DIR / 'kr' / 'supply'


def _guard_no_raw_path(*paths: Path) -> None:
    """
    
        Role: 경로 중에 'raw'가 포함되어 있는지 확인하여 가공 데이터의 오염(raw 참조)을 방지한다.
        Input: paths (검사할 경로 목록)
        Output: None (위반 시 AssertionError 발생)
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
    for p in paths:
        p_str = str(p).replace('\\', '/').lower()
        assert '/raw/' not in p_str, f'RAW path reference detected: {p}'


def generate_features(stock_code):
    """
    
        Role: 특정 종목의 10년치 정제 데이터를 기반으로 가격 모멘텀, 변동성, 수급 지표 등 핵심 피처를 산출한다.
        Input: stock_code (종목코드)
        Output: df (피처가 포함된 데이터프레임)
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
    ohlcv_path = OHLCV_DIR / f'{stock_code}.csv'
    supply_path = SUPPLY_DIR / f'{stock_code}_supply.csv'

    _guard_no_raw_path(ohlcv_path, supply_path)

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
