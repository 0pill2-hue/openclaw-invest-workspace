from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import tempfile
import time
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

ROOT_PATH = Path(__file__).resolve().parents[4]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from invest.stages.stage2.scripts.stage2_config import load_stage2_config_bundle

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

STAGE1_DIR = ROOT_PATH / 'invest/stages/stage1'
RAW_ROOT = STAGE1_DIR / 'outputs/raw'
SIDECAR_ROOT = RAW_ROOT / 'qualitative/link_enrichment'
RUNTIME_DIR = STAGE1_DIR / 'outputs/runtime'
STATUS_PATH = RUNTIME_DIR / 'link_enrich_sidecar_status.json'
RULE_VERSION = 'stage1-link-sidecar-20260311-r1'

CONFIG_BUNDLE = load_stage2_config_bundle()
RUNTIME_CONFIG = CONFIG_BUNDLE['runtime']
REFINE_CONFIG = RUNTIME_CONFIG['refine']
TEXT_VALIDATION_CONFIG = REFINE_CONFIG['text_validation']
FILTER_CONFIG = REFINE_CONFIG['filters']
LINK_ENRICHMENT_CONFIG = REFINE_CONFIG['link_enrichment']

TARGET_FOLDERS = tuple(LINK_ENRICHMENT_CONFIG['target_folders'])
BLOG_UI_MARKERS = tuple(FILTER_CONFIG['blog_ui_markers'])
PREMIUM_BOILERPLATE_MARKERS = tuple(FILTER_CONFIG['premium_boilerplate_markers'])
ATTACHMENT_CLEANUP_CONFIG = FILTER_CONFIG.get('attachment_cleanup', {})
ATTACHMENT_DROP_LINE_PATTERNS = tuple(ATTACHMENT_CLEANUP_CONFIG.get('drop_line_patterns', []))
ATTACHMENT_DROP_BLOCK_PATTERNS = tuple(ATTACHMENT_CLEANUP_CONFIG.get('drop_block_patterns', []))
TRACKING_QUERY_PREFIXES = tuple(FILTER_CONFIG['tracking_query_prefixes'])
ALLOWED_LINK_DOMAIN_SUFFIXES = tuple(FILTER_CONFIG['allowed_link_domain_suffixes'])
BLOCKED_LINK_DOMAIN_SUFFIXES = tuple(FILTER_CONFIG['blocked_link_domain_suffixes'])
LINK_ENRICH_ALLOW_ALL_DOMAINS = os.environ.get(
    'LINK_ENRICH_ALLOW_ALL_DOMAINS',
    '1' if LINK_ENRICHMENT_CONFIG.get('allow_all_domains_default', True) else '0',
).strip().lower() in ('1', 'true', 'yes')

BLOG_MIN_EFFECTIVE_LEN = int(TEXT_VALIDATION_CONFIG['blog_min_effective_len'])
TELEGRAM_MIN_EFFECTIVE_LEN = int(TEXT_VALIDATION_CONFIG['telegram_min_effective_len'])
PREMIUM_MIN_EFFECTIVE_LEN = int(TEXT_VALIDATION_CONFIG['premium_min_effective_len'])
SHORT_MEANINGFUL_MIN_LEN = int(TEXT_VALIDATION_CONFIG['short_meaningful_min_len'])

LINK_FETCH_TIMEOUT_SEC = int(LINK_ENRICHMENT_CONFIG['fetch_timeout_sec'])
LINK_FETCH_MAX_RETRIES = int(LINK_ENRICHMENT_CONFIG['fetch_max_retries'])
LINK_FETCH_BACKOFF_BASE_SEC = float(LINK_ENRICHMENT_CONFIG['fetch_backoff_base_sec'])
LINK_FETCH_MAX_BYTES = int(LINK_ENRICHMENT_CONFIG['fetch_max_bytes'])
LINK_FETCH_MAX_TEXT_CHARS = int(LINK_ENRICHMENT_CONFIG['fetch_max_text_chars'])
LINK_ENRICH_MAX_URLS_PER_FILE = int(LINK_ENRICHMENT_CONFIG['max_urls_per_file'])
LINK_ENRICH_MAX_TOTAL_CHARS = int(LINK_ENRICHMENT_CONFIG['max_total_chars'])
LINK_ENRICH_MIN_EFFECTIVE_ADD = int(LINK_ENRICHMENT_CONFIG['min_effective_add'])
LINK_FETCH_ENABLE = os.environ.get('STAGE1_LINK_FETCH_ENABLE', '1').strip().lower() in ('1', 'true', 'yes')

