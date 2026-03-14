#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
BUDDIES_PATH = ROOT / "invest/stages/stage1/outputs/master/naver_buddies_full.json"
OUT_BASE = ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/blog"
BACKOFF_STATE = ROOT / "invest/stages/stage1/outputs/runtime/blog_scrape_backoff.json"
BUDDY_CURSOR_PATH = ROOT / "invest/stages/stage1/outputs/runtime/blog_buddy_cursor.json"
BLOG_LAST_RUN_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/blog_last_run_status.json"
BLOG_TERMINAL_REGISTRY_PATH = ROOT / "invest/stages/stage1/inputs/config/blog_terminal_status.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"

POST_LINK_RE = re.compile(r"https?://blog\.naver\.com/PostView\.naver\?[^\"'\s<]+")
LOGNO_RE = re.compile(r"logNo=(\d+)")
IMG_SRC_RE = re.compile(r"<img\b[^>]*\s+src=([\'\"])(.*?)\1", re.I)
IMG_DATA_SRC_RE = re.compile(r"<img\b[^>]*\s+data-src=([\'\"])(.*?)\1", re.I)
IMG_DATA_ORIGINAL_RE = re.compile(r"<img\b[^>]*\s+data-original=([\'\"])(.*?)\1", re.I)
IMG_SRCSET_RE = re.compile(r'<img\b[^>]*\s+srcset=([\'\"])(.*?)\1', re.I)
IMG_URL_RE = re.compile(r'"(https?://[^"\s]+?\.(?:png|jpg|jpeg|gif|webp|bmp|svg|tiff|tif|avif|webp)(?:[^"\s]*)?)"', re.I)
OG_IMAGE_RE = re.compile(r'<meta\s+property=["\'][^"\']*og:image[^"\']*["\']\s+content=["\']([^"\']+)["\']', re.I)
PDF_LINK_HREF_RE = re.compile(r'<a\b[^>]+href=([\'\"])(.*?)\1', re.I)
PDF_URL_RE = re.compile(r'''https?://[^"'\s<>()\[\]{}]+\.pdf(?:[?#][^"'\s<>()\[\]{}]*)?''', re.I)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".tiff", ".tif", ".avif", ".ico"}
DEFAULT_BLOG_TARGET_DATE = "2016-01-01"
PERSISTENT_TERMINAL_CAUSES = {"empty-posts", "404"}

