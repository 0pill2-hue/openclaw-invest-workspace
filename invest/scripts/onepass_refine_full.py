import os
import glob
import pandas as pd
import numpy as np
import json
import shutil
import hashlib
from datetime import datetime
import traceback

# TODO(refactor-phase2): move core refine logic into invest.pipeline modules (behavior-preserving migration).
try:
    import invest.pipeline  # noqa: F401
except Exception:
    # import 준비용: 현재 동작 영향 0 유지
    pass

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

MAX_DAILY_RET_ABS = 0.8

os.makedirs(REPORT_DIR, exist_ok=True)

INDEX_PATH = os.path.join(CLEAN_BASE, 'production', '_processed_index.json')

def _load_processed_index():
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_processed_index(idx: dict):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def _file_sig(path: str) -> str:
    st = os.stat(path)
    key = f"{st.st_size}:{int(st.st_mtime)}:{path}".encode('utf-8')
    return hashlib.sha1(key).hexdigest()

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x.columns = [str(c).strip() for c in x.columns]
    drop_cols = [c for c in x.columns if c.startswith('Unnamed:') or c in ('index', '')]
    if drop_cols:
        x = x.drop(columns=drop_cols, errors='ignore')
    rename_map = {
        '날짜': 'Date', 'date': 'Date',
        'adj close': 'Adj Close', 'adjclose': 'Adj Close',
        'vol': 'Volume', '거래량': 'Volume',
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
        q = x.copy(); q['reason'] = 'missing_date_column'
        return pd.DataFrame(), q

    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors='coerce')

    # 기본 불량
    bad = x['Date'].isna() | x['Close'].isna() | (x['Close'] <= 0)

    # 수익률 급등락은 정제 단계에서 즉시 삭제하지 않고, 검증 단계 경고/PENDING으로 처리

    # OHLC 논리 위반
    if 'High' in x.columns and 'Low' in x.columns:
        bad |= (x['High'] < x['Low'])
    if 'High' in x.columns and 'Close' in x.columns:
        bad |= (x['High'] < x['Close'])
    if 'Low' in x.columns and 'Close' in x.columns:
        bad |= (x['Low'] > x['Close'])
    if all(c in x.columns for c in ['Open', 'High', 'Low', 'Volume']):
        bad |= ((x['Volume'] > 0) & (x['Open'] <= 0) & (x['High'] <= 0) & (x['Low'] <= 0))

    # 중복 날짜 제거 및 정렬 (clean만)
    clean_df = x[~bad].copy().sort_values('Date')
    if 'Date' in clean_df.columns:
        clean_df = clean_df.drop_duplicates(subset=['Date'], keep='last')
    bad_df = x[bad].copy()
    return clean_df, bad_df

