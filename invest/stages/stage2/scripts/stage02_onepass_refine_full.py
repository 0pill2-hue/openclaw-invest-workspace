from __future__ import annotations

import argparse
import os
import glob
import pandas as pd
import json
import hashlib
import re
import shutil
import time
from datetime import datetime
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from stage2_config import load_stage2_config_bundle

# TODO(refactor-phase2): move core refine logic into invest.pipeline modules (behavior-preserving migration).
try:
    import invest.pipeline  # noqa: F401
except Exception:
    # import 준비용: 현재 동작 영향 0 유지
    pass

# Configuration (stage-local input boundary)
STAGE2_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM_STAGE1 = os.path.join(STAGE2_ROOT, 'inputs', 'upstream_stage1')
RAW_BASE = os.path.join(UPSTREAM_STAGE1, 'raw')
CLEAN_BASE = os.path.join(STAGE2_ROOT, 'outputs', 'clean')
# Stage2가 유일한 검역(quarantine) 저장 단계다. Stage1은 raw/상태 파일만 저장한다.
Q_BASE = os.path.join(STAGE2_ROOT, 'outputs', 'quarantine')
REPORT_DIR = os.path.join(STAGE2_ROOT, 'outputs', 'reports', 'qc')
STAGE2_RULE_VERSION = 'stage2-refine-20260308-r3'
STAGE2_ENABLE_LINK_ENRICHMENT = os.environ.get('STAGE2_ENABLE_LINK_ENRICHMENT', '0').strip().lower() in ('1', 'true', 'yes')
FOLDERS = [
    'kr/dart',
    'market/news/rss', 'market/news/selected_articles', 'market/macro', 'market/google_trends',
    'text/blog', 'text/telegram', 'text/premium/startale'
]
REQUIRED_REFINE_FOLDERS = {
    'kr/dart',
    'market/news/rss',
    'market/news/selected_articles',
    'text/blog',
    'text/telegram',
    'text/premium/startale',
}
# image 계열은 운영 정책상 Stage1/2 범위에서 제외

# Stage2 clean/quarantine canonical output track
SIGNAL_FOLDERS = {
    'kr/ohlcv', 'kr/supply', 'us/ohlcv', 'market/macro', 'market/google_trends'
}
QUALITATIVE_FOLDERS = {
    'kr/dart', 'market/news/rss', 'market/news/selected_articles', 'market/rss',
    'text/blog', 'text/telegram', 'text/premium/startale'
}

# raw/output 경로 alias 정합성
FOLDER_ALIAS = {
    'market/news/rss': 'market/rss',
}

STAGE2_CONFIG_BUNDLE = load_stage2_config_bundle()
STAGE2_RUNTIME_CONFIG = STAGE2_CONFIG_BUNDLE['runtime']
STAGE2_REASON_CONFIG = STAGE2_CONFIG_BUNDLE['reason']
STAGE2_CONFIG_PROVENANCE = STAGE2_CONFIG_BUNDLE['provenance']
STAGE2_CONFIG_SHA1 = STAGE2_CONFIG_PROVENANCE['bundle_sha1']

REFINE_RUNTIME_CONFIG = STAGE2_RUNTIME_CONFIG['refine']
REFINE_REASON_CONFIG = STAGE2_REASON_CONFIG['refine']
TEXT_VALIDATION_CONFIG = REFINE_RUNTIME_CONFIG['text_validation']
DEDUP_CONFIG = REFINE_RUNTIME_CONFIG['dedup']
FILTER_CONFIG = REFINE_RUNTIME_CONFIG['filters']
LINK_ENRICHMENT_CONFIG = REFINE_RUNTIME_CONFIG['link_enrichment']
ATTACHMENT_CLEANUP_CONFIG = FILTER_CONFIG.get('attachment_cleanup', {})

BLOG_UI_MARKERS = set(FILTER_CONFIG['blog_ui_markers'])
PREMIUM_BOILERPLATE_MARKERS = set(FILTER_CONFIG['premium_boilerplate_markers'])
ATTACHMENT_DROP_LINE_PATTERNS = tuple(ATTACHMENT_CLEANUP_CONFIG.get('drop_line_patterns', []))
ATTACHMENT_DROP_BLOCK_PATTERNS = tuple(ATTACHMENT_CLEANUP_CONFIG.get('drop_block_patterns', []))

# 텍스트 정제 최소 길이(의미 있는 단문을 과도 격리하지 않도록 완화)
BLOG_MIN_EFFECTIVE_LEN = int(TEXT_VALIDATION_CONFIG['blog_min_effective_len'])
TELEGRAM_MIN_EFFECTIVE_LEN = int(TEXT_VALIDATION_CONFIG['telegram_min_effective_len'])
PREMIUM_MIN_EFFECTIVE_LEN = int(TEXT_VALIDATION_CONFIG['premium_min_effective_len'])
SELECTED_ARTICLES_MIN_TEXT_LEN = int(TEXT_VALIDATION_CONFIG['selected_articles_min_text_len'])
DEDUP_MIN_FP_TEXT_LEN = int(DEDUP_CONFIG['min_fingerprint_text_len'])
SHORT_MEANINGFUL_MIN_LEN = int(TEXT_VALIDATION_CONFIG['short_meaningful_min_len'])

DEDUP_TARGET_FOLDERS = set(DEDUP_CONFIG['target_folders'])
TARGET_LINK_ENRICH_FOLDERS = set(LINK_ENRICHMENT_CONFIG['target_folders'])

URL_PATTERN = re.compile(r'https?://[^\s<>()\[\]{}"\']+', flags=re.IGNORECASE)
ATTACH_TEXT_BLOCK_RE = re.compile(r'(?is)\[ATTACH_TEXT\]\s*(.*?)\s*\[/ATTACH_TEXT\]')
TRACKING_QUERY_PREFIXES = tuple(FILTER_CONFIG['tracking_query_prefixes'])
ALLOWED_LINK_DOMAIN_SUFFIXES = tuple(FILTER_CONFIG['allowed_link_domain_suffixes'])
# allowlist 확장 모드(기본 ON): 뉴스/리포트 링크 누락 최소화
LINK_ENRICH_ALLOW_ALL_DOMAINS = os.environ.get(
    'LINK_ENRICH_ALLOW_ALL_DOMAINS',
    '1' if LINK_ENRICHMENT_CONFIG.get('allow_all_domains_default', True) else '0',
).strip().lower() in ('1', 'true', 'yes')
BLOCKED_LINK_DOMAIN_SUFFIXES = tuple(FILTER_CONFIG['blocked_link_domain_suffixes'])

LINK_FETCH_TIMEOUT_SEC = int(LINK_ENRICHMENT_CONFIG['fetch_timeout_sec'])
LINK_FETCH_MAX_RETRIES = int(LINK_ENRICHMENT_CONFIG['fetch_max_retries'])
LINK_FETCH_BACKOFF_BASE_SEC = float(LINK_ENRICHMENT_CONFIG['fetch_backoff_base_sec'])
LINK_FETCH_MAX_BYTES = int(LINK_ENRICHMENT_CONFIG['fetch_max_bytes'])
LINK_FETCH_MAX_TEXT_CHARS = int(LINK_ENRICHMENT_CONFIG['fetch_max_text_chars'])
LINK_ENRICH_MAX_URLS_PER_FILE = int(LINK_ENRICHMENT_CONFIG['max_urls_per_file'])
LINK_ENRICH_MAX_TOTAL_CHARS = int(LINK_ENRICHMENT_CONFIG['max_total_chars'])
LINK_ENRICH_MIN_EFFECTIVE_ADD = int(LINK_ENRICHMENT_CONFIG['min_effective_add'])

os.makedirs(REPORT_DIR, exist_ok=True)

INDEX_PATH = os.path.join(CLEAN_BASE, 'production', '_processed_index.json')
INDEX_META_KEY = '__meta__'
INDEX_ENTRIES_KEY = 'entries'


def _new_link_runtime_stats() -> dict:
    return {
        'url_raw_extracted_total': 0,
        'url_canonical_total': 0,
        'url_deduped_within_file': 0,
        'url_cache_hits': 0,
        'url_disallowed': 0,
        'url_fetch_success': 0,
        'url_fetch_failure': 0,
        'content_fingerprint_dedup': 0,
        'enrichment_attempt_files': 0,
        'enrichment_applied_files': 0,
        'enrichment_promoted_files': 0,
        'enrichment_still_quarantined_files': 0,
        'attachment_blocks_seen': 0,
        'attachment_text_chars_total': 0,
        'corpus_dedup_registered_items': 0,
        'corpus_dedup_duplicate_items': 0,
        'corpus_dedup_bootstrap_files': 0,
        'corpus_dedup_bootstrap_records': 0,
    }


LINK_FETCH_CACHE: dict[str, dict] = {}
LINK_RUNTIME_STATS: dict = _new_link_runtime_stats()


def _normalize_folder(folder: str) -> str:
    return FOLDER_ALIAS.get(folder, folder)


def _folder_bucket(folder: str) -> str:
    normalized = _normalize_folder(folder)
    if normalized in SIGNAL_FOLDERS:
        return 'signal'
    if normalized in QUALITATIVE_FOLDERS:
        return 'qualitative'
    return ''


def _resolve_raw_dir(folder: str) -> str:
    normalized = _normalize_folder(folder)
    bucket = _folder_bucket(folder)
    if bucket:
        return os.path.join(RAW_BASE, bucket, normalized)
    return os.path.join(RAW_BASE, normalized)


def _output_paths(base_dir: str, folder: str, rel_path: str) -> list[str]:
    """Canonical only: {base}/(signal|qualitative)/{normalized-folder}/..."""
    normalized = _normalize_folder(folder)
    bucket = _folder_bucket(folder)
    if bucket:
        return [os.path.join(base_dir, bucket, normalized, rel_path)]
    return [os.path.join(base_dir, normalized, rel_path)]


