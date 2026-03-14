from __future__ import annotations

import argparse
import os
import sys
import glob
import pandas as pd
import json
import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

MACOS_SWIFT_BIN = '/usr/bin/swift'
SWIFT_PDFKIT_EXTRACT_SCRIPT = r'''
import Foundation
import PDFKit

let args = CommandLine.arguments

guard args.count >= 3 else {
    fputs("usage: pdf_extract.swift <pdf_path> <max_pages>\n", stderr)
    exit(64)
}

let pdfPath = args[1]
let maxPages = max(1, Int(args[2]) ?? 1)
guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
    fputs("open_failed\n", stderr)
    exit(65)
}

var chunks: [String] = []
let upper = min(doc.pageCount, maxPages)
if upper > 0 {
    for idx in 0..<upper {
        if let page = doc.page(at: idx) {
            let text = (page.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                chunks.append(text)
            }
        }
    }
}

FileHandle.standardOutput.write((chunks.joined(separator: "\n\n")).data(using: .utf8) ?? Data())
'''

ROOT_PATH = Path(__file__).resolve().parents[4]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from stage2_config import load_stage2_config_bundle

# TODO(refactor-phase2): move core refine logic into invest.pipeline modules (behavior-preserving migration).
try:
    import invest.pipeline  # noqa: F401
except Exception:
    # import 준비용: 현재 동작 영향 0 유지
    pass

try:
    from invest.stages.common.stage_raw_db import (
        DEFAULT_DB_PATH as DEFAULT_STAGE1_RAW_DB_PATH,
        prepare_stage2_raw_input_root,
        stage2_default_prefixes,
    )
except Exception:
    DEFAULT_STAGE1_RAW_DB_PATH = None
    prepare_stage2_raw_input_root = None
    stage2_default_prefixes = None

# Configuration (stage-local input boundary)
STAGE2_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM_STAGE1 = os.path.join(STAGE2_ROOT, 'inputs', 'upstream_stage1')
_RAW_BASE_FALLBACK = os.path.join(UPSTREAM_STAGE1, 'raw')
_STAGE1_RAW_DB_PATH = os.environ.get(
    'STAGE1_RAW_DB_PATH',
    str(DEFAULT_STAGE1_RAW_DB_PATH) if DEFAULT_STAGE1_RAW_DB_PATH is not None else '',
).strip()
_STAGE2_DB_MIRROR_ROOT = os.environ.get(
    'STAGE2_DB_MIRROR_ROOT',
    os.path.join(STAGE2_ROOT, 'outputs', 'runtime', 'upstream_stage1_db_mirror'),
).strip()
_DB_PREFIXES = stage2_default_prefixes() if stage2_default_prefixes is not None else []
STAGE2_ALLOW_RAW_FILES_FALLBACK = os.environ.get(
    'STAGE2_ALLOW_RAW_FILES_FALLBACK',
    '0',
).strip().lower() in ('1', 'true', 'yes', 'on')
RAW_BASE = (
    prepare_stage2_raw_input_root(
        db_path=_STAGE1_RAW_DB_PATH,
        mirror_root=_STAGE2_DB_MIRROR_ROOT,
        prefixes=_DB_PREFIXES,
    )
    if prepare_stage2_raw_input_root is not None and _STAGE1_RAW_DB_PATH
    else ''
) or _RAW_BASE_FALLBACK
STAGE2_INPUT_SOURCE = 'stage1_raw_db_mirror' if RAW_BASE != _RAW_BASE_FALLBACK else 'stage1_raw_files'
if STAGE2_INPUT_SOURCE == 'stage1_raw_db_mirror':
    STAGE2_INPUT_SOURCE_STATUS = 'ok'
    STAGE2_FALLBACK_REASON = 'none'
    STAGE2_FALLBACK_SCOPE = 'none'
elif STAGE2_ALLOW_RAW_FILES_FALLBACK:
    STAGE2_INPUT_SOURCE_STATUS = 'degraded_raw_files_fallback_opt_in'
    STAGE2_FALLBACK_REASON = 'stage1_raw_db_mirror_unavailable'
    STAGE2_FALLBACK_SCOPE = 'stage2_raw_input_boundary'
else:
    STAGE2_INPUT_SOURCE_STATUS = 'blocked_raw_files_fallback_opt_in_required'
    STAGE2_FALLBACK_REASON = 'stage1_raw_db_mirror_unavailable'
    STAGE2_FALLBACK_SCOPE = 'stage2_raw_input_boundary'
CLEAN_BASE = os.path.join(STAGE2_ROOT, 'outputs', 'clean')
# Stage2가 유일한 검역(quarantine) 저장 단계다. Stage1은 raw/상태 파일만 저장한다.
Q_BASE = os.path.join(STAGE2_ROOT, 'outputs', 'quarantine')
REPORT_DIR = os.path.join(STAGE2_ROOT, 'outputs', 'reports', 'qc')
RUNTIME_DIR = os.path.join(STAGE2_ROOT, 'outputs', 'runtime')
INTEGRITY_SUMMARY_PATH = os.path.join(RUNTIME_DIR, 'stage2_integrity_summary.json')
STAGE1_ROOT = os.path.join(os.path.dirname(STAGE2_ROOT), 'stage1')
STAGE1_CHECKPOINT_STATUS_PATH = os.path.join(STAGE1_ROOT, 'outputs', 'reports', 'data_quality', 'stage01_checkpoint_status.json')
STAGE1_SOURCE_COVERAGE_PATH = os.path.join(STAGE1_ROOT, 'outputs', 'raw', 'source_coverage_index.json')
STAGE1_ATTACHMENT_RECOVERY_SUMMARY_PATH = os.path.join(STAGE1_ROOT, 'outputs', 'runtime', 'stage1_attachment_recovery_summary.json')
MASTER_LIST_PATH = os.path.join(UPSTREAM_STAGE1, 'master', 'kr_stock_list.csv')
STAGE2_RULE_VERSION = 'stage2-refine-20260311-r6'
CLASSIFICATION_VERSION = 'stage2-classify-20260311-r5'
SEMANTIC_SCHEMA_VERSION = 'stage-semantic-20260311-r4'
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
STAGE2_ENABLE_LINK_ENRICHMENT = os.environ.get(
    'STAGE2_ENABLE_LINK_ENRICHMENT',
    '1' if LINK_ENRICHMENT_CONFIG.get('enabled_default', True) else '0',
).strip().lower() in ('1', 'true', 'yes')
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
TELEGRAM_ATTACH_ROOT = os.path.join(RAW_BASE, 'qualitative', 'attachments', 'telegram')
LINK_SIDECAR_ROOT = os.path.join(RAW_BASE, 'qualitative', 'link_enrichment')
TELEGRAM_ATTACH_BUCKET_COUNT = max(1, int(os.environ.get('TELEGRAM_ATTACH_BUCKET_COUNT', '128')))
STAGE2_ENABLE_LIVE_LINK_FETCH = os.environ.get('STAGE2_ENABLE_LIVE_LINK_FETCH', '0').strip().lower() in ('1', 'true', 'yes')
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
        'stage1_sidecar_seen_files': 0,
        'stage1_sidecar_canonical_urls_total': 0,
        'stage1_sidecar_promoted_files': 0,
        'stage1_sidecar_dedup_signal_files': 0,
        'attachment_blocks_seen': 0,
        'attachment_text_chars_total': 0,
        'telegram_pdf_total': 0,
        'telegram_pdf_stage1_extract_reused': 0,
        'telegram_pdf_stage2_extract_ok': 0,
        'telegram_pdf_extract_failed': 0,
        'telegram_pdf_messages_promoted_by_pdf': 0,
        'telegram_pdf_chars_added_total': 0,
        'telegram_pdf_path_resolution_marker': 0,
        'telegram_pdf_path_resolution_fallback': 0,
        'telegram_pdf_orphan_artifacts': 0,
        'telegram_pdf_status_promoted': 0,
        'telegram_pdf_status_bounded_by_cap': 0,
        'telegram_pdf_status_recoverable_missing_artifact': 0,
        'telegram_pdf_status_extractor_unavailable': 0,
        'telegram_pdf_status_parse_failed': 0,
        'telegram_pdf_status_placeholder_only': 0,
        'telegram_pdf_status_lineage_mismatch': 0,
        'telegram_pdf_status_diagnostics_only': 0,
        'telegram_pdf_declared_page_count_total': 0,
        'telegram_pdf_indexed_page_rows_total': 0,
        'telegram_pdf_materialized_text_pages_total': 0,
        'telegram_pdf_materialized_render_pages_total': 0,
        'telegram_pdf_placeholder_page_rows_total': 0,
        'telegram_pdf_bounded_by_cap_total': 0,
        'telegram_pdf_bounded_by_cap_docs': 0,
        'telegram_pdf_bounded_pages_total': 0,
        'telegram_pdf_join_strategy_canonical_marker': 0,
        'telegram_pdf_join_strategy_canonical_flat': 0,
        'telegram_pdf_join_strategy_legacy_dir': 0,
        'telegram_pdf_join_strategy_recovered_local_extract': 0,
        'telegram_pdf_join_confidence_strong': 0,
        'telegram_pdf_join_confidence_medium': 0,
        'telegram_pdf_join_confidence_weak': 0,
        'telegram_pdf_lineage_status_confirmed': 0,
        'telegram_pdf_lineage_status_probable': 0,
        'telegram_pdf_lineage_status_unresolved': 0,
        'corpus_dedup_registered_items': 0,
        'corpus_dedup_duplicate_items': 0,
        'corpus_dedup_bootstrap_files': 0,
        'corpus_dedup_bootstrap_records': 0,
    }


LINK_FETCH_CACHE: dict[str, dict] = {}
LINK_RUNTIME_STATS: dict = _new_link_runtime_stats()
CLASSIFICATION_RUNTIME_STATS: dict[str, int] = {
    'documents_classified': 0,
    'documents_with_stock': 0,
    'documents_with_industry': 0,
    'selected_articles_rows_classified': 0,
}

INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    '반도체': ('반도체', '메모리', 'dram', 'nand', '낸드', 'hbm', '파운드리'),
    '자동차': ('자동차', '완성차', 'ev', '전기차', '하이브리드', '차량용'),
    '2차전지': ('2차전지', '배터리', '양극재', '음극재', '전해액', 'lfp'),
    '바이오/헬스케어': ('바이오', '헬스케어', '의약', '제약', '임상', '의료기기'),
    '인터넷/플랫폼': ('플랫폼', '인터넷', '커머스', '포털', '핀테크'),
    '게임/콘텐츠': ('게임', '콘텐츠', '엔터', '드라마', '웹툰', '음원'),
    '조선/해운': ('조선', '해운', '선박', 'lng선', '수주잔고'),
    '방산/우주': ('방산', '국방', '우주', '위성', '미사일', '항공우주'),
    '철강/소재': ('철강', '소재', '알루미늄', '구리', '니켈', '희토류'),
    '정유/화학': ('정유', '화학', '석유화학', '납사', '에틸렌', '정제마진'),
    '은행/금융': (
        '금융', '금감원', '금융위', '금융위원회', '금융당국', '뱅크',
        '보험사', '증권사', '투자증권', '카드사', '여신', 'npl',
        '자산운용', '운용사', '연금', '기금운용', '의결권', '주주활동', '자사주',
        'etf', '상장지수펀드', '펀드',
    ),
    '건설/부동산': ('건설', '부동산', '분양', '재건축', 'pf', '플랜트'),
    '통신/네트워크': ('통신', '네트워크', '5g', '통신장비', '가입자'),
    '유통/소비재': ('유통', '소비재', '면세', '리테일', '백화점', '편의점'),
    '전력/유틸리티': ('전력', '유틸리티', '원전', '태양광', '풍력', '송배전'),
}
INDUSTRY_MIN_SCORE: dict[str, int] = {
    '은행/금융': 2,
}
INDUSTRY_STRONG_KEYWORDS: dict[str, tuple[str, ...]] = {
    '은행/금융': (
        '금융', '금감원', '금융위', '금융위원회', '금융당국', '뱅크',
        '자산운용', '운용사', '연금', '기금운용', '의결권', '주주활동', '자사주',
        'etf', '상장지수펀드',
    ),
}
EVENT_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    'order': ('수주', '공급계약', '단일판매', '계약체결', '수주계약', '판매계약', 'order', 'contract'),
    'rights_issue': ('유상증자', '증자', '전환사채', 'cb', 'bw', '신주발행', '희석', 'rights issue', 'dilution'),
    'lawsuit': ('소송', '피소', '판결', '항소', '가처분', '분쟁', 'lawsuit', 'litigation', 'dispute'),
    'guidance': ('가이던스', '실적전망', '전망치', '컨센서스', '잠정실적', '실적발표', 'guidance', 'earnings'),
}
MACRO_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    'risk_on': ('금리인하', '금리 인하', '랠리', 'risk-on', 'risk on', 'soft landing', 'stimulus', 'easing'),
    'risk_off': ('긴축', '인상', '침체', '전쟁', '관세', '리스크오프', 'risk-off', 'risk off', 'recession', 'conflict', 'sanction'),
    'rates': ('금리', '기준금리', 'fed', 'fomc', 'ecb', 'boj', 'yield', '국채', '채권수익률'),
    'inflation': ('인플레이션', 'cpi', 'ppi', '물가', 'inflation'),
    'fx': ('환율', '환전', '원/달러', '원달러', '엔화', 'dxy', 'fx', '외환', 'usdkrw'),
    'liquidity': ('유동성', '양적완화', '양적긴축', 'qe', 'qt', 'liquidity'),
    'policy': (
        '정책', '재정', '부양책', 'stimulus', 'regulation', '규제', '관세', '제재',
        '금융위', '금융위원회', '금감원', '금융감독원', '보건복지부', '산업통상부', '산업부',
        '육성 방안', '기금운용위원회', '자본시장', '기관투자자',
    ),
    'energy': ('국제유가', '유가 상승', '유가 하락', 'wti', 'brent', '원유', '천연가스', 'lng'),
    'recession_growth': ('침체', 'recession', '성장률', 'gdp', '경기', 'soft landing', '둔화'),
    'geopolitics': ('전쟁', '분쟁', '중동', '러시아', '우크라이나', 'iran', '이란', 'china', 'taiwan', '제재', '무력 충돌'),
}
REGION_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    'kr': ('한국', '국내', 'korea', 'kospi', 'kosdaq', 'krx', 'krw', '원/달러'),
    'us': ('미국', '연준', 'fed', 'fomc', 'nasdaq', 's&p', 'dow', 'qqq', 'spy', 'treasury', 'dxy', 'usa'),
    'cn': ('중국', 'china', '위안', 'csi300', '상하이', '홍콩'),
    'jp': ('일본', 'japan', 'boj', '닛케이', 'nikkei'),
    'eu': ('유럽', 'eurozone', 'ecb', '독일', '프랑스', 'france', 'italy'),
    'global': ('글로벌', 'global', 'world', '해외', '국제'),
}
SHORT_HORIZON_KEYWORDS = ('오늘', '당일', '즉시', '단기', '이번주', '이번 달', '이번달', 'near-term', 'short-term', '1-5d')
MEDIUM_HORIZON_KEYWORDS = ('분기', '이번 분기', '연내', '상반기', '하반기', '6개월', 'quarter', 'half-year', 'medium-term')
LONG_HORIZON_KEYWORDS = ('장기', '중장기', '구조적', '연간', '다년', 'pipeline', 'recurring', 'long-term', 'backlog')
POSITIVE_DIRECTION_WORDS = {
    '성장', '개선', '확대', '수주', '계약', '흑자', '상향', '반등', '증가', '회복', '신제품', '점유율', '가이던스', '성공', '강세',
    'growth', 'improve', 'expand', 'order', 'beat', 'upgrade', 'strong', 'recovery', 'guidance', 'launch',
    '인하', '랠리', 'risk-on', 'risk on', 'soft landing', 'stimulus', 'easing',
}
NEGATIVE_DIRECTION_WORDS = {
    '감소', '부진', '하락', '적자', '둔화', '악화', '소송', '분쟁', '유상증자', '리스크', '규제', '지연', '차질', '정정', '우려',
    'decline', 'weak', 'drop', 'loss', 'lawsuit', 'dispute', 'dilution', 'downgrade', 'risk', 'regulation', 'delay', 'concern',
    '긴축', '인상', '침체', '전쟁', '관세', '리스크오프', 'risk-off', 'risk off', 'recession', 'conflict', 'sanction',
}

