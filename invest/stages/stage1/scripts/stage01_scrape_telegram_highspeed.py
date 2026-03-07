import asyncio
import os
import subprocess
import sys
import time
import json
import re
import fcntl
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    from telethon import TelegramClient
except ModuleNotFoundError:
    # Cron may run with system python; re-exec with workspace venv if available.
    venv_py = '/Users/jobiseu/.openclaw/workspace/.venv/bin/python3'
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
save_dir = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/raw/qualitative/text/telegram'
os.makedirs(save_dir, exist_ok=True)

# Time windows
_target_years = max(1, int(os.environ.get('TELEGRAM_TARGET_YEARS', '10')))
target_date = datetime.now(timezone.utc) - timedelta(days=365 * _target_years)
bootstrap_lookback_days = int(os.environ.get('TELEGRAM_BOOTSTRAP_LOOKBACK_DAYS', str(365 * _target_years)))
bootstrap_date = datetime.now(timezone.utc) - timedelta(days=max(1, bootstrap_lookback_days))

LOCK_FILE = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/runtime/telegram_scrape.lock'
CHECKPOINT_FILE = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/runtime/telegram_scrape_checkpoint.json'
ALLOWLIST_FILE = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt'
RUN_STATUS_FILE = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/runtime/telegram_last_run_status.json'
INVEST_KEYWORDS = (
    '투자', '주식', '리서치', '뉴스', '증시', '마켓', 'stock', 'invest', 'research', 'market',
    'trading', 'finance', 'alpha', 'macro'
)

# Reliability guards (seconds)
GLOBAL_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_GLOBAL_TIMEOUT_SEC', '7200'))
PER_CHANNEL_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_PER_CHANNEL_TIMEOUT_SEC', '600'))
DASHBOARD_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_DASHBOARD_TIMEOUT_SEC', '45'))
MAX_MESSAGES_PER_CHANNEL = int(os.environ.get('TELEGRAM_MAX_MESSAGES_PER_CHANNEL', '0'))
INCREMENTAL_ONLY = os.environ.get('TELEGRAM_INCREMENTAL_ONLY', '1').strip().lower() not in ('0', 'false', 'no')
FORCE_FULL_BACKFILL = os.environ.get('TELEGRAM_FORCE_FULL_BACKFILL', '0').strip().lower() in ('1', 'true', 'yes')
COLLECT_ALL_CHANNELS = os.environ.get('TELEGRAM_COLLECT_ALL_CHANNELS', '0').strip().lower() in ('1', 'true', 'yes')
TIMEOUT_RETRY_SEC = int(os.environ.get('TELEGRAM_TIMEOUT_RETRY_SEC', '1800'))
TIMEOUT_RETRY_COUNT = max(0, int(os.environ.get('TELEGRAM_TIMEOUT_RETRY_COUNT', '1')))

