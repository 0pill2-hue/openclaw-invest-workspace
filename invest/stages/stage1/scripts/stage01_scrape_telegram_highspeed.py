import asyncio
import os
import sys
import time
import json
import re
import fcntl
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[4]
STAGE1_DIR = ROOT / 'invest/stages/stage1'
WORKSPACE_VENV_PY = ROOT / '.venv/bin/python3'

try:
    from telethon import TelegramClient
except ModuleNotFoundError:
    # Cron may run with system python; re-exec with workspace venv if available.
    venv_py = str(WORKSPACE_VENV_PY)
    if os.path.exists(venv_py) and os.path.realpath(sys.executable) != os.path.realpath(venv_py):
        os.execv(venv_py, [venv_py] + sys.argv)
    raise

from pipeline_logger import append_pipeline_event

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)


# Load .env file if exists
def load_env():
    """
    Role: load_env 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()

# API credentials from environment (security fix)
api_id = int(os.environ.get('TELEGRAM_API_ID', '0'))
api_hash = os.environ.get('TELEGRAM_API_HASH', '')

if not api_id or not api_hash:
    err = "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment."
    print(f"ERROR: {err}")
    append_pipeline_event("scrape_telegram_highspeed", "FAILED", count=0, errors=[err], note="missing telegram credentials")
    sys.exit(1)

# Save directory
save_dir = str(STAGE1_DIR / 'outputs/raw/qualitative/text/telegram')
os.makedirs(save_dir, exist_ok=True)

# Time windows
_target_years = max(1, int(os.environ.get('TELEGRAM_TARGET_YEARS', '10')))
target_date = datetime.now(timezone.utc) - timedelta(days=365 * _target_years)
bootstrap_lookback_days = int(os.environ.get('TELEGRAM_BOOTSTRAP_LOOKBACK_DAYS', str(365 * _target_years)))
bootstrap_date = datetime.now(timezone.utc) - timedelta(days=max(1, bootstrap_lookback_days))

LOCK_FILE = str(STAGE1_DIR / 'outputs/runtime/telegram_scrape.lock')
CHECKPOINT_FILE = str(STAGE1_DIR / 'outputs/runtime/telegram_scrape_checkpoint.json')
ALLOWLIST_FILE = str(STAGE1_DIR / 'inputs/config/telegram_channel_allowlist.txt')
RUN_STATUS_FILE = str(STAGE1_DIR / 'outputs/runtime/telegram_last_run_status.json')
INVEST_KEYWORDS = (
    '투자', '주식', '리서치', '뉴스', '증시', '마켓', 'stock', 'invest', 'research', 'market',
    'trading', 'finance', 'alpha', 'macro'
)

DEFAULT_PER_CHANNEL_TIMEOUT_SEC = 900
DEFAULT_TIMEOUT_RETRY_SEC = 2700
DEFAULT_TIMEOUT_RETRY_COUNT = 2
MACOS_SWIFT_BIN = '/usr/bin/swift'

# Reliability guards (seconds)
GLOBAL_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_GLOBAL_TIMEOUT_SEC', '7200'))
PER_CHANNEL_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_PER_CHANNEL_TIMEOUT_SEC', str(DEFAULT_PER_CHANNEL_TIMEOUT_SEC)))
DASHBOARD_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_DASHBOARD_TIMEOUT_SEC', '45'))
MAX_MESSAGES_PER_CHANNEL = int(os.environ.get('TELEGRAM_MAX_MESSAGES_PER_CHANNEL', '0'))
INCREMENTAL_ONLY = os.environ.get('TELEGRAM_INCREMENTAL_ONLY', '1').strip().lower() not in ('0', 'false', 'no')
FORCE_FULL_BACKFILL = os.environ.get('TELEGRAM_FORCE_FULL_BACKFILL', '0').strip().lower() in ('1', 'true', 'yes')
COLLECT_ALL_CHANNELS = os.environ.get('TELEGRAM_COLLECT_ALL_CHANNELS', '0').strip().lower() in ('1', 'true', 'yes')
TIMEOUT_RETRY_SEC = int(os.environ.get('TELEGRAM_TIMEOUT_RETRY_SEC', str(DEFAULT_TIMEOUT_RETRY_SEC)))
TIMEOUT_RETRY_COUNT = max(0, int(os.environ.get('TELEGRAM_TIMEOUT_RETRY_COUNT', str(DEFAULT_TIMEOUT_RETRY_COUNT))))

URL_REGEX = re.compile(r"https?://[^\s<>()\[\]{}\"']+", flags=re.IGNORECASE)
ATTACH_EXTRACT_ENABLED = os.environ.get('TELEGRAM_ATTACH_EXTRACT_ENABLED', '1').strip().lower() not in ('0', 'false', 'no')
ATTACH_MAX_FILE_BYTES = int(os.environ.get('TELEGRAM_ATTACH_MAX_FILE_BYTES', str(15 * 1024 * 1024)))
ATTACH_MAX_TEXT_CHARS = int(os.environ.get('TELEGRAM_ATTACH_MAX_TEXT_CHARS', '6000'))
ATTACH_PDF_MAX_PAGES = int(os.environ.get('TELEGRAM_ATTACH_PDF_MAX_PAGES', '25'))
ATTACH_STORE_MAX_FILE_BYTES = int(os.environ.get('TELEGRAM_ATTACH_STORE_MAX_FILE_BYTES', str(50 * 1024 * 1024)))
ATTACH_ARTIFACT_ROOT = STAGE1_DIR / 'outputs/raw/qualitative/attachments/telegram'
ATTACH_STATS_FILE = str(STAGE1_DIR / 'outputs/runtime/telegram_attachment_extract_stats_latest.json')

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff'}
TEXT_DOC_EXTS = {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.log', '.rtf'}
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


def acquire_lock():
    """
    Role: acquire_lock 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs(str(STAGE1_DIR / 'outputs/runtime'), exist_ok=True)
    fp = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        return fp
    except BlockingIOError:
        print('SKIP: telegram scraper already running (lock exists).')
        fp.close()
        return None


