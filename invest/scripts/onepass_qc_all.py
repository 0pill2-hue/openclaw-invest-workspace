import os
import glob
import pandas as pd
import numpy as np
import random
import json
import shutil
from datetime import datetime
import traceback

# Configuration
BASE_DATA = '/Users/jobiseu/.openclaw/workspace/invest/data'
RAW_BASE = os.path.join(BASE_DATA, 'raw')
CLEAN_BASE = os.path.join(BASE_DATA, 'clean')
Q_BASE = os.path.join(BASE_DATA, 'quarantine')
REPORT_DIR = '/Users/jobiseu/.openclaw/workspace/reports/qc'

FOLDERS = [
    'kr/ohlcv', 'kr/supply', 'kr/dart',
    'us/ohlcv',
    'market/news/rss', 'market/macro', 'market/google_trends',
    'text/blog', 'text/telegram', 'text/image_map', 'text/images_ocr', 'text/premium/startale'
]

MIN_VALID_VOLUME = 1
MAX_DAILY_RET_ABS = 0.8  # more relaxed to avoid over-quarantine on valid volatile names

os.makedirs(REPORT_DIR, exist_ok=True)

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x.columns = [str(c).strip() for c in x.columns]

    # drop accidental unnamed/index-like columns from shifted exports
    drop_cols = [c for c in x.columns if c.startswith('Unnamed:') or c in ('index', '')]
    if drop_cols:
        x = x.drop(columns=drop_cols, errors='ignore')

    # common alias mapping (KR/US mixed headers)
    rename_map = {
        '날짜': 'Date',
        'date': 'Date',
        'adj close': 'Adj Close',
        'adjclose': 'Adj Close',
        'vol': 'Volume',
        '거래량': 'Volume',
    }
    low_map = {c: rename_map[c.lower()] for c in x.columns if c.lower() in rename_map}
    if low_map:
        x = x.rename(columns=low_map)

    return x


def sanitize_ohlcv(df: pd.DataFrame):
    x = _normalize_columns(df)
    if x.empty: return x, x

    if 'Date' not in x.columns and not isinstance(x.index, pd.DatetimeIndex):
        x = x.reset_index().rename(columns={'index': 'Date'})

    if 'Date' not in x.columns:
        # hard schema miss -> quarantine as-is
        q = x.copy()
        q['reason'] = 'missing_date_column'
        return pd.DataFrame(), q

    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors='coerce')
    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    r1 = (
        x['Date'].isna() |
        x['Close'].isna() | (x['Close'] <= 0)
    )
    bad |= r1
    reason.loc[r1] = 'invalid_date_or_price'

    if 'Close' in x.columns:
        ret = x['Close'].pct_change().abs() > MAX_DAILY_RET_ABS
        # avoid over-quarantine: only flag when volume exists and positive
        vol_ok = (x['Volume'] > 0) if 'Volume' in x.columns else True
        spike = ret.fillna(False) & vol_ok
        bad |= spike
        reason.loc[spike] = 'extreme_return_spike'
    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values

    clean_df = x[~bad].copy()
    return clean_df, bad_df

