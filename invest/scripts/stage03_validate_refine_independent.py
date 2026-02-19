#!/usr/bin/env python3
"""
validate_refine_independent.py
------------------------------
독립 계열 정제 검증기 (onepass_refine_full.py 로직 재사용 최소화)

핵심 가드레일 3개:
  [GR-1] 레코드 보존법칙  : total_in == clean + quarantine + dropped_known
  [GR-2] Blind-review 분리: 판정값(verdict_*.json) / 근거(evidence/*.json) 완전 분리
  [GR-3] 고위험 상한 캡   : L3 후보 비율 > 20% → 경고

기본 검증:
  - 스키마 / 날짜 / 중복 / 결측 / 비정상범위
  - clean 0건 폴더 탐지
  - .fail / traceback 흔적 탐지

주의: raw 데이터 수정 금지, onepass_refine_full.py 로직 재사용 최소화.
"""

import os
import sys
import json
import glob
import re
from datetime import datetime, date

import pandas as pd
import numpy as np

try:
    from invest.scripts.run_manifest import write_run_manifest
except Exception:
    from run_manifest import write_run_manifest

# TODO(refactor-phase2): migrate validator building blocks to invest.validation modules in small, behavior-preserving steps.
try:
    import invest.validation  # noqa: F401
except Exception:
    # import 준비용: 현재 동작 영향 0 유지
    pass

# ─────────────────────────────────────────────────────────────────────────────
# 경로 상수
# ─────────────────────────────────────────────────────────────────────────────
WORKSPACE   = '/Users/jobiseu/.openclaw/workspace'
BASE_DATA   = os.path.join(WORKSPACE, 'invest', 'data')
CLEAN_PROD  = os.path.join(BASE_DATA, 'clean', 'production')
Q_PROD      = os.path.join(BASE_DATA, 'quarantine', 'production')
RAW_BASE    = os.path.join(BASE_DATA, 'raw')
REPORT_DIR  = os.path.join(WORKSPACE, 'reports', 'qc')
EVIDENCE_DIR = os.path.join(REPORT_DIR, 'evidence')

# clean/production 하위 12개 폴더
FOLDERS = [
    'kr/ohlcv',
    'kr/supply',
    'kr/dart',
    'us/ohlcv',
    'market/news/rss',
    'market/macro',
    'market/google_trends',
    'text/blog',
    'text/telegram',
    'text/image_map',
    'text/images_ocr',
    'text/premium/startale',
]

# ─────────────────────────────────────────────────────────────────────────────
# 검증 임계값 (onepass와 독립 정의)
# ─────────────────────────────────────────────────────────────────────────────
MAX_DAILY_RET_ABS    = 0.80   # 일간 수익률 절댓값 한계
MISSING_RATIO_WARN   = 0.30   # 결측률 경고 임계 (30%)
MIN_TEXT_LEN_CHARS   = 10     # 텍스트 최소 유효 길이
L3_ISSUE_THRESHOLD   = 3      # 레코드당 이슈 ≥ 3 → L3 후보
L3_RATIO_CAP         = 0.20   # L3 비율 > 20% → 경고 [GR-3]

# 폴더 유형 분류 (독립 정의)
_OHLCV_KEYS    = {'kr/ohlcv', 'us/ohlcv'}
_SUPPLY_KEYS   = {'kr/supply'}
_DART_KEYS     = {'kr/dart'}
_MACRO_KEYS    = {'market/macro', 'market/google_trends'}
_JSON_KEYS     = {'market/news/rss', 'text/image_map'}
_TEXT_KEYS     = {'text/blog', 'text/telegram', 'text/images_ocr',
                  'text/premium/startale'}

# ─────────────────────────────────────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────────────────────────────────────

def _collect_files(directory: str) -> list:
    """
    재귀적으로 데이터 파일 수집 (raw 읽기 전용)
    
    Role: _collect_files 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    if not os.path.exists(directory):
        return []
    result = []
    for ext in ('*.csv', '*.json', '*.md', '*.txt'):
        result.extend(glob.glob(os.path.join(directory, '**', ext), recursive=True))
    return sorted(result)


def _detect_fail_traces(directory: str) -> list:
    """
    
        디렉토리 내 .fail 파일 또는 traceback 흔적 탐지
        - 파일명에 .fail 포함
        - 파일명에 traceback / error 포함
        - 텍스트 파일 내용에 'Traceback (most recent call last)' 존재
        
    Role: _detect_fail_traces 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    found = []
    if not os.path.exists(directory):
        return found
    for root, _, files in os.walk(directory):
        for fn in files:
            fpath = os.path.join(root, fn)
            if fn.endswith('.fail'):
                found.append(fpath)
                continue
            fn_lower = fn.lower()
            if 'traceback' in fn_lower or fn_lower.startswith('error_'):
                found.append(fpath)
                continue
            if fn.endswith(('.txt', '.log', '.md')):
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                        snippet = fh.read(3000)
                    if re.search(r'Traceback \(most recent call last\)', snippet):
                        found.append(fpath)
                except OSError:
                    pass
    return found