def load_allowlist():
    """
    Role: load_allowlist 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    allowed = set()
    if os.path.exists(ALLOWLIST_FILE):
        with open(ALLOWLIST_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                v = line.strip()
                if not v or v.startswith('#'):
                    continue
                allowed.add(v.lstrip('@').lower())
    env_allowed = os.environ.get('TELEGRAM_CHANNEL_ALLOWLIST', '').strip()
    if env_allowed:
        for item in env_allowed.split(','):
            v = item.strip()
            if v:
                allowed.add(v.lstrip('@').lower())
    return allowed


def is_investment_channel(title, username, allowed):
    """
    Role: is_investment_channel 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    uname = (username or '').strip().lstrip('@').lower()
    title_l = (title or '').lower()

    if uname and uname in allowed:
        return True
    if title_l in allowed:
        return True

    # Safety default: skip channels not explicitly allowlisted unless they look investment-related
    return any(k in title_l for k in INVEST_KEYWORDS)


def _load_checkpoint():
    """
    Role: _load_checkpoint 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    if not os.path.exists(CHECKPOINT_FILE):
        return {}
    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_checkpoint(checkpoint):
    """
    Role: _save_checkpoint 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    try:
        payload = dict(checkpoint)
        payload['_saved_at'] = datetime.now(timezone.utc).isoformat()
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"WARNING: failed to save checkpoint: {e}", flush=True)


def _save_attachment_stats(stats: dict):
    try:
        os.makedirs(os.path.dirname(ATTACH_STATS_FILE), exist_ok=True)
        payload = {
            'saved_at': datetime.now(timezone.utc).isoformat(),
            **stats,
        }
        with open(ATTACH_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"WARNING: failed to save attachment stats: {e}", flush=True)


def _load_seen_message_ids(path: str, max_scan_ids: int = 200000) -> set[int]:
    seen: set[int] = set()
    if not os.path.exists(path):
        return seen
    pat = re.compile(r"(?m)^MessageID:\s*(\d+)")
    try:
        txt = open(path, 'r', encoding='utf-8', errors='ignore').read()
    except Exception:
        return seen

    for m in pat.finditer(txt):
        try:
            seen.add(int(m.group(1)))
        except Exception:
            continue
        if len(seen) >= max_scan_ids:
            break
    return seen


def _new_attachment_stats() -> dict:
    return {
        'artifact_schema_version': 1,
        'messages_with_attach_text': 0,
        'messages_with_attach_paths': 0,
        'attachments_total': 0,
        'attachments_supported': 0,
        'attachments_text_extracted': 0,
        'attachments_failed': 0,
        'attachments_unsupported': 0,
        'attachments_meta_written': 0,
        'attachments_original_saved': 0,
        'attachments_original_failed': 0,
        'attachments_text_files_written': 0,
        'reason_counts': {},
    }


def _bump_reason(stats: dict, reason: str):
    key = (reason or 'unknown').strip() or 'unknown'
    rc = stats.setdefault('reason_counts', {})
    rc[key] = int(rc.get(key, 0)) + 1


def _clip_text(text: str, max_chars: int = ATTACH_MAX_TEXT_CHARS) -> str:
    t = (text or '').replace('\x00', ' ').strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars].rstrip() + f"\n[TRUNCATED] max_chars={max_chars}"


def _safe_component(value: str, fallback: str = 'item') -> str:
    raw = str(value or '').strip()
    cleaned = ''.join(ch if (ch.isalnum() or ch in ('-', '_', '.', ' ')) else '_' for ch in raw)
    cleaned = re.sub(r'\s+', '_', cleaned)
    cleaned = re.sub(r'_+', '_', cleaned).strip('._')
    return cleaned[:160] or fallback


def _extract_pdf_text_swift(path: str) -> tuple[str, str]:
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
            [MACOS_SWIFT_BIN, script_path, path, str(max(1, ATTACH_PDF_MAX_PAGES))],
            capture_output=True,
            text=True,
            timeout=max(30, min(300, ATTACH_PDF_MAX_PAGES * 12)),
        )
    except FileNotFoundError:
        return '', 'swift_unavailable'
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
        if 'no such module' in stderr and 'pdfkit' in stderr:
            return '', 'swift_pdfkit_unavailable'
        if 'open_failed' in stderr:
            return '', 'swift_pdf_open_failed'
        return '', f'swift_pdfkit_error:{proc.returncode}'

    txt = _clip_text(proc.stdout or '')
    if txt:
        return txt, 'ok'
    return '', 'pdf_text_empty'