def _current_index_meta() -> dict:
    return {
        'stage2_rule_version': STAGE2_RULE_VERSION,
        'stage2_config_sha1': STAGE2_CONFIG_SHA1,
        'link_enrichment_enabled': bool(STAGE2_ENABLE_LINK_ENRICHMENT),
        'folders': list(FOLDERS),
    }


def _load_processed_index() -> tuple[dict, dict]:
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            if isinstance(payload, dict) and INDEX_ENTRIES_KEY in payload:
                return payload.get(INDEX_ENTRIES_KEY, {}), payload.get(INDEX_META_KEY, {})
            if isinstance(payload, dict):
                return payload, {}
        except Exception:
            return {}, {}
    return {}, {}


def _save_processed_index(idx: dict):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    payload = {
        INDEX_META_KEY: _current_index_meta(),
        INDEX_ENTRIES_KEY: idx,
    }
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _reset_output_tree(base_dir: str):
    seen = set()
    for folder in FOLDERS:
        normalized = _normalize_folder(folder)
        bucket = _folder_bucket(folder)
        target = os.path.join(base_dir, bucket, normalized) if bucket else os.path.join(base_dir, normalized)
        if target in seen:
            continue
        seen.add(target)
        if os.path.exists(target):
            shutil.rmtree(target)


def _file_sig(path: str) -> str:
    st = os.stat(path)
    key = f"{STAGE2_RULE_VERSION}:{STAGE2_CONFIG_SHA1}:{int(STAGE2_ENABLE_LINK_ENRICHMENT)}:{st.st_size}:{int(st.st_mtime)}:{path}".encode('utf-8')
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


def _strip_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    for col in x.columns:
        if pd.api.types.is_object_dtype(x[col]) or str(x[col].dtype).startswith('string'):
            x[col] = x[col].map(lambda v: pd.NA if pd.isna(v) else str(v).strip())
            x[col] = x[col].replace({'': pd.NA, 'nan': pd.NA, 'None': pd.NA, 'null': pd.NA})
    return x


def _first_present_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    return ''


def _set_reason(reason: pd.Series, mask: pd.Series, value: str) -> None:
    if mask.any():
        reason.loc[mask & reason.eq('')] = value


def sanitize_ohlcv(df: pd.DataFrame):
    x = _normalize_columns(df)
    if x.empty:
        return x, x
    if 'Date' not in x.columns and not isinstance(x.index, pd.DatetimeIndex):
        x = x.reset_index().rename(columns={'index': 'Date'})
    if 'Date' not in x.columns:
        q = x.copy()
        q['reason'] = 'missing_date_column'
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
    if x.empty:
        return x, x
    col_map = {'날짜': 'Date', '일자': 'Date', '기관': 'Inst', '법인': 'Corp', '개인': 'Indiv', '외국인': 'Foreign', '합계': 'Total'}
    x = x.rename(columns={c: col_map[c] for c in x.columns if c in col_map})
    required = ['Date', 'Inst', 'Corp', 'Indiv', 'Foreign', 'Total']
    if not all(c in x.columns for c in required):
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
    clean_df = x[~bad].copy().sort_values('Date').drop_duplicates(subset=['Date'], keep='last')
    bad_df = x[bad].copy()
    return clean_df, bad_df


def _sanitize_dart_csv(df: pd.DataFrame):
    x = _strip_object_columns(_normalize_columns(df))
    required = ['corp_code', 'corp_name', 'report_nm', 'rcept_no', 'rcept_dt']
    missing = [c for c in required if c not in x.columns]
    if missing:
        q = x.copy()
        q['reason'] = f"missing_required_columns:{','.join(missing)}"
        return pd.DataFrame(), q

    parsed_dt = pd.to_datetime(x['rcept_dt'], format='%Y%m%d', errors='coerce')
    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    mask = parsed_dt.isna()
    bad |= mask
    _set_reason(reason, mask, 'invalid_rcept_dt')

    mask = x['report_nm'].isna()
    bad |= mask
    _set_reason(reason, mask, 'missing_report_nm')

    mask = x['rcept_no'].isna()
    bad |= mask
    _set_reason(reason, mask, 'missing_rcept_no')

    stock_col = 'stock_code' if 'stock_code' in x.columns else ''
    identity_missing = x['corp_code'].isna()
    if stock_col:
        identity_missing &= x[stock_col].isna()
    bad |= identity_missing
    _set_reason(reason, identity_missing, 'missing_corp_or_stock_code')

    dup = x['rcept_no'].duplicated(keep='last') & x['rcept_no'].notna()
    bad |= dup
    _set_reason(reason, dup, 'duplicate_rcept_no')

    if 'rcept_dt' in x.columns:
        x['rcept_dt'] = parsed_dt.dt.strftime('%Y-%m-%d')

    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values
    clean_df = x[~bad].copy().sort_values(['rcept_dt', 'rcept_no'])
    return clean_df, bad_df


def _sanitize_min_qualitative_csv(df: pd.DataFrame):
    x = _strip_object_columns(_normalize_columns(df)).dropna(how='all')
    if x.empty:
        return pd.DataFrame(), pd.DataFrame([{'reason': 'empty_after_strip'}])

    bad = pd.Series(False, index=x.index)
    reason = pd.Series('', index=x.index, dtype='object')

    date_col = _first_present_column(x, ['published_at', 'published', 'datetime', 'timestamp', 'Date', 'date'])
    if date_col:
        parsed_dt = pd.to_datetime(x[date_col], errors='coerce')
        mask = parsed_dt.isna()
        bad |= mask
        _set_reason(reason, mask, f'invalid_{date_col.lower()}')

    title_col = _first_present_column(x, ['title', 'headline', 'subject'])
    body_col = _first_present_column(x, ['body', 'content', 'text', 'summary', 'description'])
    url_col = _first_present_column(x, ['url', 'link', 'href'])

    if title_col or body_col or url_col:
        title_ok = x[title_col].notna() if title_col else pd.Series(False, index=x.index)
        body_ok = x[body_col].notna() if body_col else pd.Series(False, index=x.index)
        url_ok = x[url_col].notna() if url_col else pd.Series(False, index=x.index)
        mask = ~(title_ok | body_ok | url_ok)
        bad |= mask
        _set_reason(reason, mask, 'missing_title_body_url')

    id_col = _first_present_column(x, ['id', 'post_id', 'message_id', 'url', 'link'])
    if id_col:
        dup = x[id_col].duplicated(keep='last') & x[id_col].notna()
        bad |= dup
        _set_reason(reason, dup, f'duplicate_{id_col.lower()}')
    elif date_col and title_col:
        dup = x[[date_col, title_col]].astype(str).duplicated(keep='last')
        bad |= dup
        _set_reason(reason, dup, 'duplicate_date_title')

    bad_df = x[bad].copy()
    if not bad_df.empty:
        bad_df['reason'] = reason.loc[bad_df.index].values
    clean_df = x[~bad].copy()
    return clean_df, bad_df


def sanitize_generic_csv(df: pd.DataFrame, folder: str = ''):
    x = _normalize_columns(df)
    if _folder_bucket(folder) != 'qualitative':
        return x, pd.DataFrame()
    normalized_folder = _normalize_folder(folder)
    if normalized_folder == 'kr/dart':
        return _sanitize_dart_csv(x)
    return _sanitize_min_qualitative_csv(x)


def _text_without_urls(content: str) -> str:
    x = re.sub(r'https?://\S+', ' ', content or '')
    x = re.sub(r'[`*_>#\[\]()|]+', ' ', x)
    x = re.sub(r'\s+', ' ', x).strip()
    return x


def _extract_effective_lines(content: str, skip_patterns: list[str], marker_filters: set[str] | None = None) -> str:
    lines = []
    marker_filters = marker_filters or set()
    for raw in (content or '').splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.match(r'(?i)^\[/?ATTACH_TEXT\]$', s):
            continue
        if re.match(r'(?i)^\[ATTACH_TEXT_STATUS\]', s):
            continue
        if any(re.match(p, s, flags=re.IGNORECASE) for p in skip_patterns):
            continue
        sl = s.lower()
        if any(m in sl for m in marker_filters):
            continue
        lines.append(s)
    return '\n'.join(lines)


def _is_meaningful_short_text(effective: str) -> bool:
    t = (effective or '').strip()
    if len(t) < SHORT_MEANINGFUL_MIN_LEN:
        return False

    # 숫자/심볼만 있는 노이즈 배제
    if not re.search(r'[A-Za-z가-힣]', t):
        return False

    # 문장 구분자 또는 줄바꿈이 있고, 금융/기업 문맥 키워드 일부가 있으면 통과
    has_sentence_shape = bool(re.search(r'[.!?]|\n', t))
    finance_kw = bool(
        re.search(
            r'(실적|매출|이익|가이던스|밸류|PER|PBR|수주|계약|리스크|주가|상승|하락|증가|감소|투자|업황|현금흐름|capex|margin|guidance|earnings|revenue|profit|order|risk)',
            t,
            flags=re.IGNORECASE,
        )
    )
    return has_sentence_shape and finance_kw


def _extract_urls(text: str) -> list[str]:
    return [m.group(0).rstrip('.,);]\"\'') for m in URL_PATTERN.finditer(text or '')]


def _extract_attach_text(content: str) -> str:
    chunks = []
    for m in ATTACH_TEXT_BLOCK_RE.finditer(content or ''):
        chunk = (m.group(1) or '').strip()
        if chunk:
            chunks.append(chunk)
    return '\n'.join(chunks).strip()