def _safe_to_numeric(series: pd.Series) -> pd.Series:
    """
    Role: _safe_to_numeric 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    return pd.to_numeric(series, errors='coerce')


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    컬럼명 정규화 (Unnamed 제거, strip)
    
    Role: _normalize_cols 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    drop = [c for c in df.columns if c.startswith('Unnamed:') or c == '']
    if drop:
        df = df.drop(columns=drop, errors='ignore')
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 파일 유형별 독립 검증 함수
# ─────────────────────────────────────────────────────────────────────────────

def _validate_ohlcv_file(path: str) -> dict:
    """
    OHLCV CSV 검증 - 독립 로직
    
    Role: _validate_ohlcv_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    issues = []
    record_count = 0
    l3_count = 0

    try:
        df = pd.read_csv(path)
        df = _normalize_cols(df)
        record_count = len(df)

        # [S1] 스키마 검사 - 핵심 컬럼 존재
        has_date  = 'Date' in df.columns
        has_close = 'Close' in df.columns

        if not has_date:
            issues.append('schema:missing_Date')
        if not has_close:
            issues.append('schema:missing_Close')

        # 날짜 파싱
        date_parsed = None
        if has_date:
            date_parsed = pd.to_datetime(df['Date'], errors='coerce')
            bad_date = int(date_parsed.isna().sum())
            if bad_date:
                issues.append(f'date:invalid_count={bad_date}')
            future = int((date_parsed > pd.Timestamp(date.today())).sum())
            if future:
                issues.append(f'date:future_count={future}')
            dup_dates = int(date_parsed.dropna().duplicated().sum())
            if dup_dates:
                issues.append(f'date:duplicate_count={dup_dates}')

        # Close 검증
        close_s = None
        if has_close:
            close_s = _safe_to_numeric(df['Close'])
            missing_close = int(close_s.isna().sum())
            if missing_close:
                issues.append(f'missing:Close_count={missing_close}')
            neg_close = int((close_s <= 0).sum())
            if neg_close:
                issues.append(f'range:non_positive_Close_count={neg_close}')
            # 일간 수익률 이상치: 거래일(Volume>0) 기준으로만 계산
            if 'Volume' in df.columns:
                vol = _safe_to_numeric(df['Volume']).fillna(0)
                trade_mask = vol > 0
            else:
                trade_mask = pd.Series(True, index=df.index)

            ret = close_s[trade_mask].pct_change(fill_method=None).abs()
            outlier = int((ret > MAX_DAILY_RET_ABS).sum())
            if outlier:
                issues.append(f'range:return_outlier_count={outlier}')

        # OHLC 논리: High >= Low, High >= Close, Low <= Close
        if 'High' in df.columns and 'Low' in df.columns:
            hi = _safe_to_numeric(df['High'])
            lo = _safe_to_numeric(df['Low'])
            viol = int((hi < lo).sum())
            if viol:
                issues.append(f'ohlc:High<Low_count={viol}')

        if 'High' in df.columns and 'Close' in df.columns:
            hi = _safe_to_numeric(df['High'])
            cl = _safe_to_numeric(df['Close'])
            viol = int((hi < cl).sum())
            if viol:
                issues.append(f'ohlc:High<Close_count={viol}')

        if 'Low' in df.columns and 'Close' in df.columns:
            lo = _safe_to_numeric(df['Low'])
            cl = _safe_to_numeric(df['Close'])
            viol = int((lo > cl).sum())
            if viol:
                issues.append(f'ohlc:Low>Close_count={viol}')

        # 결측률 검사
        for col in ('Open', 'High', 'Low', 'Close', 'Volume'):
            if col in df.columns:
                ratio = df[col].isna().mean()
                if ratio > MISSING_RATIO_WARN:
                    issues.append(f'missing:{col}_ratio={ratio:.1%}')

        # [L3] 레코드별 이슈 집계 → L3 후보
        if record_count > 0:
            flags = pd.DataFrame(index=df.index)
            if date_parsed is not None:
                flags['f_bad_date'] = date_parsed.isna()
            if close_s is not None:
                flags['f_neg_close'] = (close_s <= 0) | close_s.isna()
                flags['f_ret_outlier'] = close_s.pct_change().abs() > MAX_DAILY_RET_ABS
            if 'High' in df.columns and 'Low' in df.columns:
                hi2 = _safe_to_numeric(df['High'])
                lo2 = _safe_to_numeric(df['Low'])
                flags['f_ohlc_err'] = hi2 < lo2
            # 모든 수치 컬럼 결측
            num_cols = [c for c in ('Open','High','Low','Close','Volume') if c in df.columns]
            if num_cols:
                flags['f_all_num_na'] = df[num_cols].isna().all(axis=1)
            issue_per_row = flags.sum(axis=1)
            l3_count = int((issue_per_row >= L3_ISSUE_THRESHOLD).sum())

    except Exception as exc:
        issues.append(f'read_error:{exc}')

    return {'record_count': record_count, 'issues': issues, 'l3_candidates': l3_count}