def _rel_stage1_path(path_value) -> str:
    path = Path(path_value)
    try:
        return str(path.resolve().relative_to(STAGE1_DIR))
    except Exception:
        return str(path)


def _write_json_file(path_value, payload: dict):
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _normalize_url(url: str) -> str:
    if not isinstance(url, str):
        return ''
    s = url.strip().strip('"\'()[]{}<>')
    s = s.rstrip('.,);]\'"')
    if not s:
        return ''
    if not re.match(r'(?i)^https?://', s):
        return ''
    return s


def _classify_channel_failure(raw: str) -> str:
    s = (raw or '').strip().lower()
    if 'timeout' in s:
        return 'timeout'
    if 'floodwait' in s or 'flood wait' in s:
        return 'floodwait'
    if 'private' in s or 'forbidden' in s or 'not enough rights' in s or 'chatadminrequired' in s:
        return 'private/no access'
    if 'parse' in s or 'render_message_exception' in s:
        return 'parse-fail'
    return 'other'


def _save_run_status(payload: dict):
    try:
        os.makedirs(os.path.dirname(RUN_STATUS_FILE), exist_ok=True)
        with open(RUN_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"WARNING: failed to save run status: {e}", flush=True)


def _message_meta_lines(message) -> list[str]:
    lines = []
    for key, value in [
        ('Views', getattr(message, 'views', None)),
        ('Forwards', getattr(message, 'forwards', None)),
        ('Replies', getattr(getattr(message, 'replies', None), 'replies', None)),
        ('PostAuthor', getattr(message, 'post_author', None)),
        ('GroupedID', getattr(message, 'grouped_id', None)),
    ]:
        if value not in (None, ''):
            lines.append(f"{key}: {value}")
    return lines


def _extract_message_urls(message) -> list[str]:
    out = []
    txt = str(getattr(message, 'text', '') or getattr(message, 'message', '') or '')
    entities = getattr(message, 'entities', None) or []

    for ent in entities:
        url = _normalize_url(getattr(ent, 'url', None))
        if url:
            out.append(url)
            continue

        # MessageEntityUrl는 offset/length만 제공할 수 있음
        try:
            offset = int(getattr(ent, 'offset', -1))
            length = int(getattr(ent, 'length', 0))
        except Exception:
            offset, length = -1, 0
        if txt and offset >= 0 and length > 0:
            seg = _normalize_url(txt[offset: offset + length])
            if seg:
                out.append(seg)

    for m in URL_REGEX.finditer(txt or ''):
        raw = _normalize_url(m.group(0))
        if raw:
            out.append(raw)

    uniq = []
    seen = set()
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    return uniq


def _describe_media(message) -> tuple[list[str], dict]:
    if not getattr(message, 'media', None):
        return [], {}

    lines = [f"[MEDIA] {type(message.media).__name__}"]
    meta = {
        'name': '',
        'mime': '',
        'size': 0,
        'kind': '',
    }

    fobj = getattr(message, 'file', None)
    if fobj:
        name = str(getattr(fobj, 'name', '') or '')
        mime = str(getattr(fobj, 'mime_type', '') or '').lower()
        try:
            size = int(getattr(fobj, 'size', 0) or 0)
        except Exception:
            size = 0

        meta['name'] = name
        meta['mime'] = mime
        meta['size'] = size

        if name:
            lines.append(f"[FILE_NAME] {name}")
        if mime:
            lines.append(f"[MIME] {mime}")
        if size:
            lines.append(f"[FILE_SIZE] {size}")

    ext = Path(meta.get('name') or '').suffix.lower()
    mime = meta.get('mime') or ''

    if 'pdf' in mime or ext == '.pdf':
        meta['kind'] = 'pdf'
    elif getattr(message, 'photo', None) is not None or mime.startswith('image/') or ext in IMAGE_EXTS:
        meta['kind'] = 'image'
    elif ext == '.docx':
        meta['kind'] = 'docx'
    elif mime.startswith('text/') or ext in TEXT_DOC_EXTS:
        meta['kind'] = 'text_doc'
    elif getattr(message, 'document', None) is not None:
        meta['kind'] = 'document'

    if meta.get('kind'):
        lines.append(f"[ATTACH_KIND] {meta['kind']}")

    return lines, meta