_STOCK_REF_LOADED = False
STOCK_NAME_TO_ENTRY: dict[str, dict] = {}
STOCK_CODE_TO_ENTRY: dict[str, dict] = {}
STOCK_NAME_PATTERN: re.Pattern[str] | None = None
TOKEN_CHAR_RE = re.compile(r'[0-9A-Za-z가-힣]')
ASCII_WORD_RE = re.compile(r'(?<![0-9a-z]){keyword}(?![0-9a-z])')
KOREAN_POSTFIX_PREFIXES = tuple(
    sorted(
        {
            '은', '는', '이', '가', '을', '를', '과', '와', '도', '만', '의', '에', '엔', '에서', '에게', '께', '으로', '로',
            '부터', '까지', '처럼', '보다', '뿐', '뿐만', '이나', '나', '랑', '하고', '마다', '씩', '조차', '마저', '라도',
            '이라', '라', '이며', '이다', '이었다', '였다', '으로는', '로는', '에는', '에서의', '에서도', '에는서', '와의', '과의',
        },
        key=len,
        reverse=True,
    )
)


def _load_stock_reference() -> None:
    global _STOCK_REF_LOADED, STOCK_NAME_PATTERN
    if _STOCK_REF_LOADED:
        return
    _STOCK_REF_LOADED = True
    if not os.path.exists(MASTER_LIST_PATH):
        return
    try:
        df = pd.read_csv(MASTER_LIST_PATH)
    except Exception:
        return
    if 'Code' not in df.columns or 'Name' not in df.columns:
        return
    for row in df.itertuples(index=False):
        code = str(getattr(row, 'Code', '') or '').strip().zfill(6)
        name = str(getattr(row, 'Name', '') or '').strip()
        market = str(getattr(row, 'Market', '') or '').strip()
        if not code or not name:
            continue
        entry = {'ticker': code, 'stock_name': name, 'market': market}
        STOCK_CODE_TO_ENTRY.setdefault(code, entry)
        STOCK_NAME_TO_ENTRY.setdefault(name, entry)
    names = sorted(STOCK_NAME_TO_ENTRY.keys(), key=len, reverse=True)
    if names:
        STOCK_NAME_PATTERN = re.compile('|'.join(re.escape(name) for name in names))


def _is_token_char(ch: str) -> bool:
    return bool(ch) and bool(TOKEN_CHAR_RE.match(ch))


def _has_korean_postfix(text: str, start: int) -> bool:
    tail = text[start:start + 6]
    return any(tail.startswith(prefix) for prefix in KOREAN_POSTFIX_PREFIXES)


def _is_valid_stock_name_match(text: str, start: int, end: int) -> bool:
    if start > 0 and _is_token_char(text[start - 1]):
        return False
    if end < len(text) and _is_token_char(text[end]) and not _has_korean_postfix(text, end):
        return False
    return True


ANALYST_ATTRIBUTION_SUFFIXES = (
    ' 연구원',
    ' 수석연구원',
    ' 애널리스트',
    ' 리서치센터',
    ' 센터장',
    ' 전략가',
    ' 연구위원',
)


def _should_skip_stock_mention(text: str, start: int, end: int) -> bool:
    tail = text[end:end + 16]
    return any(tail.startswith(suffix) for suffix in ANALYST_ATTRIBUTION_SUFFIXES)


def _count_keyword_occurrences(text_l: str, keyword: str) -> int:
    normalized = str(keyword or '').strip().lower()
    if not normalized:
        return 0
    if normalized.isascii() and normalized.isalnum():
        return len(ASCII_WORD_RE.pattern) and len(re.findall(ASCII_WORD_RE.pattern.format(keyword=re.escape(normalized)), text_l))
    return text_l.count(normalized)


def _extract_stock_mentions(text: str) -> list[dict]:
    _load_stock_reference()
    raw = str(text or '').strip()
    if not raw:
        return []
    mentions: list[dict] = []
    seen: set[str] = set()
    if STOCK_NAME_PATTERN is not None:
        for match in STOCK_NAME_PATTERN.finditer(raw):
            if not _is_valid_stock_name_match(raw, match.start(), match.end()):
                continue
            if _should_skip_stock_mention(raw, match.start(), match.end()):
                continue
            entry = STOCK_NAME_TO_ENTRY.get(match.group(0))
            if not entry:
                continue
            ticker = str(entry.get('ticker') or '')
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            mentions.append(dict(entry))
    for code in re.findall(r'(?<!\d)(\d{6})(?!\d)', raw):
        entry = STOCK_CODE_TO_ENTRY.get(code)
        if not entry:
            continue
        ticker = str(entry.get('ticker') or '')
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        mentions.append(dict(entry))
    return mentions