def _validate_supply_file(path: str) -> dict:
    """
    공급 데이터 CSV 검증
    
    Role: _validate_supply_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    issues = []
    record_count = 0
    l3_count = 0
    SUPPLY_COLS = ('Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total')

    try:
        df = pd.read_csv(path)
        df = _normalize_cols(df)
        record_count = len(df)

        missing_cols = [c for c in SUPPLY_COLS if c not in df.columns]
        if missing_cols:
            issues.append(f'schema:missing={missing_cols}')

        date_parsed = None
        if 'Date' in df.columns:
            date_parsed = pd.to_datetime(df['Date'], errors='coerce')
            bad_date = int(date_parsed.isna().sum())
            if bad_date:
                issues.append(f'date:invalid_count={bad_date}')
            dup = int(date_parsed.dropna().duplicated().sum())
            if dup:
                issues.append(f'date:duplicate_count={dup}')

        num_cols = [c for c in ('Inst', 'Corp', 'Indiv', 'Foreign', 'Total') if c in df.columns]
        for col in num_cols:
            s = _safe_to_numeric(df[col])
            ratio = s.isna().mean()
            if ratio > MISSING_RATIO_WARN:
                issues.append(f'missing:{col}_ratio={ratio:.1%}')

        # L3
        if record_count > 0:
            flags = pd.DataFrame(index=df.index)
            if date_parsed is not None:
                flags['f_bad_date'] = date_parsed.isna()
            if num_cols:
                flags['f_all_num_na'] = df[num_cols].isna().all(axis=1)
            issue_per_row = flags.sum(axis=1)
            l3_count = int((issue_per_row >= L3_ISSUE_THRESHOLD).sum())

    except Exception as exc:
        issues.append(f'read_error:{exc}')

    return {'record_count': record_count, 'issues': issues, 'l3_candidates': l3_count}


def _validate_dart_file(path: str) -> dict:
    """
    DART 공시 파일 검증 (CSV / JSON)
    
    Role: _validate_dart_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    issues = []
    record_count = 0
    DART_KEY_COLS = ('corp_code', 'rcept_no', 'rcept_dt')

    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(path)
            df = _normalize_cols(df)
            record_count = len(df)
            missing_cols = [c for c in DART_KEY_COLS if c not in df.columns]
            if missing_cols:
                issues.append(f'schema:missing={missing_cols}')
            if 'rcept_no' in df.columns:
                dup = int(df['rcept_no'].dropna().duplicated().sum())
                if dup:
                    issues.append(f'duplicate:rcept_no_count={dup}')
            if 'rcept_dt' in df.columns:
                parsed = pd.to_datetime(df['rcept_dt'].astype(str), format='%Y%m%d', errors='coerce')
                bad = int(parsed.isna().sum())
                if bad:
                    issues.append(f'date:invalid_rcept_dt_count={bad}')
        elif ext == '.json':
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if isinstance(data, list):
                record_count = len(data)
                if record_count == 0:
                    issues.append('empty:json_array')
            elif isinstance(data, dict):
                record_count = len(data)
        else:
            issues.append(f'unsupported_ext:{ext}')
    except Exception as exc:
        issues.append(f'read_error:{exc}')

    return {'record_count': record_count, 'issues': issues, 'l3_candidates': 0}