def _extract_pdf_text(path: str) -> tuple[str, str]:
    last_reason = ''

    # 1) pypdf 우선
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(path)
        chunks = []
        for page in reader.pages[: max(1, ATTACH_PDF_MAX_PAGES)]:
            try:
                t = page.extract_text() or ''
            except Exception:
                t = ''
            if t.strip():
                chunks.append(t.strip())
            if len('\n\n'.join(chunks)) >= ATTACH_MAX_TEXT_CHARS:
                break
        merged = _clip_text('\n\n'.join(chunks))
        if merged:
            return merged, 'ok'
        last_reason = 'pdf_text_empty'
    except ModuleNotFoundError:
        last_reason = 'pypdf_unavailable'
    except Exception as e:
        last_reason = f'pypdf_error:{type(e).__name__}'

    # 2) pdfminer fallback
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore

        txt = pdfminer_extract_text(path, maxpages=max(1, ATTACH_PDF_MAX_PAGES)) or ''
        txt = _clip_text(txt)
        if txt:
            return txt, 'ok'
        last_reason = 'pdf_text_empty'
    except ModuleNotFoundError:
        if not last_reason:
            last_reason = 'pdfminer_unavailable'
    except Exception as e:
        last_reason = f'pdfminer_error:{type(e).__name__}'

    # 3) macOS Swift/PDFKit fallback
    txt, reason = _extract_pdf_text_swift(path)
    if txt:
        return txt, 'ok'

    if reason not in ('swift_unavailable', 'swift_pdfkit_unavailable', 'swift_pdfkit_non_darwin'):
        return '', reason or last_reason or 'pdf_extractor_unavailable'

    if last_reason in ('pypdf_unavailable', 'pdfminer_unavailable', ''):
        return '', 'pdf_extractor_unavailable'
    return '', last_reason


def _extract_docx_text(path: str) -> tuple[str, str]:
    try:
        import zipfile
        from html import unescape

        with zipfile.ZipFile(path) as zf:
            with zf.open('word/document.xml') as f:
                xml = f.read().decode('utf-8', errors='ignore')
        xml = re.sub(r'(?i)</w:p>', '\n', xml)
        xml = re.sub(r'<[^>]+>', ' ', xml)
        xml = unescape(xml)
        xml = re.sub(r'\s+', ' ', xml).strip()
        xml = _clip_text(xml)
        if xml:
            return xml, 'ok'
        return '', 'docx_text_empty'
    except KeyError:
        return '', 'docx_missing_document_xml'
    except Exception as e:
        return '', f'docx_parse_error:{type(e).__name__}'


def _extract_plain_text_doc(path: str) -> tuple[str, str]:
    try:
        with open(path, 'rb') as f:
            raw = f.read(min(ATTACH_MAX_FILE_BYTES, 2 * 1024 * 1024))
    except Exception as e:
        return '', f'text_read_error:{type(e).__name__}'

    for enc in ('utf-8', 'cp949', 'latin-1'):
        try:
            txt = raw.decode(enc, errors='ignore')
            txt = re.sub(r'\r', '', txt)
            txt = _clip_text(txt)
            if txt.strip():
                return txt, 'ok'
        except Exception:
            continue
    return '', 'text_decode_failed'