def _extract_industry_mentions(text: str) -> list[str]:
    raw = str(text or '').strip().lower()
    if not raw:
        return []
    scored: list[tuple[str, int]] = []
    for label, keywords in INDUSTRY_KEYWORDS.items():
        score = sum(_count_keyword_occurrences(raw, str(keyword)) for keyword in keywords if keyword)
        if score <= 0:
            continue
        min_score = int(INDUSTRY_MIN_SCORE.get(label, 1))
        strong_keywords = INDUSTRY_STRONG_KEYWORDS.get(label, ())
        strong_score = sum(_count_keyword_occurrences(raw, str(keyword)) for keyword in strong_keywords if keyword)
        if score < min_score and strong_score <= 0:
            continue
        scored.append((label, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [label for label, _ in scored]


def _keyword_hit_count(text_l: str, keywords: tuple[str, ...] | set[str]) -> int:
    return sum(_count_keyword_occurrences(text_l, str(keyword)) for keyword in keywords if keyword)


def _ranked_tags_from_keywords(text: str, table: dict[str, tuple[str, ...]]) -> list[str]:
    text_l = str(text or '').lower()
    scored: list[tuple[str, int]] = []
    for tag, keywords in table.items():
        score = _keyword_hit_count(text_l, keywords)
        if score > 0:
            scored.append((tag, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [tag for tag, _ in scored]


def _infer_impact_direction(text: str, event_tags: list[str]) -> str:
    text_l = str(text or '').lower()
    pos_hits = _keyword_hit_count(text_l, POSITIVE_DIRECTION_WORDS)
    neg_hits = _keyword_hit_count(text_l, NEGATIVE_DIRECTION_WORDS)
    if 'order' in event_tags or 'guidance' in event_tags:
        pos_hits += 1
    if 'rights_issue' in event_tags or 'lawsuit' in event_tags:
        neg_hits += 1
    if pos_hits > 0 and neg_hits == 0:
        return 'positive'
    if neg_hits > 0 and pos_hits == 0:
        return 'negative'
    if pos_hits > 0 and neg_hits > 0:
        return 'mixed'
    return 'neutral'


def _infer_horizon(text: str, folder: str = '') -> str:
    text_l = str(text or '').lower()
    if any(keyword.lower() in text_l for keyword in LONG_HORIZON_KEYWORDS):
        return 'long_term'
    if any(keyword.lower() in text_l for keyword in MEDIUM_HORIZON_KEYWORDS):
        return 'medium_term'
    if any(keyword.lower() in text_l for keyword in SHORT_HORIZON_KEYWORDS):
        return 'short_term'
    if _normalize_folder(folder) == 'market/rss':
        return 'short_term'
    return 'unknown'


def _infer_region_tags(text: str, *, folder: str, stock_tags: list[str]) -> list[str]:
    tags = _ranked_tags_from_keywords(text, REGION_TAG_KEYWORDS)
    normalized_folder = _normalize_folder(folder)
    if stock_tags and normalized_folder in {'kr/dart', 'market/news/selected_articles', 'market/rss', 'text/blog', 'text/telegram', 'text/premium/startale'} and 'kr' not in tags:
        tags.append('kr')
    if normalized_folder == 'market/rss' and 'global' in tags and 'us' not in tags:
        tags.append('us')
    return tags


def _semantic_fields(text: str, *, folder: str, stocks: list[dict], industries: list[str]) -> dict:
    stock_tags = [str(entry.get('ticker') or '').strip() for entry in stocks if str(entry.get('ticker') or '').strip()]
    macro_tags = _ranked_tags_from_keywords(text, MACRO_TAG_KEYWORDS)
    event_tags = _ranked_tags_from_keywords(text, EVENT_TAG_KEYWORDS)
    region_tags = _infer_region_tags(text, folder=folder, stock_tags=stock_tags)
    target_levels: list[str] = []
    if macro_tags:
        target_levels.append('macro')
    if industries:
        target_levels.append('industry')
    if stock_tags:
        target_levels.append('stock')
    return {
        'semantic_version': SEMANTIC_SCHEMA_VERSION,
        'target_levels': target_levels,
        'macro_tags': macro_tags,
        'industry_tags': industries,
        'stock_tags': stock_tags,
        'event_tags': event_tags,
        'impact_direction': _infer_impact_direction(text, event_tags),
        'horizon': _infer_horizon(text, folder=folder),
        'region_tags': region_tags,
    }


def _classify_document_text(text: str, *, title: str = '', folder: str = '', source_file: str = '') -> dict:
    body = '\n'.join(part for part in [str(title or '').strip(), str(text or '').strip()] if part).strip()
    stocks = _extract_stock_mentions(body)
    industries = _extract_industry_mentions(body)
    semantic = _semantic_fields(body, folder=folder, stocks=stocks, industries=industries)
    CLASSIFICATION_RUNTIME_STATS['documents_classified'] += 1
    if stocks:
        CLASSIFICATION_RUNTIME_STATS['documents_with_stock'] += 1
    if industries:
        CLASSIFICATION_RUNTIME_STATS['documents_with_industry'] += 1
    return {
        'classification_version': CLASSIFICATION_VERSION,
        'folder': folder,
        'source_file': source_file,
        'primary_ticker': stocks[0]['ticker'] if stocks else '',
        'primary_stock_name': stocks[0]['stock_name'] if stocks else '',
        'mentioned_tickers': [entry['ticker'] for entry in stocks],
        'mentioned_stock_names': [entry['stock_name'] for entry in stocks],
        'primary_industry': industries[0] if industries else '',
        'mentioned_industries': industries,
        **semantic,
    }


def _classification_output_path(base_dir: str, folder: str, rel_path: str) -> str:
    base = _output_paths(base_dir, folder, rel_path)[0]
    return f'{base}.classification.json'


def _build_selected_article_classification(row: dict) -> dict:
    title = str(row.get('title') or '').strip()
    body = str(row.get('body') or '').strip()
    summary = str(row.get('summary') or '').strip()
    text_parts = [title]
    if body:
        text_parts.append(body)
    if summary and len(body) < SELECTED_ARTICLES_MIN_TEXT_LEN:
        text_parts.append(summary)
    text = '\n'.join(part for part in text_parts if part)
    classification = _classify_document_text(
        text,
        title=title,
        folder='market/news/selected_articles',
        source_file=str(row.get('url') or ''),
    )
    CLASSIFICATION_RUNTIME_STATS['selected_articles_rows_classified'] += 1
    return classification


def _build_selected_articles_classification_summary(rows: list[dict], source_file: str) -> dict:
    return {
        'classification_version': CLASSIFICATION_VERSION,
        'folder': 'market/news/selected_articles',
        'source_file': source_file,
        'rows': [
            {
                'line_no': idx,
                'title': str(row.get('title') or '').strip(),
                'published_date': str(row.get('published_date') or row.get('published_at') or '').strip(),
                **dict(row.get('stage2_classification') or {}),
            }
            for idx, row in enumerate(rows, start=1)
        ],
    }


def _build_text_classification_payload(content: str, folder: str, source_file: str) -> dict:
    return _classify_document_text(
        content,
        title=_extract_text_title(content),
        folder=folder,
        source_file=source_file,
    )


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


def _input_source_policy_payload() -> dict:
    return {
        'input_source': STAGE2_INPUT_SOURCE,
        'input_source_status': STAGE2_INPUT_SOURCE_STATUS,
        'fallback_reason': STAGE2_FALLBACK_REASON,
        'fallback_scope': STAGE2_FALLBACK_SCOPE,
        'raw_base': RAW_BASE,
        'db_path': _STAGE1_RAW_DB_PATH,
        'mirror_root': _STAGE2_DB_MIRROR_ROOT,
        'raw_files_fallback_opt_in': bool(STAGE2_ALLOW_RAW_FILES_FALLBACK),
    }


def _enforce_input_source_policy() -> None:
    if STAGE2_INPUT_SOURCE_STATUS == 'blocked_raw_files_fallback_opt_in_required':
        raise SystemExit(
            'stage2_input_source_policy_violation: stage1_raw_db_mirror unavailable and '
            'raw-files fallback is blocked by default. '
            'Set STAGE2_ALLOW_RAW_FILES_FALLBACK=1 for explicit degraded opt-in.'
        )


def _load_json_file(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _build_stage1_handoff_completeness() -> dict:
    checkpoint = _load_json_file(STAGE1_CHECKPOINT_STATUS_PATH)
    coverage = _load_json_file(STAGE1_SOURCE_COVERAGE_PATH)
    attachment = _load_json_file(STAGE1_ATTACHMENT_RECOVERY_SUMMARY_PATH)
    completeness = attachment.get('completeness') if isinstance(attachment.get('completeness'), dict) else {}
    collected_total = _as_int(completeness.get('collected_total'), 0)
    placeholder_only = _as_int(completeness.get('placeholder_only'), 0)
    recoverable_missing = _as_int(completeness.get('recoverable_missing_artifact'), 0)
    severe_missing = _as_int(completeness.get('unrecoverable_missing'), 0)

    raw_checkpoint_status = 'PASS' if checkpoint.get('ok') is True else ('FAIL' if checkpoint else '미확인')
    post_validate = ((coverage.get('runtime_health') or {}).get('post_collection_validate') or {}) if isinstance(coverage, dict) else {}
    source_coverage_status = 'PASS' if post_validate.get('ok') is True else ('FAIL' if coverage else '미확인')
    attachment_stage_status = str(attachment.get('stage_status') or '미확인')
    attachment_completeness_status = str(attachment.get('completeness_status') or '미확인')
    attachment_recovery_status = f'{attachment_stage_status}:{attachment_completeness_status}' if attachment_stage_status != '미확인' or attachment_completeness_status != '미확인' else '미확인'

    placeholder_ratio = _safe_ratio(placeholder_only, collected_total)
    recoverable_missing_ratio = _safe_ratio(recoverable_missing, collected_total)
    severe_missing_ratio = _safe_ratio(severe_missing, collected_total)

    if raw_checkpoint_status != 'PASS' or source_coverage_status != 'PASS':
        handoff_status = 'BLOCKED'
    elif attachment_completeness_status == 'UNRECOVERABLE' or severe_missing_ratio > 0:
        handoff_status = 'NEED_RECOVERY_FIRST'
    elif attachment_completeness_status in {'DEGRADED', 'PARTIAL_RECOVERY'} or placeholder_ratio > 0 or recoverable_missing_ratio > 0:
        handoff_status = 'READY_WITH_WARNINGS'
    else:
        handoff_status = 'READY'

    return {
        'raw_checkpoint_status': raw_checkpoint_status,
        'source_coverage_status': source_coverage_status,
        'attachment_recovery_status': attachment_recovery_status,
        'placeholder_ratio': placeholder_ratio,
        'recoverable_missing_ratio': recoverable_missing_ratio,
        'severe_missing_ratio': severe_missing_ratio,
        'handoff_status': handoff_status,
        'proof_paths': {
            'raw_checkpoint_status_path': STAGE1_CHECKPOINT_STATUS_PATH,
            'source_coverage_status_path': STAGE1_SOURCE_COVERAGE_PATH,
            'attachment_recovery_status_path': STAGE1_ATTACHMENT_RECOVERY_SUMMARY_PATH,
        },
    }


def _build_stage2_integrity_summary(*, results: list[dict], total_exceptions: int, hard_fail_issues: list[dict]) -> tuple[dict, dict, dict, dict, str, str]:
    pdf_status_buckets = {
        'promoted': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_promoted', 0)),
        'bounded_by_cap': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_bounded_by_cap', 0)),
        'recoverable_missing_artifact': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_recoverable_missing_artifact', 0)),
        'placeholder_only': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_placeholder_only', 0)),
        'extractor_unavailable': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_extractor_unavailable', 0)),
        'parse_failed': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_parse_failed', 0)),
        'lineage_mismatch': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_lineage_mismatch', 0)),
        'diagnostics_only': int(LINK_RUNTIME_STATS.get('telegram_pdf_status_diagnostics_only', 0)),
    }
    bounded_stop_visibility = {
        'declared_page_count_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_declared_page_count_total', 0)),
        'indexed_page_rows_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_indexed_page_rows_total', 0)),
        'materialized_text_pages_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_materialized_text_pages_total', 0)),
        'materialized_render_pages_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_materialized_render_pages_total', 0)),
        'placeholder_page_rows_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_placeholder_page_rows_total', 0)),
        'bounded_by_cap_docs': int(LINK_RUNTIME_STATS.get('telegram_pdf_bounded_by_cap_docs', 0)),
        'bounded_pages_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_bounded_pages_total', 0)),
    }
    legacy_join_visibility = {
        'join_strategy': {
            'canonical_marker': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_canonical_marker', 0)),
            'canonical_flat': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_canonical_flat', 0)),
            'legacy_dir': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_legacy_dir', 0)),
            'recovered_local_extract': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_recovered_local_extract', 0)),
        },
        'join_confidence': {
            'strong': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_confidence_strong', 0)),
            'medium': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_confidence_medium', 0)),
            'weak': int(LINK_RUNTIME_STATS.get('telegram_pdf_join_confidence_weak', 0)),
        },
        'lineage_status': {
            'confirmed': int(LINK_RUNTIME_STATS.get('telegram_pdf_lineage_status_confirmed', 0)),
            'probable': int(LINK_RUNTIME_STATS.get('telegram_pdf_lineage_status_probable', 0)),
            'unresolved': int(LINK_RUNTIME_STATS.get('telegram_pdf_lineage_status_unresolved', 0)),
        },
    }
    handoff_completeness = _build_stage1_handoff_completeness()

    inherited_signal = handoff_completeness.get('handoff_status') in {'READY_WITH_WARNINGS', 'NEED_RECOVERY_FIRST', 'BLOCKED'}
    introduced_signal = (
        pdf_status_buckets['lineage_mismatch'] > 0
        or pdf_status_buckets['diagnostics_only'] > 0
        or pdf_status_buckets['parse_failed'] > 0
    )
    if inherited_signal and introduced_signal:
        origin_of_degradation = 'unresolved_mixed_origin'
    elif inherited_signal:
        origin_of_degradation = 'inherited_from_stage1'
    else:
        origin_of_degradation = 'introduced_in_stage2'

    if hard_fail_issues:
        stage3_ready_status = 'BLOCKED'
    elif handoff_completeness.get('handoff_status') == 'BLOCKED':
        stage3_ready_status = 'BLOCKED'
    elif handoff_completeness.get('handoff_status') == 'NEED_RECOVERY_FIRST':
        stage3_ready_status = 'DEGRADED'
    elif (
        handoff_completeness.get('handoff_status') == 'READY_WITH_WARNINGS'
        or pdf_status_buckets['bounded_by_cap'] > 0
        or pdf_status_buckets['recoverable_missing_artifact'] > 0
        or pdf_status_buckets['placeholder_only'] > 0
        or pdf_status_buckets['lineage_mismatch'] > 0
        or pdf_status_buckets['diagnostics_only'] > 0
    ):
        stage3_ready_status = 'READY_WITH_WARNINGS'
    else:
        stage3_ready_status = 'READY'

    total_records_seen = int(sum(r.get('total', 0) for r in results))
    total_records_clean = int(sum(r.get('clean', 0) for r in results))
    total_records_quarantine = int(sum(r.get('quarantine', 0) for r in results))
    pdf_docs_seen = int(LINK_RUNTIME_STATS.get('telegram_pdf_total', 0))
    pdf_missing_docs = int(
        pdf_status_buckets['recoverable_missing_artifact']
        + pdf_status_buckets['extractor_unavailable']
        + pdf_status_buckets['parse_failed']
        + pdf_status_buckets['lineage_mismatch']
        + pdf_status_buckets['diagnostics_only']
    )
    lineage_unresolved_docs = int(legacy_join_visibility['lineage_status']['unresolved'])

    integrity_summary = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'input_source_status': STAGE2_INPUT_SOURCE_STATUS,
        'total_records_seen': total_records_seen,
        'total_records_clean': total_records_clean,
        'total_records_quarantine': total_records_quarantine,
        'pdf_docs_seen': pdf_docs_seen,
        'pdf_promoted_docs': int(pdf_status_buckets['promoted']),
        'pdf_bounded_docs': int(pdf_status_buckets['bounded_by_cap']),
        'pdf_missing_docs': pdf_missing_docs,
        'pdf_placeholder_only_docs': int(pdf_status_buckets['placeholder_only']),
        'lineage_unresolved_docs': lineage_unresolved_docs,
        'stage3_ready_status': stage3_ready_status,
        'pdf_status_buckets': pdf_status_buckets,
        'bounded_stop_visibility': bounded_stop_visibility,
        'legacy_join_visibility': legacy_join_visibility,
        'handoff_completeness': handoff_completeness,
        'origin_of_degradation': origin_of_degradation,
        'hard_fail_count': int(len(hard_fail_issues)),
        'total_exceptions': int(total_exceptions),
        'proof_paths': {
            'integrity_summary_path': INTEGRITY_SUMMARY_PATH,
            'stage1_checkpoint_status_path': STAGE1_CHECKPOINT_STATUS_PATH,
            'stage1_source_coverage_path': STAGE1_SOURCE_COVERAGE_PATH,
            'stage1_attachment_recovery_summary_path': STAGE1_ATTACHMENT_RECOVERY_SUMMARY_PATH,
        },
    }
    return integrity_summary, pdf_status_buckets, bounded_stop_visibility, legacy_join_visibility, stage3_ready_status, origin_of_degradation


def _current_index_meta() -> dict:
    return {
        'stage2_rule_version': STAGE2_RULE_VERSION,
        'stage2_config_sha1': STAGE2_CONFIG_SHA1,
        'classification_version': CLASSIFICATION_VERSION,
        'semantic_version': SEMANTIC_SCHEMA_VERSION,
        'link_enrichment_enabled': bool(STAGE2_ENABLE_LINK_ENRICHMENT),
        'live_link_fetch_enabled': bool(STAGE2_ENABLE_LIVE_LINK_FETCH),
        'input_source': STAGE2_INPUT_SOURCE,
        'input_source_status': STAGE2_INPUT_SOURCE_STATUS,
        'fallback_reason': STAGE2_FALLBACK_REASON,
        'fallback_scope': STAGE2_FALLBACK_SCOPE,
        'input_source_raw_files_fallback_opt_in': bool(STAGE2_ALLOW_RAW_FILES_FALLBACK),
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


def _classification_sidecar_exists(ext: str, folder: str, clean_paths: list[str]) -> bool:
    if not clean_paths:
        return False
    normalized_folder = _normalize_folder(folder)
    if ext == '.jsonl' and normalized_folder == 'market/news/selected_articles':
        clean_path = clean_paths[0]
        sidecar_path = f'{clean_path}.classification.json'
        if not (os.path.exists(clean_path) and os.path.exists(sidecar_path)):
            return False
        try:
            with open(clean_path, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict) or not isinstance(row.get('stage2_classification'), dict):
                        return False
        except Exception:
            return False
        return True
    if _folder_bucket(folder) == 'qualitative' and ext in {'.md', '.txt'}:
        return os.path.exists(f'{clean_paths[0]}.classification.json')
    return True


def _parse_folder_targets(raw_value: str | None) -> list[str] | None:
    if not raw_value:
        return None
    requested = [item.strip() for item in str(raw_value).split(',') if item.strip()]
    if not requested:
        return None
    invalid = [item for item in requested if item not in FOLDERS]
    if invalid:
        raise ValueError(f'unknown folders: {invalid}')
    return requested


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


def _telegram_channel_slug_from_log_path(path: str) -> str:
    base = os.path.basename(path or '')
    if base.lower().endswith('.md'):
        base = base[:-3]
    if base.endswith('_full'):
        base = base[:-5]
    return base.strip()


def _telegram_attachment_dir_for_log(path: str) -> str:
    slug = _telegram_channel_slug_from_log_path(path)
    return os.path.join(TELEGRAM_ATTACH_ROOT, slug) if slug else ''


def _telegram_attach_file_stem(message_id: str) -> str:
    return f'msg_{int(message_id)}'


def _telegram_attach_bucket_name(message_id: str) -> str:
    width = max(2, len(str(max(0, TELEGRAM_ATTACH_BUCKET_COUNT - 1))))
    return f"bucket_{int(message_id) % TELEGRAM_ATTACH_BUCKET_COUNT:0{width}d}"


def _telegram_attach_bucket_dir(channel_slug: str, message_id: str) -> str:
    return os.path.join(TELEGRAM_ATTACH_ROOT, channel_slug, _telegram_attach_bucket_name(message_id)) if channel_slug else ''


def _telegram_attach_legacy_dir(channel_slug: str, message_id: str) -> str:
    return os.path.join(TELEGRAM_ATTACH_ROOT, channel_slug, f'msg_{message_id}') if channel_slug else ''


def _telegram_attach_meta_path(channel_slug: str, message_id: str) -> str:
    bucket_dir = _telegram_attach_bucket_dir(channel_slug, message_id)
    return os.path.join(bucket_dir, f"{_telegram_attach_file_stem(message_id)}__meta.json") if bucket_dir else ''


def _telegram_attach_extract_path(channel_slug: str, message_id: str) -> str:
    bucket_dir = _telegram_attach_bucket_dir(channel_slug, message_id)
    return os.path.join(bucket_dir, f"{_telegram_attach_file_stem(message_id)}__extracted.txt") if bucket_dir else ''


def _telegram_attach_original_candidates(channel_slug: str, message_id: str) -> list[str]:
    bucket_dir = _telegram_attach_bucket_dir(channel_slug, message_id)
    if not bucket_dir:
        return []
    return sorted(glob.glob(os.path.join(bucket_dir, f"{_telegram_attach_file_stem(message_id)}__original__*")))


def _telegram_attachment_subtree_sig(path: str) -> str:
    attach_dir = _telegram_attachment_dir_for_log(path)
    if not attach_dir or not os.path.isdir(attach_dir):
        return 'no-attachments'

    parts = []
    for root, _, files in os.walk(attach_dir):
        for name in sorted(files):
            fp = os.path.join(root, name)
            try:
                st = os.stat(fp)
            except FileNotFoundError:
                continue
            rel = os.path.relpath(fp, attach_dir).replace('\\', '/')
            parts.append(f"{rel}:{st.st_size}:{int(st.st_mtime)}")
    digest_src = '\n'.join(parts) if parts else 'empty-attachments'
    return hashlib.sha1(digest_src.encode('utf-8')).hexdigest()


def _sidecar_path_for_source(path: str, folder: str = '') -> str:
    normalized = os.path.normpath(path)
    candidates = []
    normalized_folder = _normalize_folder(folder)
    if normalized_folder in TARGET_LINK_ENRICH_FOLDERS:
        candidates.append(normalized_folder)
    else:
        candidates.extend(sorted(TARGET_LINK_ENRICH_FOLDERS, key=lambda x: len(x), reverse=True))

    for candidate in candidates:
        folder_root = os.path.normpath(_resolve_raw_dir(candidate))
        if normalized == folder_root or not normalized.startswith(folder_root + os.sep):
            continue
        rel = os.path.relpath(normalized, folder_root)
        if rel.startswith('..'):
            continue
        return os.path.join(LINK_SIDECAR_ROOT, candidate, rel + '.json')
    return ''


def _stage1_sidecar_sig(path: str, folder: str = '') -> str:
    sidecar_path = _sidecar_path_for_source(path, folder=folder)
    if not sidecar_path:
        return ''
    if not os.path.exists(sidecar_path):
        return 'sidecar:missing'
    try:
        st = os.stat(sidecar_path)
    except FileNotFoundError:
        return 'sidecar:missing'
    rel = os.path.relpath(sidecar_path, LINK_SIDECAR_ROOT).replace('\\', '/')
    return f"sidecar:{rel}:{st.st_size}:{int(st.st_mtime)}"


def _file_sig(path: str) -> str:
    st = os.stat(path)
    extra = ''
    normalized = os.path.normpath(path)
    telegram_root = os.path.normpath(os.path.join(RAW_BASE, 'qualitative', 'text', 'telegram'))
    if normalized.startswith(telegram_root + os.sep) and normalized.lower().endswith('.md'):
        extra = ':' + _telegram_attachment_subtree_sig(path)
    sidecar_sig = _stage1_sidecar_sig(path)
    if sidecar_sig:
        extra += ':' + sidecar_sig
    key = (
        f"{STAGE2_RULE_VERSION}:{STAGE2_CONFIG_SHA1}:{int(STAGE2_ENABLE_LINK_ENRICHMENT)}:"
        f"{int(STAGE2_ENABLE_LIVE_LINK_FETCH)}:{st.st_size}:{int(st.st_mtime)}:{path}{extra}"
    ).encode('utf-8')
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
        if re.match(r'(?i)^\[FILE_NAME\].*$', s):
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


def _telegram_block_marker_value(block: str, marker: str) -> str:
    m = re.search(rf'(?mi)^\[{re.escape(marker)}\]\s*(.+)$', block or '')
    return str(m.group(1) or '').strip() if m else ''


def _telegram_rewrite_stage1_path(raw_path: str) -> str:
    candidate = str(raw_path or '').strip()
    if not candidate:
        return ''
    candidate = candidate.replace('\\', '/')
    if os.path.isabs(candidate):
        return candidate if os.path.exists(candidate) else ''
    if candidate.startswith('outputs/raw/qualitative/'):
        candidate = 'raw/qualitative/' + candidate[len('outputs/raw/qualitative/'):]
    elif 'outputs/raw/qualitative/' in candidate:
        candidate = 'raw/qualitative/' + candidate.split('outputs/raw/qualitative/', 1)[1]
    elif candidate.startswith('./'):
        candidate = candidate[2:]
    resolved = os.path.join(UPSTREAM_STAGE1, candidate)
    return resolved if os.path.exists(resolved) else ''


def _telegram_pdf_original_candidates(channel_slug: str, message_id: str, artifact_dir: str, meta: dict) -> list[str]:
    candidates = []

    def _add(raw: str) -> None:
        if not raw:
            return
        resolved = _telegram_rewrite_stage1_path(raw) if not os.path.isabs(raw) else raw
        if resolved and os.path.exists(resolved) and resolved not in candidates:
            candidates.append(resolved)

    _add(str(meta.get('original_path') or ''))

    for fp in _telegram_attach_original_candidates(channel_slug, message_id):
        if fp not in candidates:
            candidates.append(fp)

    if artifact_dir and os.path.isdir(artifact_dir):
        for name in sorted(os.listdir(artifact_dir)):
            if name.lower().endswith('.pdf'):
                fp = os.path.join(artifact_dir, name)
                if fp not in candidates:
                    candidates.append(fp)
    return candidates


def _extract_pdf_text_swift(original_path: str, max_pages: int = 25) -> tuple[str, str]:
    if os.uname().sysname.lower() != 'darwin':
        return '', 'swift_pdfkit_non_darwin'
    if not os.path.exists(MACOS_SWIFT_BIN):
        return '', 'swift_unavailable'

    script_path = ''
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.swift', delete=False) as tf:
            tf.write(SWIFT_PDFKIT_EXTRACT_SCRIPT)
            script_path = tf.name
        proc = subprocess.run(
            [MACOS_SWIFT_BIN, script_path, str(original_path), str(max(1, max_pages))],
            capture_output=True,
            text=True,
            timeout=max(30, min(300, max_pages * 12)),
        )
    except subprocess.TimeoutExpired:
        return '', 'swift_timeout'
    except Exception as e:
        return '', f'swift_run_error:{type(e).__name__}'
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except Exception:
                pass

    if proc.returncode != 0:
        stderr = (proc.stderr or '').lower()
        if 'open_failed' in stderr:
            return '', 'swift_pdf_open_failed'
        if 'no such module' in stderr and 'pdfkit' in stderr:
            return '', 'swift_pdfkit_unavailable'
        return '', f'swift_pdfkit_error:{proc.returncode}'

    text = (proc.stdout or '').strip()
    return (text, 'swift_pdfkit') if text else ('', 'swift_pdf_text_empty')


def _telegram_extract_pdf_text_from_original(original_path: str) -> tuple[str, str]:
    if not original_path or not os.path.exists(original_path):
        return '', 'original_missing'

    try:
        from pypdf import PdfReader  # type: ignore

        pages = []
        reader = PdfReader(original_path)
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or '')
            except Exception:
                continue
        merged = '\n'.join(pages).strip()
        if merged:
            return merged, 'pypdf'
    except Exception:
        pass

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore

        merged = (pdfminer_extract_text(original_path) or '').strip()
        if merged:
            return merged, 'pdfminer'
    except Exception:
        pass

    swift_text, swift_origin = _extract_pdf_text_swift(original_path)
    if swift_text:
        return swift_text, swift_origin

    return '', swift_origin or 'extractor_unavailable_or_failed'


