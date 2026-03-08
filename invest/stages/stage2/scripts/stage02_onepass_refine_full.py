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
STAGE2_RULE_VERSION = 'stage2-refine-20260308'
STAGE2_ENABLE_LINK_ENRICHMENT = os.environ.get('STAGE2_ENABLE_LINK_ENRICHMENT', '0').strip().lower() in ('1', 'true', 'yes')
FOLDERS = [
    'kr/dart',
    'market/news/rss', 'market/macro', 'market/google_trends',
    'text/blog', 'text/telegram', 'text/image_map', 'text/images_ocr', 'text/premium/startale'
]
REQUIRED_REFINE_FOLDERS = {
    'kr/dart',
    'market/news/rss',
    'text/blog',
    'text/telegram',
    'text/image_map',
    'text/premium/startale',
}

# Stage2 clean/quarantine canonical output track
SIGNAL_FOLDERS = {
    'kr/ohlcv', 'kr/supply', 'us/ohlcv', 'market/macro', 'market/google_trends'
}
QUALITATIVE_FOLDERS = {
    'kr/dart', 'market/news/rss', 'market/rss',
    'text/blog', 'text/telegram', 'text/image_map', 'text/images_ocr', 'text/premium/startale'
}

# raw/output 경로 alias 정합성
FOLDER_ALIAS = {
    'market/news/rss': 'market/rss',
}

BLOG_UI_MARKERS = {
    '본문 바로가기', '카테고리 이동', '검색', 'my메뉴 열기', '메뉴 바로가기', '이 블로그',
}
PREMIUM_BOILERPLATE_MARKERS = {
    'disclaimer', '본 포스팅에 수록된 내용은', '매수/매도 추천', '투자 결과에 대한 법적 책임소재',
    '별도의 투자 상담', '구독자 여러분 스스로 공부',
}

# 텍스트 정제 최소 길이(의미 있는 단문을 과도 격리하지 않도록 완화)
BLOG_MIN_EFFECTIVE_LEN = 80
TELEGRAM_MIN_EFFECTIVE_LEN = 60
PREMIUM_MIN_EFFECTIVE_LEN = 100
IMAGES_OCR_MIN_EFFECTIVE_LEN = 50
SHORT_MEANINGFUL_MIN_LEN = 45

TARGET_LINK_ENRICH_FOLDERS = {
    'text/blog',
    'text/telegram',
    'text/premium/startale',
    'text/images_ocr',
}

URL_PATTERN = re.compile(r'https?://[^\s<>()\[\]{}"\']+', flags=re.IGNORECASE)
ATTACH_TEXT_BLOCK_RE = re.compile(r'(?is)\[ATTACH_TEXT\]\s*(.*?)\s*\[/ATTACH_TEXT\]')
TRACKING_QUERY_PREFIXES = (
    'utm_', 'fbclid', 'gclid', 'igshid', 'mc_cid', 'mc_eid', 'spm', 'ref', 'ref_src',
)
ALLOWED_LINK_DOMAIN_SUFFIXES = (
    'naver.com',
    'telegra.ph',
    't.me',
    'medium.com',
    'coindesk.com',
    'cointelegraph.com',
    'theblock.co',
    'bloomberg.com',
    'reuters.com',
    'cnbc.com',
    'marketwatch.com',
    'investing.com',
    'yahoo.com',
    'yna.co.kr',
    'yonhapnews.co.kr',
    'hankyung.com',
    'mk.co.kr',
    'sedaily.com',
    'edaily.co.kr',
    'fnnews.com',
    'newsis.com',
    'chosun.com',
    'joongang.co.kr',
    'donga.com',
    'khan.co.kr',
    'hani.co.kr',
)
# allowlist 확장 모드(기본 ON): 뉴스/리포트 링크 누락 최소화
LINK_ENRICH_ALLOW_ALL_DOMAINS = os.environ.get('LINK_ENRICH_ALLOW_ALL_DOMAINS', '1').strip().lower() in ('1', 'true', 'yes')
BLOCKED_LINK_DOMAIN_SUFFIXES = (
    'telegram.org', 'web.telegram.org',
    'facebook.com', 'instagram.com', 'x.com', 'twitter.com',
)

LINK_FETCH_TIMEOUT_SEC = 6
LINK_FETCH_MAX_RETRIES = 3
LINK_FETCH_BACKOFF_BASE_SEC = 0.7
LINK_FETCH_MAX_BYTES = 350_000
LINK_FETCH_MAX_TEXT_CHARS = 3_000
LINK_ENRICH_MAX_URLS_PER_FILE = 12
LINK_ENRICH_MAX_TOTAL_CHARS = 4000
LINK_ENRICH_MIN_EFFECTIVE_ADD = 50

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
    key = f"{STAGE2_RULE_VERSION}:{int(STAGE2_ENABLE_LINK_ENRICHMENT)}:{st.st_size}:{int(st.st_mtime)}:{path}".encode('utf-8')
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