def _strip_attachment_residue(content: str) -> str:
    cleaned = content or ''
    for pat in ATTACHMENT_DROP_BLOCK_PATTERNS:
        cleaned = re.sub(pat, '\n', cleaned)

    kept_lines = []
    for raw in cleaned.splitlines():
        s = raw.strip()
        if s and any(re.match(pat, s) for pat in ATTACHMENT_DROP_LINE_PATTERNS):
            continue
        kept_lines.append(raw.rstrip())

    text = '\n'.join(kept_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + ('\n' if text.strip() else '')


def _build_link_source_text(content: str, attach_text: str = '') -> str:
    src = content or ''
    attach = (attach_text or '').strip()
    if not attach:
        return src
    return f"{src}\n{attach}"


def _canonicalize_url(url: str) -> str:
    if not url:
        return ''
    raw = (url or '').strip().strip('"\'()[]{}<>')
    if not raw:
        return ''
    try:
        p = urlparse(raw)
    except Exception:
        return ''

    if p.scheme.lower() not in {'http', 'https'}:
        return ''

    host = (p.hostname or '').lower().strip()
    if not host:
        return ''

    port = p.port
    if port and not ((p.scheme.lower() == 'http' and port == 80) or (p.scheme.lower() == 'https' and port == 443)):
        netloc = f'{host}:{port}'
    else:
        netloc = host

    path = re.sub(r'/+', '/', p.path or '/').strip()
    if not path.startswith('/'):
        path = '/' + path
    if path != '/':
        path = path.rstrip('/')

    kept_qs = []
    for k, v in parse_qsl(p.query or '', keep_blank_values=False):
        lk = (k or '').lower().strip()
        if not lk:
            continue
        if any(lk == t or lk.startswith(t) for t in TRACKING_QUERY_PREFIXES):
            continue
        kept_qs.append((k, v))
    query = urlencode(sorted(kept_qs), doseq=True)

    return urlunparse(('https', netloc, path, '', query, ''))


def _is_allowed_link_url(canonical_url: str) -> bool:
    try:
        host = (urlparse(canonical_url).hostname or '').lower()
    except Exception:
        return False
    if not host:
        return False

    # 공통 차단 도메인
    if any(host == d or host.endswith('.' + d) for d in BLOCKED_LINK_DOMAIN_SUFFIXES):
        return False

    # 확장 모드: 대부분 도메인 허용(차단목록 우선)
    if LINK_ENRICH_ALLOW_ALL_DOMAINS:
        return '.' in host

    return any(host == d or host.endswith('.' + d) for d in ALLOWED_LINK_DOMAIN_SUFFIXES)


def _normalize_for_fingerprint(text: str) -> str:
    x = (text or '').lower()
    x = re.sub(r'https?://\S+', ' ', x)
    x = re.sub(r'[^0-9a-z가-힣\s]', ' ', x)
    x = re.sub(r'\s+', ' ', x).strip()
    return x


def _fingerprint(text: str) -> str:
    return hashlib.sha1(_normalize_for_fingerprint(text).encode('utf-8')).hexdigest()


def _html_to_text(payload: str) -> str:
    html = payload or ''
    html = re.sub(r'(?is)<(script|style|noscript|iframe|svg).*?>.*?</\1>', ' ', html)
    html = re.sub(r'(?i)<br\s*/?>', '\n', html)
    html = re.sub(r'(?i)</(p|div|section|article|li|h1|h2|h3|h4|h5|h6)>', '\n', html)
    html = re.sub(r'(?s)<[^>]+>', ' ', html)
    html = unescape(html)
    html = html.replace('\xa0', ' ')

    lines = []
    seen = set()
    for raw in html.splitlines():
        s = re.sub(r'\s+', ' ', raw).strip()
        if len(s) < 25:
            continue
        fp = _fingerprint(s)
        if fp in seen:
            continue
        seen.add(fp)
        lines.append(s)
        if len('\n'.join(lines)) >= LINK_FETCH_MAX_TEXT_CHARS:
            break

    return '\n'.join(lines)[:LINK_FETCH_MAX_TEXT_CHARS].strip()


def _fetch_link_text(canonical_url: str) -> tuple[str, str]:
    cached = LINK_FETCH_CACHE.get(canonical_url)
    if cached is not None:
        LINK_RUNTIME_STATS['url_cache_hits'] += 1
        return cached.get('text', ''), cached.get('error', '')

    if not _is_allowed_link_url(canonical_url):
        LINK_RUNTIME_STATS['url_disallowed'] += 1
        LINK_FETCH_CACHE[canonical_url] = {'text': '', 'error': 'disallowed_domain'}
        return '', 'disallowed_domain'

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; stage2-link-enrich/1.0)',
        'Accept': 'text/html,application/xhtml+xml,text/plain',
    }

    last_err = 'fetch_failed'
    for attempt in range(LINK_FETCH_MAX_RETRIES + 1):
        try:
            req = Request(canonical_url, headers=headers)
            with urlopen(req, timeout=LINK_FETCH_TIMEOUT_SEC) as resp:
                raw = resp.read(LINK_FETCH_MAX_BYTES)
                content_type = str(resp.headers.get('Content-Type', '')).lower()

            if 'charset=' in content_type:
                charset = content_type.split('charset=')[-1].split(';')[0].strip()
            else:
                charset = 'utf-8'
            try:
                decoded = raw.decode(charset, errors='ignore')
            except Exception:
                decoded = raw.decode('utf-8', errors='ignore')

            if 'html' in content_type or '<html' in decoded[:500].lower():
                text = _html_to_text(decoded)
            else:
                text = re.sub(r'\s+', ' ', decoded).strip()[:LINK_FETCH_MAX_TEXT_CHARS]

            effective = _text_without_urls(text)
            if len(effective) < LINK_ENRICH_MIN_EFFECTIVE_ADD:
                last_err = 'fetched_text_too_short'
                continue

            LINK_RUNTIME_STATS['url_fetch_success'] += 1
            LINK_FETCH_CACHE[canonical_url] = {'text': text, 'error': ''}
            return text, ''
        except Exception as e:
            last_err = f'{type(e).__name__}:{e}'
            if attempt < LINK_FETCH_MAX_RETRIES:
                time.sleep(LINK_FETCH_BACKOFF_BASE_SEC * (2 ** attempt))

    LINK_RUNTIME_STATS['url_fetch_failure'] += 1
    LINK_FETCH_CACHE[canonical_url] = {'text': '', 'error': last_err}
    return '', last_err


def _canonical_dedup_urls(urls: list[str]) -> tuple[list[str], int]:
    canonical = []
    seen = set()
    deduped = 0
    for u in urls:
        cu = _canonicalize_url(u)
        if not cu:
            continue
        if cu in seen:
            deduped += 1
            continue
        seen.add(cu)
        canonical.append(cu)
    return canonical, deduped


def _needs_link_enrichment(content: str, effective: str, min_len: int, url_count: int) -> bool:
    if url_count <= 0:
        return False
    eff_len = len((effective or '').strip())
    if eff_len < min_len:
        return True

    non_ws = len(re.sub(r'\s+', '', content or ''))
    non_ws_no_url = len(re.sub(r'\s+', '', _text_without_urls(content or '')))
    if non_ws <= 0:
        return True
    ratio = non_ws_no_url / non_ws
    return ratio < 0.55


def _collect_unique_enrichment_blocks(canonical_urls: list[str], base_effective: str) -> tuple[list[tuple[str, str]], int, dict]:
    seen_fp = set()
    if base_effective.strip():
        seen_fp.add(_fingerprint(base_effective))

    blocks = []
    content_dup_count = 0
    total_chars = 0
    fetch_meta = {
        'attempted_urls': 0,
        'successful_urls': 0,
        'fetch_failed_urls': 0,
        'disallowed_urls': 0,
        'fetched_text_too_short_urls': 0,
    }

    for cu in canonical_urls[:LINK_ENRICH_MAX_URLS_PER_FILE]:
        fetch_meta['attempted_urls'] += 1
        fetched_text, fetch_error = _fetch_link_text(cu)
        if not fetched_text:
            if fetch_error == 'disallowed_domain':
                fetch_meta['disallowed_urls'] += 1
            elif fetch_error == 'fetched_text_too_short':
                fetch_meta['fetched_text_too_short_urls'] += 1
            else:
                fetch_meta['fetch_failed_urls'] += 1
            continue

        fetch_meta['successful_urls'] += 1
        candidates = []
        for seg in re.split(r'\n{2,}', fetched_text):
            s = re.sub(r'\s+', ' ', seg).strip()
            if len(s) < 45:
                continue
            candidates.append(s)

        kept = []
        for seg in candidates:
            fp = _fingerprint(seg)
            if fp in seen_fp:
                content_dup_count += 1
                continue
            seen_fp.add(fp)
            kept.append(seg)

        if not kept:
            continue

        merged = '\n'.join(kept)
        if total_chars + len(merged) > LINK_ENRICH_MAX_TOTAL_CHARS:
            allowed = max(0, LINK_ENRICH_MAX_TOTAL_CHARS - total_chars)
            merged = merged[:allowed].strip()
        if not merged:
            continue

        blocks.append((cu, merged))
        total_chars += len(merged)
        if total_chars >= LINK_ENRICH_MAX_TOTAL_CHARS:
            break

    return blocks, content_dup_count, fetch_meta