def _normalize_pdf_title(raw: str, fallback_path: str = '') -> str:
    title = str(raw or '').strip()
    if not title and fallback_path:
        title = os.path.basename(fallback_path)
    title = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE).strip()
    title = re.sub(r'[_\-]+', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title or 'attached pdf'


def _cleanup_pdf_text(raw_text: str) -> str:
    text = (raw_text or '').replace('\x00', ' ').replace('\r\n', '\n').replace('\r', '\n')
    raw_lines = [line.strip() for line in text.split('\n')]
    line_counts = {}
    for line in raw_lines:
        normalized = re.sub(r'\s+', ' ', line).strip().lower()
        if normalized:
            line_counts[normalized] = line_counts.get(normalized, 0) + 1

    boilerplate_patterns = [
        r'(?i)all rights reserved',
        r'(?i)copyright',
        r'(?i)disclaimer',
        r'(?i)무단전재',
        r'(?i)배포\s*금지',
        r'(?i)저작권',
        r'(?i)법적 책임소재',
        r'(?i)사용될 수 없습니다',
    ]

    cleaned = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        normalized = re.sub(r'\s+', ' ', line).strip()
        low = normalized.lower()
        if not normalized:
            cleaned.append('')
            i += 1
            continue
        if re.fullmatch(r'(?:page\s*)?\d{1,4}(?:\s*/\s*\d{1,4})?', low):
            i += 1
            continue
        if re.fullmatch(r'\d{1,4}©.*', normalized):
            i += 1
            continue
        if any(re.search(pat, normalized) for pat in boilerplate_patterns):
            i += 1
            continue
        if line_counts.get(low, 0) >= 3 and len(normalized) <= 120 and any(tok in low for tok in ['all rights reserved', 'copyright', 'disclaimer', 'investor relations', 'ir', 'confidential']):
            i += 1
            continue

        if normalized.endswith('-') and i + 1 < len(raw_lines):
            nxt = raw_lines[i + 1].strip()
            if nxt and re.match(r'^[A-Za-z0-9가-힣]', nxt):
                cleaned.append((normalized[:-1] + nxt).strip())
                i += 2
                continue

        cleaned.append(normalized)
        i += 1

    text = '\n'.join(cleaned)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _parse_telegram_message_id(block: str) -> str:
    m = re.search(r'(?mi)^MessageID\s*:\s*(\d+)', block or '')
    return str(m.group(1)) if m else ''


def _as_int(raw: object, default: int = 0) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _telegram_pdf_manifest_diag(meta: dict, *, fallback_manifest_path: str = '') -> dict:
    manifest_rel = str(meta.get('pdf_manifest_path') or '').strip()
    manifest_path = fallback_manifest_path or _telegram_rewrite_stage1_path(manifest_rel)
    manifest = {}
    if manifest_path and os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as mf:
                payload = json.load(mf)
            if isinstance(payload, dict):
                manifest = payload
        except Exception:
            manifest = {}

    pages = manifest.get('pages', []) if isinstance(manifest.get('pages'), list) else []
    indexed_page_rows = 0
    materialized_text_pages = 0
    materialized_render_pages = 0
    placeholder_page_rows = 0
    seen_page_nos: set[int] = set()
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_no = _as_int(page.get('page_no'), 0)
        if page_no <= 0 or page_no in seen_page_nos:
            continue
        seen_page_nos.add(page_no)
        indexed_page_rows += 1
        has_text = bool(str(page.get('text_rel_path') or '').strip())
        has_render = bool(str(page.get('render_rel_path') or '').strip())
        if has_text:
            materialized_text_pages += 1
        if has_render:
            materialized_render_pages += 1
        if not has_text and not has_render:
            placeholder_page_rows += 1

    declared_page_count = max(
        0,
        _as_int(
            manifest.get('declared_page_count')
            or manifest.get('page_count')
            or meta.get('pdf_declared_page_count')
            or meta.get('pdf_page_count')
            or 0
        ),
    )
    if not indexed_page_rows:
        indexed_page_rows = max(0, _as_int(manifest.get('indexed_page_rows') or meta.get('pdf_indexed_page_rows') or 0))
    if not materialized_text_pages:
        materialized_text_pages = max(0, _as_int(manifest.get('materialized_text_pages') or manifest.get('text_pages_written') or meta.get('pdf_materialized_text_pages') or meta.get('pdf_text_pages') or 0))
    if not materialized_render_pages:
        materialized_render_pages = max(0, _as_int(manifest.get('materialized_render_pages') or manifest.get('rendered_pages_written') or meta.get('pdf_materialized_render_pages') or meta.get('pdf_render_pages') or 0))
    if not placeholder_page_rows:
        placeholder_page_rows = max(0, _as_int(manifest.get('placeholder_page_rows') or meta.get('pdf_placeholder_page_rows') or 0))

    max_pages_applied = max(
        0,
        _as_int(manifest.get('max_pages_applied') or meta.get('pdf_max_pages_applied') or 0),
    )
    bounded_by_cap = bool(
        (
            declared_page_count > indexed_page_rows
            and max_pages_applied > 0
            and indexed_page_rows >= max_pages_applied
        )
        or manifest.get('bounded_by_cap')
        or meta.get('pdf_bounded_by_cap')
    )

    return {
        'manifest_path': manifest_path,
        'manifest_exists': bool(manifest_path and os.path.exists(manifest_path)),
        'declared_page_count': declared_page_count,
        'indexed_page_rows': indexed_page_rows,
        'materialized_text_pages': materialized_text_pages,
        'materialized_render_pages': materialized_render_pages,
        'placeholder_page_rows': placeholder_page_rows,
        'bounded_by_cap': bounded_by_cap,
    }


def _is_extractor_unavailable_reason(reason: str) -> bool:
    low = str(reason or '').strip().lower()
    if not low:
        return False
    unavailable_tokens = (
        'extractor_unavailable',
        'pypdf_unavailable',
        'pdfminer_unavailable',
        'swift_unavailable',
        'swift_pdfkit_unavailable',
        'swift_pdfkit_non_darwin',
    )
    return any(token in low for token in unavailable_tokens)


def _pick_telegram_pdf_status(
    *,
    promoted: bool,
    bounded_by_cap: bool,
    recoverable_missing_artifact: bool,
    extractor_unavailable: bool,
    placeholder_only: bool,
    lineage_mismatch: bool,
    diagnostics_only: bool,
) -> str:
    if lineage_mismatch:
        return 'lineage_mismatch'
    if diagnostics_only:
        return 'diagnostics_only'
    if promoted:
        return 'promoted'
    if bounded_by_cap:
        return 'bounded_by_cap'
    if recoverable_missing_artifact:
        return 'recoverable_missing_artifact'
    if extractor_unavailable:
        return 'extractor_unavailable'
    if placeholder_only:
        return 'placeholder_only'
    return 'parse_failed'


def _telegram_pdf_join_strategy(*, resolution_mode: str, meta_path: str, text_source: str) -> str:
    if text_source == 'stage2_pdf_extract':
        return 'recovered_local_extract'
    if resolution_mode == 'canonical_marker':
        return 'canonical_marker'
    if meta_path and os.path.basename(meta_path) == 'meta.json':
        return 'legacy_dir'
    return 'canonical_flat'


def _telegram_pdf_lineage_meta(*, meta: dict, channel_slug: str, message_id: str, join_strategy: str) -> dict:
    meta_channel_slug = str(meta.get('channel_slug') or '').strip().lower()
    expected_channel_slug = str(channel_slug or '').strip().lower()
    meta_message_id = str(meta.get('message_id') or '').strip()
    expected_message_id = str(message_id or '').strip()
    lineage_mismatch = bool(meta_message_id and expected_message_id and meta_message_id != expected_message_id)
    if lineage_mismatch:
        return {
            'join_confidence': 'weak',
            'lineage_status': 'unresolved',
            'lineage_mismatch': True,
            'diagnostics_only': True,
        }
    if join_strategy == 'canonical_marker':
        return {
            'join_confidence': 'strong',
            'lineage_status': 'confirmed' if meta_channel_slug == expected_channel_slug and meta_message_id == expected_message_id else 'probable',
            'lineage_mismatch': False,
            'diagnostics_only': False,
        }
    if join_strategy == 'canonical_flat':
        return {
            'join_confidence': 'strong' if meta_channel_slug == expected_channel_slug and meta_message_id == expected_message_id else 'medium',
            'lineage_status': 'confirmed' if meta_channel_slug == expected_channel_slug and meta_message_id == expected_message_id else 'probable',
            'lineage_mismatch': False,
            'diagnostics_only': False,
        }
    if join_strategy == 'recovered_local_extract':
        return {
            'join_confidence': 'medium' if meta_channel_slug == expected_channel_slug and meta_message_id == expected_message_id else 'weak',
            'lineage_status': 'probable' if meta_channel_slug == expected_channel_slug and meta_message_id == expected_message_id else 'unresolved',
            'lineage_mismatch': False,
            'diagnostics_only': not (meta_channel_slug == expected_channel_slug and meta_message_id == expected_message_id),
        }
    return {
        'join_confidence': 'weak',
        'lineage_status': 'probable' if meta_message_id == expected_message_id else 'unresolved',
        'lineage_mismatch': False,
        'diagnostics_only': True,
    }


def _record_telegram_pdf_diag_stats(diag: dict) -> None:
    status = str(diag.get('pdf_status') or 'parse_failed').strip() or 'parse_failed'
    status_key = f'telegram_pdf_status_{status}'
    if status_key in LINK_RUNTIME_STATS:
        LINK_RUNTIME_STATS[status_key] += 1
    LINK_RUNTIME_STATS['telegram_pdf_declared_page_count_total'] += _as_int(diag.get('declared_page_count'), 0)
    LINK_RUNTIME_STATS['telegram_pdf_indexed_page_rows_total'] += _as_int(diag.get('indexed_page_rows'), 0)
    LINK_RUNTIME_STATS['telegram_pdf_materialized_text_pages_total'] += _as_int(diag.get('materialized_text_pages'), 0)
    LINK_RUNTIME_STATS['telegram_pdf_materialized_render_pages_total'] += _as_int(diag.get('materialized_render_pages'), 0)
    LINK_RUNTIME_STATS['telegram_pdf_placeholder_page_rows_total'] += _as_int(diag.get('placeholder_page_rows'), 0)
    join_strategy = str(diag.get('join_strategy') or '').strip()
    join_confidence = str(diag.get('join_confidence') or '').strip()
    lineage_status = str(diag.get('lineage_status') or '').strip()
    if join_strategy:
        key = f'telegram_pdf_join_strategy_{join_strategy}'
        if key in LINK_RUNTIME_STATS:
            LINK_RUNTIME_STATS[key] += 1
    if join_confidence:
        key = f'telegram_pdf_join_confidence_{join_confidence}'
        if key in LINK_RUNTIME_STATS:
            LINK_RUNTIME_STATS[key] += 1
    if lineage_status:
        key = f'telegram_pdf_lineage_status_{lineage_status}'
        if key in LINK_RUNTIME_STATS:
            LINK_RUNTIME_STATS[key] += 1
    if bool(diag.get('bounded_by_cap')):
        LINK_RUNTIME_STATS['telegram_pdf_bounded_by_cap_total'] += 1
        LINK_RUNTIME_STATS['telegram_pdf_bounded_by_cap_docs'] += 1
        declared_page_count = _as_int(diag.get('declared_page_count'), 0)
        indexed_page_rows = _as_int(diag.get('indexed_page_rows'), 0)
        LINK_RUNTIME_STATS['telegram_pdf_bounded_pages_total'] += max(0, declared_page_count - indexed_page_rows)


def _collect_telegram_pdf_diag(
    *,
    meta: dict,
    meta_path: str,
    original_path: str,
    extract_path: str,
    extract_failure_reason: str,
    promoted: bool,
    text_source: str,
    cleaned_pdf: str,
    resolution_mode: str,
    channel_slug: str,
    message_id: str,
) -> dict:
    manifest_diag = _telegram_pdf_manifest_diag(meta)
    extract_exists = bool(extract_path and os.path.exists(extract_path))
    original_exists = bool(original_path and os.path.exists(original_path))
    extraction_reason = str(
        extract_failure_reason
        or meta.get('extraction_reason')
        or ''
    ).strip()
    recoverable_missing_artifact = bool(
        (not original_exists)
        and (manifest_diag.get('manifest_exists') or extract_exists)
    )
    placeholder_only = bool(
        manifest_diag.get('declared_page_count', 0) > 0
        and manifest_diag.get('materialized_text_pages', 0) == 0
        and manifest_diag.get('materialized_render_pages', 0) == 0
        and manifest_diag.get('placeholder_page_rows', 0) > 0
    )
    extractor_unavailable = _is_extractor_unavailable_reason(extraction_reason)
    join_strategy = _telegram_pdf_join_strategy(
        resolution_mode=resolution_mode,
        meta_path=meta_path,
        text_source=text_source,
    )
    lineage_meta = _telegram_pdf_lineage_meta(
        meta=meta,
        channel_slug=channel_slug,
        message_id=message_id,
        join_strategy=join_strategy,
    )
    pdf_status = _pick_telegram_pdf_status(
        promoted=promoted,
        bounded_by_cap=bool(manifest_diag.get('bounded_by_cap')),
        recoverable_missing_artifact=recoverable_missing_artifact,
        extractor_unavailable=extractor_unavailable,
        placeholder_only=placeholder_only,
        lineage_mismatch=bool(lineage_meta.get('lineage_mismatch')),
        diagnostics_only=bool(lineage_meta.get('diagnostics_only')),
    )
    return {
        'pdf_status': pdf_status,
        'pdf_status_reason': extraction_reason or ('ok' if promoted else ''),
        'pdf_promoted': bool(promoted),
        'pdf_source': text_source,
        'declared_page_count': int(manifest_diag.get('declared_page_count') or 0),
        'indexed_page_rows': int(manifest_diag.get('indexed_page_rows') or 0),
        'materialized_text_pages': int(manifest_diag.get('materialized_text_pages') or 0),
        'materialized_render_pages': int(manifest_diag.get('materialized_render_pages') or 0),
        'placeholder_page_rows': int(manifest_diag.get('placeholder_page_rows') or 0),
        'bounded_by_cap': bool(manifest_diag.get('bounded_by_cap')),
        'recoverable_missing_artifact': recoverable_missing_artifact,
        'extractor_unavailable': extractor_unavailable,
        'placeholder_only': placeholder_only,
        'join_strategy': join_strategy,
        'join_confidence': str(lineage_meta.get('join_confidence') or ''),
        'lineage_status': str(lineage_meta.get('lineage_status') or ''),
        'lineage_mismatch': bool(lineage_meta.get('lineage_mismatch')),
        'diagnostics_only': bool(lineage_meta.get('diagnostics_only')),
        'pdf_text_present': bool((cleaned_pdf or '').strip()),
        'attachment_meta_rel_path': os.path.relpath(meta_path, UPSTREAM_STAGE1).replace('\\', '/') if meta_path else '',
        'attachment_original_rel_path': os.path.relpath(original_path, UPSTREAM_STAGE1).replace('\\', '/') if original_path and original_path.startswith(UPSTREAM_STAGE1) else original_path,
    }


def _resolve_telegram_pdf_artifact(block: str, log_path: str) -> tuple[dict | None, dict]:
    message_id = _parse_telegram_message_id(block)
    channel_slug = _telegram_channel_slug_from_log_path(log_path)
    if not message_id or '[ATTACH_KIND] pdf' not in (block or ''):
        return None, {}

    LINK_RUNTIME_STATS['telegram_pdf_total'] += 1

    marker_meta = _telegram_rewrite_stage1_path(_telegram_block_marker_value(block, 'ATTACH_META_PATH'))
    marker_original = _telegram_rewrite_stage1_path(_telegram_block_marker_value(block, 'ATTACH_ORIGINAL_PATH'))
    marker_extract = _telegram_rewrite_stage1_path(_telegram_block_marker_value(block, 'ATTACH_TEXT_PATH'))
    marker_dir = _telegram_rewrite_stage1_path(_telegram_block_marker_value(block, 'ATTACH_ARTIFACT_DIR'))

    meta_path = ''
    resolution_mode = ''
    if marker_meta and os.path.exists(marker_meta):
        meta_path = marker_meta
        resolution_mode = 'canonical_marker'
    else:
        fallback_candidates = []
        if channel_slug:
            fallback_candidates.append(_telegram_attach_meta_path(channel_slug, message_id))
            legacy_dir = _telegram_attach_legacy_dir(channel_slug, message_id)
            if legacy_dir:
                fallback_candidates.append(os.path.join(legacy_dir, 'meta.json'))
        for candidate in fallback_candidates:
            if candidate and os.path.exists(candidate):
                meta_path = candidate
                resolution_mode = 'legacy_dir' if os.path.basename(candidate) == 'meta.json' else 'canonical_flat'
                break

    if not meta_path:
        LINK_RUNTIME_STATS['telegram_pdf_orphan_artifacts'] += 1
        diag = {
            'pdf_status': 'diagnostics_only',
            'pdf_promoted': False,
            'pdf_extract_failure_reason': 'telegram_pdf_meta_missing',
            'pdf_status_reason': 'telegram_pdf_meta_missing',
            'join_strategy': 'canonical_marker' if marker_meta else 'canonical_flat',
            'join_confidence': 'weak',
            'lineage_status': 'unresolved',
            'lineage_mismatch': False,
            'diagnostics_only': True,
            'pdf_message_id': message_id,
            'pdf_channel_slug': channel_slug,
        }
        _record_telegram_pdf_diag_stats(diag)
        return None, diag

    if resolution_mode == 'canonical_marker':
        LINK_RUNTIME_STATS['telegram_pdf_path_resolution_marker'] += 1
    elif resolution_mode in {'canonical_flat', 'legacy_dir'}:
        LINK_RUNTIME_STATS['telegram_pdf_path_resolution_fallback'] += 1

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        LINK_RUNTIME_STATS['telegram_pdf_extract_failed'] += 1
        diag = {
            'pdf_status': 'diagnostics_only',
            'pdf_promoted': False,
            'pdf_extract_failure_reason': f'telegram_pdf_meta_invalid:{type(e).__name__}',
            'pdf_status_reason': f'telegram_pdf_meta_invalid:{type(e).__name__}',
            'join_strategy': resolution_mode or 'canonical_flat',
            'join_confidence': 'weak',
            'lineage_status': 'unresolved',
            'lineage_mismatch': False,
            'diagnostics_only': True,
            'pdf_message_id': message_id,
            'pdf_channel_slug': channel_slug,
            'attachment_meta_rel_path': os.path.relpath(meta_path, UPSTREAM_STAGE1).replace('\\', '/'),
        }
        _record_telegram_pdf_diag_stats(diag)
        return None, diag

    if str(meta.get('kind') or '').strip().lower() != 'pdf':
        LINK_RUNTIME_STATS['telegram_pdf_extract_failed'] += 1
        diag = {
            'pdf_status': 'diagnostics_only',
            'pdf_promoted': False,
            'pdf_extract_failure_reason': 'telegram_pdf_kind_not_pdf',
            'pdf_status_reason': 'telegram_pdf_kind_not_pdf',
            'join_strategy': resolution_mode or 'canonical_flat',
            'join_confidence': 'weak',
            'lineage_status': 'unresolved',
            'lineage_mismatch': False,
            'diagnostics_only': True,
            'pdf_message_id': message_id,
            'pdf_channel_slug': channel_slug,
            'attachment_meta_rel_path': os.path.relpath(meta_path, UPSTREAM_STAGE1).replace('\\', '/'),
        }
        _record_telegram_pdf_diag_stats(diag)
        return None, diag

    if str(meta.get('message_id') or '') != str(message_id):
        LINK_RUNTIME_STATS['telegram_pdf_extract_failed'] += 1
        diag = {
            'pdf_status': 'lineage_mismatch',
            'pdf_promoted': False,
            'pdf_extract_failure_reason': 'telegram_pdf_meta_message_mismatch',
            'pdf_status_reason': 'telegram_pdf_meta_message_mismatch',
            'join_strategy': resolution_mode or 'canonical_flat',
            'join_confidence': 'weak',
            'lineage_status': 'unresolved',
            'lineage_mismatch': True,
            'diagnostics_only': True,
            'pdf_message_id': message_id,
            'pdf_channel_slug': channel_slug,
            'attachment_meta_rel_path': os.path.relpath(meta_path, UPSTREAM_STAGE1).replace('\\', '/'),
        }
        _record_telegram_pdf_diag_stats(diag)
        return None, diag

    bucket_dir = _telegram_attach_bucket_dir(channel_slug, message_id) if channel_slug else ''
    legacy_dir = _telegram_attach_legacy_dir(channel_slug, message_id) if channel_slug else ''
    if marker_dir and os.path.isdir(marker_dir):
        artifact_dir = marker_dir
    elif os.path.basename(meta_path) == 'meta.json' and legacy_dir and os.path.isdir(legacy_dir):
        artifact_dir = legacy_dir
    else:
        artifact_dir = os.path.dirname(meta_path)

    extract_path = marker_extract if marker_extract and os.path.exists(marker_extract) else _telegram_rewrite_stage1_path(str(meta.get('extract_path') or ''))
    if not extract_path:
        for probe in [
            _telegram_attach_extract_path(channel_slug, message_id) if channel_slug else '',
            os.path.join(legacy_dir, 'extracted.txt') if legacy_dir else '',
            os.path.join(artifact_dir, 'extracted.txt') if artifact_dir else '',
        ]:
            if probe and os.path.exists(probe):
                extract_path = probe
                break

    original_path = marker_original if marker_original and os.path.exists(marker_original) else ''
    if not original_path:
        original_candidates = _telegram_pdf_original_candidates(channel_slug, message_id, artifact_dir, meta)
        original_path = original_candidates[0] if original_candidates else ''

    text_source = ''
    pdf_text = ''
    extract_failure_reason = ''
    if str(meta.get('extraction_status') or '').strip().lower() == 'ok' and extract_path and os.path.exists(extract_path):
        pdf_text = _safe_read_text(extract_path, max_chars=1000000)
        if pdf_text.strip():
            text_source = 'stage1_extracted'
            LINK_RUNTIME_STATS['telegram_pdf_stage1_extract_reused'] += 1

    if not pdf_text.strip():
        pdf_text, extract_origin = _telegram_extract_pdf_text_from_original(original_path)
        if pdf_text.strip():
            text_source = 'stage2_pdf_extract'
            LINK_RUNTIME_STATS['telegram_pdf_stage2_extract_ok'] += 1
        else:
            extract_failure_reason = f'telegram_pdf_extract_failed:{extract_origin}'
            LINK_RUNTIME_STATS['telegram_pdf_extract_failed'] += 1

    cleaned_pdf = _cleanup_pdf_text(pdf_text) if pdf_text else ''
    if not cleaned_pdf:
        diag = _collect_telegram_pdf_diag(
            meta=meta,
            meta_path=meta_path,
            original_path=original_path,
            extract_path=extract_path,
            extract_failure_reason=extract_failure_reason or 'telegram_pdf_body_empty_after_normalize',
            promoted=False,
            text_source=text_source,
            cleaned_pdf='',
            resolution_mode=resolution_mode,
            channel_slug=channel_slug,
            message_id=message_id,
        )
        diag.update({
            'pdf_extract_failure_reason': extract_failure_reason or 'telegram_pdf_body_empty_after_normalize',
            'pdf_message_id': message_id,
            'pdf_channel_slug': channel_slug,
        })
        _record_telegram_pdf_diag_stats(diag)
        return None, diag

    title = _normalize_pdf_title(str(meta.get('original_name') or ''), original_path)
    promoted_block = f'[ATTACHED_PDF] {title}\n{cleaned_pdf}'.strip()
    chars_added = len(cleaned_pdf)
    LINK_RUNTIME_STATS['telegram_pdf_messages_promoted_by_pdf'] += 1
    LINK_RUNTIME_STATS['telegram_pdf_chars_added_total'] += chars_added
    diag = _collect_telegram_pdf_diag(
        meta=meta,
        meta_path=meta_path,
        original_path=original_path,
        extract_path=extract_path,
        extract_failure_reason='',
        promoted=True,
        text_source=text_source,
        cleaned_pdf=cleaned_pdf,
        resolution_mode=resolution_mode,
        channel_slug=channel_slug,
        message_id=message_id,
    )
    diag.update({
        'pdf_chars_added': chars_added,
        'pdf_nonempty_lines_added': len([line for line in cleaned_pdf.splitlines() if line.strip()]),
        'pdf_message_id': message_id,
        'pdf_channel_slug': channel_slug,
        'pdf_title_normalized': title,
    })
    _record_telegram_pdf_diag_stats(diag)
    return {
        'promoted_block': promoted_block,
        'text_source': text_source,
        'title': title,
        'chars_added': chars_added,
        'message_id': message_id,
        'channel_slug': channel_slug,
        'meta_path': meta_path,
        'original_path': original_path,
    }, diag


def _promote_telegram_pdf_content(raw_content: str, path: str) -> tuple[str, dict]:
    content = raw_content or ''
    if '[ATTACH_KIND] pdf' not in content:
        return content, {
            'pdf_promoted': False,
            'pdf_status': 'parse_failed',
            'pdf_source': '',
            'pdf_chars_added': 0,
            'pdf_nonempty_lines_added': 0,
            'declared_page_count': 0,
            'indexed_page_rows': 0,
            'materialized_text_pages': 0,
            'materialized_render_pages': 0,
            'placeholder_page_rows': 0,
            'bounded_by_cap': False,
        }

    parts = re.split(r'(?mi)^---\s*$', content)
    merged_parts = []
    promoted_any = False
    aggregate_meta = {
        'pdf_promoted': False,
        'pdf_status': 'parse_failed',
        'pdf_source': '',
        'pdf_chars_added': 0,
        'pdf_nonempty_lines_added': 0,
        'declared_page_count': 0,
        'indexed_page_rows': 0,
        'materialized_text_pages': 0,
        'materialized_render_pages': 0,
        'placeholder_page_rows': 0,
        'bounded_by_cap': False,
    }

    for part in parts:
        segment = part.strip('\n')
        if not segment:
            merged_parts.append(segment)
            continue
        promoted, meta = _resolve_telegram_pdf_artifact(segment, path)
        if promoted and promoted.get('promoted_block'):
            promoted_any = True
            for key, value in meta.items():
                if key in {
                    'pdf_promoted',
                    'pdf_status',
                    'pdf_source',
                    'pdf_chars_added',
                    'pdf_nonempty_lines_added',
                    'declared_page_count',
                    'indexed_page_rows',
                    'materialized_text_pages',
                    'materialized_render_pages',
                    'placeholder_page_rows',
                    'bounded_by_cap',
                }:
                    continue
                aggregate_meta[key] = value
            aggregate_meta['pdf_promoted'] = True
            aggregate_meta['pdf_status'] = 'promoted'
            aggregate_meta['pdf_source'] = meta.get('pdf_source', aggregate_meta.get('pdf_source', ''))
            aggregate_meta['pdf_chars_added'] = int(aggregate_meta.get('pdf_chars_added', 0)) + int(meta.get('pdf_chars_added', 0))
            aggregate_meta['pdf_nonempty_lines_added'] = int(aggregate_meta.get('pdf_nonempty_lines_added', 0)) + int(meta.get('pdf_nonempty_lines_added', 0))
            aggregate_meta['declared_page_count'] = int(aggregate_meta.get('declared_page_count', 0)) + int(meta.get('declared_page_count', 0))
            aggregate_meta['indexed_page_rows'] = int(aggregate_meta.get('indexed_page_rows', 0)) + int(meta.get('indexed_page_rows', 0))
            aggregate_meta['materialized_text_pages'] = int(aggregate_meta.get('materialized_text_pages', 0)) + int(meta.get('materialized_text_pages', 0))
            aggregate_meta['materialized_render_pages'] = int(aggregate_meta.get('materialized_render_pages', 0)) + int(meta.get('materialized_render_pages', 0))
            aggregate_meta['placeholder_page_rows'] = int(aggregate_meta.get('placeholder_page_rows', 0)) + int(meta.get('placeholder_page_rows', 0))
            aggregate_meta['bounded_by_cap'] = bool(aggregate_meta.get('bounded_by_cap')) or bool(meta.get('bounded_by_cap'))
            aggregate_meta['recoverable_missing_artifact'] = bool(aggregate_meta.get('recoverable_missing_artifact')) or bool(meta.get('recoverable_missing_artifact'))
            aggregate_meta['extractor_unavailable'] = bool(aggregate_meta.get('extractor_unavailable')) or bool(meta.get('extractor_unavailable'))
            aggregate_meta['placeholder_only'] = bool(aggregate_meta.get('placeholder_only')) or bool(meta.get('placeholder_only'))
            aggregate_meta['pdf_text_present'] = bool(aggregate_meta.get('pdf_text_present')) or bool(meta.get('pdf_text_present'))
            aggregate_meta.pop('pdf_extract_failure_reason', None)
            if not segment.rstrip().endswith(promoted['promoted_block']):
                segment = segment.rstrip() + '\n\n' + promoted['promoted_block'] + '\n'
        elif meta:
            for k, v in meta.items():
                if k not in aggregate_meta or not aggregate_meta.get(k):
                    aggregate_meta[k] = v
        merged_parts.append(segment)

    if not promoted_any:
        aggregate_meta['pdf_promoted'] = False
    merged = '\n---\n'.join(part for part in merged_parts if part is not None)
    return merged.strip() + ('\n' if merged.strip() else ''), aggregate_meta


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


def _looks_like_pdf_link(canonical_url: str, content_type: str = '', content_disposition: str = '') -> bool:
    path = ''
    try:
        path = (urlparse(canonical_url).path or '').lower()
    except Exception:
        path = ''

    ct = (content_type or '').lower()
    cd = (content_disposition or '').lower()
    return (
        path.endswith('.pdf')
        or 'application/pdf' in ct
        or ('attachment' in cd and '.pdf' in cd)
    )


def _extract_pdf_text_from_bytes(raw: bytes) -> tuple[str, str]:
    if not raw:
        return '', 'pdf_bytes_empty'

    tmp_path = ''
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
            tf.write(raw)
            tmp_path = tf.name
        text, origin = _telegram_extract_pdf_text_from_original(tmp_path)
        cleaned = _cleanup_pdf_text(text) if text else ''
        if cleaned:
            return cleaned[:LINK_FETCH_MAX_TEXT_CHARS], origin
        return '', origin or 'pdf_text_empty'
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _fetch_link_text(canonical_url: str) -> tuple[str, str, dict]:
    cached = LINK_FETCH_CACHE.get(canonical_url)
    if cached is not None:
        LINK_RUNTIME_STATS['url_cache_hits'] += 1
        return cached.get('text', ''), cached.get('error', ''), dict(cached.get('meta') or {})

    if not _is_allowed_link_url(canonical_url):
        LINK_RUNTIME_STATS['url_disallowed'] += 1
        LINK_FETCH_CACHE[canonical_url] = {'text': '', 'error': 'disallowed_domain', 'meta': {'is_pdf': False, 'allow_short': False}}
        return '', 'disallowed_domain', {'is_pdf': False, 'allow_short': False}

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; stage2-link-enrich/1.0)',
        'Accept': 'text/html,application/xhtml+xml,text/plain,application/pdf',
    }

    last_err = 'fetch_failed'
    last_meta = {'is_pdf': False, 'allow_short': False}
    for attempt in range(LINK_FETCH_MAX_RETRIES + 1):
        try:
            req = Request(canonical_url, headers=headers)
            with urlopen(req, timeout=LINK_FETCH_TIMEOUT_SEC) as resp:
                raw = resp.read(LINK_FETCH_MAX_BYTES)
                content_type = str(resp.headers.get('Content-Type', '')).lower()
                content_disposition = str(resp.headers.get('Content-Disposition', '')).lower()

            is_pdf = _looks_like_pdf_link(canonical_url, content_type, content_disposition)
            if is_pdf:
                pdf_text, pdf_origin = _extract_pdf_text_from_bytes(raw)
                last_meta = {'is_pdf': True, 'allow_short': True, 'pdf_origin': pdf_origin}
                if pdf_text:
                    LINK_RUNTIME_STATS['url_fetch_success'] += 1
                    LINK_FETCH_CACHE[canonical_url] = {'text': pdf_text, 'error': '', 'meta': last_meta}
                    return pdf_text, '', last_meta
                last_err = f'pdf_extract_failed:{pdf_origin}'
                continue

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
            LINK_FETCH_CACHE[canonical_url] = {'text': text, 'error': '', 'meta': last_meta}
            return text, '', last_meta
        except Exception as e:
            last_err = f'{type(e).__name__}:{e}'
            if attempt < LINK_FETCH_MAX_RETRIES:
                time.sleep(LINK_FETCH_BACKOFF_BASE_SEC * (2 ** attempt))

    LINK_RUNTIME_STATS['url_fetch_failure'] += 1
    LINK_FETCH_CACHE[canonical_url] = {'text': '', 'error': last_err, 'meta': last_meta}
    return '', last_err, last_meta


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


