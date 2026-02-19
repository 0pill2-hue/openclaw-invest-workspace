import os
import glob
import pandas as pd
import numpy as np
import random
from datetime import datetime

# Paths
BASE = '/Users/jobiseu/.openclaw/workspace/invest/data'
RAW_DIRS = {
    'kr_ohlcv': os.path.join(BASE, 'raw/kr/ohlcv'),
    'kr_supply': os.path.join(BASE, 'raw/kr/supply'),
    'us_ohlcv': os.path.join(BASE, 'raw/us/ohlcv')
}
CLEAN_BASE = os.path.join(BASE, 'clean')
Q_BASE = os.path.join(BASE, 'quarantine')
REPORT_DIR = '/Users/jobiseu/.openclaw/workspace/reports/qc'

MIN_VALID_VOLUME = 10
MAX_DAILY_RET_ABS = 0.35

os.makedirs(REPORT_DIR, exist_ok=True)

def sanitize_ohlcv(df: pd.DataFrame):
    """
    Role: sanitize_ohlcv 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    x = df.copy()
    if 'Date' not in x.columns and not isinstance(x.index, pd.DatetimeIndex):
        # fdr format sometimes has Date as index
        x = x.reset_index().rename(columns={'index': 'Date'})
    
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors='coerce')

    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    r1 = (
        x['Date'].isna() |
        x['Close'].isna() | (x['Close'] <= 0) |
        x['Open'].isna() | x['High'].isna() | x['Low'].isna() |
        x['Volume'].isna() | (x['Volume'] < MIN_VALID_VOLUME)
    )
    bad |= r1
    reason.loc[r1] = 'basic_invalid_or_low_liquidity'

    r2 = ((x['Open'] <= 0) & (x['High'] <= 0) & (x['Low'] <= 0) & (x['Close'] > 0) & (x['Volume'] == 0))
    bad |= r2
    reason.loc[r2] = 'zero_candle'

    if 'Close' in x.columns:
        ret = x['Close'].pct_change().abs() > MAX_DAILY_RET_ABS
        bad |= ret.fillna(False)
        reason.loc[ret.fillna(False)] = 'return_spike_gt_35pct'

    # duplicate dates: keep first
    dup = x['Date'].duplicated(keep='first')
    bad |= dup
    reason.loc[dup] = 'duplicate_date'

    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values

    clean_df = x[~bad].copy()
    clean_df = clean_df.dropna(subset=['Date']).sort_values('Date')
    
    return clean_df, bad_df

def sanitize_supply(df: pd.DataFrame):
    """
    Role: sanitize_supply 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    x = df.copy()
    if x.shape[1] >= 6:
        x = x.iloc[:, :6]
        x.columns = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
    
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors='coerce')

    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    r1 = x['Date'].isna() | x[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']].isna().any(axis=1)
    bad |= r1
    reason.loc[r1] = 'invalid_date_or_nonnumeric'

    dup = x['Date'].duplicated(keep='first')
    bad |= dup
    reason.loc[dup] = 'duplicate_date'

    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values

    clean_df = x[~bad].copy().dropna(subset=['Date']).sort_values('Date')
    
    return clean_df, bad_df

def run_qc():
    """
    Role: run_qc 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    report_data = []
    anomalies = []

    for group, raw_dir in RAW_DIRS.items():
        if not os.path.exists(raw_dir):
            print(f"Skipping {group}, directory not found: {raw_dir}")
            continue

        all_files = glob.glob(os.path.join(raw_dir, '*.csv'))
        num_files = len(all_files)
        sample_size = max(1, int(num_files * 0.1))
        sample_files = random.sample(all_files, sample_size)

        print(f"Processing group {group}: {num_files} total files, 10% sample = {sample_size} files")

        total_input_rows = 0
        total_clean_rows = 0
        total_q_rows = 0
        
        group_clean_dir = os.path.join(CLEAN_BASE, group.replace('_', '/'))
        group_q_dir = os.path.join(Q_BASE, group.replace('_', '/'))
        os.makedirs(group_clean_dir, exist_ok=True)
        os.makedirs(group_q_dir, exist_ok=True)

        for f in sample_files:
            filename = os.path.basename(f)
            try:
                df = pd.read_csv(f)
                input_rows = len(df)
                total_input_rows += input_rows

                if 'supply' in group:
                    clean_df, bad_df = sanitize_supply(df)
                else:
                    clean_df, bad_df = sanitize_ohlcv(df)

                clean_rows = len(clean_df)
                q_rows = len(bad_df)
                total_clean_rows += clean_rows
                total_q_rows += q_rows

                # Save results (dry-run style, but in the requested directories)
                clean_df.to_csv(os.path.join(group_clean_dir, filename), index=False)
                if not bad_df.empty:
                    bad_df.to_csv(os.path.join(group_q_dir, filename), index=False)

                # Check for full file quarantine
                if input_rows > 0 and clean_rows == 0:
                    anomalies.append({
                        'group': group,
                        'file': filename,
                        'type': 'full_quarantine',
                        'rows': input_rows,
                        'reason': 'All rows failed validation'
                    })
                
                # Check for high quarantine ratio (> 30%)
                if input_rows > 10 and (q_rows / input_rows) > 0.3:
                    anomalies.append({
                        'group': group,
                        'file': filename,
                        'type': 'high_quarantine_ratio',
                        'ratio': f"{q_rows/input_rows:.2%}",
                        'clean': clean_rows,
                        'quarantine': q_rows
                    })

            except Exception as e:
                print(f"Error processing {f}: {e}")

        clean_ratio = total_clean_rows / total_input_rows if total_input_rows > 0 else 0
        report_data.append({
            'folder': group,
            'input_files': sample_size,
            'total_input_rows': total_input_rows,
            'clean_rows': total_clean_rows,
            'q_rows': total_q_rows,
            'clean_ratio': f"{clean_ratio:.2%}"
        })

        # Check for folders with 0 clean records
        if total_clean_rows == 0 and total_input_rows > 0:
            anomalies.append({
                'group': group,
                'type': 'zero_clean_folder',
                'reason': 'No clean rows found in the entire sample'
            })

    # Generate Markdown Report
    report_path = os.path.join(REPORT_DIR, f"QC_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Data Cleaning QC Report (10% Sample)\n\n")
        f.write(f"Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Summary\n\n")
        f.write("| Folder | Sample Files | Clean Rows | Quarantine Rows | Clean Ratio |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for d in report_data:
            f.write(f"| {d['folder']} | {d['input_files']} | {d['clean_rows']} | {d['q_rows']} | {d['clean_ratio']} |\n")
        
        f.write("\n## Anomalies\n\n")
        if not anomalies:
            f.write("No major anomalies detected.\n")
        else:
            for a in anomalies:
                if a['type'] == 'full_quarantine':
                    f.write(f"- **FULL QUARANTINE**: `{a['group']}/{a['file']}` ({a['rows']} rows). Hypothesis: Symbol might be delisted or have extremely low liquidity.\n")
                elif a['type'] == 'high_quarantine_ratio':
                    f.write(f"- **HIGH Q RATIO**: `{a['group']}/{a['file']}` ratio={a['ratio']}. Hypothesis: Data feed might be noisy or contains many extreme outliers.\n")
                elif a['type'] == 'zero_clean_folder':
                    f.write(f"- **ZERO CLEAN FOLDER**: `{a['group']}`. Hypothesis: Rule set might be too strict for this folder's data format.\n")

    print(f"Report generated: {report_path}")
    return report_path

if __name__ == "__main__":
    run_qc()
