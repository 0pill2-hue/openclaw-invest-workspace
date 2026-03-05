import os
import json
import sys
from pathlib import Path
from collections import Counter

import pandas as pd

try:
    from invest.stages.run_manifest import write_run_manifest
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from run_manifest import write_run_manifest

STAGE5_ROOT = Path(__file__).resolve().parents[1]
INPUTS_ROOT = STAGE5_ROOT / 'inputs'

CLEAN_PROD_DIR = INPUTS_ROOT / 'upstream_stage2_clean'
OHLCV_DIR = CLEAN_PROD_DIR / 'kr' / 'ohlcv'
SUPPLY_DIR = CLEAN_PROD_DIR / 'kr' / 'supply'
MASTER_LIST_PATH = INPUTS_ROOT / 'upstream_stage1_master' / 'kr_stock_list.csv'
OUTPUT_DIR = STAGE5_ROOT / 'outputs' / 'features' / 'kr'
REPORT_DIR = STAGE5_ROOT / 'outputs' / 'reports'

INCLUDED_MARKETS = {"KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"}
INCLUDED_MARKET_IDS = {"STK", "KSQ"}


def _guard_no_raw_path(*paths: Path) -> None:
    """
    Role: 경로 중에 'raw'가 포함되어 있는지 확인하여 가공 데이터의 오염(raw 참조)을 방지한다.
    Input: paths (검사할 경로 목록)
    Output: None (위반 시 AssertionError 발생)
    Author: 조비스 (Flash)
    Date: 2026-02-18

    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-03-04
    """
    for p in paths:
        p_str = str(p).replace('\\', '/').lower()
        assert '/raw/' not in p_str, f'RAW path reference detected: {p}'


def _load_kr_universe_codes() -> list[str]:
    if not MASTER_LIST_PATH.exists():
        raise FileNotFoundError(f"master list not found: {MASTER_LIST_PATH}")

    df = pd.read_csv(MASTER_LIST_PATH)
    if 'Code' not in df.columns:
        raise ValueError('master list missing required column: Code')

    x = df.copy()
    x['Code'] = x['Code'].astype(str).str.zfill(6)

    if 'Market' in x.columns:
        x['Market'] = x['Market'].astype(str).str.upper().str.strip()
        x = x[x['Market'].isin(INCLUDED_MARKETS)]
    elif 'MarketId' in x.columns:
        x['MarketId'] = x['MarketId'].astype(str).str.upper().str.strip()
        x = x[x['MarketId'].isin(INCLUDED_MARKET_IDS)]

    return sorted(x['Code'].dropna().unique().tolist())