def _safe_read_json_dict(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sha1_text(text: str) -> str:
    return hashlib.sha1((text or '').encode('utf-8')).hexdigest()


def _load_stage1_link_sidecar(path: str, folder: str, source_sha1: str) -> dict:
    out = {
        'exists': False,
        'sidecar_path': '',
        'sidecar_rel_path': '',
        'canonical_urls': [],
        'blocks': [],
        'fetch_meta': {},
        'source_sha1_match': False,
    }
    sidecar_path = _sidecar_path_for_source(path, folder=folder)
    if not sidecar_path:
        return out
    out['sidecar_path'] = sidecar_path
    out['sidecar_rel_path'] = os.path.relpath(sidecar_path, RAW_BASE).replace('\\', '/')
    if not os.path.exists(sidecar_path):
        return out

    payload = _safe_read_json_dict(sidecar_path)
    if not payload:
        return out

    sidecar_source_sha1 = str(payload.get('source_sha1') or '').strip()
    source_match = bool(sidecar_source_sha1 and source_sha1 and sidecar_source_sha1 == source_sha1)
    out['source_sha1_match'] = source_match
    out['exists'] = True
    if sidecar_source_sha1 and source_sha1 and not source_match:
        return out

    canonical_urls, _ = _canonical_dedup_urls(list(payload.get('canonical_urls') or []))
    out['canonical_urls'] = canonical_urls
    out['fetch_meta'] = dict(payload.get('fetch_meta') or {})

    blocks = []
    for row in (payload.get('blocks') or []):
        if not isinstance(row, dict):
            continue
        canonical_url = _canonicalize_url(str(row.get('canonical_url') or '').strip())
        text = str(row.get('text') or '').strip()
        if not canonical_url or not text:
            continue
        blocks.append((canonical_url, text))
    out['blocks'] = blocks
    return out


def _collect_sidecar_enrichment_blocks(blocks: list[tuple[str, str]], base_effective: str) -> tuple[list[tuple[str, str]], int]:
    seen_fp = set()
    if base_effective.strip():
        seen_fp.add(_fingerprint(base_effective))

    out = []
    deduped = 0
    total_chars = 0
    for canonical_url, raw_text in blocks[:LINK_ENRICH_MAX_URLS_PER_FILE]:
        text = str(raw_text or '').strip()
        if not text:
            continue
        fp = _fingerprint(text)
        if fp in seen_fp:
            deduped += 1
            continue
        seen_fp.add(fp)
        if total_chars + len(text) > LINK_ENRICH_MAX_TOTAL_CHARS:
            allowed = max(0, LINK_ENRICH_MAX_TOTAL_CHARS - total_chars)
            text = text[:allowed].strip()
        if not text:
            continue
        out.append((canonical_url, text))
        total_chars += len(text)
        if total_chars >= LINK_ENRICH_MAX_TOTAL_CHARS:
            break
    return out, deduped


def _merge_canonical_urls(primary: list[str], secondary: list[str]) -> list[str]:
    merged, _ = _canonical_dedup_urls([*(primary or []), *(secondary or [])])
    return merged


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
        'pdf_urls': 0,
        'pdf_short_override_urls': 0,
    }

    for cu in canonical_urls[:LINK_ENRICH_MAX_URLS_PER_FILE]:
        fetch_meta['attempted_urls'] += 1
        fetched_text, fetch_error, fetch_info = _fetch_link_text(cu)
        if not fetched_text:
            if fetch_error == 'disallowed_domain':
                fetch_meta['disallowed_urls'] += 1
            elif fetch_error == 'fetched_text_too_short':
                fetch_meta['fetched_text_too_short_urls'] += 1
            else:
                fetch_meta['fetch_failed_urls'] += 1
            continue

        fetch_meta['successful_urls'] += 1
        if fetch_info.get('is_pdf'):
            fetch_meta['pdf_urls'] += 1
            if fetch_info.get('allow_short'):
                fetch_meta['pdf_short_override_urls'] += 1

        candidates = []
        min_seg_len = 1 if fetch_info.get('allow_short') else 45
        for seg in re.split(r'\n{2,}', fetched_text):
            s = re.sub(r'\s+', ' ', seg).strip()
            if len(s) < min_seg_len:
                continue
            if fetch_info.get('allow_short') and not re.search(r'[A-Za-z가-힣]', s):
                continue
            candidates.append(s)

        if fetch_info.get('allow_short') and not candidates:
            fallback = re.sub(r'\s+', ' ', fetched_text).strip()
            if fallback and re.search(r'[A-Za-z가-힣]', fallback):
                candidates.append(fallback)

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
        text_for_clean = raw_content
        pdf_meta = {
            'pdf_promoted': False,
            'pdf_status': 'parse_failed',
            'pdf_source': '',
            'pdf_chars_added': 0,
            'pdf_nonempty_lines_added': 0,
            'declared_page_count': 0,
            'indexed_page_rows': 0,
            'materialized_text_pages': 0,
            'materialized_render_pages': 0,
            'placeholder_page_rows': 0,
            'bounded_by_cap': False,
        }
        if normalized_folder == 'text/telegram':
            text_for_clean, pdf_meta = _promote_telegram_pdf_content(raw_content, path)

        source_sha1 = _sha1_text(raw_content)
        sidecar_meta = _load_stage1_link_sidecar(path, folder=normalized_folder, source_sha1=source_sha1)
        sidecar_urls = list(sidecar_meta.get('canonical_urls') or [])
        if sidecar_meta.get('exists'):
            LINK_RUNTIME_STATS['stage1_sidecar_seen_files'] += 1
            LINK_RUNTIME_STATS['stage1_sidecar_canonical_urls_total'] += len(sidecar_urls)

        cleaned_content = _strip_attachment_residue(text_for_clean)
        common_meta = {
            'sidecar_canonical_urls': sidecar_urls,
            'sidecar_rel_path': sidecar_meta.get('sidecar_rel_path', ''),
            'sidecar_source_sha1_match': bool(sidecar_meta.get('source_sha1_match')),
            **pdf_meta,
        }

        ok, reason, ctx = _validate_text_by_folder(cleaned_content, normalized_folder)
        if ok:
            return cleaned_content, None, {
                'link_enriched': False,
                'canonical_urls': len(sidecar_urls),
                'attachment_residue_removed': cleaned_content != raw_content,
                **common_meta,
            }

        if normalized_folder == 'text/telegram' and pdf_meta.get('pdf_promoted') and _is_short_reason(reason):
            return cleaned_content, None, {
                'link_enriched': False,
                'canonical_urls': len(sidecar_urls),
                'attachment_residue_removed': cleaned_content != raw_content,
                'pdf_short_override': True,
                **common_meta,
            }

        if not STAGE2_ENABLE_LINK_ENRICHMENT:
            return None, reason, {
                'link_enriched': False,
                'link_enrichment_enabled': False,
                **common_meta,
            }

        if normalized_folder not in TARGET_LINK_ENRICH_FOLDERS or not _is_short_reason(reason):
            return None, reason, common_meta

        link_source_text = _build_link_source_text(text_for_clean, attach_text)
        raw_urls = _extract_urls(link_source_text)
        LINK_RUNTIME_STATS['url_raw_extracted_total'] += len(raw_urls)
        canonical_urls_raw, deduped_raw = _canonical_dedup_urls(raw_urls)
        canonical_urls = _merge_canonical_urls(sidecar_urls, canonical_urls_raw)
        deduped_total = max(0, (len(sidecar_urls) + len(canonical_urls_raw)) - len(canonical_urls)) + deduped_raw
        LINK_RUNTIME_STATS['url_canonical_total'] += len(canonical_urls)
        LINK_RUNTIME_STATS['url_deduped_within_file'] += deduped_total

        if not _needs_link_enrichment(cleaned_content, ctx.get('effective', ''), int(ctx.get('min_len', 0)), len(canonical_urls)):
            return None, reason, common_meta

        LINK_RUNTIME_STATS['enrichment_attempt_files'] += 1

        sidecar_blocks, sidecar_block_dedup = _collect_sidecar_enrichment_blocks(
            list(sidecar_meta.get('blocks') or []),
            str(ctx.get('effective', '') or ''),
        )
        if sidecar_blocks:
            LINK_RUNTIME_STATS['content_fingerprint_dedup'] += sidecar_block_dedup
            fetch_meta = {
                'attempted_urls': int((sidecar_meta.get('fetch_meta') or {}).get('attempted_urls', len(canonical_urls))),
                'successful_urls': int((sidecar_meta.get('fetch_meta') or {}).get('successful_urls', len(sidecar_blocks))),
                'fetch_failed_urls': int((sidecar_meta.get('fetch_meta') or {}).get('fetch_failed_urls', 0)),
                'disallowed_urls': int((sidecar_meta.get('fetch_meta') or {}).get('disallowed_urls', 0)),
                'fetched_text_too_short_urls': int((sidecar_meta.get('fetch_meta') or {}).get('fetched_text_too_short_urls', 0)),
                'pdf_urls': int((sidecar_meta.get('fetch_meta') or {}).get('pdf_urls', 0)),
                'pdf_short_override_urls': int((sidecar_meta.get('fetch_meta') or {}).get('pdf_short_override_urls', 0)),
                'source': 'stage1_sidecar',
            }
            enriched_content = _inject_enriched_content(cleaned_content, normalized_folder, sidecar_blocks, canonical_urls)
            ok2, reason2, _ = _validate_text_by_folder(enriched_content, normalized_folder)
            if ok2 or (fetch_meta.get('pdf_short_override_urls', 0) > 0 and _is_short_reason(reason2)):
                LINK_RUNTIME_STATS['enrichment_applied_files'] += 1
                LINK_RUNTIME_STATS['enrichment_promoted_files'] += 1
                LINK_RUNTIME_STATS['stage1_sidecar_promoted_files'] += 1
                return enriched_content, None, {
                    'link_enriched': True,
                    'canonical_urls': len(canonical_urls),
                    'enriched_blocks': len(sidecar_blocks),
                    'attachment_residue_removed': cleaned_content != raw_content,
                    'pdf_short_override': fetch_meta.get('pdf_short_override_urls', 0) > 0 and _is_short_reason(reason2),
                    **fetch_meta,
                    **common_meta,
                }

        if not STAGE2_ENABLE_LIVE_LINK_FETCH:
            LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
            return None, reason, {
                'link_enriched': False,
                'live_link_fetch_enabled': False,
                **common_meta,
            }

        blocks, content_dup_count, fetch_meta = _collect_unique_enrichment_blocks(canonical_urls, ctx.get('effective', ''))
        LINK_RUNTIME_STATS['content_fingerprint_dedup'] += content_dup_count
        if not blocks:
            LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
            if fetch_meta.get('attempted_urls', 0) > 0 and fetch_meta.get('successful_urls', 0) == 0 and fetch_meta.get('fetch_failed_urls', 0) > 0:
                return None, _link_fetch_failure_reason(normalized_folder), {'link_enriched': False, **fetch_meta, **common_meta}
            return None, reason, {'link_enriched': False, **fetch_meta, **common_meta}

        enriched_content = _inject_enriched_content(cleaned_content, normalized_folder, blocks, canonical_urls)
        ok2, reason2, _ = _validate_text_by_folder(enriched_content, normalized_folder)
        if ok2 or (fetch_meta.get('pdf_short_override_urls', 0) > 0 and _is_short_reason(reason2)):
            LINK_RUNTIME_STATS['enrichment_applied_files'] += 1
            LINK_RUNTIME_STATS['enrichment_promoted_files'] += 1
            return enriched_content, None, {
                'link_enriched': True,
                'canonical_urls': len(canonical_urls),
                'enriched_blocks': len(blocks),
                'attachment_residue_removed': cleaned_content != raw_content,
                'pdf_short_override': fetch_meta.get('pdf_short_override_urls', 0) > 0 and _is_short_reason(reason2),
                **fetch_meta,
                **common_meta,
            }

        LINK_RUNTIME_STATS['enrichment_still_quarantined_files'] += 1
        return None, reason2, {**fetch_meta, **common_meta}
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


