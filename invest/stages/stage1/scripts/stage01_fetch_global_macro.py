"""
Global Macro Data Fetcher
- VIX, DXY, 10Y-2Y spread, SOX (semiconductor index)
- For regime detection and correlation analysis
"""
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json

# Output directory
DATA_DIR = 'invest/stages/stage1/outputs/raw/signal/market/macro'
os.makedirs(DATA_DIR, exist_ok=True)

# Global macro symbols
SYMBOLS = {
    'VIX': '^VIX',           # CBOE Volatility Index
    'DXY': 'DX-Y.NYB',       # US Dollar Index
    'SOX': '^SOX',           # Philadelphia Semiconductor Index
    'TNX': '^TNX',           # 10-Year Treasury Yield
    'IRX': '^IRX',           # 13-Week Treasury Bill
    'SPY': 'SPY',            # S&P 500 ETF (for correlation)
    'QQQ': 'QQQ',            # NASDAQ 100 ETF
}

# Additional spread calculations
SPREADS = {
    '10Y3M': ('TNX', 'IRX'),  # Yield curve: 10Y - 3M (IRX is 13-week T-bill)
}


def ten_years_ago_start() -> str:
    today = datetime.now().date()
    try:
        start = today.replace(year=today.year - 10)
    except ValueError:
        # Handle leap day (e.g., Feb 29 -> Feb 28)
        start = today.replace(year=today.year - 10, day=28)
    return start.strftime("%Y-%m-%d")


def fetch_symbol(symbol: str, ticker: str, period: str = '10y') -> pd.DataFrame:
    """
    Fetch historical data for a single symbol.
    
    Role: fetch_symbol 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            print(f"  [WARN] No data for {symbol} ({ticker})")
            return None
        
        # Handle yfinance MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
        data.index.name = 'Date'
        start_date = pd.to_datetime(ten_years_ago_start())
        data = data[data.index >= start_date]
        if data.empty:
            print(f"  [WARN] No data for {symbol} ({ticker})")
            return None
        return data
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {symbol}: {e}")
        return None


def fetch_fred_series(series_id: str, start: str | None = None) -> pd.DataFrame | None:
    try:
        if start is None:
            start = ten_years_ago_start()

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        df = pd.read_csv(url)
        if df is None or df.empty:
            return None

        cols = {str(c).strip().lstrip("\ufeff").lower(): c for c in df.columns}
        date_col = cols.get("date") or cols.get("observation_date") or list(df.columns)[0]
        value_col = cols.get(series_id.lower()) or list(df.columns)[-1]

        out = df[[date_col, value_col]].copy()
        out.columns = ["Date", "value"]
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out = out[out["Date"] >= pd.to_datetime(start)]
        out["value"] = pd.to_numeric(out["value"], errors="coerce")
        out = out.dropna(subset=["Date", "value"]).sort_values("Date")
        return out
    except Exception as e:
        print(f"  [WARN] Failed to fetch FRED {series_id}: {e}")
        return None


def _save_macro_frame(name: str, df: pd.DataFrame) -> None:
    out = os.path.join(DATA_DIR, f"{name}.csv")
    df.to_csv(out, index=False)


def _extract_latest_metric(df: pd.DataFrame, value_col: str = "Close") -> dict:
    if df is None or df.empty or value_col not in df.columns:
        return {}
    s = pd.to_numeric(df[value_col], errors="coerce").dropna()
    if s.empty:
        return {}
    latest_value = float(s.iloc[-1])
    change_prev = float((s.iloc[-1] / s.iloc[-2] - 1.0)) if len(s) > 1 and s.iloc[-2] != 0 else 0.0
    latest_idx = df.index[-1]
    date_value = latest_idx.strftime('%Y-%m-%d') if hasattr(latest_idx, "strftime") else str(latest_idx)[:10]
    return {
        "date": date_value,
        "latest_value": latest_value,
        "change_prev": change_prev,
        "change_1d": change_prev,
    }


def build_custom_macro_indicators(summary_latest: dict) -> None:
    summary_latest.setdefault("BUFFETT_INDICATOR", {
        "date": "",
        "latest_value": None,
        "change_prev": None,
        "change_1d": None,
        "status": "미확인",
    })
    summary_latest.setdefault("CREDIT_OSCILLATOR", {
        "date": "",
        "latest_value": None,
        "change_prev": None,
        "change_1d": None,
        "status": "미확인",
    })

    # Buffett 지수: FRED의 시가총액/GDP 비율 시계열(%).
    # (대체 수집: DDDM01USA156NWDB)
    buffett = fetch_fred_series("DDDM01USA156NWDB", start=ten_years_ago_start())
    if buffett is not None and not buffett.empty:
        buffett_df = buffett.rename(columns={"value": "Buffett_Indicator"})[["Date", "Buffett_Indicator"]]
        buffett_df = buffett_df.dropna().sort_values("Date")
        if not buffett_df.empty:
            _save_macro_frame("BUFFETT_INDICATOR", buffett_df)
            metric = _extract_latest_metric(buffett_df.set_index("Date"), "Buffett_Indicator")
            if metric:
                summary_latest["BUFFETT_INDICATOR"] = metric
                summary_latest["BUFFETT_INDICATOR"]["status"] = "OK"

    # 신용 오실레이터: Moody's BAA-AAA 스프레드
    baa = fetch_fred_series("BAA10YM")
    if baa is None or baa.empty:
        baa = fetch_fred_series("BAA")
    aaa = fetch_fred_series("AAA10YM")
    if aaa is None or aaa.empty:
        aaa = fetch_fred_series("AAA")
    if baa is not None and aaa is not None:
        b = baa.rename(columns={"value": "baa"})
        a = aaa.rename(columns={"value": "aaa"})
        merged = pd.merge(b, a, on="Date", how="inner")
        merged["Credit_Oscillator"] = merged["baa"] - merged["aaa"]
        credit_df = merged[["Date", "Credit_Oscillator"]].dropna().sort_values("Date")
        if not credit_df.empty:
            _save_macro_frame("CREDIT_OSCILLATOR", credit_df)
            metric = _extract_latest_metric(credit_df.set_index("Date"), "Credit_Oscillator")
            if metric:
                summary_latest["CREDIT_OSCILLATOR"] = metric
                summary_latest["CREDIT_OSCILLATOR"]["status"] = "OK"


def calculate_spreads(data_dict: dict) -> dict:
    """
    Calculate derived spread indicators.
    
    Role: calculate_spreads 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    spreads = {}
    
    # 10Y-2Y spread (using IRX as proxy for short-term)
    if 'TNX' in data_dict and 'IRX' in data_dict:
        tnx = data_dict['TNX']['Close']
        irx = data_dict['IRX']['Close']
        # Align indices
        common_idx = tnx.index.intersection(irx.index)
        spread = tnx.loc[common_idx] - irx.loc[common_idx]
        spreads['YIELD_SPREAD'] = pd.DataFrame({'Spread': spread})
    
    return spreads