def _inject_enriched_content(content: str, folder: str, blocks: list[tuple[str, str]], canonical_urls: list[str]) -> str:
    if not blocks:
        return content

    normalized_folder = _normalize_folder(folder)
    if normalized_folder == 'text/premium/startale':
        meta_lines = [
            '- LinkEnriched: true',
            f'- CanonicalURLs: {len(canonical_urls)}',
        ]
        if '## 본문' in content:
            content = content.replace('## 본문', '\n'.join(meta_lines) + '\n\n## 본문', 1)
        else:
            content += '\n' + '\n'.join(meta_lines) + '\n'
    else:
        meta_lines = [
            'LinkEnriched: true',
            f'CanonicalURLs: {len(canonical_urls)}',
        ]
        m = re.search(r'(?mi)^Source\s*:\s*https?://\S+\s*$', content)
        if m:
            insert_at = m.end()
            content = content[:insert_at] + '\n' + '\n'.join(meta_lines) + content[insert_at:]
        else:
            content += '\n' + '\n'.join(meta_lines) + '\n'

    enrich_buf = ['\n', '[LinkEnrichment]']
    for cu, text in blocks:
        enrich_buf.append(f'CanonicalURL: {cu}')
        enrich_buf.append(text)
        enrich_buf.append('')

    return content.rstrip() + '\n\n' + '\n'.join(enrich_buf).strip() + '\n'


def _text_reason_prefix(normalized_folder: str) -> str:
    return {
        'text/blog': 'blog',
        'text/telegram': 'telegram',
        'text/premium/startale': 'premium',
    }.get(normalized_folder, 'text')


def _text_body_reason(normalized_folder: str, effective: str) -> str:
    prefix = _text_reason_prefix(normalized_folder)
    if normalized_folder == 'text/premium/startale':
        if not (effective or '').strip():
            return 'premium_effective_body_empty_or_boilerplate'
        return 'premium_effective_body_too_short'
    if not (effective or '').strip():
        return f'{prefix}_effective_body_empty'
    return f'{prefix}_effective_body_too_short'


def _link_fetch_failure_reason(normalized_folder: str) -> str:
    return f"{_text_reason_prefix(normalized_folder)}_link_body_fetch_failed"