def _validate_macro_file(path: str) -> dict:
    """
    거시경제 / Google Trends CSV 검증
    
    Role: _validate_macro_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    issues = []
    record_count = 0
    l3_count = 0

    try:
        df = pd.read_csv(path)
        df = _normalize_cols(df)
        # 소문자화 매핑
        col_lower = {c.lower(): c for c in df.columns}
        record_count = len(df)

        date_col = col_lower.get('date') or col_lower.get('날짜')
        val_col  = col_lower.get('value') or col_lower.get('val')

        if not date_col:
            issues.append('schema:missing_date_column')
        else:
            date_parsed = pd.to_datetime(df[date_col], errors='coerce')
            bad_date = int(date_parsed.isna().sum())
            if bad_date:
                issues.append(f'date:invalid_count={bad_date}')
            dup = int(date_parsed.dropna().duplicated().sum())
            if dup:
                issues.append(f'date:duplicate_count={dup}')

        if not val_col:
            issues.append('schema:missing_value_column')
        else:
            s = _safe_to_numeric(df[val_col])
            ratio = s.isna().mean()
            if ratio > MISSING_RATIO_WARN:
                issues.append(f'missing:value_ratio={ratio:.1%}')

        # L3
        if record_count > 0 and date_col and val_col:
            flags = pd.DataFrame(index=df.index)
            flags['f_bad_date']    = pd.to_datetime(df[date_col], errors='coerce').isna()
            flags['f_missing_val'] = _safe_to_numeric(df[val_col]).isna()
            issue_per_row = flags.sum(axis=1)
            l3_count = int((issue_per_row >= L3_ISSUE_THRESHOLD).sum())

    except Exception as exc:
        issues.append(f'read_error:{exc}')

    return {'record_count': record_count, 'issues': issues, 'l3_candidates': l3_count}


def _validate_json_file(path: str) -> dict:
    """
    일반 JSON 파일 검증
    
    Role: _validate_json_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    issues = []
    record_count = 0

    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, list):
            record_count = len(data)
            if record_count == 0:
                issues.append('empty:json_array')
        elif isinstance(data, dict):
            record_count = len(data)
            if record_count == 0:
                issues.append('empty:json_object')
        else:
            record_count = 1
    except json.JSONDecodeError as exc:
        issues.append(f'json_parse_error:{exc}')
    except Exception as exc:
        issues.append(f'read_error:{exc}')

    return {'record_count': record_count, 'issues': issues, 'l3_candidates': 0}


def _validate_text_file(path: str) -> dict:
    """
    텍스트 / 마크다운 파일 검증
    
    Role: _validate_text_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    issues = []
    record_count = 0

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        stripped = content.strip()
        lines = stripped.splitlines()
        record_count = len(lines)

        if len(stripped) < MIN_TEXT_LEN_CHARS:
            issues.append(f'too_short:{len(stripped)}chars')
        # traceback 내용 탐지
        if re.search(r'Traceback \(most recent call last\)', content):
            issues.append('traceback_found_in_content')
    except Exception as exc:
        issues.append(f'read_error:{exc}')

    return {'record_count': record_count, 'issues': issues, 'l3_candidates': 0}


def validate_file(path: str, folder_key: str) -> dict:
    """
    폴더 유형에 맞는 검증 함수 디스패치
    
    Role: validate_file 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    ext = os.path.splitext(path)[1].lower()

    if folder_key in _OHLCV_KEYS and ext == '.csv':
        return _validate_ohlcv_file(path)
    elif folder_key in _SUPPLY_KEYS and ext == '.csv':
        return _validate_supply_file(path)
    elif folder_key in _DART_KEYS:
        return _validate_dart_file(path)
    elif folder_key in _MACRO_KEYS and ext == '.csv':
        return _validate_macro_file(path)
    elif ext == '.json':
        return _validate_json_file(path)
    elif ext in ('.md', '.txt'):
        return _validate_text_file(path)
    elif ext == '.csv':
        return _validate_macro_file(path)   # generic CSV fallback
    else:
        return {'record_count': 0, 'issues': [f'unsupported_ext:{ext}'], 'l3_candidates': 0}


# ─────────────────────────────────────────────────────────────────────────────
# [GR-1] 레코드 보존법칙
# ─────────────────────────────────────────────────────────────────────────────

