import os
import glob
import json
from pathlib import Path
from datetime import datetime

import pandas as pd

from stage2_config import load_stage2_config_bundle

# Paths (stage-local input boundary)
STAGE2_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_STAGE1 = STAGE2_ROOT / 'inputs' / 'upstream_stage1'
STAGE2_OUT_BASE = STAGE2_ROOT / 'outputs'


def _resolve_raw_dir(rel_path: str) -> Path:
    return UPSTREAM_STAGE1 / 'raw' / 'signal' / rel_path


RAW_DIRS = {
    'kr_ohlcv': str(_resolve_raw_dir('kr/ohlcv')),
    'kr_supply': str(_resolve_raw_dir('kr/supply')),
    'us_ohlcv': str(_resolve_raw_dir('us/ohlcv')),
}
MASTER_LIST_PATH = str(UPSTREAM_STAGE1 / 'master/kr_stock_list.csv')
CLEAN_BASE = str(STAGE2_OUT_BASE / 'clean')
Q_BASE = str(STAGE2_OUT_BASE / 'quarantine')
REPORT_DIR = str(STAGE2_OUT_BASE / 'reports')
STAGE2_QC_VERSION = '2026-03-08-stage2-qc-r3'

STAGE2_CONFIG_BUNDLE = load_stage2_config_bundle()
STAGE2_RUNTIME_CONFIG = STAGE2_CONFIG_BUNDLE['runtime']
STAGE2_REASON_CONFIG = STAGE2_CONFIG_BUNDLE['reason']
STAGE2_CONFIG_PROVENANCE = STAGE2_CONFIG_BUNDLE['provenance']

QC_RUNTIME_CONFIG = STAGE2_RUNTIME_CONFIG['qc']
QC_REASON_CONFIG = STAGE2_REASON_CONFIG['qc']
QC_UNIVERSE_CONFIG = QC_RUNTIME_CONFIG['universe']
QC_THRESHOLD_CONFIG = QC_RUNTIME_CONFIG['thresholds']
QC_ANOMALY_TAXONOMY = QC_REASON_CONFIG['anomaly_taxonomy']

HARD_FAIL_TYPES = set(QC_ANOMALY_TAXONOMY['fail_types'])
INCLUDED_MARKETS = set(QC_UNIVERSE_CONFIG['included_markets'])
INCLUDED_MARKET_IDS = set(QC_UNIVERSE_CONFIG['included_market_ids'])
MIN_VALID_VOLUME = int(QC_THRESHOLD_CONFIG['min_valid_volume'])
MAX_DAILY_RET_ABS = float(QC_THRESHOLD_CONFIG['max_daily_ret_abs'])

os.makedirs(REPORT_DIR, exist_ok=True)


def _load_kr_universe_codes() -> list[str]:
    if not os.path.exists(MASTER_LIST_PATH):
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