def _validate_blog_text(content: str) -> tuple[bool, str, dict]:
    has_date = bool(re.search(r'(?mi)^(Date|PublishedDate)\s*:\s*.+$', content or ''))
    has_source = bool(re.search(r'(?mi)^Source\s*:\s*https?://\S+', content or ''))
    if not (has_date and has_source):
        return False, 'blog_missing_required_metadata', {}

    body = _extract_effective_lines(
        content,
        skip_patterns=[
            r'^#\s+', r'^(Date|PublishedDate|Source|LinkEnriched|CanonicalURLs)\s*:', r'^---$',
        ],
        marker_filters=BLOG_UI_MARKERS,
    )
    effective = _text_without_urls(body)
    context = {
        'effective': effective,
        'min_len': BLOG_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < BLOG_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, _text_body_reason('text/blog', effective), context
    return True, '', context


def _validate_telegram_text(content: str) -> tuple[bool, str, dict]:
    has_date = bool(re.search(r'(?mi)^Date\s*:\s*.+$', content or ''))
    has_source = bool(re.search(r'(?mi)^Source\s*:\s*https?://\S+', content or ''))
    has_post_meta = bool(re.search(r'(?mi)^Post(ID|Date|DateTime)?\s*:', content or ''))

    # highspeed full 로그 포맷 지원
    has_log_header = bool(re.search(r'(?mi)^#\s*Telegram\s+Log\s*:', content or ''))
    has_message_meta = bool(re.search(r'(?mi)^MessageID\s*:\s*\d+', content or ''))

    metadata_ok = (has_source and has_post_meta) or (has_log_header and has_message_meta)
    if not (has_date and metadata_ok):
        return False, 'telegram_missing_required_metadata', {}

    body = _extract_effective_lines(
        content,
        skip_patterns=[
            r'^#\s+', r'^(Date|Source|LinkEnriched|CanonicalURLs)\s*:', r'^---$',
            r'^Post(ID|Date|DateTime)?\s*:',
            r'^MessageID\s*:\s*\d+', r'^Forwarded from\s*:',
        ],
    )
    effective = _text_without_urls(body)
    context = {
        'effective': effective,
        'min_len': TELEGRAM_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < TELEGRAM_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, _text_body_reason('text/telegram', effective), context
    return True, '', context


def _validate_premium_text(content: str) -> tuple[bool, str, dict]:
    has_url = bool(re.search(r'(?mi)^-\s*URL\s*:\s*https?://\S+', content or ''))
    has_published = bool(re.search(r'(?mi)^-\s*PublishedAt\s*:\s*.+$', content or ''))
    status_match = re.search(r'(?mi)^-\s*Status\s*:\s*(.+)$', content or '')
    reason_match = re.search(r'(?mi)^-\s*Reason\s*:\s*(.+)$', content or '')

    if not (has_url and has_published and status_match):
        return False, 'premium_missing_required_metadata', {}

    status = status_match.group(1).strip().upper()
    if status not in {'SUCCESS', 'OK'}:
        return False, f'premium_bad_status_{status}', {}

    reason = (reason_match.group(1).strip().lower() if reason_match else '')
    if any(k in reason for k in ['paywall', 'subscription', 'session', 'blocked']):
        return False, 'premium_paywall_or_blocked_reason', {}

    parts = re.split(r'(?mi)^##\s*본문\s*$', content or '', maxsplit=1)
    body = parts[1] if len(parts) > 1 else ''
    effective_body = _extract_effective_lines(
        body,
        skip_patterns=[],
        marker_filters=PREMIUM_BOILERPLATE_MARKERS,
    )
    effective = _text_without_urls(effective_body)
    context = {
        'effective': effective,
        'min_len': PREMIUM_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < PREMIUM_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, _text_body_reason('text/premium/startale', effective), context

    return True, '', context


def _validate_text_by_folder(content: str, normalized_folder: str) -> tuple[bool, str, dict]:
    if normalized_folder == 'text/blog':
        return _validate_blog_text(content)
    if normalized_folder == 'text/telegram':
        return _validate_telegram_text(content)
    if normalized_folder == 'text/premium/startale':
        return _validate_premium_text(content)
    return True, '', {}


def _is_short_reason(reason: str) -> bool:
    return reason in {
        'blog_effective_body_empty',
        'blog_effective_body_too_short',
        'telegram_effective_body_empty',
        'telegram_effective_body_too_short',
        'premium_effective_body_empty_or_boilerplate',
        'premium_effective_body_too_short',
    }


def sanitize_text(path: str, folder: str = ''):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        raw_trim = (raw_content or '').strip()
        if len(raw_trim) < 10:
            return None, 'text_too_short', {}

        attach_text = _extract_attach_text(raw_content)
        if attach_text:
            LINK_RUNTIME_STATS['attachment_blocks_seen'] += 1
            LINK_RUNTIME_STATS['attachment_text_chars_total'] += len(attach_text)

        normalized_folder = _normalize_folder(folder)
        cleaned_content = _strip_attachment_residue(raw_content)
        ok, reason, ctx = _validate_text_by_folder(cleaned_content, normalized_folder)
        if ok:
            return cleaned_content, None, {'link_enriched': False, 'canonical_urls': 0, 'attachment_residue_removed': cleaned_content != raw_content}

        if not STAGE2_ENABLE_LINK_ENRICHMENT:
            return None, reason, {'link_enriched': False, 'link_enrichment_enabled': False}

        if normalized_folder not in TARGET_LINK_ENRICH_FOLDERS or not _is_short_reason(reason):
            return None, reason, {}

        link_source_text = _build_link_source_text(raw_content, attach_text)
        raw_urls = _extract_urls(link_source_text)
        LINK_RUNTIME_STATS['url_raw_extracted_total'] += len(raw_urls)
        canonical_urls, deduped = _canonical_dedup_urls(raw_urls)
        LINK_RUNTIME_STATS['url_canonical_total'] += len(canonical_urls)
        LINK_RUNTIME_STATS['url_deduped_within_file'] += deduped

        if not _needs_link_enrichment(cleaned_content, ctx.get('effective', ''), int(ctx.get('min_len', 0)), len(canonical_urls)):
            return None, reason, {}

        LINK_RUNTIME_STATS['enrichment_attempt_files'] += 1
        blocks, content_dup_count, fetch_meta = _collect_unique_enrichment_blocks(canonical_urls, ctx.get('effective', ''))
        LINK_RUNTIME_STATS['content_fingerprint_dedup'] += content_dup_count
        if not blocks:
            LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
            if fetch_meta.get('attempted_urls', 0) > 0 and fetch_meta.get('successful_urls', 0) == 0 and fetch_meta.get('fetch_failed_urls', 0) > 0:
                return None, _link_fetch_failure_reason(normalized_folder), {'link_enriched': False, **fetch_meta}
            return None, reason, {'link_enriched': False, **fetch_meta}

        enriched_content = _inject_enriched_content(cleaned_content, normalized_folder, blocks, canonical_urls)
        ok2, reason2, _ = _validate_text_by_folder(enriched_content, normalized_folder)
        if ok2:
            LINK_RUNTIME_STATS['enrichment_applied_files'] += 1
            LINK_RUNTIME_STATS['enrichment_promoted_files'] += 1
            return enriched_content, None, {
                'link_enriched': True,
                'canonical_urls': len(canonical_urls),
                'enriched_blocks': len(blocks),
                'attachment_residue_removed': cleaned_content != raw_content,
            }

        LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
        return None, reason2, {}
    except Exception as e:
        return None, f'exception:{type(e).__name__}:{e}', {}


def _flatten_rss_entries(data) -> list[dict]:
    entries = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                entries.append(item)
    elif isinstance(data, dict):
        for _, value in data.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        entries.append(item)
            elif isinstance(value, dict):
                entries.append(value)
    return entries


def _has_any_nonempty_key(d: dict, keys: set[str]) -> bool:
    for k, v in d.items():
        if str(k).strip().lower() in keys and str(v or '').strip():
            return True
    return False


def _validate_market_rss_json(data) -> tuple[bool, str]:
    entries = _flatten_rss_entries(data)
    if not entries:
        return False, 'rss_no_entries'

    title_keys = {'title', 'headline', 'subject'}
    datetime_keys = {'published', 'published_at', 'publisheddate', 'pubdate', 'date', 'datetime', 'timestamp'}
    url_keys = {'link', 'url', 'href'}

    valid_entries = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        has_title = _has_any_nonempty_key(e, title_keys)
        has_dt = _has_any_nonempty_key(e, datetime_keys)
        has_url = _has_any_nonempty_key(e, url_keys)
        if has_title and has_dt and has_url:
            valid_entries += 1

    if valid_entries <= 0:
        return False, 'rss_missing_required_fields(title/datetime/url)'

    return True, ''


def sanitize_json(path: str, folder: str = ''):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data:
            return None, 'empty_json'

        normalized_folder = _normalize_folder(folder)
        if normalized_folder == 'market/rss':
            ok, reason = _validate_market_rss_json(data)
            if not ok:
                return None, reason

        return data, None
    except Exception:
        return None, 'invalid_json'


def _ensure_parent(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _remove_if_exists(path: str):
    if os.path.exists(path):
        os.remove(path)


def _write_csv(df: pd.DataFrame, paths: list[str]):
    output_path = paths[0]
    _ensure_parent(output_path)
    df.to_csv(output_path, index=False)


def _write_json(data, paths: list[str]):
    output_path = paths[0]
    _ensure_parent(output_path)
    with open(output_path, 'w', encoding='utf-8') as fout:
        json.dump(data, fout, ensure_ascii=False, indent=2)


def _write_text(text: str, paths: list[str]):
    output_path = paths[0]
    _ensure_parent(output_path)
    with open(output_path, 'w', encoding='utf-8') as fout:
        fout.write(text)


def _safe_read_text(path: str, max_chars: int = 4000) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(max_chars)
    except Exception:
        return ''


def _extract_quarantine_meta_lines(content: str, max_lines: int = 12) -> list[str]:
    if not content:
        return []
    lines = []
    pats = [
        r'(?i)^#\s+.+$',
        r'(?i)^-\s*(Title|Date|PublishedDate|PublishedAt|Source|URL|Status|Reason|PostID|PostDate|PostDateTime)\s*:\s*.+$',
        r'(?i)^(Title|Date|PublishedDate|PublishedAt|Source|URL|Status|Reason|PostID|PostDate|PostDateTime)\s*:\s*.+$',
    ]
    for raw in content.splitlines():
        s = raw.strip()
        if not s:
            continue
        if any(re.match(p, s) for p in pats):
            lines.append(s)
        if len(lines) >= max_lines:
            break
    return lines


def _extract_quarantine_preview(content: str, max_chars: int = 600) -> str:
    if not content:
        return ''
    cleaned = []
    for raw in content.splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.match(r'(?i)^#\s+.+$', s):
            continue
        if re.match(r'(?i)^-\s*(Title|Date|PublishedDate|PublishedAt|Source|URL|Status|Reason|PostID|PostDate|PostDateTime)\s*:\s*.+$', s):
            continue
        if re.match(r'(?i)^(Title|Date|PublishedDate|PublishedAt|Source|URL|Status|Reason|PostID|PostDate|PostDateTime)\s*:\s*.+$', s):
            continue
        if s == '---':
            continue
        cleaned.append(s)

    x = '\n'.join(cleaned)
    x = re.sub(r'\n{3,}', '\n\n', x).strip()
    return x[:max_chars]


def _build_text_quarantine_payload(folder: str, source_file: str, reason: str, raw_text: str, extra_meta: dict | None = None) -> str:
    reason = (reason or 'invalid_text').strip()
    meta_lines = _extract_quarantine_meta_lines(raw_text)
    preview = _extract_quarantine_preview(raw_text)

    buf = []
    buf.append(f'reason: {reason}')
    buf.append(f'folder: {folder}')
    buf.append(f'source_file: {source_file}')
    buf.append(f'sanitized_at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    buf.append(f'stage2_rule_version: {STAGE2_RULE_VERSION}')
    if extra_meta:
        for key, value in extra_meta.items():
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, ensure_ascii=False)
            else:
                rendered = str(value)
            buf.append(f'{key}: {rendered}')
    buf.append('')
    buf.append('meta_lines:')
    if meta_lines:
        for m in meta_lines:
            buf.append(f'- {m}')
    else:
        buf.append('- (none)')
    buf.append('')
    buf.append('preview:')
    buf.append(preview if preview else '(empty)')
    buf.append('')
    return '\n'.join(buf)


def _normalize_title_text(text: str) -> str:
    x = _normalize_for_fingerprint(text)
    return re.sub(r'\s+', ' ', x).strip()


def _normalize_date_token(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    parsed = pd.to_datetime(raw, errors='coerce')
    if not pd.isna(parsed):
        return parsed.strftime('%Y-%m-%d')

    m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', raw)
    if not m:
        return ''
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime('%Y-%m-%d')
    except Exception:
        return ''


def _extract_text_title(content: str) -> str:
    for pat in [
        r'(?mi)^Title\s*:\s*(.+)$',
        r'(?mi)^#\s+(.+?)\s*$',
    ]:
        m = re.search(pat, content or '')
        if m:
            title = str(m.group(1) or '').strip()
            if title:
                return title
    return ''


def _extract_text_date(content: str) -> str:
    for pat in [
        r'(?mi)^(?:Date|PublishedDate|PostDate|PostDateTime)\s*:\s*(.+)$',
        r'(?mi)^-\s*(?:PublishedAt|Date)\s*:\s*(.+)$',
    ]:
        m = re.search(pat, content or '')
        if not m:
            continue
        normalized = _normalize_date_token(m.group(1))
        if normalized:
            return normalized
    return ''


def _extract_text_canonical_urls(content: str) -> list[str]:
    raw_urls = []
    for pat in [
        r'(?mi)^(?:Source|URL|CanonicalURL)\s*:\s*(https?://\S+)\s*$',
        r'(?mi)^-\s*(?:URL|CanonicalURL)\s*:\s*(https?://\S+)\s*$',
    ]:
        raw_urls.extend(m.group(1) for m in re.finditer(pat, content or ''))
    canonical_urls, _ = _canonical_dedup_urls(raw_urls)
    return canonical_urls


def _extract_text_effective_for_dedup(content: str, folder: str) -> str:
    normalized_folder = _normalize_folder(folder)
    _, _, ctx = _validate_text_by_folder(content, normalized_folder)
    effective = str(ctx.get('effective') or '').strip()
    if effective:
        return effective

    if normalized_folder == 'text/premium/startale':
        parts = re.split(r'(?mi)^##\s*본문\s*$', content or '', maxsplit=1)
        body = parts[1] if len(parts) > 1 else ''
        effective_body = _extract_effective_lines(body, skip_patterns=[], marker_filters=PREMIUM_BOILERPLATE_MARKERS)
        return _text_without_urls(effective_body)

    return _text_without_urls(content or '')


def _content_fingerprints(text: str) -> list[str]:
    base = (text or '').strip()
    if not base:
        return []

    candidates = [base]
    candidates.extend(seg.strip() for seg in re.split(r'\n{2,}', base) if seg.strip())
    if len(candidates) <= 1:
        candidates.extend(seg.strip() for seg in base.splitlines() if seg.strip())

    seen = set()
    fps = []
    for cand in candidates:
        norm = _normalize_for_fingerprint(cand)
        if len(norm) < DEDUP_MIN_FP_TEXT_LEN:
            continue
        fp = hashlib.sha1(norm.encode('utf-8')).hexdigest()
        if fp in seen:
            continue
        seen.add(fp)
        fps.append(fp)
    return fps


def _should_use_title_date_key(folder: str, title: str) -> bool:
    normalized_folder = _normalize_folder(folder)
    normalized_title = _normalize_title_text(title)
    if len(normalized_title) < 12:
        return False
    if normalized_folder == 'text/telegram' and normalized_title.startswith('telegram public fallback'):
        return False
    if normalized_folder == 'text/telegram' and normalized_title.startswith('telegram log'):
        return False
    return True


def _build_text_dedup_signals(content: str, folder: str) -> dict:
    title = _extract_text_title(content)
    date = _extract_text_date(content)
    normalized_title = _normalize_title_text(title)
    title_date_keys = [f'{date}|{normalized_title}'] if date and _should_use_title_date_key(folder, title) else []
    effective = _extract_text_effective_for_dedup(content, folder)
    return {
        'title': title,
        'date': date,
        'canonical_urls': _extract_text_canonical_urls(content),
        'title_date_keys': title_date_keys,
        'content_fingerprints': _content_fingerprints(effective),
    }


def _selected_article_effective_text(row: dict) -> str:
    parts = []
    for key in ('summary', 'body'):
        value = str(row.get(key) or '').strip()
        if value:
            parts.append(value)
    return _text_without_urls('\n'.join(parts))


def _validate_selected_article_row(row: dict) -> tuple[bool, str, dict]:
    if not isinstance(row, dict):
        return False, 'selected_articles_row_not_object', {}

    clean_row = dict(row)
    clean_row['url'] = _canonicalize_url(str(clean_row.get('url') or ''))
    clean_row['title'] = str(clean_row.get('title') or '').strip()

    normalized_date = _normalize_date_token(str(clean_row.get('published_date') or clean_row.get('published_at') or ''))
    if normalized_date:
        clean_row['published_date'] = normalized_date

    effective = _selected_article_effective_text(clean_row)
    if not clean_row['url']:
        return False, 'selected_articles_missing_url', clean_row
    if not clean_row['title']:
        return False, 'selected_articles_missing_title', clean_row
    if not normalized_date:
        return False, 'selected_articles_missing_published_date', clean_row
    if len(effective) < SELECTED_ARTICLES_MIN_TEXT_LEN and not _is_meaningful_short_text(effective):
        return False, 'selected_articles_effective_body_too_short', clean_row
    return True, '', clean_row


def _build_selected_article_dedup_signals(row: dict) -> dict:
    canonical_urls, _ = _canonical_dedup_urls([str(row.get('url') or '')])
    title = str(row.get('title') or '').strip()
    date = _normalize_date_token(str(row.get('published_date') or row.get('published_at') or ''))
    normalized_title = _normalize_title_text(title)
    title_date_keys = [f'{date}|{normalized_title}'] if date and normalized_title else []
    return {
        'title': title,
        'date': date,
        'canonical_urls': canonical_urls,
        'title_date_keys': title_date_keys,
        'content_fingerprints': _content_fingerprints(_selected_article_effective_text(row)),
    }


def _new_corpus_dedup_registry() -> dict:
    return {
        'by_url': {},
        'by_title_date': {},
        'by_content_fp': {},
        'registered_items': 0,
        'duplicate_items': 0,
        'bootstrap_files': 0,
        'bootstrap_records': 0,
    }


def _make_dedup_ref(folder: str, rel_path: str, source_file: str, *, title: str = '', date: str = '', canonical_url: str = '', record_index: int | None = None) -> dict:
    return {
        'folder': folder,
        'rel_path': rel_path.replace('\\', '/'),
        'source_file': source_file,
        'record_index': record_index,
        'title': title,
        'date': date,
        'canonical_url': canonical_url,
    }


def _same_logical_item(existing: dict, current: dict) -> bool:
    return (
        existing.get('folder') == current.get('folder')
        and existing.get('rel_path') == current.get('rel_path')
        and existing.get('record_index') == current.get('record_index')
    )


def _has_dedup_signals(signals: dict) -> bool:
    return any(signals.get(k) for k in ('canonical_urls', 'title_date_keys', 'content_fingerprints'))


def _find_corpus_duplicate(registry: dict, signals: dict, current_ref: dict) -> dict | None:
    for kind, keys, bucket in [
        ('canonical_url', signals.get('canonical_urls') or [], 'by_url'),
        ('title_date', signals.get('title_date_keys') or [], 'by_title_date'),
        ('content_fingerprint', signals.get('content_fingerprints') or [], 'by_content_fp'),
    ]:
        store = registry[bucket]
        for key in keys:
            existing = store.get(key)
            if existing and not _same_logical_item(existing, current_ref):
                registry['duplicate_items'] += 1
                return {
                    'kind': kind,
                    'key': key,
                    'matched_ref': existing,
                }
    return None


def _register_corpus_signals(registry: dict, signals: dict, current_ref: dict):
    registered = False
    for key in signals.get('canonical_urls') or []:
        if key and key not in registry['by_url']:
            registry['by_url'][key] = dict(current_ref)
            registered = True
    for key in signals.get('title_date_keys') or []:
        if key and key not in registry['by_title_date']:
            registry['by_title_date'][key] = dict(current_ref)
            registered = True
    for key in signals.get('content_fingerprints') or []:
        if key and key not in registry['by_content_fp']:
            registry['by_content_fp'][key] = dict(current_ref)
            registered = True
    if registered:
        registry['registered_items'] += 1


def _duplicate_meta(duplicate: dict | None) -> dict:
    if not duplicate:
        return {}
    matched = duplicate.get('matched_ref') or {}
    return {
        'duplicate_kind': duplicate.get('kind', ''),
        'duplicate_key': duplicate.get('key', ''),
        'duplicate_of': {
            'folder': matched.get('folder', ''),
            'rel_path': matched.get('rel_path', ''),
            'source_file': matched.get('source_file', ''),
            'record_index': matched.get('record_index'),
        },
    }


def _reason_taxonomy_snapshot() -> dict:
    snapshot = json.loads(json.dumps(REFINE_REASON_CONFIG, ensure_ascii=False))
    snapshot['terminal_quarantine_reasons'] = snapshot['quarantine_reason_groups']
    snapshot['max_available_policy'] = snapshot['reason_filter_taxonomy']['max_available']
    snapshot['warn_report_issue_types'] = snapshot['report_issue_filters']['warn']
    snapshot['fail_report_issue_types'] = snapshot['report_issue_filters']['fail']
    return snapshot


def _read_jsonl_records(path: str) -> tuple[list[dict], list[dict]]:
    rows = []
    errors = []
    with open(path, 'r', encoding='utf-8') as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception as e:
                errors.append({
                    'reason': f'jsonl_parse_error:{type(e).__name__}:{e}',
                    'line_no': line_no,
                    'raw_preview': line[:400],
                })
                continue
            if not isinstance(data, dict):
                errors.append({
                    'reason': 'jsonl_row_not_object',
                    'line_no': line_no,
                    'raw_preview': line[:400],
                })
                continue
            rows.append(data)
    return rows, errors


def sanitize_jsonl(path: str, folder: str = '', dedup_registry: dict | None = None, rel_path: str = ''):
    normalized_folder = _normalize_folder(folder)
    if normalized_folder != 'market/news/selected_articles':
        return None, [{
            'reason': 'unsupported_jsonl_folder',
            'folder': folder,
            'source_file': path,
            'stage2_rule_version': STAGE2_RULE_VERSION,
        }], {}

    rows, parse_errors = _read_jsonl_records(path)
    clean_rows = []
    quarantine_rows = [
        {
            **err,
            'folder': folder,
            'source_file': path,
            'stage2_rule_version': STAGE2_RULE_VERSION,
        }
        for err in parse_errors
    ]
    deduped_rows = 0

    for line_no, row in enumerate(rows, start=1):
        ok, reason, clean_row = _validate_selected_article_row(row)
        if not ok:
            quarantine_rows.append({
                'reason': reason,
                'line_no': line_no,
                'folder': folder,
                'source_file': path,
                'stage2_rule_version': STAGE2_RULE_VERSION,
                'row': clean_row or row,
            })
            continue

        signals = _build_selected_article_dedup_signals(clean_row)
        current_ref = _make_dedup_ref(
            folder,
            rel_path or os.path.basename(path),
            path,
            title=signals.get('title', ''),
            date=signals.get('date', ''),
            canonical_url=(signals.get('canonical_urls') or [''])[0],
            record_index=line_no,
        )
        duplicate = _find_corpus_duplicate(dedup_registry, signals, current_ref) if dedup_registry and _has_dedup_signals(signals) else None
        if duplicate is not None:
            deduped_rows += 1
            quarantine_rows.append({
                'reason': f"duplicate_{duplicate['kind']}",
                'line_no': line_no,
                'folder': folder,
                'source_file': path,
                'stage2_rule_version': STAGE2_RULE_VERSION,
                **_duplicate_meta(duplicate),
                'row': clean_row,
            })
            continue

        if dedup_registry and _has_dedup_signals(signals):
            _register_corpus_signals(dedup_registry, signals, current_ref)
        clean_rows.append(clean_row)

    if not clean_rows and not quarantine_rows:
        quarantine_rows.append({
            'reason': 'empty_jsonl',
            'folder': folder,
            'source_file': path,
            'stage2_rule_version': STAGE2_RULE_VERSION,
        })

    return clean_rows, quarantine_rows, {
        'rows': len(rows),
        'parse_errors': len(parse_errors),
        'clean_rows': len(clean_rows),
        'quarantine_rows': len(quarantine_rows),
        'deduped_rows': deduped_rows,
    }


def _write_jsonl(rows: list[dict], paths: list[str]):
    output_path = paths[0]
    _ensure_parent(output_path)
    with open(output_path, 'w', encoding='utf-8') as fout:
        for row in rows:
            fout.write(json.dumps(row, ensure_ascii=False) + '\n')


def _bootstrap_corpus_dedup_registry(registry: dict, clean_base: str):
    for folder in sorted(DEDUP_TARGET_FOLDERS):
        folder_dir = _output_paths(clean_base, folder, '')[0]
        if not os.path.isdir(folder_dir):
            continue

        patterns = ['*.md', '*.txt']
        if _normalize_folder(folder) == 'market/news/selected_articles':
            patterns.append('*.jsonl')

        for pattern in patterns:
            for path in glob.glob(os.path.join(folder_dir, '**', pattern), recursive=True):
                rel_path = os.path.relpath(path, folder_dir)
                registry['bootstrap_files'] += 1
                if path.endswith('.jsonl'):
                    rows, _ = _read_jsonl_records(path)
                    for line_no, row in enumerate(rows, start=1):
                        signals = _build_selected_article_dedup_signals(row)
                        if not _has_dedup_signals(signals):
                            continue
                        current_ref = _make_dedup_ref(
                            folder,
                            rel_path,
                            path,
                            title=signals.get('title', ''),
                            date=signals.get('date', ''),
                            canonical_url=(signals.get('canonical_urls') or [''])[0],
                            record_index=line_no,
                        )
                        _register_corpus_signals(registry, signals, current_ref)
                        registry['bootstrap_records'] += 1
                else:
                    content = _safe_read_text(path, max_chars=500000)
                    if not content:
                        continue
                    signals = _build_text_dedup_signals(content, folder)
                    if not _has_dedup_signals(signals):
                        continue
                    current_ref = _make_dedup_ref(
                        folder,
                        rel_path,
                        path,
                        title=signals.get('title', ''),
                        date=signals.get('date', ''),
                        canonical_url=(signals.get('canonical_urls') or [''])[0],
                    )
                    _register_corpus_signals(registry, signals, current_ref)
                    registry['bootstrap_records'] += 1


def run_full_refine(force_rebuild: bool = False):
    global LINK_FETCH_CACHE, LINK_RUNTIME_STATS

    LINK_FETCH_CACHE = {}
    LINK_RUNTIME_STATS = _new_link_runtime_stats()

    results = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    final_clean_base = os.path.join(CLEAN_BASE, 'production')
    final_q_base = os.path.join(Q_BASE, 'production')
    run_mode = 'force_rebuild' if force_rebuild else 'incremental'
    if force_rebuild:
        processed_index = {}
        _reset_output_tree(final_clean_base)
        _reset_output_tree(final_q_base)
        processed_index_meta = _current_index_meta()
    else:
        processed_index, processed_index_meta = _load_processed_index()
        if processed_index_meta != _current_index_meta():
            processed_index = {}
            processed_index_meta = _current_index_meta()

    total_exceptions = 0
    hard_fail_issues = []
    report_only_issues = []
    corpus_dedup_registry = _new_corpus_dedup_registry()
    if not force_rebuild:
        _bootstrap_corpus_dedup_registry(corpus_dedup_registry, final_clean_base)

    for folder in FOLDERS:
        raw_dir = _resolve_raw_dir(folder)
        if not os.path.exists(raw_dir):
            issue = {
                'type': 'missing_input_folder',
                'folder': folder,
                'path': raw_dir,
                'required': folder in REQUIRED_REFINE_FOLDERS,
                'severity': 'fail' if folder in REQUIRED_REFINE_FOLDERS else 'warn',
            }
            if folder in REQUIRED_REFINE_FOLDERS:
                hard_fail_issues.append(issue)
            else:
                report_only_issues.append(issue)
            continue

        all_files = []
        for ext in ['*.csv', '*.json', '*.jsonl', '*.md', '*.txt']:
            all_files.extend(glob.glob(os.path.join(raw_dir, '**', ext), recursive=True))

        num_files = len(all_files)
        clean_count = 0
        q_count = 0
        skipped_count = 0
        exception_count = 0

        for f in all_files:
            rel_path = os.path.relpath(f, raw_dir)
            ext = os.path.splitext(f)[1].lower()
            clean_paths = _output_paths(final_clean_base, folder, rel_path)
            q_paths = _output_paths(final_q_base, folder, rel_path)

            idx_key = f"{folder}/{rel_path}".replace('\\', '/')
            sig = _file_sig(f)
            prev_sig = processed_index.get(idx_key)
            if (not force_rebuild) and prev_sig == sig and any(os.path.exists(p) for p in (clean_paths + q_paths)):
                skipped_count += 1
                continue

            try:
                if ext == '.csv':
                    df = pd.read_csv(f)
                    c_df, q_df = (
                        sanitize_ohlcv(df) if 'ohlcv' in folder else
                        sanitize_supply(df) if 'supply' in folder else
                        sanitize_generic_csv(df, folder=folder)
                    )
                    if not c_df.empty:
                        _write_csv(c_df, clean_paths)
                        for p in q_paths:
                            _remove_if_exists(p)
                        clean_count += 1
                    if not q_df.empty:
                        _write_csv(q_df, q_paths)
                        q_count += 1
                    elif c_df.empty:
                        for p in clean_paths:
                            _remove_if_exists(p)
                        _write_csv(pd.DataFrame([{'reason': 'empty_after_sanitize'}]), q_paths)
                        q_count += 1
                elif ext == '.json':
                    data, err = sanitize_json(f, folder=folder)
                    if data is not None:
                        _write_json(data, clean_paths)
                        for p in q_paths:
                            _remove_if_exists(p)
                        clean_count += 1
                    else:
                        for p in clean_paths:
                            _remove_if_exists(p)
                        raw_preview = _safe_read_text(f, max_chars=1200)
                        _write_json(
                            {
                                'reason': err or 'invalid_json',
                                'folder': folder,
                                'source_file': f,
                                'sanitized_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'stage2_rule_version': STAGE2_RULE_VERSION,
                                'raw_preview': raw_preview,
                            },
                            q_paths,
                        )
                        q_count += 1
                elif ext == '.jsonl':
                    clean_rows, quarantine_rows, _stats = sanitize_jsonl(
                        f,
                        folder=folder,
                        dedup_registry=corpus_dedup_registry,
                        rel_path=rel_path,
                    )
                    if clean_rows:
                        _write_jsonl(clean_rows, clean_paths)
                        clean_count += 1
                    else:
                        for p in clean_paths:
                            _remove_if_exists(p)
                    if quarantine_rows:
                        _write_jsonl(quarantine_rows, q_paths)
                        q_count += 1
                    else:
                        for p in q_paths:
                            _remove_if_exists(p)
                else:
                    content, err, _meta = sanitize_text(f, folder=folder)
                    if content is not None:
                        duplicate = None
                        normalized_folder = _normalize_folder(folder)
                        if normalized_folder in DEDUP_TARGET_FOLDERS:
                            signals = _build_text_dedup_signals(content, folder)
                            current_ref = _make_dedup_ref(
                                folder,
                                rel_path,
                                f,
                                title=signals.get('title', ''),
                                date=signals.get('date', ''),
                                canonical_url=(signals.get('canonical_urls') or [''])[0],
                            )
                            if _has_dedup_signals(signals):
                                duplicate = _find_corpus_duplicate(corpus_dedup_registry, signals, current_ref)
                                if duplicate is None:
                                    _register_corpus_signals(corpus_dedup_registry, signals, current_ref)
                        if duplicate is None:
                            _write_text(content, clean_paths)
                            for p in q_paths:
                                _remove_if_exists(p)
                            clean_count += 1
                        else:
                            for p in clean_paths:
                                _remove_if_exists(p)
                            payload = _build_text_quarantine_payload(
                                folder=folder,
                                source_file=f,
                                reason=f"duplicate_{duplicate['kind']}",
                                raw_text=content,
                                extra_meta=_duplicate_meta(duplicate),
                            )
                            _write_text(payload, q_paths)
                            q_count += 1
                    else:
                        for p in clean_paths:
                            _remove_if_exists(p)
                        raw_text = _safe_read_text(f, max_chars=12000)
                        payload = _build_text_quarantine_payload(
                            folder=folder,
                            source_file=f,
                            reason=err or 'invalid_text',
                            raw_text=raw_text,
                        )
                        _write_text(payload, q_paths)
                        q_count += 1

                processed_index[idx_key] = sig
            except Exception as e:
                exception_count += 1
                for p in clean_paths:
                    _remove_if_exists(p)
                raw_text = _safe_read_text(f, max_chars=12000)
                payload = _build_text_quarantine_payload(
                    folder=folder,
                    source_file=f,
                    reason=f'exception:{type(e).__name__}:{e}',
                    raw_text=raw_text,
                )
                _write_text(payload, q_paths)
                q_count += 1

        if exception_count > 0:
            hard_fail_issues.append({
                'type': 'folder_processing_exception',
                'folder': folder,
                'count': int(exception_count),
            })
        if folder in REQUIRED_REFINE_FOLDERS and num_files > 0 and clean_count == 0:
            hard_fail_issues.append({
                'type': 'zero_clean_required_folder',
                'folder': folder,
                'input_files': int(num_files),
                'quarantine_files': int(q_count),
            })
        elif num_files > 0 and clean_count == 0:
            report_only_issues.append({
                'type': 'zero_clean_optional_folder',
                'folder': folder,
                'input_files': int(num_files),
                'quarantine_files': int(q_count),
            })

        total_exceptions += exception_count
        results.append({
            'folder': folder,
            'bucket': _folder_bucket(folder),
            'canonical_folder': _normalize_folder(folder),
            'total': num_files,
            'clean': clean_count,
            'quarantine': q_count,
            'skipped': skipped_count,
            'exceptions': exception_count,
        })

    report_path = os.path.join(REPORT_DIR, f"FULL_REFINE_REPORT_{timestamp}.md")
    report_json_path = os.path.join(REPORT_DIR, f"FULL_REFINE_REPORT_{timestamp}.json")
    reason_taxonomy = _reason_taxonomy_snapshot()

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Full Refinement Report\n\n")
        f.write(f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Rule Version: {STAGE2_RULE_VERSION}\n")
        f.write(f"- Run Mode: {run_mode}\n")
        f.write(f"- Processed Index: {'reset' if force_rebuild else 'reuse_if_signature_matches'}\n")
        f.write(f"- Incremental Signature Salt: {STAGE2_RULE_VERSION}\n")
        f.write(f"- Config Bundle SHA1: {STAGE2_CONFIG_PROVENANCE['bundle_sha1']}\n")
        f.write(f"- Runtime Config: {STAGE2_CONFIG_PROVENANCE['runtime_config_path']} ({STAGE2_CONFIG_PROVENANCE['runtime_config_sha1']})\n")
        f.write(f"- Reason Config: {STAGE2_CONFIG_PROVENANCE['reason_config_path']} ({STAGE2_CONFIG_PROVENANCE['reason_config_sha1']})\n")
        f.write(f"- Clean Base: {final_clean_base}\n")
        f.write(f"- Quarantine Base: {final_q_base}\n")
        f.write("- Writer policy: market signal + qualitative canonical writer=`stage02_onepass_refine_full.py`, kr/us signal canonical writer=`stage02_qc_cleaning_full.py`\n")
        f.write("- Output policy: canonical=`production/(signal|qualitative)/*` only\n")
        f.write(f"- Link enrichment enabled: {STAGE2_ENABLE_LINK_ENRICHMENT}\n\n")
        f.write("| Folder | Bucket | Canonical | Total | Clean | Quarantine | Skipped(incremental) | Exceptions |\n")
        f.write("| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |\n")
        for r in results:
            f.write(
                f"| {r['folder']} | {r['bucket']} | {r['canonical_folder']} | {r['total']} | {r['clean']} | "
                f"{r['quarantine']} | {r.get('skipped', 0)} | {r.get('exceptions', 0)} |\n"
            )

        f.write("\n## Totals\n\n")
        f.write(f"- folders={len(results)}\n")
        f.write(f"- total_input_files={sum(r['total'] for r in results)}\n")
        f.write(f"- total_clean_files={sum(r['clean'] for r in results)}\n")
        f.write(f"- total_quarantine_files={sum(r['quarantine'] for r in results)}\n")
        f.write(f"- total_skipped_files={sum(r['skipped'] for r in results)}\n")
        f.write(f"- total_exceptions={total_exceptions}\n")

        f.write("\n## Quality Gate\n\n")
        f.write(f"- hard_fail_count={len(hard_fail_issues)}\n")
        f.write(f"- report_only_count={len(report_only_issues)}\n")
        f.write(f"- verdict={'FAIL' if hard_fail_issues else 'PASS'}\n")
        if hard_fail_issues:
            f.write("- hard_fail_issues:\n")
            for issue in hard_fail_issues:
                f.write(f"  - {json.dumps(issue, ensure_ascii=False)}\n")
        if report_only_issues:
            f.write("- report_only_issues:\n")
            for issue in report_only_issues:
                f.write(f"  - {json.dumps(issue, ensure_ascii=False)}\n")

        dedup_urls_total = int(LINK_RUNTIME_STATS.get('url_deduped_within_file', 0) + LINK_RUNTIME_STATS.get('url_cache_hits', 0))
        f.write("\n## Link Enrichment / Dedup Stats\n\n")
        f.write(f"- enrichment_attempt_files={int(LINK_RUNTIME_STATS.get('enrichment_attempt_files', 0))}\n")
        f.write(f"- enrichment_applied_files={int(LINK_RUNTIME_STATS.get('enrichment_applied_files', 0))}\n")
        f.write(f"- enrichment_promoted_files={int(LINK_RUNTIME_STATS.get('enrichment_promoted_files', 0))}\n")
        f.write(f"- enrichment_still_quarantined_files={int(LINK_RUNTIME_STATS.get('enrichment_still_quarantined_files', 0))}\n")
        f.write(f"- url_raw_extracted_total={int(LINK_RUNTIME_STATS.get('url_raw_extracted_total', 0))}\n")
        f.write(f"- url_canonical_total={int(LINK_RUNTIME_STATS.get('url_canonical_total', 0))}\n")
        f.write(f"- url_deduped_within_file={int(LINK_RUNTIME_STATS.get('url_deduped_within_file', 0))}\n")
        f.write(f"- url_cache_hits={int(LINK_RUNTIME_STATS.get('url_cache_hits', 0))}\n")
        f.write(f"- deduped_url_total={dedup_urls_total}\n")
        f.write(f"- url_fetch_success={int(LINK_RUNTIME_STATS.get('url_fetch_success', 0))}\n")
        f.write(f"- url_fetch_failure={int(LINK_RUNTIME_STATS.get('url_fetch_failure', 0))}\n")
        f.write(f"- url_disallowed={int(LINK_RUNTIME_STATS.get('url_disallowed', 0))}\n")
        f.write(f"- content_fingerprint_dedup={int(LINK_RUNTIME_STATS.get('content_fingerprint_dedup', 0))}\n")
        f.write("\n## Reason / Filter / Quarantine Taxonomy\n\n")
        f.write("- reason_filter_taxonomy:\n")
        for name, meta in reason_taxonomy['reason_filter_taxonomy'].items():
            f.write(f"  - {name}: {meta['description']}\n")
            if meta.get('includes'):
                f.write(f"    - includes: {', '.join(meta['includes'])}\n")
            if meta.get('reasons'):
                f.write(f"    - reasons: {', '.join(meta['reasons'])}\n")
        f.write("- quarantine_reason_groups:\n")
        for category, reasons in reason_taxonomy['quarantine_reason_groups'].items():
            f.write(f"  - {category}: {', '.join(reasons)}\n")
        f.write("- normalizable_clean_transforms: " + ', '.join(reason_taxonomy['normalizable_clean_transforms']) + "\n")
        f.write("- report_issue_filters.warn: " + ', '.join(reason_taxonomy['report_issue_filters']['warn']) + "\n")
        f.write("- report_issue_filters.fail: " + ', '.join(reason_taxonomy['report_issue_filters']['fail']) + "\n")
        f.write("\n## Corpus-level Qualitative Dedup\n\n")
        f.write(f"- bootstrap_files={int(corpus_dedup_registry.get('bootstrap_files', 0))}\n")
        f.write(f"- bootstrap_records={int(corpus_dedup_registry.get('bootstrap_records', 0))}\n")
        f.write(f"- registered_items={int(corpus_dedup_registry.get('registered_items', 0))}\n")
        f.write(f"- duplicate_items={int(corpus_dedup_registry.get('duplicate_items', 0))}\n")
        for rule in reason_taxonomy['corpus_dedup_rules']:
            f.write(f"- dedup_rule[{rule['name']}] => {rule['duplicate_reason']} ({rule['description']})\n")

    dedup_urls_total = int(LINK_RUNTIME_STATS.get('url_deduped_within_file', 0) + LINK_RUNTIME_STATS.get('url_cache_hits', 0))

    payload = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stage2_rule_version': STAGE2_RULE_VERSION,
        'run_mode': run_mode,
        'processed_index_policy': 'reset' if force_rebuild else 'reuse_if_signature_matches',
        'incremental_signature': {
            'salt': STAGE2_RULE_VERSION,
            'config_bundle_sha1': STAGE2_CONFIG_PROVENANCE['bundle_sha1'],
            'link_enrichment_enabled': STAGE2_ENABLE_LINK_ENRICHMENT,
            'strategy': 'size+mtime+path+rule_version+config_bundle_sha1+link_enrichment_flag',
        },
        'config_provenance': STAGE2_CONFIG_PROVENANCE,
        'clean_base': final_clean_base,
        'quarantine_base': final_q_base,
        'writer_policy': {
            'market_signal_canonical_writer': 'stage02_onepass_refine_full.py',
            'qualitative_canonical_writer': 'stage02_onepass_refine_full.py',
            'kr_us_signal_canonical_writer': 'stage02_qc_cleaning_full.py',
        },
        'output_policy': {
            'canonical': 'production/(signal|qualitative)/*',
            'aliases_in_canonical': FOLDER_ALIAS,
        },
        'quality_gate': {
            'verdict': 'FAIL' if hard_fail_issues else 'PASS',
            'hard_fail_count': int(len(hard_fail_issues)),
            'report_only_count': int(len(report_only_issues)),
            'hard_fail_issues': hard_fail_issues,
            'report_only_issues': report_only_issues,
            'taxonomy': {
                'warn_report_issue_types': reason_taxonomy['report_issue_filters']['warn'],
                'fail_report_issue_types': reason_taxonomy['report_issue_filters']['fail'],
            },
        },
        'results': results,
        'totals': {
            'folders': len(results),
            'total_input_files': int(sum(r['total'] for r in results)),
            'total_clean_files': int(sum(r['clean'] for r in results)),
            'total_quarantine_files': int(sum(r['quarantine'] for r in results)),
            'total_skipped_files': int(sum(r['skipped'] for r in results)),
            'total_exceptions': int(total_exceptions),
        },
        'link_enrichment': {
            'enabled': STAGE2_ENABLE_LINK_ENRICHMENT,
            **{k: int(v) for k, v in LINK_RUNTIME_STATS.items()},
            'deduped_url_total': dedup_urls_total,
        },
        'reason_taxonomy': reason_taxonomy,
        'corpus_dedup': {
            'bootstrap_files': int(corpus_dedup_registry.get('bootstrap_files', 0)),
            'bootstrap_records': int(corpus_dedup_registry.get('bootstrap_records', 0)),
            'registered_items': int(corpus_dedup_registry.get('registered_items', 0)),
            'duplicate_items': int(corpus_dedup_registry.get('duplicate_items', 0)),
            'rules': [rule['name'] for rule in reason_taxonomy['corpus_dedup_rules']],
            'rule_reason_map': {
                rule['name']: rule['duplicate_reason'] for rule in reason_taxonomy['corpus_dedup_rules']
            },
            'scope': sorted(DEDUP_TARGET_FOLDERS),
        },
    }

    LINK_RUNTIME_STATS['corpus_dedup_registered_items'] = int(corpus_dedup_registry.get('registered_items', 0))
    LINK_RUNTIME_STATS['corpus_dedup_duplicate_items'] = int(corpus_dedup_registry.get('duplicate_items', 0))
    LINK_RUNTIME_STATS['corpus_dedup_bootstrap_files'] = int(corpus_dedup_registry.get('bootstrap_files', 0))
    LINK_RUNTIME_STATS['corpus_dedup_bootstrap_records'] = int(corpus_dedup_registry.get('bootstrap_records', 0))

    with open(report_json_path, 'w', encoding='utf-8') as jf:
        json.dump(payload, jf, ensure_ascii=False, indent=2)

    _save_processed_index(processed_index)
    print(f"Full refinement report: {report_path}")
    print(f"Full refinement report json: {report_json_path}")
    if hard_fail_issues:
        raise SystemExit(1)
    return report_path, report_json_path


def _parse_args():
    parser = argparse.ArgumentParser(description='Stage2 full refine runner')
    parser.add_argument(
        '--force-rebuild', '--full-rerun',
        dest='force_rebuild',
        action='store_true',
        help='Ignore incremental processed_index, reset canonical clean/quarantine outputs, and rebuild from upstream Stage1 inputs.',
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_full_refine(force_rebuild=args.force_rebuild)