async def _persist_attachment_artifact(client, message, meta: dict, channel_meta: dict, stats: dict) -> dict:
    kind = str(meta.get('kind') or '')
    msg_id = int(getattr(message, 'id', 0) or 0)
    channel_slug = _safe_component(str(channel_meta.get('slug') or channel_meta.get('username') or 'unknown_channel'), 'unknown_channel')
    artifact_dir = ATTACH_ARTIFACT_ROOT / channel_slug / f'msg_{msg_id}'
    artifact_dir.mkdir(parents=True, exist_ok=True)

    raw_name = str(meta.get('name') or '')
    ext = Path(raw_name).suffix
    fallback_name = f'msg_{msg_id}{ext}' if ext else f'msg_{msg_id}'
    original_name = _safe_component(os.path.basename(raw_name) or fallback_name, fallback_name)
    original_path = artifact_dir / original_name
    extract_path = artifact_dir / 'extracted.txt'
    meta_path = artifact_dir / 'meta.json'

    result = {
        'artifact_dir': _rel_stage1_path(artifact_dir),
        'original_path': '',
        'extract_path': '',
        'meta_path': _rel_stage1_path(meta_path),
        'text': '',
        'reason': '',
        'kind': kind,
    }
    payload = {
        'saved_at': datetime.now(timezone.utc).isoformat(),
        'channel_title': str(channel_meta.get('title') or ''),
        'channel_username': str(channel_meta.get('username') or ''),
        'channel_slug': channel_slug,
        'message_id': msg_id,
        'message_date': getattr(message, 'date', None).isoformat() if getattr(message, 'date', None) else '',
        'kind': kind,
        'mime': str(meta.get('mime') or ''),
        'declared_size': int(meta.get('size') or 0),
        'original_name': original_name,
        'artifact_dir': result['artifact_dir'],
        'original_path': '',
        'extract_path': '',
        'meta_path': result['meta_path'],
        'original_store_status': '',
        'original_store_reason': '',
        'extraction_status': '',
        'extraction_reason': '',
    }

    if not kind or kind == 'image':
        result['reason'] = 'no_supported_media'
        payload['extraction_status'] = 'skip'
        payload['extraction_reason'] = result['reason']
        _write_json_file(meta_path, payload)
        stats['attachments_meta_written'] = int(stats.get('attachments_meta_written', 0)) + 1
        return result

    stats['attachments_total'] = int(stats.get('attachments_total', 0)) + 1

    original_saved = False
    store_reason = ''
    declared_size = int(meta.get('size') or 0)
    if declared_size > ATTACH_STORE_MAX_FILE_BYTES:
        store_reason = f'file_too_large_to_store:{kind or "unknown"}'
    else:
        try:
            dl_path = await client.download_media(message, file=str(original_path))
            actual_path = Path(dl_path) if dl_path else original_path
            if actual_path.exists():
                if actual_path.resolve() != original_path.resolve():
                    original_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(actual_path, original_path)
                payload['original_path'] = _rel_stage1_path(original_path)
                payload['original_size'] = int(original_path.stat().st_size)
                result['original_path'] = payload['original_path']
                original_saved = True
                stats['attachments_original_saved'] = int(stats.get('attachments_original_saved', 0)) + 1
            else:
                store_reason = f'download_failed:{kind or "unknown"}'
        except Exception as e:
            store_reason = f'attachment_store_exception:{type(e).__name__}'

    if original_saved:
        payload['original_store_status'] = 'ok'
        payload['original_store_reason'] = 'ok'
    else:
        payload['original_store_status'] = 'failed'
        payload['original_store_reason'] = store_reason or 'original_store_failed'
        stats['attachments_original_failed'] = int(stats.get('attachments_original_failed', 0)) + 1
        if store_reason:
            _bump_reason(stats, store_reason)

    supported = kind in {'pdf', 'text_doc', 'docx'}
    if supported:
        stats['attachments_supported'] = int(stats.get('attachments_supported', 0)) + 1
    else:
        stats['attachments_unsupported'] = int(stats.get('attachments_unsupported', 0)) + 1

    if not supported:
        result['reason'] = f'unsupported_kind:{kind or "unknown"}'
        _bump_reason(stats, result['reason'])
        payload['extraction_status'] = 'unsupported'
        payload['extraction_reason'] = result['reason']
    elif not ATTACH_EXTRACT_ENABLED:
        result['reason'] = 'attach_extract_disabled'
        payload['extraction_status'] = 'skipped'
        payload['extraction_reason'] = result['reason']
    elif not original_saved:
        result['reason'] = store_reason or 'no_original_for_extract'
        stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
        _bump_reason(stats, result['reason'])
        payload['extraction_status'] = 'failed'
        payload['extraction_reason'] = result['reason']
    else:
        actual_size = int(payload.get('original_size') or 0)
        if actual_size > ATTACH_MAX_FILE_BYTES:
            result['reason'] = f'file_too_large:{kind}'
            stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
            _bump_reason(stats, result['reason'])
            payload['extraction_status'] = 'failed'
            payload['extraction_reason'] = result['reason']
        else:
            if kind == 'pdf':
                attach_text, reason = _extract_pdf_text(str(original_path))
            elif kind == 'docx':
                attach_text, reason = _extract_docx_text(str(original_path))
            else:
                attach_text, reason = _extract_plain_text_doc(str(original_path))

            attach_text = _clip_text(attach_text)
            if attach_text:
                extract_path.write_text(attach_text, encoding='utf-8')
                result['text'] = attach_text
                result['reason'] = 'ok'
                result['extract_path'] = _rel_stage1_path(extract_path)
                payload['extract_path'] = result['extract_path']
                payload['extraction_status'] = 'ok'
                payload['extraction_reason'] = 'ok'
                stats['attachments_text_extracted'] = int(stats.get('attachments_text_extracted', 0)) + 1
                stats['attachments_text_files_written'] = int(stats.get('attachments_text_files_written', 0)) + 1
            else:
                result['reason'] = reason or f'empty_text:{kind}'
                payload['extraction_status'] = 'failed'
                payload['extraction_reason'] = result['reason']
                stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
                _bump_reason(stats, result['reason'])

    _write_json_file(meta_path, payload)
    stats['attachments_meta_written'] = int(stats.get('attachments_meta_written', 0)) + 1
    return result


async def _render_message_body(client, message, attach_stats: dict, channel_meta: dict) -> str:
    parts = []
    txt = (message.text or '').strip()
    if txt:
        parts.append(txt)

    for u in _extract_message_urls(message):
        parts.append(f"[ENTITY_URL] {u}")

    media_lines, media_meta = _describe_media(message)
    parts.extend(media_lines)

    if media_meta:
        attach_result = await _persist_attachment_artifact(client, message, media_meta, channel_meta, attach_stats)
        if attach_result.get('artifact_dir') and attach_result.get('kind') not in ('', 'image'):
            parts.append(f"[ATTACH_ARTIFACT_DIR] {attach_result['artifact_dir']}")
        if attach_result.get('original_path'):
            parts.append(f"[ATTACH_ORIGINAL_PATH] {attach_result['original_path']}")
        if attach_result.get('meta_path') and attach_result.get('kind') not in ('', 'image'):
            parts.append(f"[ATTACH_META_PATH] {attach_result['meta_path']}")
        if attach_result.get('extract_path'):
            parts.append(f"[ATTACH_TEXT_PATH] {attach_result['extract_path']}")
        if attach_result.get('original_path') or (attach_result.get('meta_path') and attach_result.get('kind') not in ('', 'image')):
            attach_stats['messages_with_attach_paths'] = int(attach_stats.get('messages_with_attach_paths', 0)) + 1

        attach_text = attach_result.get('text') or ''
        reason = attach_result.get('reason') or ''
        if attach_text:
            parts.append('[ATTACH_TEXT]')
            parts.append(attach_text)
            parts.append('[/ATTACH_TEXT]')
            attach_stats['messages_with_attach_text'] = int(attach_stats.get('messages_with_attach_text', 0)) + 1
        elif reason and reason not in ('no_supported_media',):
            parts.append(f"[ATTACH_TEXT_STATUS] {reason}")

    if not parts:
        return '[NO_TEXT_OR_MEDIA_METADATA]'
    return '\n'.join(parts)