BLOG_ATTACH_ARTIFACT_ROOT = ROOT / "invest/stages/stage1/outputs/raw/qualitative/attachments/blog"
BLOG_IMAGE_DOWNLOAD_ENABLED = os.environ.get("BLOG_IMAGE_DOWNLOAD_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
BLOG_PDF_DOWNLOAD_ENABLED = os.environ.get("BLOG_PDF_DOWNLOAD_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
try:
    BLOG_IMAGE_MAX_PER_POST = max(0, int(os.environ.get("BLOG_IMAGE_MAX_PER_POST", "12").strip() or "12"))
except Exception:
    BLOG_IMAGE_MAX_PER_POST = 12
try:
    BLOG_IMAGE_MAX_BYTES = max(1024, int(os.environ.get("BLOG_IMAGE_MAX_BYTES", str(8 * 1024 * 1024)).strip() or str(8 * 1024 * 1024)))
except Exception:
    BLOG_IMAGE_MAX_BYTES = 8 * 1024 * 1024
try:
    BLOG_IMAGE_MAX_TOTAL_BYTES_PER_POST = max(1024, int(os.environ.get("BLOG_IMAGE_MAX_TOTAL_BYTES_PER_POST", str(32 * 1024 * 1024)).strip() or str(32 * 1024 * 1024)))
except Exception:
    BLOG_IMAGE_MAX_TOTAL_BYTES_PER_POST = 32 * 1024 * 1024
try:
    BLOG_IMAGE_BUCKET_COUNT = max(1, int(os.environ.get("BLOG_IMAGE_BUCKET_COUNT", "128").strip() or "128"))
except Exception:
    BLOG_IMAGE_BUCKET_COUNT = 128
try:
    BLOG_IMAGE_EXT_TIMEOUT_SEC = max(1, int(os.environ.get("BLOG_IMAGE_EXT_TIMEOUT_SEC", "18").strip() or "18"))
except Exception:
    BLOG_IMAGE_EXT_TIMEOUT_SEC = 18
try:
    BLOG_IMAGE_DOWNLOAD_RETRIES = max(0, int(os.environ.get("BLOG_IMAGE_DOWNLOAD_RETRIES", "1").strip() or "1"))
except Exception:
    BLOG_IMAGE_DOWNLOAD_RETRIES = 1
try:
    BLOG_PDF_MAX_PER_POST = max(0, int(os.environ.get("BLOG_PDF_MAX_PER_POST", "5").strip() or "5"))
except Exception:
    BLOG_PDF_MAX_PER_POST = 5
try:
    BLOG_PDF_MAX_BYTES = max(1024, int(os.environ.get("BLOG_PDF_MAX_BYTES", str(24 * 1024 * 1024)).strip() or str(24 * 1024 * 1024)))
except Exception:
    BLOG_PDF_MAX_BYTES = 24 * 1024 * 1024
try:
    BLOG_PDF_MAX_TOTAL_BYTES_PER_POST = max(1024, int(os.environ.get("BLOG_PDF_MAX_TOTAL_BYTES_PER_POST", str(96 * 1024 * 1024)).strip() or str(96 * 1024 * 1024)))
except Exception:
    BLOG_PDF_MAX_TOTAL_BYTES_PER_POST = 96 * 1024 * 1024
try:
    BLOG_PDF_EXT_TIMEOUT_SEC = max(1, int(os.environ.get("BLOG_PDF_EXT_TIMEOUT_SEC", "24").strip() or "24"))
except Exception:
    BLOG_PDF_EXT_TIMEOUT_SEC = 24
try:
    BLOG_PDF_DOWNLOAD_RETRIES = max(0, int(os.environ.get("BLOG_PDF_DOWNLOAD_RETRIES", "1").strip() or "1"))
except Exception:
    BLOG_PDF_DOWNLOAD_RETRIES = 1


def _resolve_target_date(raw_target_date: Optional[str], target_years: int) -> str:
    if raw_target_date and str(raw_target_date).strip():
        return str(raw_target_date).strip()
    return os.environ.get("BLOG_DEFAULT_TARGET_DATE", DEFAULT_BLOG_TARGET_DATE).strip() or DEFAULT_BLOG_TARGET_DATE


def _parse_target_date(raw_target_date: str) -> datetime.date:
    try:
        return datetime.fromisoformat(str(raw_target_date).strip()).date()
    except Exception:
        return datetime(2016, 1, 1).date()


def _safe_int(name: str, default: int, min_v: int = 0) -> int:
    try:
        return max(min_v, int(str(os.environ.get(name, str(default))).strip()))
    except Exception:
        return default


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_backoff_until() -> Optional[datetime]:
    if not BACKOFF_STATE.exists():
        return None
    try:
        data = json.loads(BACKOFF_STATE.read_text(encoding="utf-8"))
        raw = str(data.get("next_allowed_at", "")).strip()
        if not raw:
            return None
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _save_backoff_until(dt: Optional[datetime], reason: str = "") -> None:
    BACKOFF_STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_now().isoformat(),
        "next_allowed_at": dt.isoformat() if dt is not None else "",
        "reason": reason,
    }
    BACKOFF_STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sleep_with_jitter(base_sec: float) -> None:
    min_env = os.environ.get("BLOG_FETCH_SLEEP_MIN_SEC", "").strip()
    max_env = os.environ.get("BLOG_FETCH_SLEEP_MAX_SEC", "").strip()
    if min_env and max_env:
        try:
            lo = max(0.0, float(min_env))
            hi = max(lo, float(max_env))
            time.sleep(random.uniform(lo, hi))
            return
        except Exception:
            pass
    base = max(0.0, float(base_sec))
    if base <= 0:
        return
    lo = max(0.0, base * 0.7)
    hi = max(lo, base * 1.3)
    time.sleep(random.uniform(lo, hi))


def _http_get(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _http_get_with_retry(url: str, timeout: int = 20, retries: int = 2, retry_sleep: float = 0.8) -> str:
    last_err = None
    max_retries = max(0, int(retries))
    for attempt in range(max_retries + 1):
        try:
            return _http_get(url, timeout=timeout)
        except Exception as e:
            last_err = e
            if attempt >= max_retries:
                break
            _sleep_with_jitter(max(0.0, float(retry_sleep)) * (attempt + 1))
    if last_err is not None:
        raise last_err
    raise RuntimeError("http_get_with_retry_failed")


def _safe_path_component(value: str, fallback: str = "item") -> str:
    raw = str(value or "").strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned[:160] or fallback


def _to_rel_stage1_path(path_or_value) -> str:
    try:
        target = Path(path_or_value)
        return str(target.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        text = str(path_or_value)
        return text.replace("\\", "/")


def _image_url_digest(url: str) -> str:
    raw = str(url or "").strip().encode("utf-8")
    if not raw:
        return ""
    return hashlib.sha1(raw).hexdigest()[:12]


def _normalize_img_url(src: str) -> str:
    if not src:
        return ""
    u = src.strip()
    if u.startswith("data:"):
        return ""
    if u.startswith("//"):
        return f"https:{u}"
    if u.startswith("/"):
        return urljoin("https://m.blog.naver.com", u)
    return u


def _extract_image_urls(html: str, max_count: int = 0) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for pattern in (IMG_SRC_RE, IMG_DATA_SRC_RE, IMG_DATA_ORIGINAL_RE):
        for m in pattern.finditer(html or ""):
            val = _normalize_img_url(m.group(2) if len(m.groups()) >= 2 else "")
            if not val:
                continue
            low = val.lower()
            if low in seen:
                continue
            seen.add(low)
            found.append(val)

    for m in IMG_SRCSET_RE.finditer(html or ""):
        raw = m.group(2) if len(m.groups()) >= 2 else ""
        for seg in (raw or "").split(","):
            seg_parts = seg.strip().split()
            if not seg_parts:
                continue
            piece = seg_parts[0]
            if not piece:
                continue
            lower = piece.lower()
            if not (lower.startswith("http://") or lower.startswith("https://") or lower.startswith("//")):
                continue
            val = _normalize_img_url(piece)
            if not val:
                continue
            low = val.lower()
            if low in seen:
                continue
            seen.add(low)
            found.append(val)

    for m in OG_IMAGE_RE.finditer(html or ""):
        val = _normalize_img_url(m.group(1) if m.groups() else "")
        if not val:
            continue
        low = val.lower()
        if low in seen:
            continue
        seen.add(low)
        found.append(val)

    for m in IMG_URL_RE.finditer(html or ""):
        val = _normalize_img_url(m.group(1) if m.groups() else "")
        if not val:
            continue
        low = val.lower()
        if low in seen:
            continue
        seen.add(low)
        found.append(val)

    if not found:
        return []

    if max_count <= 0:
        max_count = max(1, BLOG_IMAGE_MAX_PER_POST)
    return found[:max_count]


def _looks_like_pdf(url: str) -> bool:
    if not url:
        return False
    p = urlparse(url)
    path = (p.path or "").lower()
    if path.endswith(".pdf"):
        return True
    if ".pdf" in path:
        return True
    q = (p.query or "").lower()
    if not q:
        return False
    for k, v_list in parse_qs(q, keep_blank_values=True).items():
        if any((str(v or "").lower().endswith(".pdf") or str(v or "").lower() == "pdf") for v in (v_list or [])):
            return True
    return False


def _extract_pdf_urls(html: str, max_count: int = 0) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for m in PDF_LINK_HREF_RE.finditer(html or ""):
        val = _normalize_img_url(m.group(2) if len(m.groups()) >= 2 else "")
        if not val or not _looks_like_pdf(val):
            continue
        low = val.lower()
        if low in seen:
            continue
        seen.add(low)
        found.append(val)

    for m in PDF_URL_RE.finditer(html or ""):
        val = _normalize_img_url(m.group(0))
        if not val:
            continue
        low = val.lower()
        if low in seen:
            continue
        seen.add(low)
        found.append(val)

    if not found:
        return []

    if max_count <= 0:
        max_count = max(1, BLOG_PDF_MAX_PER_POST)
    return found[:max_count]


def _image_ext_from_url(url: str, content_type: str = "") -> str:
    p = urlparse(url)
    path = (p.path or "").lower()
    for ext in IMAGE_EXTS:
        if path.endswith(ext):
            return ext

    ct = (content_type or "").lower()
    if "image/" in ct:
        token = ct.split(";")[0].strip()
        if token == "image/jpeg":
            return ".jpg"
        if token.startswith("image/"):
            maybe = token.split("/", 1)[1]
            if maybe:
                return f".{maybe.replace('jpeg', 'jpg')}"

    return ".img"


def _build_blog_attachment_paths(buddy_slug: str, log_no: str, kind: str) -> tuple[Path, Path]:
    bucket_count = max(1, BLOG_IMAGE_BUCKET_COUNT)
    try:
        num = int(log_no)
    except Exception:
        num = 0
    width = max(1, len(str(max(1, bucket_count - 1))))
    bucket = f"bucket_{num % bucket_count:0{width}d}"
    safe_kind = str(kind or "artifact").strip() or "artifact"
    artifact_dir = BLOG_ATTACH_ARTIFACT_ROOT / _safe_path_component(buddy_slug) / bucket
    manifest_name = f"msg_{_safe_path_component(log_no, fallback='0000')}__{safe_kind}_meta.json"
    return artifact_dir, artifact_dir / manifest_name


def _build_blog_image_paths(buddy_slug: str, log_no: str) -> tuple[Path, Path]:
    return _build_blog_attachment_paths(buddy_slug, log_no, "images")


def _download_blog_image(url: str, artifact_dir: Path, index: int) -> tuple[str, int, str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    reason = ""
    data: bytes | None = None
    ctype = ""
    for attempt in range(BLOG_IMAGE_DOWNLOAD_RETRIES + 1):
        try:
            req = Request(
                url,
                headers={"User-Agent": UA, "Referer": "https://m.blog.naver.com/"},
            )
            with urlopen(req, timeout=BLOG_IMAGE_EXT_TIMEOUT_SEC) as resp:
                ctype = str(resp.headers.get("Content-Type", "")).lower()
                data = resp.read(BLOG_IMAGE_MAX_BYTES + 1)
            break
        except Exception as e:  # noqa: BLE001
            reason = str(e)
            if attempt >= BLOG_IMAGE_DOWNLOAD_RETRIES:
                break
            _sleep_with_jitter(0.5)

    if data is None:
        return "", 0, ctype, reason or "download_failed"

    if len(data) > BLOG_IMAGE_MAX_BYTES:
        return "", 0, ctype, "file_too_large"

    ext = _image_ext_from_url(url, ctype)
    if not ext.startswith("."):
        ext = f".{ext}"

    digest = _image_url_digest(url)
    suffix = f"{digest}{ext}" if digest else f"{int(index):04d}__post_image{ext}"
    file_name = f"msg_{int(index):04d}__{suffix}"
    image_path = artifact_dir / file_name

    # if collision exists, append index suffix and avoid overwriting existing payload
    if image_path.exists():
        file_name = f"msg_{int(index):04d}__{int(time.time())}__{suffix}"
        image_path = artifact_dir / file_name

    image_path.write_bytes(data)
    return str(image_path), len(data), ctype, ""


def _download_blog_pdf(url: str, artifact_dir: Path, index: int) -> tuple[str, int, str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    reason = ""
    data: bytes | None = None
    ctype = ""
    for attempt in range(BLOG_PDF_DOWNLOAD_RETRIES + 1):
        try:
            req = Request(
                url,
                headers={"User-Agent": UA, "Referer": "https://m.blog.naver.com/"},
            )
            with urlopen(req, timeout=BLOG_PDF_EXT_TIMEOUT_SEC) as resp:
                ctype = str(resp.headers.get("Content-Type", "")).lower()
                data = resp.read(BLOG_PDF_MAX_BYTES + 1)
            break
        except Exception as e:  # noqa: BLE001
            reason = str(e)
            if attempt >= BLOG_PDF_DOWNLOAD_RETRIES:
                break
            _sleep_with_jitter(0.5)

    if data is None:
        return "", 0, ctype, reason or "download_failed"

    if len(data) > BLOG_PDF_MAX_BYTES:
        return "", 0, ctype, "file_too_large"

    if not data.lstrip().startswith(b"%PDF-") and "application/pdf" not in ctype:
        return "", 0, ctype, "not_pdf_content"

    digest = _image_url_digest(url)
    suffix = f"{digest}.pdf" if digest else f"{int(index):04d}__post_pdf.pdf"
    file_name = f"msg_{int(index):04d}__{suffix}"
    pdf_path = artifact_dir / file_name

    if pdf_path.exists():
        file_name = f"msg_{int(index):04d}__{int(time.time())}__{suffix}"
        pdf_path = artifact_dir / file_name

    pdf_path.write_bytes(data)
    return str(pdf_path), len(data), ctype, ""


def _collect_blog_images(
    buddy_slug: str,
    log_no: str,
    post_url: str,
    html: str,
    download_enabled: Optional[bool] = None,
) -> tuple[list[dict], Optional[Path]]:
    if html is None:
        html = ""
    urls = _extract_image_urls(html)
    if not urls:
        return [], None

    artifact_dir, manifest_path = _build_blog_image_paths(buddy_slug, log_no)
    image_items: list[dict] = []
    if download_enabled is None:
        download_enabled = bool(BLOG_IMAGE_DOWNLOAD_ENABLED)

    total_saved = 0
    total_bytes = 0
    manifest_status_counts: dict[str, int] = {}

    for idx, img_url in enumerate(urls, start=1):
        item = {
            "index": idx,
            "source_url": img_url,
            "source_digest": _image_url_digest(img_url),
            "status": "queued",
        }
        if download_enabled:
            if total_bytes >= BLOG_IMAGE_MAX_TOTAL_BYTES_PER_POST:
                item["status"] = "skipped_total_cap"
                item["error"] = "post_total_bytes_cap_reached"
            else:
                try:
                    saved_path, size, ctype, err = _download_blog_image(img_url, artifact_dir, idx)
                    if err:
                        item["status"] = "failed"
                        item["error"] = err
                    elif size > 0 and saved_path:
                        expected_bytes = total_bytes + size
                        if expected_bytes > BLOG_IMAGE_MAX_TOTAL_BYTES_PER_POST:
                            item["status"] = "skipped_total_cap"
                            item["error"] = "post_total_bytes_cap_reached"
                        else:
                            item["status"] = "saved"
                            item["artifact_path"] = _to_rel_stage1_path(saved_path)
                            item["artifact_abs_path"] = saved_path
                            item["size_bytes"] = size
                            item["content_type"] = ctype
                            total_saved += 1
                            total_bytes = expected_bytes
                    else:
                        item["status"] = "empty"
                except Exception as e:
                    item["status"] = "failed"
                    item["error"] = str(e)
        else:
            item["status"] = "reference_only"

        manifest_status_counts[item["status"]] = int(manifest_status_counts.get(item["status"], 0)) + 1
        image_items.append(item)

    manifest = {
        "artifact_schema_version": 2,
        "artifact_layout": "blog_bucketed_v2",
        "post_url": post_url,
        "captured_at": _utc_now().isoformat(),
        "buddy": str(buddy_slug),
        "log_no": str(log_no),
        "contract": {
            "max_per_post": BLOG_IMAGE_MAX_PER_POST,
            "max_bytes_per_post": BLOG_IMAGE_MAX_TOTAL_BYTES_PER_POST,
            "max_bytes_per_file": BLOG_IMAGE_MAX_BYTES,
            "bucket_count": BLOG_IMAGE_BUCKET_COUNT,
            "download_enabled": bool(download_enabled),
            "download_retries": BLOG_IMAGE_DOWNLOAD_RETRIES,
        },
        "images": image_items,
        "totals": {
            "found": len(urls),
            "saved": total_saved,
            "bytes": total_bytes,
            "status_counts": manifest_status_counts,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return image_items, manifest_path


def _collect_blog_pdfs(
    buddy_slug: str,
    log_no: str,
    post_url: str,
    html: str,
    download_enabled: Optional[bool] = None,
) -> tuple[list[dict], Optional[Path]]:
    if html is None:
        html = ""
    urls = _extract_pdf_urls(html)
    if not urls:
        return [], None

    artifact_dir, manifest_path = _build_blog_attachment_paths(buddy_slug, log_no, "pdf")
    pdf_items: list[dict] = []
    if download_enabled is None:
        download_enabled = bool(BLOG_PDF_DOWNLOAD_ENABLED)

    total_saved = 0
    total_bytes = 0
    manifest_status_counts: dict[str, int] = {}

    for idx, pdf_url in enumerate(urls, start=1):
        item = {
            "index": idx,
            "source_url": pdf_url,
            "source_digest": _image_url_digest(pdf_url),
            "status": "queued",
        }
        if download_enabled:
            if total_bytes >= BLOG_PDF_MAX_TOTAL_BYTES_PER_POST:
                item["status"] = "skipped_total_cap"
                item["error"] = "post_total_bytes_cap_reached"
            else:
                try:
                    saved_path, size, ctype, err = _download_blog_pdf(pdf_url, artifact_dir, idx)
                    if err:
                        item["status"] = "failed"
                        item["error"] = err
                    elif size > 0 and saved_path:
                        expected_bytes = total_bytes + size
                        if expected_bytes > BLOG_PDF_MAX_TOTAL_BYTES_PER_POST:
                            item["status"] = "skipped_total_cap"
                            item["error"] = "post_total_bytes_cap_reached"
                        else:
                            item["status"] = "saved"
                            item["artifact_path"] = _to_rel_stage1_path(saved_path)
                            item["artifact_abs_path"] = saved_path
                            item["size_bytes"] = size
                            item["content_type"] = ctype
                            total_saved += 1
                            total_bytes = expected_bytes
                    else:
                        item["status"] = "empty"
                except Exception as e:
                    item["status"] = "failed"
                    item["error"] = str(e)
        else:
            item["status"] = "reference_only"

        manifest_status_counts[item["status"]] = int(manifest_status_counts.get(item["status"], 0)) + 1
        pdf_items.append(item)

    manifest = {
        "artifact_schema_version": 2,
        "artifact_layout": "blog_bucketed_v2",
        "post_url": post_url,
        "captured_at": _utc_now().isoformat(),
        "buddy": str(buddy_slug),
        "log_no": str(log_no),
        "contract": {
            "max_per_post": BLOG_PDF_MAX_PER_POST,
            "max_bytes_per_post": BLOG_PDF_MAX_TOTAL_BYTES_PER_POST,
            "max_bytes_per_file": BLOG_PDF_MAX_BYTES,
            "bucket_count": BLOG_IMAGE_BUCKET_COUNT,
            "download_enabled": bool(download_enabled),
            "download_retries": BLOG_PDF_DOWNLOAD_RETRIES,
        },
        "pdfs": pdf_items,
        "totals": {
            "found": len(urls),
            "saved": total_saved,
            "bytes": total_bytes,
            "status_counts": manifest_status_counts,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return pdf_items, manifest_path




def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _extract_post_links(html: str) -> list[str]:
    links = set(POST_LINK_RE.findall(html))
    for m in re.finditer(r"logNo=(\d+)", html):
        log_no = m.group(1)
        if log_no:
            links.add(f"https://blog.naver.com/PostView.naver?logNo={log_no}")
    return sorted(links)


def _extract_title(html: str) -> str:
    for pat in [
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r"<title>(.*?)</title>",
    ]:
        m = re.search(pat, html, flags=re.I | re.S)
        if m:
            return _strip_html(m.group(1))[:200]
    return ""


def _extract_body(html: str) -> str:
    candidates = [
        r'(?is)<div[^>]+class="[^"]*se-main-container[^"]*"[^>]*>(.*?)</div>',
        r'(?is)<div[^>]+id="postViewArea"[^>]*>(.*?)</div>',
        r'(?is)<div[^>]+class="[^"]*post_ct[^"]*"[^>]*>(.*?)</div>',
    ]
    for pat in candidates:
        m = re.search(pat, html)
        if m:
            body = _strip_html(m.group(1))
            if len(body) >= 80:
                return body
    return _strip_html(html)


def _normalize_date(raw: str) -> str:
    m = re.search(r"(20\d{2})[./-]\s*([01]?\d)[./-]\s*([0-3]?\d)", raw)
    if not m:
        return ""
    y = int(m.group(1)); mo = int(m.group(2)); d = int(m.group(3))
    if mo < 1 or mo > 12 or d < 1 or d > 31:
        return ""
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _extract_post_date(html: str) -> str:
    pats = [
        r'<meta\s+property="article:published_time"\s+content="([^"]+)"',
        r'<meta\s+property="og:article:published_time"\s+content="([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'<span[^>]+class="[^"]*se_publishDate[^"]*"[^>]*>(.*?)</span>',
        r'<p[^>]+class="[^"]*date[^"]*"[^>]*>(.*?)</p>',
    ]
    for pat in pats:
        m = re.search(pat, html, flags=re.I | re.S)
        if m:
            d = _normalize_date(_strip_html(m.group(1)))
            if d:
                return d

    # fallback: first plausible YYYY-MM-DD style found in page
    d = _normalize_date(html)
    return d


def _logno_from_url(url: str) -> str:
    q = parse_qs(urlparse(url).query)
    if "logNo" in q and q["logNo"]:
        return q["logNo"][0]
    m = LOGNO_RE.search(url)
    return m.group(1) if m else ""


def _iter_buddies(limit: int) -> list[dict]:
    if not BUDDIES_PATH.exists():
        return []
    try:
        data = json.loads(BUDDIES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    total = len(data)
    if total == 0:
        return []

    start_index = 0
    if BUDDY_CURSOR_PATH.exists():
        try:
            cursor = json.loads(BUDDY_CURSOR_PATH.read_text(encoding="utf-8"))
            if isinstance(cursor, dict):
                start_index = int(cursor.get("next_index", 0))
        except Exception:
            start_index = 0

    start_index = start_index % total
    pick_count = total if limit <= 0 else min(limit, total)
    picked = [data[(start_index + i) % total] for i in range(pick_count)]
    next_index = (start_index + pick_count) % total

    try:
        BUDDY_CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _utc_now().isoformat(),
            "total_buddies": total,
            "limit": int(limit),
            "start_index": start_index,
            "next_index": next_index,
        }
        BUDDY_CURSOR_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return picked


def _classify_buddy_error(raw: str) -> str:
    s = (raw or "").lower()
    if "429" in s:
        return "rate-limit"
    if "404" in s:
        return "404"
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "403" in s:
        return "access-denied"
    if "empty-posts" in s:
        return "empty-posts"
    if "parse-fail" in s or "short_body" in s:
        return "parse-fail"
    return "fetch-fail"


def _load_blog_terminal_registry() -> dict:
    default_payload = {
        "checked_at": _utc_now().isoformat(),
        "ssot": "Stage1 blog buddy terminal/non-archive classification registry",
        "note": (
            "Missing buddy entries with these classifications are treated as 정상 종결(MAX_AVAILABLE_OK) "
            "rather than crawler failure. Collector-observed empty-posts/404 cases may be appended automatically."
        ),
        "entries": {},
    }
    if not BLOG_TERMINAL_REGISTRY_PATH.exists():
        return default_payload
    try:
        payload = json.loads(BLOG_TERMINAL_REGISTRY_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            if not isinstance(payload.get("entries"), dict):
                payload["entries"] = {}
            payload.setdefault("ssot", default_payload["ssot"])
            payload.setdefault("note", default_payload["note"])
            return payload
    except Exception:
        pass
    return default_payload


def _persist_terminal_registry_entries(rows: list[dict]) -> None:
    registry = _load_blog_terminal_registry()
    entries = registry.setdefault("entries", {})
    changed = False
    checked_at = _utc_now().isoformat()

    for row in rows:
        bid = str(row.get("id", "")).strip()
        cause = str(row.get("cause", "")).strip().lower()
        if not bid or cause not in PERSISTENT_TERMINAL_CAUSES:
            continue

        existing = entries.get(bid, {}) if isinstance(entries.get(bid), dict) else {}
        classification = "삭제/404" if cause == "404" else "no-data/collector-observed"
        evidence = (
            "collector page fetch returned 404"
            if cause == "404"
            else "collector sampled buddy and found zero candidate posts (empty-posts)"
        )
        merged = dict(existing)
        merged.setdefault("classification", classification)
        merged["cause"] = cause
        merged["status"] = existing.get("status") or "collector-registry"
        merged["direct_url"] = existing.get("direct_url") or row.get("url") or f"https://blog.naver.com/{bid}"
        merged["evidence"] = existing.get("evidence") or evidence
        merged["normal_completion_class"] = "MAX_AVAILABLE_OK"
        merged["picked_count"] = row.get("picked_count")
        merged["saved_count"] = row.get("saved_count")
        merged["last_seen_at"] = checked_at
        merged["source_script"] = "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py"
        if merged != existing:
            entries[bid] = merged
            changed = True

    if not changed:
        return

    registry["checked_at"] = checked_at
    BLOG_TERMINAL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLOG_TERMINAL_REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def run(
    limit_buddies: int,
    max_posts_per_buddy: int,
    max_pages_per_buddy: int,
    sleep_sec: float,
    target_date: str,
    backoff_hours: int,
    force_run: bool,
) -> dict:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    buddies = _iter_buddies(limit_buddies)
    target_dt = _parse_target_date(target_date)

    now = _utc_now()
    until = _load_backoff_until()
    if (not force_run) and until is not None and now < until:
        remain = int((until - now).total_seconds())
        msg = f"backoff_active_until={until.isoformat()} remain_sec={remain}"
        append_pipeline_event(
            source="scrape_all_posts_v2",
            status="WARN",
            count=0,
            errors=["backoff_active"],
            note=msg,
        )
        return {
            "status": "SKIP_BACKOFF",
            "buddies_target": len(buddies),
            "buddies_done": 0,
            "posts_saved": 0,
            "max_posts_per_buddy": max_posts_per_buddy,
            "max_pages_per_buddy": max_pages_per_buddy,
            "target_date": target_dt.isoformat(),
            "errors": ["backoff_active"],
            "next_allowed_at": until.isoformat(),
            "remain_sec": remain,
        }

    errors: list[str] = []
    post_saved = 0
    images_total = 0
    images_saved = 0
    images_failed = 0
    images_skipped = 0
    image_manifests = 0
    pdf_total = 0
    pdf_saved = 0
    pdf_failed = 0
    pdf_skipped = 0
    pdf_manifests = 0
    buddy_done = 0
    buddy_results: list[dict] = []

    for item in buddies:
        bid = str(item.get("id", "")).strip()
        if not bid:
            continue
        blog_url = str(item.get("url", "") or f"https://blog.naver.com/{bid}").strip()
        if not blog_url:
            continue

        buddy_dir = OUT_BASE / bid
        saved_for_buddy = 0
        short_body_count = 0
        picked: list[tuple[str, str]] = []
        page_error = ""
        buddy_images_total = 0
        buddy_images_saved = 0
        buddy_images_skipped = 0
        buddy_pdf_total = 0
        buddy_pdf_saved = 0
        buddy_pdf_skipped = 0

        try:
            seen_logno = set()
            for page in range(1, max(1, max_pages_per_buddy) + 1):
                post_list_url = (
                    f"https://blog.naver.com/PostList.naver?blogId={bid}&from=postList&currentPage={page}"
                )
                try:
                    html = _http_get_with_retry(post_list_url)
                except Exception as e:
                    page_error = str(e)
                    errors.append(f"{bid}:page_fetch:{e}")
                    break

                links = _extract_post_links(html)
                if not links:
                    m = re.search(r'(?is)<iframe[^>]+id="mainFrame"[^>]+src="([^"]+)"', html)
                    if m:
                        try:
                            iframe_html = _http_get_with_retry(urljoin("https://blog.naver.com/", m.group(1)))
                            links = _extract_post_links(iframe_html)
                        except Exception as e:
                            page_error = str(e)
                            errors.append(f"{bid}:iframe_fetch:{e}")
                            break

                page_added = 0
                for u in links:
                    log_no = _logno_from_url(u)
                    if not log_no or log_no in seen_logno:
                        continue
                    seen_logno.add(log_no)
                    picked.append((log_no, u))
                    page_added += 1
                    if len(picked) >= max_posts_per_buddy:
                        break

                if len(picked) >= max_posts_per_buddy:
                    break
                if page_added == 0:
                    break

            reached_target_for_buddy = False
            if picked:
                for log_no, post_url in picked:
                    buddy_dir.mkdir(parents=True, exist_ok=True)
                    out_path = buddy_dir / f"{log_no}.md"
                    if out_path.exists() and out_path.stat().st_size > 120:
                        prev = out_path.read_text(encoding="utf-8", errors="ignore")
                        if "PublishedDate:" in prev:
                            m_prev = re.search(r"(?m)^PublishedDate:\s*(\d{4}-\d{2}-\d{2})", prev)
                            if m_prev:
                                try:
                                    prev_dt = datetime.fromisoformat(m_prev.group(1)).date()
                                    if prev_dt < target_dt:
                                        reached_target_for_buddy = True
                                        break
                                    if prev_dt == target_dt:
                                        reached_target_for_buddy = True
                                        break
                                except Exception:
                                    pass
                            continue

                    mobile_url = f"https://m.blog.naver.com/PostView.naver?blogId={bid}&logNo={log_no}"
                    try:
                        post_html = _http_get_with_retry(mobile_url)
                    except Exception as e:
                        errors.append(f"{bid}:post_fetch:{log_no}:{e}")
                        continue

                    title = _extract_title(post_html) or f"{bid}/{log_no}"
                    body = _extract_body(post_html)
                    post_date = _extract_post_date(post_html)

                    if post_date:
                        try:
                            post_dt = datetime.fromisoformat(post_date).date()
                            if post_dt < target_dt:
                                reached_target_for_buddy = True
                                break
                        except Exception:
                            pass

                    if len(body.strip()) < 40:
                        short_body_count += 1
                        errors.append(f"short_body:{bid}:{log_no}")
                        continue

                    now = datetime.now().isoformat(timespec="seconds")
                    date_line = f"PublishedDate: {post_date}" if post_date else "PublishedDate: 미확인"

                    image_items, image_manifest_path = _collect_blog_images(
                        bid,
                        log_no,
                        mobile_url,
                        post_html,
                    )
                    pdf_items, pdf_manifest_path = _collect_blog_pdfs(
                        bid,
                        log_no,
                        mobile_url,
                        post_html,
                    )

                    images_total += len(image_items)
                    buddy_images_total += len(image_items)
                    if image_items:
                        image_manifests += 1
                    for one in image_items:
                        status = str(one.get("status") or "").lower()
                        if status == "saved":
                            images_saved += 1
                            buddy_images_saved += 1
                        elif status == "failed":
                            images_failed += 1
                            images_skipped += 1
                            buddy_images_skipped += 1
                        elif status in {
                            "reference_only",
                            "empty",
                            "skipped_total_cap",
                            "file_too_large",
                            "download_failed",
                        }:
                            images_skipped += 1
                            buddy_images_skipped += 1

                    pdf_total += len(pdf_items)
                    buddy_pdf_total += len(pdf_items)
                    if pdf_items:
                        pdf_manifests += 1
                    for one in pdf_items:
                        status = str(one.get("status") or "").lower()
                        if status == "saved":
                            pdf_saved += 1
                            buddy_pdf_saved += 1
                        elif status == "failed":
                            pdf_failed += 1
                            pdf_skipped += 1
                            buddy_pdf_skipped += 1
                        elif status in {
                            "reference_only",
                            "empty",
                            "skipped_total_cap",
                            "file_too_large",
                            "download_failed",
                            "not_pdf_content",
                        }:
                            pdf_skipped += 1
                            buddy_pdf_skipped += 1

                    out_lines = [
                        f"# {title}\n\n",
                        f"Date: {now}\n",
                        f"{date_line}\n",
                        f"Source: {mobile_url}\n",
                    ]
                    if image_items:
                        saved_count = sum(1 for item in image_items if str(item.get("status") or "") == "saved")
                        skipped_count = len(image_items) - saved_count
                        out_lines.append(f"Images: {len(image_items)} captured\n")
                        out_lines.append(f"ImagesSummary: saved={saved_count} skipped={skipped_count}\n")
                        if image_manifest_path is not None:
                            rel_manifest = str(image_manifest_path.relative_to(ROOT))
                            out_lines.append(f"ImageManifest: {rel_manifest}\n")
                    if pdf_items:
                        saved_count = sum(1 for item in pdf_items if str(item.get("status") or "") == "saved")
                        skipped_count = len(pdf_items) - saved_count
                        out_lines.append(f"PDFs: {len(pdf_items)} captured\n")
                        out_lines.append(f"PDFSummary: saved={saved_count} skipped={skipped_count}\n")
                        if pdf_manifest_path is not None:
                            rel_manifest = str(pdf_manifest_path.relative_to(ROOT))
                            out_lines.append(f"PDFManifest: {rel_manifest}\n")
                    out_lines.append("\n")
                    out_lines.append(f"{body}\n")

                    out_path.write_text("".join(out_lines), encoding="utf-8")
                    post_saved += 1
                    saved_for_buddy += 1

                    if post_date:
                        try:
                            if datetime.fromisoformat(post_date).date() == target_dt:
                                reached_target_for_buddy = True
                                break
                        except Exception:
                            pass

                    _sleep_with_jitter(sleep_sec)

            if saved_for_buddy > 0 or reached_target_for_buddy:
                status_for_buddy = "covered"
                cause_for_buddy = ""
            elif page_error:
                status_for_buddy = "uncovered"
                cause_for_buddy = _classify_buddy_error(page_error)
            elif not picked:
                status_for_buddy = "uncovered"
                cause_for_buddy = "empty-posts"
            elif short_body_count > 0:
                status_for_buddy = "uncovered"
                cause_for_buddy = "parse-fail"
            else:
                status_for_buddy = "uncovered"
                cause_for_buddy = "미확인"

            buddy_results.append(
                {
                    "id": bid,
                    "url": blog_url,
                    "status": status_for_buddy,
                    "cause": cause_for_buddy,
                    "picked_count": len(picked),
                    "saved_count": saved_for_buddy,
                    "short_body_count": short_body_count,
                    "images_total": buddy_images_total,
                    "images_saved": buddy_images_saved,
                    "images_skipped_or_failed": buddy_images_skipped,
                    "pdf_total": buddy_pdf_total,
                    "pdf_saved": buddy_pdf_saved,
                    "pdf_skipped_or_failed": buddy_pdf_skipped,
                }
            )
            buddy_done += 1
            _sleep_with_jitter(sleep_sec)
        except Exception as e:
            errors.append(f"{bid}:{e}")
            buddy_results.append(
                {
                    "id": bid,
                    "url": blog_url,
                    "status": "uncovered",
                    "cause": _classify_buddy_error(str(e)),
                    "picked_count": len(picked),
                    "saved_count": saved_for_buddy,
                    "short_body_count": short_body_count,
                    "images_total": buddy_images_total,
                    "images_saved": buddy_images_saved,
                    "images_failed": images_failed,
                    "images_skipped_or_failed": buddy_images_skipped,
                    "pdf_total": buddy_pdf_total,
                    "pdf_saved": buddy_pdf_saved,
                    "pdf_failed": pdf_failed,
                    "pdf_skipped_or_failed": buddy_pdf_skipped,
                    "error": str(e),
                }
            )
            buddy_done += 1

    had_429 = any("429" in e for e in errors)
    next_allowed_at = None
    if had_429:
        next_allowed_at = _utc_now() + timedelta(hours=max(1, int(backoff_hours)))
        _save_backoff_until(next_allowed_at, reason="http_429")
    else:
        _save_backoff_until(None, reason="clear")

    uncovered_causes: dict[str, int] = {}
    for one in buddy_results:
        if one.get("status") != "covered":
            cause = str(one.get("cause") or "미확인")
            uncovered_causes[cause] = int(uncovered_causes.get(cause, 0)) + 1

    total_buddies = 0
    try:
        total_buddies = len(json.loads(BUDDIES_PATH.read_text(encoding="utf-8"))) if BUDDIES_PATH.exists() else 0
    except Exception:
        total_buddies = 0

    run_payload = {
        "generated_at": _utc_now().isoformat(),
        "buddies_total": total_buddies,
        "buddies_target": len(buddies),
        "buddies_done": buddy_done,
        "posts_saved": post_saved,
        "images_total": images_total,
        "images_saved": images_saved,
        "images_failed": images_failed,
        "images_manifests": image_manifests,
        "images_skipped_or_failed": images_skipped,
        "pdf_total": pdf_total,
        "pdf_saved": pdf_saved,
        "pdf_failed": pdf_failed,
        "pdf_manifests": pdf_manifests,
        "pdf_skipped_or_failed": pdf_skipped,
        "max_posts_per_buddy": max_posts_per_buddy,
        "max_pages_per_buddy": max_pages_per_buddy,
        "target_date": target_dt.isoformat(),
        "backoff_hours": backoff_hours,
        "next_allowed_at": next_allowed_at.isoformat() if next_allowed_at else "",
        "uncovered_causes": uncovered_causes,
        "all_buddies_targeted": bool(total_buddies and len(buddies) == total_buddies),
        "all_buddies_covered": buddy_done == total_buddies and not uncovered_causes if total_buddies else False,
        "buddy_results": buddy_results,
        "errors": errors[:2000],
        "blog_image_download_enabled": bool(BLOG_IMAGE_DOWNLOAD_ENABLED),
        "blog_pdf_download_enabled": bool(BLOG_PDF_DOWNLOAD_ENABLED),
    }
    try:
        _persist_terminal_registry_entries(buddy_results)
    except Exception as e:
        errors.append(f"terminal_registry_persist:{e}")
        run_payload["errors"] = errors[:2000]
    try:
        BLOG_LAST_RUN_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        BLOG_LAST_RUN_STATUS_PATH.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    status = "OK" if not errors else "WARN"
    append_pipeline_event(
        source="scrape_all_posts_v2",
        status=status,
        count=post_saved,
        errors=errors[:20],
        note=(
            f"buddies={len(buddies)} done={buddy_done} posts={post_saved} images={images_total} "
            f"images_saved={images_saved} manifests={image_manifests} "
            f"pdf={pdf_total} pdf_saved={pdf_saved} pdf_manifests={pdf_manifests} "
            f"max_posts_per_buddy={max_posts_per_buddy} max_pages_per_buddy={max_pages_per_buddy} "
            f"target_date={target_dt.isoformat()} backoff_hours={backoff_hours} "
            f"next_allowed_at={(next_allowed_at.isoformat() if next_allowed_at else '')} "
            f"uncovered={sum(uncovered_causes.values())}"
        ),
    )

    return {
        "status": status,
        "buddies_target": len(buddies),
        "buddies_done": buddy_done,
        "posts_saved": post_saved,
        "images_total": images_total,
        "images_saved": images_saved,
        "images_failed": images_failed,
        "images_manifests": image_manifests,
        "images_skipped_or_failed": images_skipped,
        "pdf_total": pdf_total,
        "pdf_saved": pdf_saved,
        "pdf_failed": pdf_failed,
        "pdf_manifests": pdf_manifests,
        "pdf_skipped_or_failed": pdf_skipped,
        "max_posts_per_buddy": max_posts_per_buddy,
        "max_pages_per_buddy": max_pages_per_buddy,
        "target_date": target_dt.isoformat(),
        "backoff_hours": backoff_hours,
        "next_allowed_at": next_allowed_at.isoformat() if next_allowed_at else "",
        "uncovered_causes": uncovered_causes,
        "status_file": str(BLOG_LAST_RUN_STATUS_PATH.relative_to(ROOT)),
        "errors": errors,
        "blog_image_download_enabled": bool(BLOG_IMAGE_DOWNLOAD_ENABLED),
        "blog_pdf_download_enabled": bool(BLOG_PDF_DOWNLOAD_ENABLED),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage1 blog collector v2")
    ap.add_argument("--limit-buddies", type=int, default=_safe_int("BLOG_LIMIT_BUDDIES", 0, min_v=0))
    ap.add_argument("--max-posts-per-buddy", type=int, default=_safe_int("BLOG_MAX_POSTS_PER_BUDDY", 80, min_v=1))
    ap.add_argument("--max-pages-per-buddy", type=int, default=_safe_int("BLOG_MAX_PAGES_PER_BUDDY", 40, min_v=1))
    ap.add_argument("--sleep", type=float, default=float(os.environ.get("BLOG_FETCH_SLEEP_SEC", "0.9")))
    ap.add_argument("--target-years", type=int, default=_safe_int("BLOG_TARGET_YEARS", 10, min_v=1))
    ap.add_argument("--target-date", type=str, default=os.environ.get("BLOG_TARGET_DATE", "").strip())
    ap.add_argument("--backoff-hours", type=int, default=_safe_int("BLOG_429_BACKOFF_HOURS", 3, min_v=1))
    ap.add_argument("--force", action="store_true", help="ignore active 429 backoff and run now")
    args = ap.parse_args()

    target_date = _resolve_target_date(args.target_date, args.target_years)
    result = run(
        args.limit_buddies,
        args.max_posts_per_buddy,
        args.max_pages_per_buddy,
        args.sleep,
        target_date,
        args.backoff_hours,
        args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