URL_PATTERN = re.compile(r'https?://[^\s<>()\[\]{}"\']+', flags=re.IGNORECASE)
ATTACH_TEXT_BLOCK_RE = re.compile(r'(?is)\[ATTACH_TEXT\]\s*(.*?)\s*\[/ATTACH_TEXT\]')


@dataclass(frozen=True)
class FolderValidation:
    normalized_folder: str
    ok: bool
    reason: str
    effective: str
    min_len: int


def _sha1_text(text: str) -> str:
    return hashlib.sha1((text or '').encode('utf-8')).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_folder(folder: str) -> str:
    return str(folder or '').strip().strip('/').replace('\\', '/')


def _folder_root(folder: str) -> Path:
    return RAW_ROOT / 'qualitative' / _normalize_folder(folder)


def _sidecar_path(source_path: Path, folder: str) -> Path:
    rel = source_path.relative_to(_folder_root(folder))
    return SIDECAR_ROOT / _normalize_folder(folder) / rel.parent / f'{rel.name}.json'


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists() or path.is_symlink():
            path.unlink()
    except Exception:
        pass


def _normalize_url(url: str) -> str:
    raw = str(url or '').strip().strip('"\'()[]{}<>')
    raw = raw.rstrip('.,);]\'"')
    return raw


def _canonicalize_url(url: str) -> str:
    raw = _normalize_url(url)
    if not raw:
        return ''
    try:
        p = urlparse(raw)
    except Exception:
        return ''
    if p.scheme.lower() not in ('http', 'https'):
        return ''
    netloc = (p.netloc or '').lower()
    if not netloc:
        return ''
    if netloc.startswith('www.'):
        netloc = netloc[4:]

    path = re.sub(r'/+', '/', p.path or '/')
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')

    kept_qs = []
    for key, value in parse_qsl(p.query, keep_blank_values=True):
        k = str(key or '').strip().lower()
        if not k:
            continue
        if k.startswith(TRACKING_QUERY_PREFIXES):
            continue
        if k in {'fbclid', 'gclid', 'igshid', 'mc_cid', 'mc_eid', 'spm', 'ref', 'ref_src'}:
            continue
        kept_qs.append((k, str(value or '').strip()))

    query = urlencode(sorted(kept_qs), doseq=True)
    return urlunparse(('https', netloc, path or '/', '', query, ''))


def _is_allowed_link_url(canonical_url: str) -> bool:
    try:
        host = (urlparse(canonical_url).hostname or '').lower()
    except Exception:
        return False
    if not host:
        return False
    if any(host == blocked or host.endswith(f'.{blocked}') for blocked in BLOCKED_LINK_DOMAIN_SUFFIXES):
        return False
    if LINK_ENRICH_ALLOW_ALL_DOMAINS:
        return True
    return any(host == suffix or host.endswith(f'.{suffix}') for suffix in ALLOWED_LINK_DOMAIN_SUFFIXES)


def _text_without_urls(text: str) -> str:
    cleaned = URL_PATTERN.sub(' ', text or '')
    return re.sub(r'\s+', ' ', cleaned).strip()


def _extract_urls(text: str) -> list[str]:
    return [m.group(0).rstrip('.,);]"\'') for m in URL_PATTERN.finditer(text or '')]


def _canonical_dedup_urls(urls: list[str]) -> tuple[list[str], int]:
    canonical = []
    seen = set()
    deduped = 0
    for raw in urls:
        cu = _canonicalize_url(raw)
        if not cu:
            continue
        if cu in seen:
            deduped += 1
            continue
        seen.add(cu)
        canonical.append(cu)
    return canonical, deduped


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


def _extract_effective_lines(content: str, *, skip_patterns: list[str], marker_filters: tuple[str, ...] = ()) -> str:
    out = []
    for raw in (content or '').splitlines():
        line = raw.rstrip()
        s = line.strip()
        if s:
            if any(re.match(pat, s, flags=re.IGNORECASE) for pat in skip_patterns):
                continue
            if marker_filters and any(marker.lower() in s.lower() for marker in marker_filters):
                continue
            if re.match(r'(?i)^\[/?LinkEnrichment\]$', s):
                continue
            if re.match(r'(?i)^CanonicalURL\s*:\s*https?://\S+', s):
                continue
        out.append(line)
    text = '\n'.join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _is_meaningful_short_text(effective: str) -> bool:
    t = (effective or '').strip()
    if len(t) < SHORT_MEANINGFUL_MIN_LEN:
        return False
    if not re.search(r'[A-Za-z가-힣]', t):
        return False
    has_sentence_shape = bool(re.search(r'[.!?]|\n', t))
    finance_kw = bool(
        re.search(
            r'(실적|매출|이익|가이던스|밸류|PER|PBR|수주|계약|리스크|주가|상승|하락|증가|감소|투자|업황|현금흐름|capex|margin|guidance|earnings|revenue|profit|order|risk)',
            t,
            flags=re.IGNORECASE,
        )
    )
    return has_sentence_shape and finance_kw