def _check_record_preservation(folder_key: str) -> dict:
    """
    
        GR-1: 레코드 보존법칙
            total_in == clean + quarantine + dropped_known
    
        raw 폴더가 존재하면 → raw 파일 수를 total_in으로 사용
        raw 폴더 없음      → clean + quarantine 합산 (내부 일관성 검사)
        dropped_known      → 별도 dropped 파일이 없으므로 0으로 처리
                             (법칙 위반 기준: preserved < total_in)
        
    Role: _check_record_preservation 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    raw_dir   = os.path.join(RAW_BASE, folder_key)
    clean_dir = os.path.join(CLEAN_PROD, folder_key)
    q_dir     = os.path.join(Q_PROD,    folder_key)

    n_raw   = len(_collect_files(raw_dir))   if os.path.exists(raw_dir)   else None
    n_clean = len(_collect_files(clean_dir)) if os.path.exists(clean_dir) else 0
    n_q     = len(_collect_files(q_dir))     if os.path.exists(q_dir)     else 0
    n_drop  = 0  # 별도 dropped 저장소 없음

    if n_raw is not None:
        # 파일 단위 보존: clean + quarantine ≥ raw (중복 저장 허용)
        # 엄격 체크: raw > (clean + q) 이면 손실 발생
        preserved   = n_clean + n_q + n_drop
        total_in    = n_raw
        law_ok      = preserved >= total_in
        note        = 'raw_exists'
    else:
        # raw 없음 → 내부 일관성만 확인 (항상 OK)
        preserved   = n_clean + n_q
        total_in    = preserved
        law_ok      = True
        note        = 'raw_not_found'

    return {
        'total_in':      total_in,
        'clean':         n_clean,
        'quarantine':    n_q,
        'dropped_known': n_drop,
        'preserved':     preserved,
        'law_satisfied': bool(law_ok),
        'note':          note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# [GR-3] 고위험 상한 캡
# ─────────────────────────────────────────────────────────────────────────────

def _check_l3_cap(total_records: int, l3_total: int) -> dict:
    """
    
        GR-3: L3 후보 비율 > 20% 시 경고
        
    Role: _check_l3_cap 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    ratio = (l3_total / total_records) if total_records > 0 else 0.0
    return {
        'total_records':  total_records,
        'l3_candidates':  l3_total,
        'l3_ratio':       round(ratio, 6),
        'cap_threshold':  L3_RATIO_CAP,
        'cap_exceeded':   ratio > L3_RATIO_CAP,
    }


# ─────────────────────────────────────────────────────────────────────────────
# [GR-2] Blind-review 분리 출력
# ─────────────────────────────────────────────────────────────────────────────