URL_REGEX = re.compile(r"https?://[^\s<>()\[\]{}\"']+", flags=re.IGNORECASE)
ATTACH_EXTRACT_ENABLED = os.environ.get('TELEGRAM_ATTACH_EXTRACT_ENABLED', '1').strip().lower() not in ('0', 'false', 'no')
ATTACH_MAX_FILE_BYTES = int(os.environ.get('TELEGRAM_ATTACH_MAX_FILE_BYTES', str(15 * 1024 * 1024)))
ATTACH_MAX_TEXT_CHARS = int(os.environ.get('TELEGRAM_ATTACH_MAX_TEXT_CHARS', '6000'))
ATTACH_PDF_MAX_PAGES = int(os.environ.get('TELEGRAM_ATTACH_PDF_MAX_PAGES', '25'))
ATTACH_OCR_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_ATTACH_OCR_TIMEOUT_SEC', '18'))
ATTACH_TMP_ROOT = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/runtime/telegram_attach_tmp'
ATTACH_STATS_FILE = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/runtime/telegram_attachment_extract_stats_latest.json'

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff'}
TEXT_DOC_EXTS = {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.log', '.rtf'}


def acquire_lock():
    """
    Role: acquire_lock 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs('/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/runtime', exist_ok=True)
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
        'messages_with_attach_text': 0,
        'attachments_total': 0,
        'attachments_supported': 0,
        'attachments_text_extracted': 0,
        'attachments_failed': 0,
        'attachments_unsupported': 0,
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
    except ModuleNotFoundError:
        pass
    except Exception as e:
        return '', f'pypdf_error:{type(e).__name__}'

    # 2) pdfminer fallback
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore

        txt = pdfminer_extract_text(path, maxpages=max(1, ATTACH_PDF_MAX_PAGES)) or ''
        txt = _clip_text(txt)
        if txt:
            return txt, 'ok'
        return '', 'pdf_text_empty'
    except ModuleNotFoundError:
        return '', 'pdf_extractor_unavailable'
    except Exception as e:
        return '', f'pdfminer_error:{type(e).__name__}'


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


def _extract_image_ocr(path: str) -> tuple[str, str]:
    # 1) pytesseract + Pillow
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        txt = pytesseract.image_to_string(Image.open(path)) or ''
        txt = _clip_text(txt)
        if txt.strip():
            return txt, 'ok'
    except ModuleNotFoundError:
        pass
    except Exception as e:
        return '', f'pytesseract_error:{type(e).__name__}'

    # 2) tesseract CLI fallback
    if shutil.which('tesseract'):
        out_base = None
        try:
            fd, out_base = tempfile.mkstemp(prefix='tgocr_', dir=ATTACH_TMP_ROOT)
            os.close(fd)
            subprocess.run(
                ['tesseract', path, out_base, '-l', 'eng'],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(1, ATTACH_OCR_TIMEOUT_SEC),
            )
            txt_path = out_base + '.txt'
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                    txt = _clip_text(f.read())
                if txt.strip():
                    return txt, 'ok'
            return '', 'ocr_text_empty'
        except subprocess.TimeoutExpired:
            return '', 'ocr_timeout'
        except Exception as e:
            return '', f'tesseract_error:{type(e).__name__}'
        finally:
            for p in [f'{out_base}.txt' if out_base else '']:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
    return '', 'ocr_unavailable'


async def _extract_attachment_text(client, message, meta: dict, stats: dict) -> tuple[str, str]:
    if not ATTACH_EXTRACT_ENABLED:
        return '', 'attach_extract_disabled'

    if not meta or not meta.get('kind'):
        return '', 'no_supported_media'

    stats['attachments_total'] = int(stats.get('attachments_total', 0)) + 1

    kind = str(meta.get('kind') or '')
    if kind not in {'pdf', 'image', 'text_doc', 'docx'}:
        stats['attachments_unsupported'] = int(stats.get('attachments_unsupported', 0)) + 1
        _bump_reason(stats, f'unsupported_kind:{kind or "unknown"}')
        return '', f'unsupported_kind:{kind or "unknown"}'

    stats['attachments_supported'] = int(stats.get('attachments_supported', 0)) + 1

    size = int(meta.get('size') or 0)
    if size > ATTACH_MAX_FILE_BYTES:
        stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
        _bump_reason(stats, f'file_too_large:{kind}')
        return '', f'file_too_large:{kind}'

    os.makedirs(ATTACH_TMP_ROOT, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix='tg_attach_', dir=ATTACH_TMP_ROOT)
    fallback_name = f'msg_{int(getattr(message, "id", 0) or 0)}'
    fname = str(meta.get('name') or fallback_name)
    target = os.path.join(tmp_dir, os.path.basename(fname))

    try:
        dl_path = await client.download_media(message, file=target)
        if not dl_path or not os.path.exists(dl_path):
            stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
            _bump_reason(stats, f'download_failed:{kind}')
            return '', f'download_failed:{kind}'

        try:
            actual_size = int(os.path.getsize(dl_path))
        except Exception:
            actual_size = 0
        if actual_size > ATTACH_MAX_FILE_BYTES:
            stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
            _bump_reason(stats, f'file_too_large_downloaded:{kind}')
            return '', f'file_too_large_downloaded:{kind}'

        if kind == 'pdf':
            txt, reason = _extract_pdf_text(dl_path)
        elif kind == 'image':
            txt, reason = _extract_image_ocr(dl_path)
        elif kind == 'docx':
            txt, reason = _extract_docx_text(dl_path)
        else:
            txt, reason = _extract_plain_text_doc(dl_path)

        txt = _clip_text(txt)
        if txt:
            stats['attachments_text_extracted'] = int(stats.get('attachments_text_extracted', 0)) + 1
            return txt, 'ok'

        stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
        _bump_reason(stats, reason or f'empty_text:{kind}')
        return '', reason or f'empty_text:{kind}'
    except Exception as e:
        stats['attachments_failed'] = int(stats.get('attachments_failed', 0)) + 1
        err_reason = f'attach_extract_exception:{type(e).__name__}'
        _bump_reason(stats, err_reason)
        return '', err_reason
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


async def _render_message_body(client, message, attach_stats: dict) -> str:
    parts = []
    txt = (message.text or '').strip()
    if txt:
        parts.append(txt)

    for u in _extract_message_urls(message):
        parts.append(f"[ENTITY_URL] {u}")

    media_lines, media_meta = _describe_media(message)
    parts.extend(media_lines)

    if media_meta:
        attach_text, reason = await _extract_attachment_text(client, message, media_meta, attach_stats)
        if attach_text:
            parts.append('[ATTACH_TEXT]')
            parts.append(attach_text)
            parts.append('[/ATTACH_TEXT]')
            attach_stats['messages_with_attach_text'] = int(attach_stats.get('messages_with_attach_text', 0)) + 1
        elif reason and reason not in ('no_supported_media', 'attach_extract_disabled'):
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
                text = await _render_message_body(client, message, attach_stats)
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
        session_name = '/Users/jobiseu/.openclaw/workspace/invest/stages/stage1/scripts/jobis_mtproto_session'
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
        return "".join([c for c in (name or '') if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_') or 'channel'

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
            'failed_count': len(failed_items),
            'message_saved_count': int(message_saved_count),
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
