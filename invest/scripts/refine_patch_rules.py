import pandas as pd
import numpy as np

def apply_patch_rules(df, folder_type):
    """
    즉시 적용할 구체적 정제 규칙 패치
    """
    if df.empty:
        return df, pd.DataFrame()
    
    # 1. 원천 데이터 노이즈 제거 (Skip first row if garbage)
    # read_csv 시점에 처리하는 것이 좋으나, 이미 로드된 경우 첫 행이 전체 NaN이면 제거
    if df.iloc[0].isna().all():
        df = df.iloc[1:].reset_index(drop=True)

    # 2. 날짜 누락 탐지 및 격리 (Missing Row Policy)
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date']).sort_values('Date')
        
        # 영업일 기준 누락 체크 (주말 제외)
        if folder_type in ['kr/ohlcv', 'us/ohlcv']:
            full_range = pd.date_range(start=df['Date'].min(), end=df['Date'].max(), freq='B')
            missing_dates = full_range.difference(df['Date'])
            if len(missing_dates) > 0:
                # 검증기에서 알림을 주기 위해 별도 표기 또는 로깅 필요
                pass

    # 3. 수치형 데이터 정밀 검증 (Z-Score Outlier)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col in ['Close', 'Adj Close']:
            # 단순 수익률 외에 이동평균 대비 이격도 체크 가능
            pass

    return df