def _merge_effective_with_attach(effective: str, content: str) -> str:
    attach = _text_without_urls(_extract_attach_text(content))
    if not attach:
        return (effective or '').strip()
    base = (effective or '').strip()
    if not base:
        return attach
    return f"{base}\n{attach}"


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


def _collect_unique_enrichment_blocks(canonical_urls: list[str], base_effective: str) -> tuple[list[tuple[str, str]], int]:
    seen_fp = set()
    if base_effective.strip():
        seen_fp.add(_fingerprint(base_effective))

    blocks = []
    content_dup_count = 0
    total_chars = 0

    for cu in canonical_urls[:LINK_ENRICH_MAX_URLS_PER_FILE]:
        fetched_text, _ = _fetch_link_text(cu)
        if not fetched_text:
            continue

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

    return blocks, content_dup_count


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
    effective = _merge_effective_with_attach(effective, content)
    context = {
        'effective': effective,
        'min_len': BLOG_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < BLOG_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, 'blog_effective_body_too_short', context
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
    effective = _merge_effective_with_attach(effective, content)
    context = {
        'effective': effective,
        'min_len': TELEGRAM_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < TELEGRAM_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, 'telegram_effective_body_too_short', context
    return True, '', context


def _validate_images_ocr_text(content: str) -> tuple[bool, str, dict]:
    body = _extract_effective_lines(
        content,
        skip_patterns=[
            r'^#\s+', r'^(Date|Source|LinkEnriched|CanonicalURLs)\s*:', r'^---$',
            r'^Post(ID|Date|DateTime)?\s*:', r'^MessageID\s*:\s*\d+',
            r'^Forwarded from\s*:',
        ],
    )
    effective = _text_without_urls(body)
    effective = _merge_effective_with_attach(effective, content)
    context = {
        'effective': effective,
        'min_len': IMAGES_OCR_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < IMAGES_OCR_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, 'images_ocr_effective_body_too_short', context
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
    effective = _merge_effective_with_attach(effective, content)
    context = {
        'effective': effective,
        'min_len': PREMIUM_MIN_EFFECTIVE_LEN,
    }
    if len(effective) < PREMIUM_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        return False, 'premium_effective_body_too_short_or_boilerplate', context

    return True, '', context


def _validate_text_by_folder(content: str, normalized_folder: str) -> tuple[bool, str, dict]:
    if normalized_folder == 'text/blog':
        return _validate_blog_text(content)
    if normalized_folder == 'text/telegram':
        return _validate_telegram_text(content)
    if normalized_folder == 'text/images_ocr':
        return _validate_images_ocr_text(content)
    if normalized_folder == 'text/premium/startale':
        return _validate_premium_text(content)
    return True, '', {}


def _is_short_reason(reason: str) -> bool:
    return reason in {
        'blog_effective_body_too_short',
        'telegram_effective_body_too_short',
        'images_ocr_effective_body_too_short',
        'premium_effective_body_too_short_or_boilerplate',
    }


def sanitize_text(path: str, folder: str = ''):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        raw_trim = (content or '').strip()
        if len(raw_trim) < 10:
            return None, 'text_too_short', {}

        attach_text = _extract_attach_text(content)
        if attach_text:
            LINK_RUNTIME_STATS['attachment_blocks_seen'] += 1
            LINK_RUNTIME_STATS['attachment_text_chars_total'] += len(attach_text)

        normalized_folder = _normalize_folder(folder)
        ok, reason, ctx = _validate_text_by_folder(content, normalized_folder)
        if ok:
            return content, None, {'link_enriched': False, 'canonical_urls': 0}

        if not STAGE2_ENABLE_LINK_ENRICHMENT:
            return None, reason, {'link_enriched': False, 'link_enrichment_enabled': False}

        if normalized_folder not in TARGET_LINK_ENRICH_FOLDERS or not _is_short_reason(reason):
            return None, reason, {}

        link_source_text = _build_link_source_text(content, attach_text)
        raw_urls = _extract_urls(link_source_text)
        LINK_RUNTIME_STATS['url_raw_extracted_total'] += len(raw_urls)
        canonical_urls, deduped = _canonical_dedup_urls(raw_urls)
        LINK_RUNTIME_STATS['url_canonical_total'] += len(canonical_urls)
        LINK_RUNTIME_STATS['url_deduped_within_file'] += deduped

        if not _needs_link_enrichment(content, ctx.get('effective', ''), int(ctx.get('min_len', 0)), len(canonical_urls)):
            return None, reason, {}

        LINK_RUNTIME_STATS['enrichment_attempt_files'] += 1
        blocks, content_dup_count = _collect_unique_enrichment_blocks(canonical_urls, ctx.get('effective', ''))
        LINK_RUNTIME_STATS['content_fingerprint_dedup'] += content_dup_count
        if not blocks:
            LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
            return None, reason, {}

        enriched_content = _inject_enriched_content(content, normalized_folder, blocks, canonical_urls)
        ok2, reason2, _ = _validate_text_by_folder(enriched_content, normalized_folder)
        if ok2:
            LINK_RUNTIME_STATS['enrichment_applied_files'] += 1
            LINK_RUNTIME_STATS['enrichment_promoted_files'] += 1
            return enriched_content, None, {
                'link_enriched': True,
                'canonical_urls': len(canonical_urls),
                'enriched_blocks': len(blocks),
            }

        LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
        return None, reason2, {}
    except Exception as e:
        return None, str(e), {}


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


def _validate_image_map_json(data) -> tuple[bool, str]:
    items = []
    if isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        if isinstance(data.get('items'), list):
            items = [x for x in data.get('items', []) if isinstance(x, dict)]
        else:
            items = [data]

    if not items:
        return False, 'image_map_no_items'

    valid = 0
    for it in items:
        lk = {str(k).strip().lower(): v for k, v in it.items()}
        has_url = any(str(lk.get(k, '')).strip() for k in ('url', 'image_url', 'link'))
        has_source = any(str(lk.get(k, '')).strip() for k in ('source', 'source_path', 'source_file'))
        if has_url and has_source:
            valid += 1

    if valid <= 0:
        return False, 'image_map_missing_required_fields(url/source)'

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
        elif normalized_folder == 'text/image_map':
            ok, reason = _validate_image_map_json(data)
            if not ok:
                return None, reason

        return data, None
    except Exception as e:
        return None, str(e)


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


def _build_text_quarantine_payload(folder: str, source_file: str, reason: str, raw_text: str) -> str:
    reason = (reason or 'invalid_text').strip()
    meta_lines = _extract_quarantine_meta_lines(raw_text)
    preview = _extract_quarantine_preview(raw_text)

    buf = []
    buf.append(f'reason: {reason}')
    buf.append(f'folder: {folder}')
    buf.append(f'source_file: {source_file}')
    buf.append(f'sanitized_at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    buf.append(f'stage2_rule_version: {STAGE2_RULE_VERSION}')
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

    for folder in FOLDERS:
        raw_dir = _resolve_raw_dir(folder)
        if not os.path.exists(raw_dir):
            issue = {
                'type': 'missing_input_folder',
                'folder': folder,
                'path': raw_dir,
            }
            if folder in REQUIRED_REFINE_FOLDERS:
                hard_fail_issues.append(issue)
            else:
                report_only_issues.append(issue)
            continue

        all_files = []
        for ext in ['*.csv', '*.json', '*.md', '*.txt']:
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
                else:
                    content, err, _meta = sanitize_text(f, folder=folder)
                    if content is not None:
                        _write_text(content, clean_paths)
                        for p in q_paths:
                            _remove_if_exists(p)
                        clean_count += 1
                    else:
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

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Full Refinement Report\n\n")
        f.write(f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Rule Version: {STAGE2_RULE_VERSION}\n")
        f.write(f"- Run Mode: {run_mode}\n")
        f.write(f"- Processed Index: {'reset' if force_rebuild else 'reuse_if_signature_matches'}\n")
        f.write(f"- Incremental Signature Salt: {STAGE2_RULE_VERSION}\n")
        f.write(f"- Clean Base: {final_clean_base}\n")
        f.write(f"- Quarantine Base: {final_q_base}\n")
        f.write("- Writer policy: signal/qualitative canonical writer=`stage02_onepass_refine_full.py`, `stage02_qc_cleaning_full.py`=`validation_only`\n")
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

    dedup_urls_total = int(LINK_RUNTIME_STATS.get('url_deduped_within_file', 0) + LINK_RUNTIME_STATS.get('url_cache_hits', 0))

    payload = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stage2_rule_version': STAGE2_RULE_VERSION,
        'run_mode': run_mode,
        'processed_index_policy': 'reset' if force_rebuild else 'reuse_if_signature_matches',
        'incremental_signature': {
            'salt': STAGE2_RULE_VERSION,
            'link_enrichment_enabled': STAGE2_ENABLE_LINK_ENRICHMENT,
            'strategy': 'size+mtime+path+rule_version+link_enrichment_flag',
        },
        'clean_base': final_clean_base,
        'quarantine_base': final_q_base,
        'writer_policy': {
            'signal_canonical_writer': 'stage02_onepass_refine_full.py',
            'qualitative_canonical_writer': 'stage02_onepass_refine_full.py',
            'stage02_qc_cleaning_full.py': 'validation_only',
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
    }

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