def sanitize_supply(df: pd.DataFrame):
    x = _normalize_columns(df)
    if x.empty: return x, x
    col_map = {'날짜': 'Date', '일자': 'Date', '기관': 'Inst', '법인': 'Corp', '개인': 'Indiv', '외국인': 'Foreign', '합계': 'Total'}
    x = x.rename(columns={c: col_map[c] for c in x.columns if c in col_map})
    required = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
    if not all(c in x.columns for c in required):
        if x.shape[1] >= 6:
            x = x.iloc[:, :6].copy()
            x.columns = required
        else:
            q = x.copy(); q['reason'] = 'missing_supply_columns'
            return pd.DataFrame(), q
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    for c in ['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    bad = x['Date'].isna() | x[['Inst', 'Corp', 'Indiv', 'Foreign', 'Total']].isna().all(axis=1)
    clean_df = x[~bad].copy().sort_values('Date').drop_duplicates(subset=['Date'], keep='last')
    bad_df = x[bad].copy()
    return clean_df, bad_df

def sanitize_generic_csv(df: pd.DataFrame, folder: str = ''):
    x = _normalize_columns(df)
    # google_trends 컬럼명 표준화
    if 'google_trends' in folder:
        lower = {c.lower(): c for c in x.columns}
        if 'value' not in x.columns:
            picked = None
            for cand in ['val', 'score', 'trend', 'interest']:
                if cand in lower:
                    picked = lower[cand]
                    break
            # 후보명이 없으면 date 제외 첫 숫자형 컬럼을 value로 승격
            if picked is None:
                for c in x.columns:
                    if c.lower() in ('date', '날짜'):
                        continue
                    s = pd.to_numeric(x[c], errors='coerce')
                    if s.notna().sum() > 0:
                        picked = c
                        break
            if picked is not None:
                x = x.rename(columns={picked: 'value'})
        if 'date' not in x.columns and 'Date' in x.columns:
            x = x.rename(columns={'Date': 'date'})
    return x, pd.DataFrame()

def sanitize_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
        return (data, None) if data else (None, "Empty JSON")
    except Exception as e: return None, str(e)

def sanitize_text(path):
    try:
        with open(path, 'r', encoding='utf-8') as f: content = f.read()
        return (content, None) if len(content.strip()) >= 10 else (None, "Too short")
    except Exception as e: return None, str(e)

def run_full_refine():
    results = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    final_clean_base = os.path.join(CLEAN_BASE, 'production')
    final_q_base = os.path.join(Q_BASE, 'production')
    processed_index = _load_processed_index()
    
    for folder in FOLDERS:
        raw_dir = os.path.join(RAW_BASE, folder)
        if not os.path.exists(raw_dir): continue

        all_files = []
        for ext in ['*.csv', '*.json', '*.md', '*.txt']:
            all_files.extend(glob.glob(os.path.join(raw_dir, '**', ext), recursive=True))
        
        num_files = len(all_files)
        clean_count = 0
        q_count = 0
        skipped_count = 0
        
        clean_out_dir = os.path.join(final_clean_base, folder)
        q_out_dir = os.path.join(final_q_base, folder)
        os.makedirs(clean_out_dir, exist_ok=True)
        os.makedirs(q_out_dir, exist_ok=True)

        for f in all_files:
            rel_path = os.path.relpath(f, raw_dir)
            ext = os.path.splitext(f)[1].lower()
            clean_path = os.path.join(clean_out_dir, rel_path)
            q_path = os.path.join(q_out_dir, rel_path)
            os.makedirs(os.path.dirname(clean_path), exist_ok=True)
            os.makedirs(os.path.dirname(q_path), exist_ok=True)

            idx_key = f"{folder}/{rel_path}".replace('\\', '/')
            sig = _file_sig(f)
            prev_sig = processed_index.get(idx_key)
            if prev_sig == sig and (os.path.exists(clean_path) or os.path.exists(q_path)):
                skipped_count += 1
                continue

            try:
                if ext == '.csv':
                    df = pd.read_csv(f)
                    c_df, q_df = (sanitize_ohlcv(df) if 'ohlcv' in folder else 
                                 sanitize_supply(df) if 'supply' in folder else 
                                 sanitize_generic_csv(df, folder=folder))
                    if not c_df.empty:
                        c_df.to_csv(clean_path, index=False)
                        clean_count += 1
                    if not q_df.empty:
                        q_df.to_csv(q_path, index=False)
                        q_count += 1
                    elif c_df.empty:
                        # 완전 탈락 파일도 보존법칙을 위해 quarantine에 이유 저장
                        pd.DataFrame([{'reason': 'empty_after_sanitize'}]).to_csv(q_path, index=False)
                        q_count += 1
                elif ext == '.json':
                    data, err = sanitize_json(f)
                    if data:
                        with open(clean_path, 'w', encoding='utf-8') as fout:
                            json.dump(data, fout, ensure_ascii=False, indent=2)
                        clean_count += 1
                    else:
                        with open(q_path, 'w', encoding='utf-8') as qout:
                            json.dump({'reason': err or 'invalid_json'}, qout, ensure_ascii=False, indent=2)
                        q_count += 1
                else:
                    content, err = sanitize_text(f)
                    if content:
                        with open(clean_path, 'w', encoding='utf-8') as fout:
                            fout.write(content)
                        clean_count += 1
                    else:
                        with open(q_path, 'w', encoding='utf-8') as qout:
                            qout.write(f'reason: {err or "invalid_text"}\n')
                        q_count += 1

                processed_index[idx_key] = sig
            except Exception as e:
                with open(q_path, 'w', encoding='utf-8') as qout:
                    qout.write(f'reason: exception\n{type(e).__name__}: {e}\n')
                q_count += 1

        results.append({
            'folder': folder, 'total': num_files, 'clean': clean_count, 'quarantine': q_count, 'skipped': skipped_count
        })

    report_path = os.path.join(REPORT_DIR, f"FULL_REFINE_REPORT_{timestamp}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Full Refinement Report\n\n")
        f.write(f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Clean Base: {final_clean_base}\n")
        f.write("| Folder | Total | Clean | Quarantine | Skipped(incremental) |\n| :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            f.write(f"| {r['folder']} | {r['total']} | {r['clean']} | {r['quarantine']} | {r.get('skipped',0)} |\n")
    
    _save_processed_index(processed_index)
    print(f"Full refinement report: {report_path}")
    return report_path

if __name__ == "__main__":
    run_full_refine()