def _write_blind_review_files(verdicts: dict, evidence: dict, timestamp: str) -> tuple:
    """
    
        GR-2: 판정값(verdict_*.json)과 근거(evidence/*.json) 분리 저장
        - verdict 파일: 판정 상태(PASS/WARN/FAIL)만, 이유 없음
        - evidence 파일: 폴더별 상세 이유, 파일별 이슈 목록
        심사자는 verdict만 먼저 열람 → 확인 후 evidence 참조 (blind review 절차)
        
    Role: _write_blind_review_files 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # ① 판정값만 (근거 배제)
    verdict_only = {
        'generated_at': datetime.now().isoformat(),
        'timestamp':    timestamp,
        'note':         'BLIND_REVIEW_VERDICT_ONLY — see evidence/ for rationale',
        'verdicts': {k: v['status'] for k, v in verdicts.items()},
        'summary': {
            'PASS': sum(1 for v in verdicts.values() if v['status'] == 'PASS'),
            'WARN': sum(1 for v in verdicts.values() if v['status'] == 'WARN'),
            'FAIL': sum(1 for v in verdicts.values() if v['status'] == 'FAIL'),
            'total': len(verdicts),
        },
    }
    verdict_path = os.path.join(REPORT_DIR, f'verdict_{timestamp}.json')
    with open(verdict_path, 'w', encoding='utf-8') as fh:
        json.dump(verdict_only, fh, ensure_ascii=False, indent=2)

    # ② 근거 파일 (폴더별 분리)
    ev_paths = {}
    for folder_key, ev_data in evidence.items():
        safe_key = folder_key.replace('/', '_').replace('\\', '_')
        ev_path  = os.path.join(EVIDENCE_DIR, f'evidence_{safe_key}_{timestamp}.json')
        with open(ev_path, 'w', encoding='utf-8') as fh:
            json.dump(ev_data, fh, ensure_ascii=False, indent=2, default=str)
        ev_paths[folder_key] = ev_path

    return verdict_path, ev_paths


# ─────────────────────────────────────────────────────────────────────────────
# 메인 검증 루프
# ─────────────────────────────────────────────────────────────────────────────

def run_validation() -> tuple:
    """
    
        12개 폴더 전체 검증 실행.
        Returns:
            verdicts : {folder_key: {status, metrics}} — 판정값 (GR-2 분리 대상)
            evidence : {folder_key: {detailed_issues}} — 근거 (GR-2 분리 대상)
        
    Role: run_validation 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    verdicts: dict = {}
    evidence: dict = {}

    # 전역 .fail / traceback 스캔
    global_fail_traces = _detect_fail_traces(CLEAN_PROD)

    for folder_key in FOLDERS:
        clean_dir = os.path.join(CLEAN_PROD, folder_key)

        folder_ev = {
            'folder_key':      folder_key,
            'clean_dir':       clean_dir,
            'issues_by_file':  {},    # 근거 데이터
            'guardrail_gr1':   {},
            'guardrail_gr3':   {},
            'fail_traces':     [],
            'errors':          [],
            'warnings':        [],
        }

        # ── 기본 검사: clean 디렉토리 존재 / 0건 탐지 ──────────────────────
        if not os.path.exists(clean_dir):
            folder_ev['errors'].append('ERR:clean_dir_not_found')
            verdicts[folder_key] = _make_verdict('FAIL', 'clean_dir_not_found')
            evidence[folder_key] = folder_ev
            continue

        clean_files = _collect_files(clean_dir)
        if len(clean_files) == 0:
            folder_ev['errors'].append('ERR:clean_zero_files')
            verdicts[folder_key] = _make_verdict('FAIL', 'clean_zero_files')
            evidence[folder_key] = folder_ev
            continue

        # ── .fail / traceback 흔적 탐지 ────────────────────────────────────
        folder_fail_traces = _detect_fail_traces(clean_dir)
        folder_ev['fail_traces'] = folder_fail_traces
        if folder_fail_traces:
            folder_ev['warnings'].append(
                f'WARN:fail_trace_count={len(folder_fail_traces)}'
            )

        # ── GR-1: 레코드 보존법칙 ──────────────────────────────────────────
        gr1 = _check_record_preservation(folder_key)
        folder_ev['guardrail_gr1'] = gr1
        if not gr1['law_satisfied']:
            folder_ev['errors'].append(
                f'ERR:GR1_preservation_violated '
                f'(raw={gr1["total_in"]}, preserved={gr1["preserved"]})'
            )

        # ── 파일별 검증 ────────────────────────────────────────────────────
        total_records = 0
        l3_total      = 0
        files_with_issues = 0

        for fpath in clean_files:
            rel = os.path.relpath(fpath, clean_dir)
            result = validate_file(fpath, folder_key)
            total_records += result['record_count']
            l3_total      += result['l3_candidates']
            if result['issues']:
                files_with_issues += 1
                folder_ev['issues_by_file'][rel] = result['issues']

        # ── GR-3: 고위험 상한 캡 ──────────────────────────────────────────
        gr3 = _check_l3_cap(total_records, l3_total)
        folder_ev['guardrail_gr3'] = gr3
        if gr3['cap_exceeded']:
            folder_ev['warnings'].append(
                f'WARN:GR3_L3_cap_exceeded '
                f'ratio={gr3["l3_ratio"]:.1%} > {L3_RATIO_CAP:.0%}'
            )

        # ── 종합 판정 ─────────────────────────────────────────────────────
        has_err  = bool(folder_ev['errors'])
        has_warn = bool(folder_ev['warnings']) or (files_with_issues > 0)

        if has_err:
            status = 'FAIL'
        elif has_warn:
            status = 'WARN'
        else:
            status = 'PASS'

        folder_ev['summary'] = {
            'status':           status,
            'total_files':      len(clean_files),
            'files_with_issues': files_with_issues,
            'total_records':    total_records,
        }

        verdicts[folder_key] = {
            'status':             status,
            'total_files':        len(clean_files),
            'files_with_issues':  files_with_issues,
            'total_records':      total_records,
            'l3_ratio':           gr3['l3_ratio'],
            'l3_cap_exceeded':    gr3['cap_exceeded'],
            'preservation_ok':    gr1['law_satisfied'],
        }
        evidence[folder_key] = folder_ev

    # 전역 흔적 별도 저장
    evidence['__global__'] = {
        'global_fail_traces': global_fail_traces,
        'scanned_at':         datetime.now().isoformat(),
    }

    return verdicts, evidence