def _validate_blog_text(content: str) -> FolderValidation:
    body = _extract_effective_lines(
        content,
        skip_patterns=[
            r'^#\s+', r'^(Date|PublishedDate|Source|LinkEnriched|CanonicalURLs)\s*:', r'^---$',
        ],
        marker_filters=BLOG_UI_MARKERS,
    )
    effective = _text_without_urls(body)
    if len(effective) < BLOG_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        reason = 'blog_effective_body_empty' if not effective.strip() else 'blog_effective_body_too_short'
        return FolderValidation('text/blog', False, reason, effective, BLOG_MIN_EFFECTIVE_LEN)
    return FolderValidation('text/blog', True, '', effective, BLOG_MIN_EFFECTIVE_LEN)


def _validate_telegram_text(content: str) -> FolderValidation:
    body = _extract_effective_lines(
        content,
        skip_patterns=[
            r'^#\s+', r'^(Date|Source|LinkEnriched|CanonicalURLs)\s*:', r'^---$',
            r'^Post(ID|Date|DateTime)?\s*:', r'^MessageID\s*:', r'^Forwarded from\s*:',
            r'^Views\s*:', r'^Forwards\s*:', r'^Replies\s*:', r'^PostAuthor\s*:', r'^GroupedID\s*:',
            r'^\[[A-Z0-9_]+\].*$',
        ],
    )
    effective = _text_without_urls(body)
    if len(effective) < TELEGRAM_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        reason = 'telegram_effective_body_empty' if not effective.strip() else 'telegram_effective_body_too_short'
        return FolderValidation('text/telegram', False, reason, effective, TELEGRAM_MIN_EFFECTIVE_LEN)
    return FolderValidation('text/telegram', True, '', effective, TELEGRAM_MIN_EFFECTIVE_LEN)


def _validate_premium_text(content: str) -> FolderValidation:
    parts = re.split(r'(?mi)^##\s*본문\s*$', content or '', maxsplit=1)
    body = parts[1] if len(parts) > 1 else content
    effective_body = _extract_effective_lines(body, skip_patterns=[], marker_filters=PREMIUM_BOILERPLATE_MARKERS)
    effective = _text_without_urls(effective_body)
    if len(effective) < PREMIUM_MIN_EFFECTIVE_LEN and not _is_meaningful_short_text(effective):
        reason = 'premium_effective_body_empty_or_boilerplate' if not effective.strip() else 'premium_effective_body_too_short'
        return FolderValidation('text/premium/startale', False, reason, effective, PREMIUM_MIN_EFFECTIVE_LEN)
    return FolderValidation('text/premium/startale', True, '', effective, PREMIUM_MIN_EFFECTIVE_LEN)


def _validate_by_folder(content: str, folder: str) -> FolderValidation:
    normalized = _normalize_folder(folder)
    if normalized == 'text/blog':
        return _validate_blog_text(content)
    if normalized == 'text/telegram':
        return _validate_telegram_text(content)
    if normalized == 'text/premium/startale':
        return _validate_premium_text(content)
    return FolderValidation(normalized, True, '', _text_without_urls(content or ''), 0)


def _is_short_reason(reason: str) -> bool:
    return reason in {
        'blog_effective_body_empty',
        'blog_effective_body_too_short',
        'telegram_effective_body_empty',
        'telegram_effective_body_too_short',
        'premium_effective_body_empty_or_boilerplate',
        'premium_effective_body_too_short',
    }


def _needs_body_enrichment(content: str, effective: str, min_len: int, url_count: int) -> bool:
    if url_count <= 0:
        return False
    if len((effective or '').strip()) < int(min_len or 0):
        return True
    non_ws = len(re.sub(r'\s+', '', content or ''))
    non_ws_no_url = len(re.sub(r'\s+', '', _text_without_urls(content or '')))
    if non_ws <= 0:
        return True
    return (non_ws_no_url / non_ws) < 0.55