async def scrape_single_channel(client, entity, title, username, fname, checkpoint, attach_stats):

    """
    
        Incremental collection:
        - If checkpoint exists: fetch only messages with id > checkpoint[channel]
        - If no checkpoint and incremental mode: bootstrap only recent N days
        - Otherwise fallback to historical N-year scan (TELEGRAM_TARGET_YEARS)
        
    Role: scrape_single_channel 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    key = str(username)
    last_id = int(checkpoint.get(key, 0) or 0)
    seen_ids = _load_seen_message_ids(fname)

    if FORCE_FULL_BACKFILL:
        msg_iter = client.iter_messages(entity)
        mode = f"forced_full({_target_years}y)"
    elif last_id > 0 and INCREMENTAL_ONLY:
        msg_iter = client.iter_messages(entity, min_id=last_id)
        mode = f"incremental(min_id={last_id})"
    else:
        msg_iter = client.iter_messages(entity)
        mode = f"bootstrap({bootstrap_lookback_days}d)" if (INCREMENTAL_ONLY and last_id <= 0) else f"full({_target_years}y)"

    new_count = 0
    max_seen_id = last_id
    created = os.path.exists(fname)

    channel_meta = {
        'title': title,
        'username': str(username),
        'slug': f"{_safe_component(title, 'channel')}_{_safe_component(str(username), 'id')}",
    }

    with open(fname, 'a', encoding='utf-8') as f:
        if not created:
            f.write(f"# Telegram Log: {title} ({username})\n\n")

        async for message in msg_iter:
            if message.id in seen_ids:
                continue

            # For first run without checkpoint, avoid full drain by default.
            if not FORCE_FULL_BACKFILL and last_id <= 0 and INCREMENTAL_ONLY:
                if message.date < bootstrap_date:
                    break
            else:
                if message.date < target_date:
                    break

            date_str = message.date.strftime('%Y-%m-%d %H:%M:%S')
            try:
                text = await _render_message_body(client, message, attach_stats, channel_meta)
            except Exception as e:
                _bump_reason(attach_stats, f'render_message_exception:{type(e).__name__}')
                text = (message.text or '').strip() or '[NO_TEXT_OR_MEDIA_METADATA]'
            f.write(f"--- \nDate: {date_str}\nMessageID: {message.id}\n")
            if message.forward:
                f.write(f"Forwarded from: {message.forward.chat_id if hasattr(message.forward, 'chat_id') else 'Unknown'}\n")
            for meta_line in _message_meta_lines(message):
                f.write(f"{meta_line}\n")
            f.write(f"\n{text}\n\n")
            new_count += 1
            seen_ids.add(message.id)

            if message.id > max_seen_id:
                max_seen_id = message.id

            if MAX_MESSAGES_PER_CHANNEL > 0 and new_count >= MAX_MESSAGES_PER_CHANNEL:
                break

            # periodic checkpoint flush for crash/timeout resilience
            if new_count % 30 == 0:
                checkpoint[key] = max_seen_id
                _save_checkpoint(checkpoint)
                f.flush()

        f.flush()

    checkpoint[key] = max_seen_id
    _save_checkpoint(checkpoint)
    return new_count, mode


async def main():
    """
    Role: main 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    lock_fp = acquire_lock()
    if lock_fp is None:
        append_pipeline_event("scrape_telegram_highspeed", "WARN", count=0, errors=[], note="already running lock exists")
        return

    scraped_count = 0
    message_saved_count = 0
    error_list = []
    final_state = "FAILED"
    allowed = set()
    client = None
    checkpoint = _load_checkpoint()
    attach_stats = _new_attachment_stats()
    dialogs_total = 0
    channels_targeted = 0
    timeout_retry_queue = []
    channel_outcomes = {}

    global_deadline = time.monotonic() + max(30, GLOBAL_TIMEOUT_SEC)

    def _record_outcome(username_key: str, payload: dict):
        channel_outcomes[username_key] = payload

    try:
        session_name = str(STAGE1_DIR / 'scripts/jobis_mtproto_session')
        client = TelegramClient(session_name, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            err = 'Authorization failed.'
            print(f"ERROR: {err}")
            append_pipeline_event("scrape_telegram_highspeed", "FAILED", count=0, errors=[err], note="telegram authorization")
            final_state = "FAILED_AUTH"
            return
    except Exception as e:
        err = f"Connection failed: {e}"
        print(f"ERROR: {err}")
        append_pipeline_event("scrape_telegram_highspeed", "FAILED", count=0, errors=[str(e)], note="telegram connect")
        final_state = "FAILED_CONNECT"
        return

    print("STATUS: FETCHING_ALL_CHANNELS")
    mode_label = "FORCED_FULL" if FORCE_FULL_BACKFILL else ("INCREMENTAL" if INCREMENTAL_ONLY else "FULL")
    scope_label = "ALL_DIALOG_CHANNELS" if COLLECT_ALL_CHANNELS else "ALLOWLIST_OR_KEYWORDS"
    print(
        f"MODE: {mode_label} scope={scope_label} target_years={_target_years} bootstrap_days={bootstrap_lookback_days} "
        f"max_msgs_per_channel={MAX_MESSAGES_PER_CHANNEL if MAX_MESSAGES_PER_CHANNEL > 0 else 'unlimited'}",
        flush=True,
    )

    if not COLLECT_ALL_CHANNELS:
        allowed = load_allowlist()
        if allowed:
            print(f"Allowlist loaded: {len(allowed)} entries", flush=True)
        else:
            print("WARNING: telegram allowlist is empty; keyword-based fallback filter will be used.", flush=True)
    else:
        print("COLLECT_ALL_CHANNELS enabled: scraping all accessible channel dialogs.", flush=True)

    async def _run_channel(entity, title, username, fname, timeout_sec: int):
        timeout_for_this_channel = max(1, min(timeout_sec, int(global_deadline - time.monotonic())))
        return await asyncio.wait_for(
            scrape_single_channel(client, entity, title, username, fname, checkpoint, attach_stats),
            timeout=timeout_for_this_channel,
        )

    def _safe_title(name: str) -> str:
        return _safe_component(name, 'channel')

    try:
        async for dialog in client.iter_dialogs():
            if time.monotonic() >= global_deadline:
                error_list.append(f"global timeout reached ({GLOBAL_TIMEOUT_SEC}s)")
                print(f"WARNING: Global timeout reached ({GLOBAL_TIMEOUT_SEC}s). Stopping further channel scans.", flush=True)
                final_state = "TIMEOUT_GLOBAL"
                break

            if not dialog.is_channel:
                continue

            dialogs_total += 1
            entity = dialog.entity
            title = dialog.name
            username = entity.username or entity.id
            username_key = str(username).strip().lower()

            if not COLLECT_ALL_CHANNELS and (not is_investment_channel(title, getattr(entity, 'username', None), allowed)):
                print(f"Skipping non-target channel: {title} ({username})", flush=True)
                continue

            channels_targeted += 1
            print(f"Scraping channel: {title} ({username})", flush=True)

            safe_title = _safe_title(title)
            fname = os.path.join(save_dir, f"{safe_title}_{username}_full.md")

            try:
                new_msgs, mode = await _run_channel(entity, title, username, fname, PER_CHANNEL_TIMEOUT_SEC)
                scraped_count += 1
                message_saved_count += new_msgs
                _record_outcome(username_key, {
                    'title': title,
                    'username': str(username),
                    'status': 'collected',
                    'reason': '',
                    'attempts': 1,
                    'new_messages': int(new_msgs),
                    'mode': mode,
                    'file': fname,
                })
                print(f"  Finished: {title} [{mode}] new_messages={new_msgs}", flush=True)


            except asyncio.TimeoutError:
                msg = f"{title}: channel timeout after {PER_CHANNEL_TIMEOUT_SEC}s"
                error_list.append(msg)
                timeout_retry_queue.append({
                    'entity': entity,
                    'title': title,
                    'username': username,
                    'username_key': username_key,
                    'fname': fname,
                    'attempts': 1,
                })
                _record_outcome(username_key, {
                    'title': title,
                    'username': str(username),
                    'status': 'failed',
                    'reason': 'timeout',
                    'attempts': 1,
                    'new_messages': 0,
                    'mode': '',
                    'file': fname,
                })
                print(f"  Error on {title}: {msg}", flush=True)
            except Exception as e:
                reason = _classify_channel_failure(str(e))
                msg = f"{title}: {e}"
                error_list.append(msg)
                _record_outcome(username_key, {
                    'title': title,
                    'username': str(username),
                    'status': 'failed',
                    'reason': reason,
                    'attempts': 1,
                    'new_messages': 0,
                    'mode': '',
                    'file': fname,
                    'error': str(e),
                })
                print(f"  Error on {title}: {e}", flush=True)

        if timeout_retry_queue and TIMEOUT_RETRY_COUNT > 0 and time.monotonic() < global_deadline:
            print(f"STATUS: RETRY_TIMEOUT_QUEUE size={len(timeout_retry_queue)} retries={TIMEOUT_RETRY_COUNT}", flush=True)

        for item in timeout_retry_queue:
            if time.monotonic() >= global_deadline:
                break

            retried = False
            retry_error = ''
            for retry_idx in range(1, TIMEOUT_RETRY_COUNT + 1):
                if time.monotonic() >= global_deadline:
                    break
                try:
                    new_msgs, mode = await _run_channel(item['entity'], item['title'], item['username'], item['fname'], TIMEOUT_RETRY_SEC)
                    scraped_count += 1
                    message_saved_count += new_msgs
                    _record_outcome(item['username_key'], {
                        'title': item['title'],
                        'username': str(item['username']),
                        'status': 'collected',
                        'reason': '',
                        'attempts': item['attempts'] + retry_idx,
                        'new_messages': int(new_msgs),
                        'mode': mode,
                        'file': item['fname'],
                        'retried': True,
                    })
                    print(
                        f"  Retry success: {item['title']} attempt={retry_idx}/{TIMEOUT_RETRY_COUNT} "
                        f"timeout={TIMEOUT_RETRY_SEC}s new_messages={new_msgs}",
                        flush=True,
                    )
                    retried = True

                    break
                except asyncio.TimeoutError:
                    retry_error = f"timeout after {TIMEOUT_RETRY_SEC}s"
                except Exception as e:
                    retry_error = str(e)
                    break

            if not retried:
                reason = _classify_channel_failure(retry_error or 'timeout')
                _record_outcome(item['username_key'], {
                    'title': item['title'],
                    'username': str(item['username']),
                    'status': 'failed',
                    'reason': reason,
                    'attempts': item['attempts'] + TIMEOUT_RETRY_COUNT,
                    'new_messages': 0,
                    'mode': '',
                    'file': item['fname'],
                    'error': retry_error,
                    'retried': True,
                })
                error_list.append(f"{item['title']}: retry_failed:{retry_error or '미확인'}")
                print(f"  Retry failed: {item['title']} reason={retry_error or '미확인'}", flush=True)

        if final_state == "FAILED":
            final_state = "OK" if not error_list else "WARN"
    finally:
        channels_collected = sum(1 for v in channel_outcomes.values() if v.get('status') == 'collected')
        failed_items = [v for v in channel_outcomes.values() if v.get('status') != 'collected']
        failure_causes = {}
        for one in failed_items:
            cause = str(one.get('reason') or '미확인')
            failure_causes[cause] = int(failure_causes.get(cause, 0)) + 1

        run_payload = {
            'saved_at': datetime.now(timezone.utc).isoformat(),
            'result': final_state,
            'collect_all_channels': bool(COLLECT_ALL_CHANNELS),
            'allowlist_total': len(allowed),
            'dialogs_total': dialogs_total,
            'channels_targeted': channels_targeted,
            'channels_collected': channels_collected,
            'missing_allowlist_count': max(0, len(allowed) - channels_collected) if not COLLECT_ALL_CHANNELS else 0,
            'all_channels_satisfied': bool(COLLECT_ALL_CHANNELS or (len(allowed) > 0 and channels_collected == len(allowed) and channels_targeted == len(allowed) and len(failed_items) == 0)),
            'failed_count': len(failed_items),
            'message_saved_count': int(message_saved_count),
            'per_channel_timeout_sec': PER_CHANNEL_TIMEOUT_SEC,
            'timeout_retry_count': TIMEOUT_RETRY_COUNT,
            'timeout_retry_sec': TIMEOUT_RETRY_SEC,
            'failure_causes': failure_causes,
            'failed_channels': failed_items,
            'channel_outcomes': list(channel_outcomes.values()),
            'errors': error_list[:200],
        }
        _save_run_status(run_payload)

        # Keep backward-compatible marker + machine-parseable result in all paths
        print(
            f"STATUS: ALL_CHANNELS_FINISHED RESULT={final_state} SCRAPED={channels_collected} "
            f"MSGS={message_saved_count} ERRORS={len(error_list)} DIALOGS={dialogs_total}",
            flush=True,
        )

        try:
            if client is not None:
                await client.disconnect()
        except Exception:
            pass

        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            lock_fp.close()
        except Exception:
            pass

    _save_attachment_stats(attach_stats)

    status = "OK" if not error_list else "WARN"
    if final_state.startswith("FAILED"):
        status = "FAILED"

    channels_collected = sum(1 for v in channel_outcomes.values() if v.get('status') == 'collected')
    failed_count = sum(1 for v in channel_outcomes.values() if v.get('status') != 'collected')
    append_pipeline_event(
        source="scrape_telegram_highspeed",
        status=status,
        count=message_saved_count,
        errors=error_list[:20],
        note=(
            f"allowlist={len(allowed)} collect_all={int(COLLECT_ALL_CHANNELS)} dialogs={dialogs_total} "
            f"targeted={channels_targeted} channels={channels_collected} failed={failed_count} "
            f"result={final_state} incremental={int(INCREMENTAL_ONLY)} force_full={int(FORCE_FULL_BACKFILL)} target_years={_target_years} "
            f"attach_text_msgs={int(attach_stats.get('messages_with_attach_text', 0))} "
            f"attach_fail={int(attach_stats.get('attachments_failed', 0))}"
        ),
    )


if __name__ == '__main__':
    asyncio.run(main())