def generate_features(stock_code: str):
    """
    Role: 특정 종목의 정제 데이터를 기반으로 가격 모멘텀, 변동성, 수급 지표 등 핵심 피처를 산출한다.
    Input: stock_code (종목코드)
    Output: (df | None, skip_reason | None)
    Side effect: 없음
    Author: 조비스 (Flash)
    Updated: 2026-03-04
    """
    ohlcv_path = OHLCV_DIR / f'{stock_code}.csv'
    supply_path = SUPPLY_DIR / f'{stock_code}_supply.csv'

    _guard_no_raw_path(ohlcv_path, supply_path, OUTPUT_DIR)

    if not os.path.exists(ohlcv_path):
        return None, 'missing_ohlcv'

    df = pd.read_csv(ohlcv_path)
    if df.empty:
        return None, 'empty_ohlcv'

    if 'Date' not in df.columns and len(df.columns) > 0:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: 'Date'})

    required_cols = {'Date', 'Open', 'High', 'Low', 'Close', 'Volume'}
    if not required_cols.issubset(set(df.columns)):
        return None, f"missing_columns:{','.join(sorted(required_cols - set(df.columns)))}"

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df = df.dropna(subset=['Date', 'Close']).sort_values('Date').drop_duplicates(subset=['Date'], keep='last')
    if df.empty:
        return None, 'no_valid_price_rows'

    df.set_index('Date', inplace=True)

    # 1. Price Momentum
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['Disparity20'] = (df['Close'] / df['MA20']) * 100

    # 2. Volatility
    df['Returns'] = df['Close'].pct_change()
    df['Volat_20'] = df['Returns'].rolling(window=20).std()

    # 3. Supply Features (optional)
    if os.path.exists(supply_path):
        sdf = pd.read_csv(supply_path)
        if not sdf.empty:
            if sdf.shape[1] >= 6:
                sdf = sdf.iloc[:, :6]
                sdf.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
            if 'Date' in sdf.columns:
                sdf['Date'] = pd.to_datetime(sdf['Date'], errors='coerce')
                for c in ['Inst', 'Foreign']:
                    if c in sdf.columns:
                        sdf[c] = pd.to_numeric(sdf[c], errors='coerce')
                sdf = sdf.dropna(subset=['Date']).drop_duplicates(subset=['Date'], keep='last').set_index('Date')
                keep_cols = [c for c in ['Inst', 'Foreign'] if c in sdf.columns]
                if keep_cols:
                    df = df.join(sdf[keep_cols], how='left')

    if 'Inst' not in df.columns:
        df['Inst'] = 0
    if 'Foreign' not in df.columns:
        df['Foreign'] = 0

    df[['Inst', 'Foreign']] = df[['Inst', 'Foreign']].fillna(0)

    # Cumulative supply momentum (20 days)
    df['Net_Foreign_20'] = df['Foreign'].rolling(window=20).sum()
    df['Net_Inst_20'] = df['Inst'].rolling(window=20).sum()

    return df.reset_index(), None


def run_stage5_batch():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    codes = _load_kr_universe_codes()

    summary = {
        'grade': 'DRAFT',
        'watermark': 'TEST ONLY',
        'adoption_gate': 'stage09_required',
        'universe_policy': {
            'kr_include_markets': sorted(INCLUDED_MARKETS),
            'kr_exclude_markets': 'others (e.g., KONEX)',
        },
        'universe_total': len(codes),
        'processed': 0,
        'skipped': 0,
        'errors': 0,
        'output_dir': str(OUTPUT_DIR),
        'report_path': '',
        'manifest_path': '',
        'skip_reasons': {},
        'error_examples': [],
    }

    skip_counter = Counter()

    for code in codes:
        try:
            feat_df, skip_reason = generate_features(code)
            if feat_df is None:
                summary['skipped'] += 1
                skip_counter[skip_reason or 'unknown_skip'] += 1
                continue

            out_path = OUTPUT_DIR / f'{code}.csv'
            feat_df.to_csv(out_path, index=False)
            summary['processed'] += 1
        except Exception as ex:
            summary['errors'] += 1
            if len(summary['error_examples']) < 30:
                summary['error_examples'].append({
                    'symbol': code,
                    'error_type': type(ex).__name__,
                    'error': str(ex),
                })

    summary['skip_reasons'] = dict(skip_counter)

    ts = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    report_path = REPORT_DIR / f'STAGE5_FEATURE_RUN_{ts}.json'
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    manifest_path = STAGE5_ROOT / 'outputs' / f'manifest_stage5_feature_{ts}.json'
    write_run_manifest(
        run_type='stage5_feature_engineering',
        params={
            'master_list': str(MASTER_LIST_PATH),
            'ohlcv_dir': str(OHLCV_DIR),
            'supply_dir': str(SUPPLY_DIR),
            'output_dir': str(OUTPUT_DIR),
        },
        inputs=[str(MASTER_LIST_PATH), str(OHLCV_DIR), str(SUPPLY_DIR)],
        outputs=[str(report_path), str(OUTPUT_DIR)],
        out_path=str(manifest_path),
        workdir='.',
    )

    summary['report_path'] = str(report_path)
    summary['manifest_path'] = str(manifest_path)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"STAGE5_DONE report={report_path}")
    print(f"STAGE5_MANIFEST={manifest_path}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    run_stage5_batch()