def sanitize_ohlcv(df: pd.DataFrame):
    """
    Role: sanitize_ohlcv 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-03-04
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
        ret = x['Close'].pct_change(fill_method=None).abs() > MAX_DAILY_RET_ABS
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
    Updated: 2026-03-04
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
    Updated: 2026-03-04
    """
    report_data = []
    anomalies = []

    universe_codes = _load_kr_universe_codes()

    for group, raw_dir in RAW_DIRS.items():
        group_stats = {
            'folder': group,
            'target_files': 0,
            'processed_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'skipped_files': 0,
            'total_input_rows': 0,
            'clean_rows': 0,
            'q_rows': 0,
            'clean_ratio': '0.00%',
        }

        if not os.path.exists(raw_dir):
            print(f"Skipping {group}, directory not found: {raw_dir}")
            report_data.append(group_stats)
            continue

        if group == 'kr_ohlcv':
            all_files = [os.path.join(raw_dir, f'{code}.csv') for code in universe_codes]
        elif group == 'kr_supply':
            all_files = [os.path.join(raw_dir, f'{code}_supply.csv') for code in universe_codes]
        else:
            all_files = sorted(glob.glob(os.path.join(raw_dir, '*.csv')))

        group_stats['target_files'] = len(all_files)
        print(f"Processing group {group}: {len(all_files)} files (full processing)")

        group_rel_path = group.replace('_', '/')
        group_clean_dir = os.path.join(CLEAN_BASE, 'production', 'signal', group_rel_path)
        group_q_dir = os.path.join(Q_BASE, 'production', 'signal', group_rel_path)
        os.makedirs(group_clean_dir, exist_ok=True)
        os.makedirs(group_q_dir, exist_ok=True)

        for f in all_files:
            group_stats['processed_files'] += 1
            filename = os.path.basename(f)

            if not os.path.exists(f):
                group_stats['skipped_files'] += 1
                anomalies.append({
                    'group': group,
                    'file': filename,
                    'type': 'missing_target_file',
                })
                continue

            try:
                df = pd.read_csv(f)
                if df.empty:
                    group_stats['skipped_files'] += 1
                    anomalies.append({
                        'group': group,
                        'file': filename,
                        'type': 'empty_input_file',
                    })
                    continue

                input_rows = len(df)
                group_stats['total_input_rows'] += input_rows

                if 'supply' in group:
                    clean_df, bad_df = sanitize_supply(df)
                else:
                    clean_df, bad_df = sanitize_ohlcv(df)

                clean_rows = len(clean_df)
                q_rows = len(bad_df)
                group_stats['clean_rows'] += clean_rows
                group_stats['q_rows'] += q_rows

                clean_df.to_csv(os.path.join(group_clean_dir, filename), index=False)
                if not bad_df.empty:
                    bad_df.to_csv(os.path.join(group_q_dir, filename), index=False)

                group_stats['success_files'] += 1

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
                        'ratio': f"{q_rows / input_rows:.2%}",
                        'clean': clean_rows,
                        'quarantine': q_rows
                    })

            except Exception as e:
                group_stats['failed_files'] += 1
                anomalies.append({
                    'group': group,
                    'file': filename,
                    'type': 'processing_error',
                    'error': str(e),
                })
                print(f"Error processing {f}: {e}")

        if group_stats['total_input_rows'] > 0:
            clean_ratio = group_stats['clean_rows'] / group_stats['total_input_rows']
            group_stats['clean_ratio'] = f"{clean_ratio:.2%}"

        # Check for folders with 0 clean records
        if group_stats['clean_rows'] == 0 and group_stats['total_input_rows'] > 0:
            anomalies.append({
                'group': group,
                'type': 'zero_clean_folder',
                'reason': 'No clean rows found in the entire full run'
            })

        report_data.append(group_stats)

    now = datetime.now()
    ts = now.strftime('%Y%m%d_%H%M%S')

    total_target = sum(d['target_files'] for d in report_data)
    total_processed = sum(d['processed_files'] for d in report_data)
    total_success = sum(d['success_files'] for d in report_data)
    total_failed = sum(d['failed_files'] for d in report_data)
    total_skipped = sum(d['skipped_files'] for d in report_data)

    hard_failures = [a for a in anomalies if a.get('type') in HARD_FAIL_TYPES]
    report_only_anomalies = [a for a in anomalies if a.get('type') not in HARD_FAIL_TYPES]

    summary = {
        'executed_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'qc_version': STAGE2_QC_VERSION,
        'mode': 'signal_validation_only_universe_based_for_kr',
        'writer_policy': {
            'signal_canonical_writer': 'stage02_qc_cleaning_full.py',
            'owned_signal_folders': ['kr/ohlcv', 'kr/supply', 'us/ohlcv'],
            'stage02_onepass_refine_full.py': 'market signal + qualitative only',
        },
        'universe_policy': {
            'kr_include_markets': sorted(INCLUDED_MARKETS),
            'kr_exclude_markets': 'others (e.g., KONEX)',
        },
        'anomaly_taxonomy': {
            'row_quarantine_reasons': list(QC_ANOMALY_TAXONOMY['row_quarantine_reasons']),
            'warn_types': list(QC_ANOMALY_TAXONOMY['warn_types']),
            'fail_types': sorted(HARD_FAIL_TYPES),
        },
        'config_provenance': STAGE2_CONFIG_PROVENANCE,
        'groups': report_data,
        'totals': {
            'target_files': total_target,
            'processed_files': total_processed,
            'success_files': total_success,
            'failed_files': total_failed,
            'skipped_files': total_skipped,
            'anomalies': len(anomalies),
            'hard_failures': len(hard_failures),
            'report_only_anomalies': len(report_only_anomalies),
        },
        'validation': {
            'pass': len(hard_failures) == 0,
            'hard_fail_types': sorted(HARD_FAIL_TYPES),
        },
        'anomalies': anomalies,
        'hard_failures': hard_failures,
        'report_only_anomalies': report_only_anomalies,
    }

    report_path = os.path.join(REPORT_DIR, f"QC_REPORT_{ts}.md")
    report_json_path = os.path.join(REPORT_DIR, f"QC_REPORT_{ts}.json")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Data Cleaning QC Report (Signal Validation Only)\n\n")
        f.write(f"Executed at: {summary['executed_at']}\n")
        f.write(f"QC version: {summary['qc_version']}\n")
        f.write("Writer policy: kr/us signal canonical writer=`stage02_qc_cleaning_full.py`, stage02_onepass_refine_full.py=`market signal + qualitative only`\n")
        f.write(f"Runtime config: {STAGE2_CONFIG_PROVENANCE['runtime_config_path']} ({STAGE2_CONFIG_PROVENANCE['runtime_config_sha1']})\n")
        f.write(f"Reason config: {STAGE2_CONFIG_PROVENANCE['reason_config_path']} ({STAGE2_CONFIG_PROVENANCE['reason_config_sha1']})\n")
        f.write(f"Config bundle SHA1: {STAGE2_CONFIG_PROVENANCE['bundle_sha1']}\n\n")
        f.write("Universe policy (KR): include KOSPI/KOSDAQ/KOSDAQ GLOBAL, exclude others (e.g., KONEX).\n\n")

        f.write("## Coverage Summary\n\n")
        f.write("| Folder | Target Files | Processed | Success | Failed | Skipped | Clean Rows | Quarantine Rows | Clean Ratio |\n")
        f.write("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n")
        for d in report_data:
            f.write(
                f"| {d['folder']} | {d['target_files']} | {d['processed_files']} | {d['success_files']} | "
                f"{d['failed_files']} | {d['skipped_files']} | {d['clean_rows']} | {d['q_rows']} | {d['clean_ratio']} |\n"
            )

        f.write("\n## Total\n\n")
        f.write(
            f"- target_files={total_target}, processed_files={total_processed}, success={total_success}, "
            f"failed={total_failed}, skipped={total_skipped}, anomalies={len(anomalies)}, hard_failures={len(hard_failures)}\n"
        )

        f.write("\n## Validation Gate\n\n")
        f.write(f"- pass={summary['validation']['pass']}\n")
        f.write(f"- hard_fail_types={', '.join(summary['validation']['hard_fail_types'])}\n")
        f.write("\n## Anomaly Taxonomy\n\n")
        f.write(f"- row_quarantine_reasons={', '.join(summary['anomaly_taxonomy']['row_quarantine_reasons'])}\n")
        f.write(f"- warn_types={', '.join(summary['anomaly_taxonomy']['warn_types'])}\n")
        f.write(f"- fail_types={', '.join(summary['anomaly_taxonomy']['fail_types'])}\n")

        f.write("\n## Anomalies\n\n")
        if not anomalies:
            f.write("No major anomalies detected.\n")
        else:
            for a in anomalies:
                t = a.get('type', 'unknown')
                if t == 'full_quarantine':
                    f.write(f"- **full_quarantine**: `{a['group']}/{a['file']}` ({a['rows']} rows).\n")
                elif t == 'high_quarantine_ratio':
                    f.write(f"- **high_quarantine_ratio**: `{a['group']}/{a['file']}` ratio={a['ratio']}.\n")
                elif t == 'zero_clean_folder':
                    f.write(f"- **zero_clean_folder**: `{a['group']}`.\n")
                elif t == 'empty_input_file':
                    f.write(f"- **empty_input_file**: `{a['group']}/{a['file']}`.\n")
                elif t == 'missing_target_file':
                    f.write(f"- **missing_target_file**: `{a['group']}/{a['file']}`.\n")
                elif t == 'processing_error':
                    f.write(f"- **processing_error**: `{a['group']}/{a['file']}` error=`{a.get('error', '')}`\n")
                else:
                    f.write(f"- {a}\n")

    with open(report_json_path, 'w', encoding='utf-8') as jf:
        json.dump(summary, jf, ensure_ascii=False, indent=2)

    print(f"Report generated: {report_path}")
    print(f"Report JSON: {report_json_path}")
    if hard_failures:
        print(f"QC hard failures detected: {len(hard_failures)}")
        raise SystemExit(1)
    return report_path, report_json_path


if __name__ == "__main__":
    run_qc()