def _make_verdict(status: str, reason: str) -> dict:
    """
    Role: _make_verdict 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    return {
        'status':            status,
        'total_files':       0,
        'files_with_issues': 0,
        'total_records':     0,
        'l3_ratio':          0.0,
        'l3_cap_exceeded':   False,
        'preservation_ok':   (status != 'FAIL'),
        'quick_reason':      reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 리포트 작성
# ─────────────────────────────────────────────────────────────────────────────

def _write_reports(verdicts: dict, evidence: dict, timestamp: str) -> tuple:
    """
    Role: _write_reports 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs(REPORT_DIR, exist_ok=True)

    pass_c = sum(1 for v in verdicts.values() if v['status'] == 'PASS')
    warn_c = sum(1 for v in verdicts.values() if v['status'] == 'WARN')
    fail_c = sum(1 for v in verdicts.values() if v['status'] == 'FAIL')
    global_traces = evidence.get('__global__', {}).get('global_fail_traces', [])

    # ── JSON 요약 ──────────────────────────────────────────────────────────
    json_path = os.path.join(REPORT_DIR, f'VALIDATION_INDEPENDENT_{timestamp}.json')
    json_summary = {
        'schema_version':    '1.0',
        'generated_at':      datetime.now().isoformat(),
        'timestamp':         timestamp,
        'validator':         'validate_refine_independent.py',
        'folders_scanned':   FOLDERS,
        'summary':           {'PASS': pass_c, 'WARN': warn_c, 'FAIL': fail_c},
        'verdicts':          verdicts,
        'global_fail_traces': global_traces,
    }
    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(json_summary, fh, ensure_ascii=False, indent=2, default=str)

    # ── Markdown 리포트 ───────────────────────────────────────────────────
    md_path = os.path.join(REPORT_DIR, f'VALIDATION_INDEPENDENT_{timestamp}.md')
    _STATUS_ICON = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '❌'}

    with open(md_path, 'w', encoding='utf-8') as fh:

        fh.write(f'# 독립 정제 검증 리포트\n\n')
        fh.write(f'- **생성시각**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        fh.write(f'- **검증기**: `validate_refine_independent.py`\n')
        fh.write(f'- **대상**: `clean/production` 하위 {len(FOLDERS)}개 폴더\n')
        fh.write(f'- **종합**: ✅ PASS {pass_c} | ⚠️ WARN {warn_c} | ❌ FAIL {fail_c}\n\n')
        fh.write('---\n\n')

        # GR-1 레코드 보존법칙
        fh.write('## [GR-1] 레코드 보존법칙\n\n')
        fh.write('> `total_in == clean + quarantine + dropped_known`\n\n')
        fh.write('| 폴더 | total_in | clean | quarantine | dropped | 충족 | 비고 |\n')
        fh.write('| :--- | ---: | ---: | ---: | ---: | :---: | :--- |\n')
        for fk in FOLDERS:
            ev = evidence.get(fk, {})
            gr1 = ev.get('guardrail_gr1', {})
            if not gr1:
                fh.write(f'| {fk} | - | - | - | - | ❓ | N/A |\n')
                continue
            icon = '✅' if gr1['law_satisfied'] else '❌'
            fh.write(
                f'| {fk} | {gr1["total_in"]} | {gr1["clean"]} | '
                f'{gr1["quarantine"]} | {gr1["dropped_known"]} | {icon} | {gr1["note"]} |\n'
            )
        fh.write('\n')

        # GR-2 설명
        fh.write('## [GR-2] Blind-review 분리 출력\n\n')
        fh.write(f'- **판정값 파일** (근거 없음): `verdict_{timestamp}.json`\n')
        fh.write(f'- **근거 파일** (상세 이유): `evidence/evidence_<폴더>_{timestamp}.json`\n')
        fh.write(
            '- 심사자는 verdict 파일만 먼저 열람 → 개별 판단 후 evidence 파일 참조\n\n'
        )

        # GR-3 L3 캡
        fh.write('## [GR-3] 고위험 상한 캡 (L3 > 20%)\n\n')
        fh.write('| 폴더 | 전체 레코드 | L3 후보 | L3 비율 | 임계 | 경고 |\n')
        fh.write('| :--- | ---: | ---: | ---: | ---: | :---: |\n')
        for fk in FOLDERS:
            ev = evidence.get(fk, {})
            gr3 = ev.get('guardrail_gr3', {})
            if not gr3:
                fh.write(f'| {fk} | - | - | - | - | ❓ |\n')
                continue
            icon = '⚠️' if gr3['cap_exceeded'] else '✅'
            fh.write(
                f'| {fk} | {gr3["total_records"]:,} | {gr3["l3_candidates"]:,} | '
                f'{gr3["l3_ratio"]:.1%} | {gr3["cap_threshold"]:.0%} | {icon} |\n'
            )
        fh.write('\n')

        # 종합 판정 테이블
        fh.write('## 종합 판정 결과\n\n')
        fh.write('| 폴더 | 상태 | 파일 수 | 이슈 파일 | 총 레코드 | L3 비율 | GR-1 |\n')
        fh.write('| :--- | :---: | ---: | ---: | ---: | ---: | :---: |\n')
        for fk in FOLDERS:
            v = verdicts.get(fk, {})
            st = v.get('status', 'N/A')
            icon = _STATUS_ICON.get(st, '❓')
            pres = '✅' if v.get('preservation_ok', True) else '❌'
            fh.write(
                f'| {fk} | {icon} {st} | {v.get("total_files", 0):,} | '
                f'{v.get("files_with_issues", 0)} | {v.get("total_records", 0):,} | '
                f'{v.get("l3_ratio", 0):.1%} | {pres} |\n'
            )
        fh.write('\n')

        # 폴더별 이슈 상세
        fh.write('## 폴더별 이슈 상세\n\n')
        for fk in FOLDERS:
            ev = evidence.get(fk, {})
            v  = verdicts.get(fk, {})
            st = v.get('status', 'N/A')
            icon = _STATUS_ICON.get(st, '❓')
            fh.write(f'### {icon} {fk}\n\n')

            errors   = ev.get('errors', [])
            warnings = ev.get('warnings', [])
            for e in errors:
                fh.write(f'- ❌ `{e}`\n')
            for w in warnings:
                fh.write(f'- ⚠️ `{w}`\n')

            issues_by_file = ev.get('issues_by_file', {})
            if issues_by_file:
                fh.write(f'\n**이슈 파일 {len(issues_by_file)}개** (최대 10개 표시):\n\n')
                shown = list(issues_by_file.items())[:10]
                for rel_path, file_issues in shown:
                    preview = ', '.join(file_issues[:4])
                    fh.write(f'  - `{rel_path}`: {preview}\n')
                if len(issues_by_file) > 10:
                    fh.write(f'  - *... 외 {len(issues_by_file)-10}개 → evidence 파일 참조*\n')
            elif st == 'PASS':
                fh.write('- 이상 없음 ✅\n')
            fh.write('\n')

        # .fail / traceback 흔적
        fh.write('## .fail / traceback 흔적 탐지\n\n')
        if global_traces:
            fh.write(f'⚠️ **{len(global_traces)}개 탐지됨**:\n\n')
            for t in global_traces[:20]:
                fh.write(f'- `{t}`\n')
            if len(global_traces) > 20:
                fh.write(f'- *... 외 {len(global_traces)-20}개*\n')
        else:
            fh.write('이상 없음 ✅\n')
        fh.write('\n---\n')
        fh.write(f'*generated by validate_refine_independent.py @ {datetime.now().isoformat()}*\n')

    return md_path, json_path


# ─────────────────────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """
    Role: main 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f'[validate_refine_independent] START @ {timestamp}')
    print(f'  대상 폴더: {len(FOLDERS)}개 (clean/production)')
    print()

    # 검증 실행
    verdicts, evidence = run_validation()

    # GR-2: Blind-review 분리 출력
    verdict_path, ev_paths = _write_blind_review_files(verdicts, evidence, timestamp)

    # 리포트 작성
    md_path, json_path = _write_reports(verdicts, evidence, timestamp)

    # 콘솔 출력
    _STATUS_ICON = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '❌'}
    pass_c = sum(1 for v in verdicts.values() if v['status'] == 'PASS')
    warn_c = sum(1 for v in verdicts.values() if v['status'] == 'WARN')
    fail_c = sum(1 for v in verdicts.values() if v['status'] == 'FAIL')

    print('=' * 65)
    print('  [결과 요약]')
    print('=' * 65)
    print(f'  PASS: {pass_c}  WARN: {warn_c}  FAIL: {fail_c}')
    print()
    for fk in FOLDERS:
        v    = verdicts.get(fk, {})
        st   = v.get('status', 'N/A')
        icon = _STATUS_ICON.get(st, '❓')
        l3_s = f" L3={v.get('l3_ratio',0):.1%}" if v.get('l3_ratio',0) > 0 else ''
        gr1s = '' if v.get('preservation_ok', True) else ' [GR1:FAIL]'
        print(f'  {icon} {fk:<38}{st}{l3_s}{gr1s}')

    global_traces = evidence.get('__global__', {}).get('global_fail_traces', [])
    if global_traces:
        print(f'\n  ⚠️  .fail/traceback 흔적: {len(global_traces)}개 탐지')

    print('\n  [리포트 경로]')
    print(f'  MD      : {md_path}')
    print(f'  JSON    : {json_path}')
    print(f'  Verdict : {verdict_path}  ← GR-2 판정값 전용')
    print(f'  Evidence: {EVIDENCE_DIR}/   ← GR-2 근거 전용')

    manifest_path = os.path.join(WORKSPACE, 'invest', 'reports', 'data_quality', f'manifest_stage2_validate_{timestamp}.json')
    write_run_manifest(
        run_type='stage2_validate_refine_independent',
        params={'folders': FOLDERS, 'l3_ratio_cap': L3_RATIO_CAP},
        inputs=[CLEAN_PROD, Q_PROD, RAW_BASE],
        outputs=[md_path, json_path, verdict_path],
        out_path=manifest_path,
        workdir=os.path.join(WORKSPACE, 'invest'),
    )
    print(f'  Manifest: {manifest_path}')
    print('=' * 65)

    return md_path, json_path, verdict_path, manifest_path


if __name__ == '__main__':
    main()