def fetch_all(period: str = '10y') -> dict:
    """
    Fetch all macro indicators.
    
    Role: fetch_all 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting global macro fetch...")
    
    data_dict = {}
    
    for symbol, ticker in SYMBOLS.items():
        print(f"  Fetching {symbol}...")
        df = fetch_symbol(symbol, ticker, period)
        if df is not None:
            # Save individual file
            path = os.path.join(DATA_DIR, f'{symbol}.csv')
            df.to_csv(path)
            data_dict[symbol] = df
            print(f"    Saved {len(df)} rows to {path}")
    
    # Calculate spreads
    spreads = calculate_spreads(data_dict)
    for name, df in spreads.items():
        path = os.path.join(DATA_DIR, f'{name}.csv')
        df.to_csv(path)
        print(f"  Calculated {name}, saved to {path}")
    
    # Create summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'symbols_fetched': list(data_dict.keys()),
        'spreads_calculated': list(spreads.keys()),
        'period': period
    }
    
    # Latest values for quick reference
    latest = {}
    for symbol, df in data_dict.items():
        if len(df) > 0:
            latest[symbol] = {
                'date': df.index[-1].strftime('%Y-%m-%d'),
                'close': float(df['Close'].iloc[-1]),
                'latest_value': float(df['Close'].iloc[-1]),
                'change_prev': float(df['Close'].pct_change().iloc[-1]) if len(df) > 1 else 0,
                'change_1d': float(df['Close'].pct_change().iloc[-1]) if len(df) > 1 else 0,
                'change_5d': float((df['Close'].iloc[-1] / df['Close'].iloc[-5] - 1)) if len(df) > 5 else 0,
            }

    build_custom_macro_indicators(latest)
    summary['latest'] = latest
    
    summary_path = os.path.join(DATA_DIR, 'macro_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Global macro fetch complete.")
    return summary


def get_regime_signals() -> dict:
    """
    
        Generate regime signals from macro data.
        Returns dict with current regime assessment.
        
    Role: get_regime_signals 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    try:
        summary_path = os.path.join(DATA_DIR, 'macro_summary.json')
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        
        latest = summary.get('latest', {})
        
        signals = {
            'timestamp': datetime.now().isoformat(),
            'regime': 'unknown',
            'confidence': 0.0,
            'factors': {}
        }
        
        # VIX-based fear gauge
        vix = latest.get('VIX', {}).get('close', 20)
        if vix > 30:
            signals['factors']['vix'] = 'high_fear'
        elif vix > 20:
            signals['factors']['vix'] = 'elevated'
        else:
            signals['factors']['vix'] = 'calm'
        
        # SOX for semiconductor sentiment
        sox_change = latest.get('SOX', {}).get('change_5d', 0)
        if sox_change > 0.05:
            signals['factors']['sox'] = 'bullish'
        elif sox_change < -0.05:
            signals['factors']['sox'] = 'bearish'
        else:
            signals['factors']['sox'] = 'neutral'
        
        # DXY for dollar strength (inverse for EM/KR)
        dxy_change = latest.get('DXY', {}).get('change_5d', 0)
        if dxy_change > 0.02:
            signals['factors']['dxy'] = 'strong_dollar'
        elif dxy_change < -0.02:
            signals['factors']['dxy'] = 'weak_dollar'
        else:
            signals['factors']['dxy'] = 'stable'
        
        # Determine overall regime
        fear_factors = sum(1 for v in signals['factors'].values() if v in ['high_fear', 'bearish', 'strong_dollar'])
        greed_factors = sum(1 for v in signals['factors'].values() if v in ['calm', 'bullish', 'weak_dollar'])
        
        if fear_factors >= 2:
            signals['regime'] = 'risk_off'
            signals['confidence'] = fear_factors / 3
        elif greed_factors >= 2:
            signals['regime'] = 'risk_on'
            signals['confidence'] = greed_factors / 3
        else:
            signals['regime'] = 'mixed'
            signals['confidence'] = 0.5
        
        return signals
        
    except Exception as e:
        return {'error': str(e), 'regime': 'unknown'}


if __name__ == "__main__":
    result = fetch_all('10y')
    print("\nSummary:")
    print(json.dumps(result, indent=2))
    
    print("\nRegime Signals:")
    signals = get_regime_signals()
    print(json.dumps(signals, indent=2))