def _build_text_dedup_signals(content: str, folder: str, sidecar_canonical_urls: list[str] | None = None) -> dict:
    title = _extract_text_title(content)
    date = _extract_text_date(content)
    normalized_title = _normalize_title_text(title)
    title_date_keys = [f'{date}|{normalized_title}'] if date and _should_use_title_date_key(folder, title) else []
    effective = _extract_text_effective_for_dedup(content, folder)
    canonical_urls = _extract_text_canonical_urls(content)
    normalized_folder = _normalize_folder(folder)
    if normalized_folder in {'text/blog', 'text/telegram'} and sidecar_canonical_urls:
        canonical_urls = _merge_canonical_urls(sidecar_canonical_urls, canonical_urls)
    return {
        'title': title,
        'date': date,
        'canonical_urls': canonical_urls,
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

        clean_row['stage2_classification'] = _build_selected_article_classification(clean_row)
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


def repair_selected_articles_clean_classification(clean_base: str | None = None) -> tuple[str, dict]:
    base_dir = clean_base or os.path.join(CLEAN_BASE, 'production')
    folder = 'market/news/selected_articles'
    folder_dir = _output_paths(base_dir, folder, '')[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(REPORT_DIR, f'SELECTED_ARTICLES_CLASSIFICATION_REPAIR_{timestamp}.json')
    stats = {
        'folder': folder,
        'clean_base': base_dir,
        'classification_version': CLASSIFICATION_VERSION,
        'semantic_version': SEMANTIC_SCHEMA_VERSION,
        'files_seen': 0,
        'files_updated': 0,
        'rows_reclassified': 0,
        'sidecars_written': 0,
        'parse_error_files': [],
        'updated_files': [],
        'sidecar_only_files': [],
    }
    if not os.path.isdir(folder_dir):
        payload = {**stats, 'status': 'missing_clean_folder', 'folder_dir': folder_dir}
        _write_json(payload, [report_path])
        return report_path, payload

    for path in sorted(glob.glob(os.path.join(folder_dir, '*.jsonl'))):
        stats['files_seen'] += 1
        rows, errors = _read_jsonl_records(path)
        if errors:
            stats['parse_error_files'].append({'path': path, 'errors': errors[:5]})
            continue
        changed = False
        for row in rows:
            classification = row.get('stage2_classification')
            if not isinstance(classification, dict) or classification.get('classification_version') != CLASSIFICATION_VERSION or classification.get('semantic_version') != SEMANTIC_SCHEMA_VERSION:
                row['stage2_classification'] = _build_selected_article_classification(row)
                stats['rows_reclassified'] += 1
                changed = True
        sidecar_path = f'{path}.classification.json'
        sidecar_missing = not os.path.exists(sidecar_path)
        if changed:
            _write_jsonl(rows, [path])
            stats['files_updated'] += 1
            stats['updated_files'].append(path)
        if changed or sidecar_missing:
            _write_json(_build_selected_articles_classification_summary(rows, path), [sidecar_path])
            stats['sidecars_written'] += 1
            if sidecar_missing and not changed:
                stats['sidecar_only_files'].append(path)

    payload = {
        **stats,
        'status': 'ok',
        'files_with_parse_errors': len(stats['parse_error_files']),
    }
    _write_json(payload, [report_path])
    return report_path, payload


def _bootstrap_corpus_dedup_registry(registry: dict, clean_base: str, target_folders: list[str] | None = None):
    bootstrap_scope = sorted(set(target_folders or DEDUP_TARGET_FOLDERS) & set(DEDUP_TARGET_FOLDERS))
    for folder in bootstrap_scope:
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
                    raw_source_path = os.path.join(_resolve_raw_dir(folder), rel_path)
                    sidecar_urls = list(_load_stage1_link_sidecar(raw_source_path, folder=folder, source_sha1='').get('canonical_urls') or [])
                    if sidecar_urls and _normalize_folder(folder) in {'text/blog', 'text/telegram'}:
                        LINK_RUNTIME_STATS['stage1_sidecar_dedup_signal_files'] += 1
                    signals = _build_text_dedup_signals(content, folder, sidecar_canonical_urls=sidecar_urls)
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


def run_full_refine(force_rebuild: bool = False, folders: list[str] | None = None):
    global LINK_FETCH_CACHE, LINK_RUNTIME_STATS

    _enforce_input_source_policy()
    LINK_FETCH_CACHE = {}
    LINK_RUNTIME_STATS = _new_link_runtime_stats()

    target_folders = list(folders or FOLDERS)
    results = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    final_clean_base = os.path.join(CLEAN_BASE, 'production')
    final_q_base = os.path.join(Q_BASE, 'production')
    run_mode = 'force_rebuild' if force_rebuild else 'incremental'
    if force_rebuild:
        processed_index = {}
        if target_folders == list(FOLDERS):
            _reset_output_tree(final_clean_base)
            _reset_output_tree(final_q_base)
        else:
            for folder in target_folders:
                shutil.rmtree(_output_paths(final_clean_base, folder, '')[0], ignore_errors=True)
                shutil.rmtree(_output_paths(final_q_base, folder, '')[0], ignore_errors=True)
        processed_index_meta = _current_index_meta()
    else:
        processed_index, processed_index_meta = _load_processed_index()

    current_index_meta = _current_index_meta()
    processed_index_meta_matches = processed_index_meta == current_index_meta

    total_exceptions = 0
    hard_fail_issues = []
    report_only_issues = []
    corpus_dedup_registry = _new_corpus_dedup_registry()
    if not force_rebuild:
        _bootstrap_corpus_dedup_registry(corpus_dedup_registry, final_clean_base, target_folders=target_folders)

    for folder in target_folders:
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
            has_clean_output = any(os.path.exists(p) for p in clean_paths)
            has_quarantine_output = any(os.path.exists(p) for p in q_paths)
            outputs_ready = has_quarantine_output or (has_clean_output and _classification_sidecar_exists(ext, folder, clean_paths))
            if (not force_rebuild) and processed_index_meta_matches and prev_sig == sig and outputs_ready:
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
                    classification_sidecar_path = _classification_output_path(final_clean_base, folder, rel_path)
                    if clean_rows:
                        _write_jsonl(clean_rows, clean_paths)
                        _write_json(_build_selected_articles_classification_summary(clean_rows, f), [classification_sidecar_path])
                        clean_count += 1
                    else:
                        for p in clean_paths:
                            _remove_if_exists(p)
                        _remove_if_exists(classification_sidecar_path)
                    if quarantine_rows:
                        _write_jsonl(quarantine_rows, q_paths)
                        q_count += 1
                    else:
                        for p in q_paths:
                            _remove_if_exists(p)
                else:
                    content, err, meta = sanitize_text(f, folder=folder)
                    if content is not None:
                        duplicate = None
                        normalized_folder = _normalize_folder(folder)
                        if normalized_folder in DEDUP_TARGET_FOLDERS:
                            sidecar_urls_for_dedup = list((meta or {}).get('sidecar_canonical_urls') or [])
                            if sidecar_urls_for_dedup and normalized_folder in {'text/blog', 'text/telegram'}:
                                LINK_RUNTIME_STATS['stage1_sidecar_dedup_signal_files'] += 1
                            signals = _build_text_dedup_signals(content, folder, sidecar_canonical_urls=sidecar_urls_for_dedup)
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
                        classification_sidecar_path = _classification_output_path(final_clean_base, folder, rel_path)
                        if duplicate is None:
                            _write_text(content, clean_paths)
                            if _folder_bucket(folder) == 'qualitative':
                                _write_json(_build_text_classification_payload(content, folder, f), [classification_sidecar_path])
                            for p in q_paths:
                                _remove_if_exists(p)
                            clean_count += 1
                        else:
                            for p in clean_paths:
                                _remove_if_exists(p)
                            _remove_if_exists(classification_sidecar_path)
                            payload = _build_text_quarantine_payload(
                                folder=folder,
                                source_file=f,
                                reason=f"duplicate_{duplicate['kind']}",
                                raw_text=content,
                                extra_meta={**_duplicate_meta(duplicate), **(meta or {})},
                            )
                            _write_text(payload, q_paths)
                            q_count += 1
                    else:
                        for p in clean_paths:
                            _remove_if_exists(p)
                        _remove_if_exists(_classification_output_path(final_clean_base, folder, rel_path))
                        raw_text = _safe_read_text(f, max_chars=12000)
                        payload = _build_text_quarantine_payload(
                            folder=folder,
                            source_file=f,
                            reason=err or 'invalid_text',
                            raw_text=raw_text,
                            extra_meta=meta or {},
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
    dedup_urls_total = int(LINK_RUNTIME_STATS.get('url_deduped_within_file', 0) + LINK_RUNTIME_STATS.get('url_cache_hits', 0))
    integrity_summary, pdf_status_buckets, bounded_stop_visibility, legacy_join_visibility, stage3_ready_status, origin_of_degradation = _build_stage2_integrity_summary(
        results=results,
        total_exceptions=total_exceptions,
        hard_fail_issues=hard_fail_issues,
    )

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
        f.write(f"- Input Source: {STAGE2_INPUT_SOURCE}\n")
        f.write(f"- Input Source Status: {STAGE2_INPUT_SOURCE_STATUS}\n")
        f.write(f"- Fallback Reason: {STAGE2_FALLBACK_REASON}\n")
        f.write(f"- Fallback Scope: {STAGE2_FALLBACK_SCOPE}\n")
        f.write(f"- Raw-files fallback opt-in: {STAGE2_ALLOW_RAW_FILES_FALLBACK}\n")
        f.write(f"- Raw Base: {RAW_BASE}\n")
        f.write(f"- Clean Base: {final_clean_base}\n")
        f.write(f"- Quarantine Base: {final_q_base}\n")
        f.write("- Writer policy: market signal + qualitative canonical writer=`stage02_onepass_refine_full.py`, kr/us signal canonical writer=`stage02_qc_cleaning_full.py`\n")
        f.write("- Output policy: canonical=`production/(signal|qualitative)/*` only\n")
        f.write(f"- Link enrichment enabled: {STAGE2_ENABLE_LINK_ENRICHMENT}\n")
        f.write(f"- Live link fetch fallback enabled: {STAGE2_ENABLE_LIVE_LINK_FETCH}\n\n")
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

        f.write("\n## Link Enrichment / Dedup Stats\n\n")
        f.write(f"- enrichment_attempt_files={int(LINK_RUNTIME_STATS.get('enrichment_attempt_files', 0))}\n")
        f.write(f"- enrichment_applied_files={int(LINK_RUNTIME_STATS.get('enrichment_applied_files', 0))}\n")
        f.write(f"- enrichment_promoted_files={int(LINK_RUNTIME_STATS.get('enrichment_promoted_files', 0))}\n")
        f.write(f"- enrichment_still_quarantined_files={int(LINK_RUNTIME_STATS.get('enrichment_still_quarantined_files', 0))}\n")
        f.write(f"- stage1_sidecar_seen_files={int(LINK_RUNTIME_STATS.get('stage1_sidecar_seen_files', 0))}\n")
        f.write(f"- stage1_sidecar_canonical_urls_total={int(LINK_RUNTIME_STATS.get('stage1_sidecar_canonical_urls_total', 0))}\n")
        f.write(f"- stage1_sidecar_promoted_files={int(LINK_RUNTIME_STATS.get('stage1_sidecar_promoted_files', 0))}\n")
        f.write(f"- stage1_sidecar_dedup_signal_files={int(LINK_RUNTIME_STATS.get('stage1_sidecar_dedup_signal_files', 0))}\n")
        f.write(f"- url_raw_extracted_total={int(LINK_RUNTIME_STATS.get('url_raw_extracted_total', 0))}\n")
        f.write(f"- url_canonical_total={int(LINK_RUNTIME_STATS.get('url_canonical_total', 0))}\n")
        f.write(f"- url_deduped_within_file={int(LINK_RUNTIME_STATS.get('url_deduped_within_file', 0))}\n")
        f.write(f"- url_cache_hits={int(LINK_RUNTIME_STATS.get('url_cache_hits', 0))}\n")
        f.write(f"- deduped_url_total={dedup_urls_total}\n")
        f.write(f"- url_fetch_success={int(LINK_RUNTIME_STATS.get('url_fetch_success', 0))}\n")
        f.write(f"- url_fetch_failure={int(LINK_RUNTIME_STATS.get('url_fetch_failure', 0))}\n")
        f.write(f"- url_disallowed={int(LINK_RUNTIME_STATS.get('url_disallowed', 0))}\n")
        f.write(f"- content_fingerprint_dedup={int(LINK_RUNTIME_STATS.get('content_fingerprint_dedup', 0))}\n")
        f.write("\n## Telegram PDF Promotion\n\n")
        f.write(f"- telegram_pdf_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_total', 0))}\n")
        f.write(f"- telegram_pdf_stage1_extract_reused={int(LINK_RUNTIME_STATS.get('telegram_pdf_stage1_extract_reused', 0))}\n")
        f.write(f"- telegram_pdf_stage2_extract_ok={int(LINK_RUNTIME_STATS.get('telegram_pdf_stage2_extract_ok', 0))}\n")
        f.write(f"- telegram_pdf_extract_failed={int(LINK_RUNTIME_STATS.get('telegram_pdf_extract_failed', 0))}\n")
        f.write(f"- telegram_pdf_messages_promoted_by_pdf={int(LINK_RUNTIME_STATS.get('telegram_pdf_messages_promoted_by_pdf', 0))}\n")
        f.write(f"- telegram_pdf_chars_added_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_chars_added_total', 0))}\n")
        f.write(f"- telegram_pdf_path_resolution_marker={int(LINK_RUNTIME_STATS.get('telegram_pdf_path_resolution_marker', 0))}\n")
        f.write(f"- telegram_pdf_path_resolution_fallback={int(LINK_RUNTIME_STATS.get('telegram_pdf_path_resolution_fallback', 0))}\n")
        f.write(f"- telegram_pdf_orphan_artifacts={int(LINK_RUNTIME_STATS.get('telegram_pdf_orphan_artifacts', 0))}\n")
        f.write(f"- telegram_pdf_status_promoted={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_promoted', 0))}\n")
        f.write(f"- telegram_pdf_status_bounded_by_cap={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_bounded_by_cap', 0))}\n")
        f.write(f"- telegram_pdf_status_recoverable_missing_artifact={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_recoverable_missing_artifact', 0))}\n")
        f.write(f"- telegram_pdf_status_extractor_unavailable={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_extractor_unavailable', 0))}\n")
        f.write(f"- telegram_pdf_status_parse_failed={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_parse_failed', 0))}\n")
        f.write(f"- telegram_pdf_status_placeholder_only={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_placeholder_only', 0))}\n")
        f.write(f"- telegram_pdf_status_lineage_mismatch={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_lineage_mismatch', 0))}\n")
        f.write(f"- telegram_pdf_status_diagnostics_only={int(LINK_RUNTIME_STATS.get('telegram_pdf_status_diagnostics_only', 0))}\n")
        f.write(f"- telegram_pdf_declared_page_count_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_declared_page_count_total', 0))}\n")
        f.write(f"- telegram_pdf_indexed_page_rows_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_indexed_page_rows_total', 0))}\n")
        f.write(f"- telegram_pdf_materialized_text_pages_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_materialized_text_pages_total', 0))}\n")
        f.write(f"- telegram_pdf_materialized_render_pages_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_materialized_render_pages_total', 0))}\n")
        f.write(f"- telegram_pdf_placeholder_page_rows_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_placeholder_page_rows_total', 0))}\n")
        f.write(f"- telegram_pdf_bounded_by_cap_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_bounded_by_cap_total', 0))}\n")
        f.write(f"- telegram_pdf_bounded_by_cap_docs={int(LINK_RUNTIME_STATS.get('telegram_pdf_bounded_by_cap_docs', 0))}\n")
        f.write(f"- telegram_pdf_bounded_pages_total={int(LINK_RUNTIME_STATS.get('telegram_pdf_bounded_pages_total', 0))}\n")
        f.write(f"- telegram_pdf_join_strategy_canonical_marker={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_canonical_marker', 0))}\n")
        f.write(f"- telegram_pdf_join_strategy_canonical_flat={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_canonical_flat', 0))}\n")
        f.write(f"- telegram_pdf_join_strategy_legacy_dir={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_legacy_dir', 0))}\n")
        f.write(f"- telegram_pdf_join_strategy_recovered_local_extract={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_strategy_recovered_local_extract', 0))}\n")
        f.write(f"- telegram_pdf_join_confidence_strong={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_confidence_strong', 0))}\n")
        f.write(f"- telegram_pdf_join_confidence_medium={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_confidence_medium', 0))}\n")
        f.write(f"- telegram_pdf_join_confidence_weak={int(LINK_RUNTIME_STATS.get('telegram_pdf_join_confidence_weak', 0))}\n")
        f.write(f"- telegram_pdf_lineage_status_confirmed={int(LINK_RUNTIME_STATS.get('telegram_pdf_lineage_status_confirmed', 0))}\n")
        f.write(f"- telegram_pdf_lineage_status_probable={int(LINK_RUNTIME_STATS.get('telegram_pdf_lineage_status_probable', 0))}\n")
        f.write(f"- telegram_pdf_lineage_status_unresolved={int(LINK_RUNTIME_STATS.get('telegram_pdf_lineage_status_unresolved', 0))}\n")
        f.write(f"- origin_of_degradation={origin_of_degradation}\n")
        f.write(f"- stage3_ready_status={stage3_ready_status}\n")
        f.write(f"- handoff_status={integrity_summary['handoff_completeness']['handoff_status']}\n")
        f.write("\n## Industry / Stock Classification\n\n")
        f.write(f"- classification_version={CLASSIFICATION_VERSION}\n")
        f.write(f"- documents_classified={int(CLASSIFICATION_RUNTIME_STATS.get('documents_classified', 0))}\n")
        f.write(f"- documents_with_stock={int(CLASSIFICATION_RUNTIME_STATS.get('documents_with_stock', 0))}\n")
        f.write(f"- documents_with_industry={int(CLASSIFICATION_RUNTIME_STATS.get('documents_with_industry', 0))}\n")
        f.write(f"- selected_articles_rows_classified={int(CLASSIFICATION_RUNTIME_STATS.get('selected_articles_rows_classified', 0))}\n")
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

    payload = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stage2_rule_version': STAGE2_RULE_VERSION,
        'run_mode': run_mode,
        'processed_index_policy': 'reset' if force_rebuild else 'reuse_if_signature_matches',
        'incremental_signature': {
            'salt': STAGE2_RULE_VERSION,
            'config_bundle_sha1': STAGE2_CONFIG_PROVENANCE['bundle_sha1'],
            'link_enrichment_enabled': STAGE2_ENABLE_LINK_ENRICHMENT,
            'live_link_fetch_enabled': STAGE2_ENABLE_LIVE_LINK_FETCH,
            'strategy': 'size+mtime+path+rule_version+config_bundle_sha1+link_enrichment_flag+live_link_fetch_flag+telegram_attachment_subtree_for_text_telegram+stage1_link_sidecar_sig',
        },
        'config_provenance': STAGE2_CONFIG_PROVENANCE,
        'input_source': STAGE2_INPUT_SOURCE,
        'input_source_status': STAGE2_INPUT_SOURCE_STATUS,
        'fallback_reason': STAGE2_FALLBACK_REASON,
        'fallback_scope': STAGE2_FALLBACK_SCOPE,
        'input_source_policy': _input_source_policy_payload(),
        'origin_of_degradation': origin_of_degradation,
        'stage3_ready_status': stage3_ready_status,
        'pdf_status_buckets': pdf_status_buckets,
        'bounded_stop_visibility': bounded_stop_visibility,
        'legacy_join_visibility': legacy_join_visibility,
        'handoff_completeness': integrity_summary['handoff_completeness'],
        'integrity_summary_path': INTEGRITY_SUMMARY_PATH,
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
            'live_link_fetch_enabled': STAGE2_ENABLE_LIVE_LINK_FETCH,
            **{k: int(v) for k, v in LINK_RUNTIME_STATS.items()},
            'deduped_url_total': dedup_urls_total,
        },
        'telegram_pdf': {
            'telegram_pdf_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_total', 0)),
            'telegram_pdf_stage1_extract_reused': int(LINK_RUNTIME_STATS.get('telegram_pdf_stage1_extract_reused', 0)),
            'telegram_pdf_stage2_extract_ok': int(LINK_RUNTIME_STATS.get('telegram_pdf_stage2_extract_ok', 0)),
            'telegram_pdf_extract_failed': int(LINK_RUNTIME_STATS.get('telegram_pdf_extract_failed', 0)),
            'telegram_pdf_messages_promoted_by_pdf': int(LINK_RUNTIME_STATS.get('telegram_pdf_messages_promoted_by_pdf', 0)),
            'telegram_pdf_chars_added_total': int(LINK_RUNTIME_STATS.get('telegram_pdf_chars_added_total', 0)),
            'telegram_pdf_path_resolution_marker': int(LINK_RUNTIME_STATS.get('telegram_pdf_path_resolution_marker', 0)),
            'telegram_pdf_path_resolution_fallback': int(LINK_RUNTIME_STATS.get('telegram_pdf_path_resolution_fallback', 0)),
            'telegram_pdf_orphan_artifacts': int(LINK_RUNTIME_STATS.get('telegram_pdf_orphan_artifacts', 0)),
            'status_counts': pdf_status_buckets,
            'page_counters': bounded_stop_visibility,
            'join_visibility': legacy_join_visibility,
        },
        'classification': {
            'classification_version': CLASSIFICATION_VERSION,
            **{k: int(v) for k, v in CLASSIFICATION_RUNTIME_STATS.items()},
            'industry_taxonomy_labels': sorted(INDUSTRY_KEYWORDS.keys()),
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
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(INTEGRITY_SUMMARY_PATH, 'w', encoding='utf-8') as jf:
        json.dump(integrity_summary, jf, ensure_ascii=False, indent=2)

    _save_processed_index(processed_index)
    print(f"Full refinement report: {report_path}")
    print(f"Full refinement report json: {report_json_path}")
    print(f"Stage2 integrity summary: {INTEGRITY_SUMMARY_PATH}")
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
    parser.add_argument(
        '--folders',
        default='',
        help='Comma-separated Stage2 folder subset to process (for example: market/news/selected_articles,text/blog).',
    )
    parser.add_argument(
        '--repair-selected-articles-clean',
        action='store_true',
        help='Backfill row-level stage2_classification and *.classification.json sidecars for existing clean selected_articles JSONL outputs.',
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.repair_selected_articles_clean:
        report_path, _payload = repair_selected_articles_clean_classification()
        print(f'Selected articles clean classification repair report: {report_path}')
    else:
        run_full_refine(force_rebuild=args.force_rebuild, folders=_parse_folder_targets(args.folders))