def _normalize_for_fingerprint(text: str) -> str:
    normalized = re.sub(r'\s+', ' ', text or '').strip().lower()
    normalized = re.sub(r'[^0-9a-z가-힣 ]+', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _fingerprint(text: str) -> str:
    return hashlib.sha1(_normalize_for_fingerprint(text).encode('utf-8')).hexdigest()


def _html_to_text(html: str) -> str:
    text = re.sub(r'(?is)<script.*?>.*?</script>', ' ', html or '')
    text = re.sub(r'(?is)<style.*?>.*?</style>', ' ', text)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p\s*>', '\n', text)
    text = re.sub(r'(?is)<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\r', '', text)
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return '\n'.join(lines)[:LINK_FETCH_MAX_TEXT_CHARS].strip()


def _cleanup_pdf_text(text: str) -> str:
    lines = []
    for raw in (text or '').splitlines():
        s = re.sub(r'\s+', ' ', raw).strip()
        if not s:
            continue
        lines.append(s)
    return '\n'.join(lines)[:LINK_FETCH_MAX_TEXT_CHARS].strip()


def _extract_pdf_text_swift(path: str, max_pages: int = 25) -> tuple[str, str]:
    if sys.platform != 'darwin':
        return '', 'swift_pdfkit_non_darwin'
    if not os.path.exists(MACOS_SWIFT_BIN):
        return '', 'swift_unavailable'
    script_path = ''
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.swift', delete=False) as tf:
            tf.write(SWIFT_PDFKIT_EXTRACT_SCRIPT)
            script_path = tf.name
        proc = subprocess.run(
            [MACOS_SWIFT_BIN, script_path, path, str(max(1, max_pages))],
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
    txt = _cleanup_pdf_text(proc.stdout or '')
    return (txt, 'ok') if txt else ('', 'pdf_text_empty')


def _extract_pdf_text_from_bytes(raw: bytes) -> tuple[str, str]:
    if not raw:
        return '', 'pdf_bytes_empty'
    tmp_path = ''
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
            tf.write(raw)
            tmp_path = tf.name
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(tmp_path)
            chunks = []
            for page in reader.pages[:25]:
                try:
                    t = page.extract_text() or ''
                except Exception:
                    t = ''
                if t.strip():
                    chunks.append(t.strip())
                if len('\n\n'.join(chunks)) >= LINK_FETCH_MAX_TEXT_CHARS:
                    break
            merged = _cleanup_pdf_text('\n\n'.join(chunks))
            if merged:
                return merged, 'pypdf'
        except Exception:
            pass
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore
            txt = pdfminer_extract_text(tmp_path, maxpages=25) or ''
            cleaned = _cleanup_pdf_text(txt)
            if cleaned:
                return cleaned, 'pdfminer'
        except Exception:
            pass
        txt, reason = _extract_pdf_text_swift(tmp_path, max_pages=25)
        return (txt, reason) if txt else ('', reason)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _looks_like_pdf_link(canonical_url: str, content_type: str = '', content_disposition: str = '') -> bool:
    try:
        path = (urlparse(canonical_url).path or '').lower()
    except Exception:
        path = ''
    ct = (content_type or '').lower()
    cd = (content_disposition or '').lower()
    return path.endswith('.pdf') or 'application/pdf' in ct or ('attachment' in cd and '.pdf' in cd)


LINK_FETCH_CACHE: dict[str, dict] = {}


def _fetch_link_text(canonical_url: str) -> tuple[str, str, dict]:
    cached = LINK_FETCH_CACHE.get(canonical_url)
    if cached is not None:
        return cached.get('text', ''), cached.get('error', ''), dict(cached.get('meta') or {})
    if not _is_allowed_link_url(canonical_url):
        LINK_FETCH_CACHE[canonical_url] = {'text': '', 'error': 'disallowed_domain', 'meta': {'is_pdf': False, 'allow_short': False}}
        return '', 'disallowed_domain', {'is_pdf': False, 'allow_short': False}
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; stage1-link-sidecar/1.0)',
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
                    LINK_FETCH_CACHE[canonical_url] = {'text': pdf_text, 'error': '', 'meta': last_meta}
                    return pdf_text, '', last_meta
                last_err = f'pdf_extract_failed:{pdf_origin}'
                continue
            charset = 'utf-8'
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[-1].split(';')[0].strip()
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
            LINK_FETCH_CACHE[canonical_url] = {'text': text, 'error': '', 'meta': last_meta}
            return text, '', last_meta
        except Exception as e:
            last_err = f'{type(e).__name__}:{e}'
            if attempt < LINK_FETCH_MAX_RETRIES:
                time.sleep(LINK_FETCH_BACKOFF_BASE_SEC * (2 ** attempt))
    LINK_FETCH_CACHE[canonical_url] = {'text': '', 'error': last_err, 'meta': last_meta}
    return '', last_err, last_meta


def _collect_unique_blocks(canonical_urls: list[str], base_effective: str) -> tuple[list[dict], dict]:
    seen_fp = set()
    if base_effective.strip():
        seen_fp.add(_fingerprint(base_effective))
    blocks = []
    total_chars = 0
    content_dup_count = 0
    fetch_meta = {
        'attempted_urls': 0,
        'successful_urls': 0,
        'fetch_failed_urls': 0,
        'disallowed_urls': 0,
        'fetched_text_too_short_urls': 0,
        'pdf_urls': 0,
        'pdf_short_override_urls': 0,
        'content_fingerprint_dedup': 0,
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
        blocks.append({'canonical_url': cu, 'text': merged})
        total_chars += len(merged)
        if total_chars >= LINK_ENRICH_MAX_TOTAL_CHARS:
            break
    fetch_meta['content_fingerprint_dedup'] = content_dup_count
    return blocks, fetch_meta


def _iter_target_files(folder: str):
    root = _folder_root(folder)
    if not root.exists():
        return []
    return [p for p in sorted(root.rglob('*')) if p.is_file() and not p.name.startswith('.')]


def _load_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore')


def _process_file(source_path: Path, folder: str) -> dict:
    raw_content = _load_text(source_path)
    source_rel_path = source_path.relative_to(RAW_ROOT).as_posix()
    source_sha1 = _sha1_text(raw_content)
    cleaned_content = _strip_attachment_residue(raw_content)
    validation = _validate_by_folder(cleaned_content, folder)
    attach_text = _extract_attach_text(raw_content)
    link_source_text = raw_content if not attach_text else f'{raw_content}\n{attach_text}'
    raw_urls = _extract_urls(link_source_text)
    canonical_urls, url_deduped = _canonical_dedup_urls(raw_urls)
    sidecar_path = _sidecar_path(source_path, folder)

    summary = {
        'folder': _normalize_folder(folder),
        'source_rel_path': source_rel_path,
        'source_sha1': source_sha1,
        'source_size_bytes': len(raw_content.encode('utf-8')),
        'source_mtime_ns': source_path.stat().st_mtime_ns,
        'raw_url_count': len(raw_urls),
        'canonical_url_count': len(canonical_urls),
        'url_deduped_within_file': url_deduped,
        'body_validation_ok': validation.ok,
        'body_validation_reason': validation.reason,
        'body_enrichment_needed': False,
        'link_fetch_enabled': bool(LINK_FETCH_ENABLE),
        'blocks': [],
        'fetch_meta': {
            'attempted_urls': 0,
            'successful_urls': 0,
            'fetch_failed_urls': 0,
            'disallowed_urls': 0,
            'fetched_text_too_short_urls': 0,
            'pdf_urls': 0,
            'pdf_short_override_urls': 0,
            'content_fingerprint_dedup': 0,
        },
    }

    if not canonical_urls:
        _safe_unlink(sidecar_path)
        summary['status'] = 'no_canonical_urls'
        return summary

    need_blocks = (
        LINK_FETCH_ENABLE
        and not validation.ok
        and _is_short_reason(validation.reason)
        and _needs_body_enrichment(cleaned_content, validation.effective, validation.min_len, len(canonical_urls))
    )
    summary['body_enrichment_needed'] = bool(need_blocks)

    blocks = []
    fetch_meta = dict(summary['fetch_meta'])
    if need_blocks:
        blocks, fetch_meta = _collect_unique_blocks(canonical_urls, validation.effective)
        summary['fetch_meta'] = fetch_meta
        summary['blocks'] = blocks

    payload = {
        'generated_at': _utc_now_iso(),
        'rule_version': RULE_VERSION,
        'config_bundle_sha1': CONFIG_BUNDLE['provenance']['bundle_sha1'],
        'folder': _normalize_folder(folder),
        'source_rel_path': source_rel_path,
        'source_sha1': source_sha1,
        'source_size_bytes': summary['source_size_bytes'],
        'source_mtime_ns': summary['source_mtime_ns'],
        'canonical_urls': canonical_urls,
        'body_validation_ok': validation.ok,
        'body_validation_reason': validation.reason,
        'body_enrichment_needed': bool(need_blocks),
        'link_fetch_enabled': bool(LINK_FETCH_ENABLE),
        'blocks': blocks,
        'fetch_meta': fetch_meta,
    }

    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    summary['sidecar_rel_path'] = sidecar_path.relative_to(RAW_ROOT).as_posix()
    summary['status'] = 'blocks_written' if blocks else 'canonical_only'
    return summary


def main() -> None:
    started_at = _utc_now_iso()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    totals = {
        'files_seen': 0,
        'files_with_urls': 0,
        'sidecars_written': 0,
        'blocks_written_files': 0,
        'canonical_only_files': 0,
        'body_enrichment_needed_files': 0,
        'total_blocks': 0,
        'canonical_urls_total': 0,
        'fetch_attempted_urls': 0,
        'fetch_successful_urls': 0,
        'fetch_failed_urls': 0,
        'disallowed_urls': 0,
        'fetched_text_too_short_urls': 0,
        'pdf_urls': 0,
        'content_fingerprint_dedup': 0,
        'removed_sidecars': 0,
        'errors': 0,
    }
    folder_stats: dict[str, dict] = {}

    for folder in TARGET_FOLDERS:
        normalized = _normalize_folder(folder)
        folder_stat = folder_stats.setdefault(normalized, {
            'files_seen': 0,
            'files_with_urls': 0,
            'sidecars_written': 0,
            'blocks_written_files': 0,
            'canonical_only_files': 0,
            'canonical_urls_total': 0,
        })
        for source_path in _iter_target_files(folder):
            totals['files_seen'] += 1
            folder_stat['files_seen'] += 1
            try:
                result = _process_file(source_path, folder)
            except Exception as e:
                totals['errors'] += 1
                results.append({
                    'folder': normalized,
                    'source_rel_path': source_path.relative_to(RAW_ROOT).as_posix(),
                    'status': 'error',
                    'error': f'{type(e).__name__}:{e}',
                })
                continue
            results.append(result)
            if result.get('status') == 'no_canonical_urls':
                totals['removed_sidecars'] += 1
                continue
            totals['files_with_urls'] += 1
            totals['sidecars_written'] += 1
            folder_stat['files_with_urls'] += 1
            folder_stat['sidecars_written'] += 1
            totals['canonical_urls_total'] += int(result.get('canonical_url_count', 0))
            folder_stat['canonical_urls_total'] += int(result.get('canonical_url_count', 0))
            if result.get('body_enrichment_needed'):
                totals['body_enrichment_needed_files'] += 1
            if result.get('status') == 'blocks_written':
                totals['blocks_written_files'] += 1
                folder_stat['blocks_written_files'] += 1
            else:
                totals['canonical_only_files'] += 1
                folder_stat['canonical_only_files'] += 1
            fetch_meta = result.get('fetch_meta') or {}
            totals['total_blocks'] += len(result.get('blocks') or [])
            totals['fetch_attempted_urls'] += int(fetch_meta.get('attempted_urls', 0))
            totals['fetch_successful_urls'] += int(fetch_meta.get('successful_urls', 0))
            totals['fetch_failed_urls'] += int(fetch_meta.get('fetch_failed_urls', 0))
            totals['disallowed_urls'] += int(fetch_meta.get('disallowed_urls', 0))
            totals['fetched_text_too_short_urls'] += int(fetch_meta.get('fetched_text_too_short_urls', 0))
            totals['pdf_urls'] += int(fetch_meta.get('pdf_urls', 0))
            totals['content_fingerprint_dedup'] += int(fetch_meta.get('content_fingerprint_dedup', 0))

    payload = {
        'generated_at': _utc_now_iso(),
        'started_at': started_at,
        'rule_version': RULE_VERSION,
        'config_bundle_sha1': CONFIG_BUNDLE['provenance']['bundle_sha1'],
        'raw_root': str(RAW_ROOT),
        'sidecar_root': str(SIDECAR_ROOT),
        'target_folders': list(TARGET_FOLDERS),
        'link_fetch_enabled': bool(LINK_FETCH_ENABLE),
        'totals': totals,
        'folder_stats': folder_stats,
        'results_preview': results[:200],
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