def sanitize_supply(df: pd.DataFrame):
    x = _normalize_columns(df)
    if x.empty: return x, x

    # explicit KR->EN mapping first
    col_map = {
        '날짜': 'Date', '일자': 'Date',
        '기관': 'Inst', '법인': 'Corp', '개인': 'Indiv', '외국인': 'Foreign', '합계': 'Total'
    }
    x = x.rename(columns={c: col_map[c] for c in x.columns if c in col_map})

    required = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
    if not all(c in x.columns for c in required):
        # fallback: positional mapping for legacy files
        if x.shape[1] >= 6:
            x = x.iloc[:, :6].copy()
            x.columns = required
        else:
            q = x.copy()
            q['reason'] = 'missing_supply_columns'
            return pd.DataFrame(), q

    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']:
        x[c] = pd.to_numeric(x[c], errors='coerce')

    bad = x['Date'].isna() | x[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']].isna().all(axis=1)
    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = 'invalid_date_or_all_numeric_missing'
    clean_df = x[~bad].copy()
    return clean_df, bad_df

def sanitize_generic_csv(df: pd.DataFrame):
    if df.empty: return df, df
    return df, pd.DataFrame()

def sanitize_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return None, "Empty JSON"
        return data, None
    except Exception as e:
        return None, str(e)

def sanitize_text(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content.strip()) < 10:
            return None, "Too short or empty"
        return content, None
    except Exception as e:
        return None, str(e)

def run_qc():
    results = []
    anomalies = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_clean_base = os.path.join(CLEAN_BASE, f'qc_run_{timestamp}')
    run_q_base = os.path.join(Q_BASE, f'qc_run_{timestamp}')
    
    for folder in FOLDERS:
        raw_dir = os.path.join(RAW_BASE, folder)
        if not os.path.exists(raw_dir):
            print(f"Directory not found: {raw_dir}")
            continue

        all_files = []
        for ext in ['*.csv', '*.json', '*.md', '*.txt']:
            all_files.extend(glob.glob(os.path.join(raw_dir, '**', ext), recursive=True))
        
        num_files = len(all_files)
        if num_files == 0:
            results.append({
                'folder': folder, 'files': 0, 'samples': 0, 
                'clean': 0, 'quarantine': 0, 'ratio': '0%', 'status': 'EMPTY'
            })
            continue

        sample_size = max(1, int(num_files * 0.1))
        sample_files = random.sample(all_files, sample_size)
        
        clean_count = 0
        q_count = 0
        fail_count = 0
        
        clean_out_dir = os.path.join(run_clean_base, folder)
        q_out_dir = os.path.join(run_q_base, folder)
        os.makedirs(clean_out_dir, exist_ok=True)
        os.makedirs(q_out_dir, exist_ok=True)

        for f in sample_files:
            fname = os.path.basename(f)
            ext = os.path.splitext(f)[1].lower()
            
            is_clean = False
            error_msg = ""
            
            try:
                if ext == '.csv':
                    df = pd.read_csv(f)
                    if 'ohlcv' in folder:
                        c_df, q_df = sanitize_ohlcv(df)
                    elif 'supply' in folder:
                        c_df, q_df = sanitize_supply(df)
                    else:
                        c_df, q_df = sanitize_generic_csv(df)
                    
                    if not c_df.empty:
                        c_df.to_csv(os.path.join(clean_out_dir, fname), index=False)
                        is_clean = True
                    if not q_df.empty:
                        q_df.to_csv(os.path.join(q_out_dir, fname), index=False)
                
                elif ext == '.json':
                    data, err = sanitize_json(f)
                    if data:
                        with open(os.path.join(clean_out_dir, fname), 'w', encoding='utf-8') as fout:
                            json.dump(data, fout, ensure_ascii=False, indent=2)
                        is_clean = True
                    else:
                        error_msg = err
                        with open(os.path.join(q_out_dir, fname + '.err'), 'w') as fout:
                            fout.write(error_msg)
                
                else: # .md, .txt
                    content, err = sanitize_text(f)
                    if content:
                        with open(os.path.join(clean_out_dir, fname), 'w', encoding='utf-8') as fout:
                            fout.write(content)
                        is_clean = True
                    else:
                        error_msg = err
                        with open(os.path.join(q_out_dir, fname + '.err'), 'w') as fout:
                            fout.write(error_msg)

            except Exception as e:
                error_msg = str(e)
                fail_count += 1
                with open(os.path.join(q_out_dir, fname + '.fail'), 'w') as fout:
                    fout.write(traceback.format_exc())

            if is_clean:
                clean_count += 1
            else:
                q_count += 1

        ratio = (clean_count / sample_size) * 100 if sample_size > 0 else 0
        status = 'OK'
        if clean_count == 0: status = 'ZERO_CLEAN'
        if q_count == sample_size: status = 'FULL_QUARANTINE'
        if fail_count > 0: status += f' (FAILS: {fail_count})'

        results.append({
            'folder': folder,
            'files': num_files,
            'samples': sample_size,
            'clean': clean_count,
            'quarantine': q_count,
            'ratio': f"{ratio:.1f}%",
            'status': status
        })

    # Generate Report
    report_path = os.path.join(REPORT_DIR, f"QC_ALL_FOLDERS_{timestamp}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# All Folders One-Pass QC Report\n\n")
        f.write(f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Sampling: ~10%\n")
        f.write(f"- Clean output: {run_clean_base}\n")
        f.write(f"- Quarantine output: {run_q_base}\n\n")
        
        f.write("## Execution Summary\n\n")
        f.write("| Folder | Total Files | Samples | Clean | Quarantine | Clean Ratio | Status |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            f.write(f"| {r['folder']} | {r['files']} | {r['samples']} | {r['clean']} | {r['quarantine']} | {r['ratio']} | {r['status']} |\n")
        
        f.write("\n## Findings & Anomalies\n\n")
        bad_folders = [r for r in results if r['clean'] == 0 and r['samples'] > 0]
        if bad_folders:
            f.write("### ⚠️ Critical Issues\n")
            for r in bad_folders:
                f.write(f"- `{r['folder']}`: 0 clean samples found. Check if parser or rules are misaligned.\n")
        else:
            f.write("No critical issues (0 clean) found.\n")

    print(f"Report saved to: {report_path}")
    return report_path, results

if __name__ == "__main__":
    run_qc()
