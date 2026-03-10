#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from invest.stages.common.stage_pdf_artifacts import ensure_pdf_support_artifacts
from pipeline_logger import append_pipeline_event

STAGE1_DIR = ROOT / "invest/stages/stage1"
ATTACH_ARTIFACT_ROOT = STAGE1_DIR / "outputs/raw/qualitative/attachments/telegram"
TELEGRAM_TEXT_ROOT = STAGE1_DIR / "outputs/raw/qualitative/text/telegram"
STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_attachment_extract_backfill_status.json"

ATTACH_BUCKET_COUNT = max(1, int(os.environ.get("TELEGRAM_ATTACH_BUCKET_COUNT", "128")))
ATTACH_MAX_FILE_BYTES = int(os.environ.get("TELEGRAM_ATTACH_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
ATTACH_MAX_TEXT_CHARS = int(os.environ.get("TELEGRAM_ATTACH_MAX_TEXT_CHARS", "6000"))
ATTACH_PDF_MAX_PAGES = int(os.environ.get("TELEGRAM_ATTACH_PDF_MAX_PAGES", "25"))
ATTACH_RENDER_MAX_WIDTH = int(os.environ.get("TELEGRAM_ATTACH_RENDER_MAX_WIDTH", "1200"))
ATTACH_HOT_WINDOW_DAYS = int(os.environ.get("TELEGRAM_ATTACH_HOT_WINDOW_DAYS", "31"))
MACOS_SWIFT_BIN = "/usr/bin/swift"
SUPPORTED_KINDS = {"pdf", "docx", "text_doc"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
TEXT_DOC_EXTS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".log", ".rtf"}
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _rel_stage1_path(path: Path) -> str:
    return os.path.relpath(path, STAGE1_DIR).replace("\\", "/")


def _resolve_stage1_path(rel_path: str | None, fallback: Path | None = None) -> Path:
    raw = str(rel_path or "").strip()
    if not raw:
        return fallback or Path("")
    p = Path(raw)
    if p.is_absolute():
        return p
    return STAGE1_DIR / raw


def _clip_text(text: str) -> str:
    x = (text or "").replace("\r", "\n")
    x = re.sub(r"\n{3,}", "\n\n", x)
    x = re.sub(r"[ \t]+", " ", x)
    return x.strip()[:ATTACH_MAX_TEXT_CHARS]


def _safe_component(value: str, fallback: str) -> str:
    s = re.sub(r"[^\w\-.]+", "_", str(value or "")).strip("._")
    return s or fallback


def _attachment_file_stem(msg_id: int) -> str:
    return f"msg_{int(msg_id)}"


def _attachment_bucket_name(msg_id: int) -> str:
    width = max(2, len(str(max(0, ATTACH_BUCKET_COUNT - 1))))
    return f"bucket_{int(msg_id) % ATTACH_BUCKET_COUNT:0{width}d}"


def _legacy_attachment_dir(channel_slug: str, msg_id: int) -> Path:
    return ATTACH_ARTIFACT_ROOT / channel_slug / f"msg_{int(msg_id)}"


def _attachment_bucket_dir(channel_slug: str, msg_id: int) -> Path:
    return ATTACH_ARTIFACT_ROOT / channel_slug / _attachment_bucket_name(msg_id)


def _attachment_meta_path(channel_slug: str, msg_id: int) -> Path:
    return _attachment_bucket_dir(channel_slug, msg_id) / f"{_attachment_file_stem(msg_id)}__meta.json"


def _attachment_extract_path(channel_slug: str, msg_id: int) -> Path:
    return _attachment_bucket_dir(channel_slug, msg_id) / f"{_attachment_file_stem(msg_id)}__extracted.txt"


def _attachment_original_path(channel_slug: str, msg_id: int, original_name: str) -> Path:
    safe_name = _safe_component(Path(original_name or "").name, _attachment_file_stem(msg_id))
    return _attachment_bucket_dir(channel_slug, msg_id) / f"{_attachment_file_stem(msg_id)}__original__{safe_name}"


def _iter_attachment_meta_paths() -> list[Path]:
    if not ATTACH_ARTIFACT_ROOT.exists():
        return []
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in ("meta.json", "*__meta.json"):
        for p in sorted(ATTACH_ARTIFACT_ROOT.rglob(pattern)):
            if not p.is_file() or p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def _attachment_original_candidates(channel_slug: str, msg_id: int, original_name: str = "") -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        if path in seen or not path.exists() or not path.is_file():
            return
        seen.add(path)
        out.append(path)

    if original_name:
        _add(_attachment_original_path(channel_slug, msg_id, original_name))

    bucket_dir = _attachment_bucket_dir(channel_slug, msg_id)
    if bucket_dir.exists():
        for candidate in sorted(bucket_dir.glob(f"{_attachment_file_stem(msg_id)}__original__*")):
            _add(candidate)

    legacy_dir = _legacy_attachment_dir(channel_slug, msg_id)
    if legacy_dir.exists():
        for candidate in sorted(legacy_dir.iterdir()):
            if candidate.name in {"meta.json", "extracted.txt"}:
                continue
            _add(candidate)

    return out


def _telegram_channel_slug_from_log_path(path: Path) -> str:
    base = path.name
    if base.lower().endswith(".md"):
        base = base[:-3]
    if base.endswith("_full"):
        base = base[:-5]
    return base.strip()


def _split_telegram_blocks(content: str) -> list[str]:
    parts = re.split(r"(?m)^---\s*$", content or "")
    out = []
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        if re.search(r"(?mi)^MessageID\s*:\s*\d+", chunk):
            out.append(chunk)
    return out


def _marker_value(block: str, marker: str) -> str:
    m = re.search(rf"(?mi)^\[{re.escape(marker)}\]\s*(.*?)\s*$", block or "")
    return str(m.group(1)).strip() if m else ""


def _attach_text_block(block: str) -> str:
    m = re.search(r"(?is)\[ATTACH_TEXT\]\s*(.*?)\s*\[/ATTACH_TEXT\]", block or "")
    return _clip_text(m.group(1) if m else "")


def _parse_message_id(block: str) -> int:
    m = re.search(r"(?mi)^MessageID\s*:\s*(\d+)", block or "")
    return int(m.group(1)) if m else 0


def _parse_message_date(block: str) -> str:
    m = re.search(r"(?mi)^Date\s*:\s*(.+)$", block or "")
    return str(m.group(1)).strip() if m else ""


def _infer_kind_from_markers(attach_kind: str, mime: str, file_name: str) -> str:
    kind = str(attach_kind or "").strip().lower()
    if kind in SUPPORTED_KINDS:
        return kind

    ext = Path(file_name or "").suffix.lower()
    low_mime = str(mime or "").strip().lower()
    if "pdf" in low_mime or ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if low_mime.startswith("text/") or ext in TEXT_DOC_EXTS:
        return "text_doc"
    if low_mime.startswith("image/") or ext in IMAGE_EXTS:
        return "image"
    return ""


def _resolve_marker_path(raw_path: str, *, log_path: Path) -> Path | None:
    raw = str(raw_path or "").strip()
    if not raw:
        return None

    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p

    stage1_rel = _resolve_stage1_path(raw, fallback=Path(""))
    if stage1_rel and stage1_rel.exists():
        return stage1_rel

    if raw.startswith("invest/stages/stage1/"):
        p2 = ROOT / raw
        if p2.exists():
            return p2

    if "invest/stages/stage1/" in raw:
        suffix = raw.split("invest/stages/stage1/", 1)[1]
        p3 = STAGE1_DIR / suffix
        if p3.exists():
            return p3

    local = (log_path.parent / raw).resolve()
    if local.exists():
        return local

    if p.is_absolute():
        return p
    return None


def _iter_legacy_logs() -> list[Path]:
    roots = [
        TELEGRAM_TEXT_ROOT,
        STAGE1_DIR / "outputs/raw/qualitative/text",
        STAGE1_DIR / "outputs/raw/qualitative/telegram",
        STAGE1_DIR / "outputs/raw/qualitative",
    ]
    out: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*_full.md")):
            if not p.is_file():
                continue
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def _build_original_target_name(file_name: str, source_path: Path | None, msg_id: int) -> str:
    if file_name:
        return _safe_component(Path(file_name).name, f"msg_{msg_id}")
    if source_path and source_path.name:
        return _safe_component(source_path.name, f"msg_{msg_id}{source_path.suffix}")
    return f"msg_{msg_id}"


def _reconcile_from_legacy_logs(stats: dict) -> None:
    logs = _iter_legacy_logs()
    stats["legacy_logs_scanned"] = len(logs)

    for log_path in logs:
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        channel_slug = _telegram_channel_slug_from_log_path(log_path)
        if not channel_slug:
            continue

        blocks = _split_telegram_blocks(content)
        for block in blocks:
            msg_id = _parse_message_id(block)
            if msg_id <= 0:
                continue

            mime = _marker_value(block, "MIME")
            file_name = _marker_value(block, "FILE_NAME")
            attach_kind = _marker_value(block, "ATTACH_KIND")
            kind = _infer_kind_from_markers(attach_kind, mime, file_name)
            if kind not in SUPPORTED_KINDS:
                continue

            stats["legacy_supported_candidates"] += 1

            artifact_dir = _attachment_bucket_dir(channel_slug, msg_id)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            meta_path = _attachment_meta_path(channel_slug, msg_id)
            extract_path = _attachment_extract_path(channel_slug, msg_id)

            meta_before = _read_json(meta_path)
            meta = dict(meta_before)
            now_iso = datetime.now(timezone.utc).isoformat()

            message_date = _parse_message_date(block)
            declared_size_raw = _marker_value(block, "FILE_SIZE")
            try:
                declared_size = int(declared_size_raw or 0)
            except Exception:
                declared_size = 0

            marker_original = _marker_value(block, "ATTACH_ORIGINAL_PATH")
            marker_extract = _marker_value(block, "ATTACH_TEXT_PATH")
            inline_attach_text = _attach_text_block(block)

            canonical_original: Path | None = None
            original_src = _resolve_marker_path(marker_original, log_path=log_path)
            if original_src and original_src.exists() and original_src.is_file():
                target_name = _build_original_target_name(file_name, original_src, msg_id)
                canonical_original = _attachment_original_path(channel_slug, msg_id, target_name)
                try:
                    if canonical_original.resolve() != original_src.resolve() and not canonical_original.exists():
                        shutil.copy2(original_src, canonical_original)
                        stats["legacy_original_copied"] += 1
                except Exception:
                    canonical_original = None

            if (not canonical_original) or (not canonical_original.exists()):
                candidates = _attachment_original_candidates(channel_slug, msg_id, str(meta.get("original_name") or file_name))
                canonical_original = candidates[0] if candidates else None

            extracted_written = False
            if inline_attach_text:
                if not extract_path.exists() or extract_path.read_text(encoding="utf-8", errors="ignore").strip() == "":
                    extract_path.write_text(inline_attach_text, encoding="utf-8")
                    stats["legacy_extract_backfilled_inline"] += 1
                extracted_written = True
            else:
                legacy_extract_src = _resolve_marker_path(marker_extract, log_path=log_path)
                if legacy_extract_src and legacy_extract_src.exists() and legacy_extract_src.is_file():
                    txt = _clip_text(legacy_extract_src.read_text(encoding="utf-8", errors="ignore"))
                    if txt:
                        if not extract_path.exists() or extract_path.read_text(encoding="utf-8", errors="ignore").strip() == "":
                            extract_path.write_text(txt, encoding="utf-8")
                            stats["legacy_extract_backfilled_path"] += 1
                        extracted_written = True

            existing_kind = str(meta.get("kind") or "").strip().lower()
            if not existing_kind:
                meta["kind"] = kind
            elif existing_kind in SUPPORTED_KINDS:
                meta["kind"] = existing_kind
            else:
                meta["kind"] = kind

            meta.setdefault("saved_at", now_iso)
            meta["artifact_schema_version"] = int(meta.get("artifact_schema_version") or 2)
            meta["artifact_layout"] = "bucketed_v2"
            meta["attachment_bucket_count"] = ATTACH_BUCKET_COUNT
            meta["attachment_bucket"] = artifact_dir.name
            meta["channel_slug"] = channel_slug
            meta["message_id"] = int(msg_id)
            meta["message_date"] = str(meta.get("message_date") or message_date)
            meta["mime"] = str(meta.get("mime") or mime)
            meta["declared_size"] = int(meta.get("declared_size") or declared_size)
            meta["artifact_dir"] = _rel_stage1_path(artifact_dir)
            meta["meta_path"] = _rel_stage1_path(meta_path)

            if canonical_original and canonical_original.exists():
                meta["original_name"] = str(meta.get("original_name") or canonical_original.name.split("__original__", 1)[-1])
                meta["original_path"] = _rel_stage1_path(canonical_original)
                meta["original_store_status"] = "ok"
                meta["original_store_reason"] = "ok"
            elif str(meta.get("original_path") or "").strip():
                resolved = _resolve_marker_path(str(meta.get("original_path") or ""), log_path=log_path)
                if resolved and resolved.exists() and resolved.is_file():
                    meta["original_path"] = _rel_stage1_path(resolved)
                else:
                    meta["original_store_status"] = str(meta.get("original_store_status") or "failed")
                    meta["original_store_reason"] = str(meta.get("original_store_reason") or "missing_original")
            else:
                meta["original_store_status"] = str(meta.get("original_store_status") or "failed")
                meta["original_store_reason"] = str(meta.get("original_store_reason") or "missing_original")

            if extract_path.exists() and extract_path.stat().st_size > 0:
                meta["extract_path"] = _rel_stage1_path(extract_path)
                meta["extraction_status"] = "ok"
                meta["extraction_reason"] = "ok"
                meta["extraction_origin"] = str(meta.get("extraction_origin") or "legacy_full_log")
            elif extracted_written:
                meta["extract_path"] = _rel_stage1_path(extract_path)
                meta["extraction_status"] = "ok"
                meta["extraction_reason"] = "ok"
                meta["extraction_origin"] = "legacy_full_log"
            elif not (canonical_original and canonical_original.exists() and canonical_original.is_file()):
                if str(meta.get("extraction_status") or "") != "ok":
                    meta["extraction_status"] = "failed"
                    meta["extraction_reason"] = "missing_original"

            meta["extraction_updated_at"] = now_iso
            meta["legacy_reconciled_at"] = now_iso

            if not meta_before:
                stats["legacy_meta_created"] += 1
            if meta != meta_before:
                _write_json(meta_path, meta)
                stats["legacy_meta_updated"] += 1


def _extract_pdf_text_swift(path: str) -> tuple[str, str]:
    if os.uname().sysname.lower() != "darwin":
        return "", "swift_pdfkit_non_darwin"
    if not os.path.exists(MACOS_SWIFT_BIN):
        return "", "swift_unavailable"

    script_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".swift", delete=False) as tf:
            tf.write(SWIFT_PDFKIT_EXTRACT_SCRIPT)
            script_path = tf.name
        proc = subprocess.run(
            [MACOS_SWIFT_BIN, script_path, path, str(max(1, ATTACH_PDF_MAX_PAGES))],
            capture_output=True,
            text=True,
            timeout=max(30, min(300, ATTACH_PDF_MAX_PAGES * 12)),
        )
    except FileNotFoundError:
        return "", "swift_unavailable"
    except subprocess.TimeoutExpired:
        return "", "swift_timeout"
    except Exception as e:
        return "", f"swift_run_error:{type(e).__name__}"
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except Exception:
                pass

    if proc.returncode != 0:
        stderr = (proc.stderr or "").lower()
        if "no such module" in stderr and "pdfkit" in stderr:
            return "", "swift_pdfkit_unavailable"
        if "open_failed" in stderr:
            return "", "swift_pdf_open_failed"
        return "", f"swift_pdfkit_error:{proc.returncode}"

    txt = _clip_text(proc.stdout or "")
    if txt:
        return txt, "ok"
    return "", "pdf_text_empty"


def _extract_pdf_text(path: str) -> tuple[str, str]:
    last_reason = ""

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(path)
        chunks: list[str] = []
        for page in reader.pages[: max(1, ATTACH_PDF_MAX_PAGES)]:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt.strip():
                chunks.append(txt.strip())
            if len("\n\n".join(chunks)) >= ATTACH_MAX_TEXT_CHARS:
                break
        merged = _clip_text("\n\n".join(chunks))
        if merged:
            return merged, "ok"
        last_reason = "pdf_text_empty"
    except ModuleNotFoundError:
        last_reason = "pypdf_unavailable"
    except Exception as e:
        last_reason = f"pypdf_error:{type(e).__name__}"

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore

        txt = pdfminer_extract_text(path, maxpages=max(1, ATTACH_PDF_MAX_PAGES)) or ""
        txt = _clip_text(txt)
        if txt:
            return txt, "ok"
        last_reason = "pdf_text_empty"
    except ModuleNotFoundError:
        if not last_reason:
            last_reason = "pdfminer_unavailable"
    except Exception as e:
        last_reason = f"pdfminer_error:{type(e).__name__}"

    txt, reason = _extract_pdf_text_swift(path)
    if txt:
        return txt, "ok"

    if reason not in ("swift_unavailable", "swift_pdfkit_unavailable", "swift_pdfkit_non_darwin"):
        return "", reason or last_reason or "pdf_extractor_unavailable"

    if last_reason in ("pypdf_unavailable", "pdfminer_unavailable", ""):
        return "", "pdf_extractor_unavailable"
    return "", last_reason


def _extract_docx_text(path: str) -> tuple[str, str]:
    try:
        import zipfile
        from html import unescape

        with zipfile.ZipFile(path) as zf:
            with zf.open("word/document.xml") as fh:
                xml = fh.read().decode("utf-8", errors="ignore")
        xml = re.sub(r"(?i)</w:p>", "\n", xml)
        xml = re.sub(r"<[^>]+>", " ", xml)
        xml = unescape(xml)
        xml = re.sub(r"\s+", " ", xml).strip()
        xml = _clip_text(xml)
        if xml:
            return xml, "ok"
        return "", "docx_text_empty"
    except KeyError:
        return "", "docx_missing_document_xml"
    except Exception as e:
        return "", f"docx_parse_error:{type(e).__name__}"


def _extract_plain_text_doc(path: str) -> tuple[str, str]:
    try:
        raw = Path(path).read_bytes()[: min(ATTACH_MAX_FILE_BYTES, 2 * 1024 * 1024)]
    except Exception as e:
        return "", f"text_read_error:{type(e).__name__}"

    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            txt = raw.decode(enc, errors="ignore")
            txt = _clip_text(txt)
            if txt:
                return txt, "ok"
        except Exception:
            continue
    return "", "text_decode_failed"


def _infer_original_path(meta: dict, meta_path: Path) -> Path:
    original = _resolve_stage1_path(meta.get("original_path"), fallback=None)
    if str(original) not in {"", "."} and original.exists() and original.is_file():
        return original

    channel_slug = str(meta.get("channel_slug") or "").strip()
    try:
        msg_id = int(meta.get("message_id") or 0)
    except Exception:
        msg_id = 0
    original_name = str(meta.get("original_name") or "").strip()
    if channel_slug and msg_id > 0:
        candidates = _attachment_original_candidates(channel_slug, msg_id, original_name)
        if candidates:
            return candidates[0]

    candidates = []
    if meta_path.name == "meta.json":
        for one in meta_path.parent.iterdir():
            if one.name in {"meta.json", "extracted.txt"}:
                continue
            if one.is_file():
                candidates.append(one)
    else:
        prefix = meta_path.name.replace("__meta.json", "__original__")
        candidates.extend(sorted(meta_path.parent.glob(f"{prefix}*")))

    if not candidates:
        return Path("")
    candidates.sort(key=lambda p: p.name)
    return candidates[0]


def _infer_kind(meta: dict, original_path: Path) -> str:
    kind = str(meta.get("kind") or "").strip().lower()
    if kind:
        return kind
    ext = original_path.suffix.lower()
    mime = str(meta.get("mime") or "").lower()
    if "pdf" in mime or ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if mime.startswith("text/") or ext in {".txt", ".md", ".csv", ".log"}:
        return "text_doc"
    return kind


def _bump_reason(stats: dict, reason: str) -> None:
    stats["reason_counts"][reason] = int(stats["reason_counts"].get(reason, 0)) + 1


def _clear_pdf_support_fields(meta: dict) -> bool:
    changed = False
    reset_map = {
        "pdf_manifest_path": "",
        "pdf_page_count": 0,
        "pdf_text_pages": 0,
        "pdf_render_pages": 0,
        "pdf_page_text_status": "",
        "pdf_page_render_status": "",
        "pdf_quality_grade": "",
        "compressed_bundle_path": "",
        "compressed_bundle_status": "",
        "compressed_bundle_reason": "",
        "human_review_window_active": False,
        "human_review_window_until": "",
    }
    for key, value in reset_map.items():
        if meta.get(key) != value:
            meta[key] = value
            changed = True
    return changed


def _apply_pdf_support_artifacts(meta: dict, meta_path: Path, original_path: Path, extract_path: Path | None, stats: dict) -> None:
    channel_slug = str(meta.get("channel_slug") or "").strip()
    try:
        msg_id = int(meta.get("message_id") or 0)
    except Exception:
        msg_id = 0
    if not channel_slug or msg_id <= 0:
        return

    artifact_dir = _attachment_bucket_dir(channel_slug, msg_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    info = ensure_pdf_support_artifacts(
        stage1_dir=STAGE1_DIR,
        artifact_dir=artifact_dir,
        meta_path=meta_path,
        original_path=original_path,
        extract_path=extract_path if extract_path and extract_path.exists() else None,
        message_id=msg_id,
        message_date=str(meta.get("message_date") or ""),
        max_pages=ATTACH_PDF_MAX_PAGES,
        max_text_chars=ATTACH_MAX_TEXT_CHARS,
        max_width=ATTACH_RENDER_MAX_WIDTH,
        hot_window_days=ATTACH_HOT_WINDOW_DAYS,
    )
    pages = info.get("pages", []) if isinstance(info.get("pages"), list) else []
    meta["artifact_schema_version"] = max(3, int(meta.get("artifact_schema_version") or 0))
    meta["artifact_layout"] = "bucketed_v3_flat"
    meta["pdf_manifest_path"] = str(info.get("manifest_rel_path") or "")
    meta["pdf_page_count"] = int(info.get("page_count") or 0)
    meta["pdf_text_pages"] = int(info.get("text_pages_written") or 0)
    meta["pdf_render_pages"] = int(info.get("rendered_pages_written") or 0)
    meta["pdf_page_text_status"] = str(info.get("text_status") or "")
    meta["pdf_page_render_status"] = str(info.get("render_status") or "")
    meta["pdf_quality_grade"] = str(info.get("quality_grade") or "")
    meta["compressed_bundle_path"] = str(info.get("compressed_bundle_path") or "")
    meta["compressed_bundle_status"] = str(info.get("compressed_bundle_status") or "")
    meta["compressed_bundle_reason"] = str(info.get("compressed_bundle_reason") or "")
    meta["human_review_window_active"] = bool(info.get("human_review_window_active"))
    meta["human_review_window_until"] = str(info.get("human_review_window_until") or "")
    stats["pdf_page_manifests_written"] += 1
    stats["pdf_page_text_files_written"] += sum(1 for page in pages if isinstance(page, dict) and str(page.get("text_rel_path") or "").strip())
    stats["pdf_page_render_files_written"] += sum(1 for page in pages if isinstance(page, dict) and str(page.get("render_rel_path") or "").strip())
    if str(info.get("compressed_bundle_status") or "") == "ok":
        stats["pdf_bundle_ok"] += 1
    else:
        stats["pdf_bundle_failed"] += 1



def _collect_pdf_totals() -> tuple[int, int]:
    totals: dict[tuple[str, int], bool] = {}
    if not ATTACH_ARTIFACT_ROOT.exists():
        return 0, 0
    for meta_path in _iter_attachment_meta_paths():
        meta = _read_json(meta_path)
        if not meta:
            continue
        kind = str(meta.get("kind") or "").strip().lower()
        if kind != "pdf":
            continue
        channel_slug = str(meta.get("channel_slug") or "").strip()
        try:
            msg_id = int(meta.get("message_id") or 0)
        except Exception:
            msg_id = 0
        if not channel_slug or msg_id <= 0:
            continue
        key = (channel_slug, msg_id)
        prev_ok = bool(totals.get(key))
        now_ok = str(meta.get("extraction_status") or "").strip().lower() == "ok"
        totals[key] = prev_ok or now_ok
    total = len(totals)
    ok = sum(1 for is_ok in totals.values() if is_ok)
    return total, ok


def main() -> int:
    started_at = datetime.now(timezone.utc)
    stats = {
        "saved_at": started_at.isoformat(),
        "artifact_root": _rel_stage1_path(ATTACH_ARTIFACT_ROOT),
        "legacy_logs_scanned": 0,
        "legacy_supported_candidates": 0,
        "legacy_meta_created": 0,
        "legacy_meta_updated": 0,
        "legacy_original_copied": 0,
        "legacy_extract_backfilled_inline": 0,
        "legacy_extract_backfilled_path": 0,
        "meta_scanned": 0,
        "supported_candidates": 0,
        "attempted": 0,
        "reused_existing": 0,
        "extracted_ok": 0,
        "failed": 0,
        "skipped_missing_original": 0,
        "updated_meta": 0,
        "pdf_page_manifests_written": 0,
        "pdf_page_text_files_written": 0,
        "pdf_page_render_files_written": 0,
        "pdf_bundle_ok": 0,
        "pdf_bundle_failed": 0,
        "reason_counts": {},
    }

    ATTACH_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    _reconcile_from_legacy_logs(stats)

    for meta_path in _iter_attachment_meta_paths():
        stats["meta_scanned"] += 1
        meta = _read_json(meta_path)
        if not meta:
            continue

        original_path = _infer_original_path(meta, meta_path)
        kind = _infer_kind(meta, original_path)
        if kind not in SUPPORTED_KINDS:
            continue

        original_ready = bool(original_path and original_path.exists() and original_path.is_file())
        stats["supported_candidates"] += 1
        extract_path = _resolve_stage1_path(meta.get("extract_path"), fallback=meta_path.parent / "extracted.txt")
        if extract_path and extract_path.exists() and extract_path.stat().st_size > 0:
            changed = False
            if meta.get("extraction_status") != "ok":
                meta["extraction_status"] = "ok"
                changed = True
            if meta.get("extraction_reason") != "ok":
                meta["extraction_reason"] = "ok"
                changed = True
            rel_extract = _rel_stage1_path(extract_path)
            if meta.get("extract_path") != rel_extract:
                meta["extract_path"] = rel_extract
                changed = True
            if kind == "pdf":
                if original_ready:
                    _apply_pdf_support_artifacts(meta, meta_path, original_path, extract_path, stats)
                    changed = True
                elif _clear_pdf_support_fields(meta):
                    changed = True
            if changed:
                meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_json(meta_path, meta)
                stats["updated_meta"] += 1
            stats["reused_existing"] += 1
            continue

        if not original_ready:
            meta["extraction_status"] = "failed"
            meta["extraction_reason"] = "missing_original"
            if kind == "pdf":
                _clear_pdf_support_fields(meta)
            meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_json(meta_path, meta)
            stats["updated_meta"] += 1
            stats["skipped_missing_original"] += 1
            stats["failed"] += 1
            _bump_reason(stats, "missing_original")
            continue

        stats["attempted"] += 1
        if original_path.stat().st_size > ATTACH_MAX_FILE_BYTES:
            text, reason = "", f"file_too_large:{kind}"
        elif kind == "pdf":
            text, reason = _extract_pdf_text(str(original_path))
        elif kind == "docx":
            text, reason = _extract_docx_text(str(original_path))
        else:
            text, reason = _extract_plain_text_doc(str(original_path))

        text = _clip_text(text)
        if text:
            extract_path.parent.mkdir(parents=True, exist_ok=True)
            extract_path.write_text(text, encoding="utf-8")
            meta["extract_path"] = _rel_stage1_path(extract_path)
            meta["extraction_status"] = "ok"
            meta["extraction_reason"] = "ok"
            meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
            meta["extraction_origin"] = "stage01_telegram_attachment_extract_backfill"
            if kind == "pdf":
                _apply_pdf_support_artifacts(meta, meta_path, original_path, extract_path, stats)
            _write_json(meta_path, meta)
            stats["updated_meta"] += 1
            stats["extracted_ok"] += 1
            continue

        fail_reason = reason or f"empty_text:{kind}"
        meta["extraction_status"] = "failed"
        meta["extraction_reason"] = fail_reason
        meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
        meta["extraction_origin"] = "stage01_telegram_attachment_extract_backfill"
        if kind == "pdf":
            _apply_pdf_support_artifacts(meta, meta_path, original_path, extract_path, stats)
        _write_json(meta_path, meta)
        stats["updated_meta"] += 1
        stats["failed"] += 1
        _bump_reason(stats, fail_reason)

    pdf_total, pdf_ok = _collect_pdf_totals()

    finished_at = datetime.now(timezone.utc)
    status = "OK" if stats["failed"] == 0 else "WARN"
    payload = {
        **stats,
        "pdf_meta_total": int(pdf_total),
        "pdf_extract_ok_total": int(pdf_ok),
        "finished_at": finished_at.isoformat(),
        "duration_sec": round((finished_at - started_at).total_seconds(), 3),
        "status": status,
    }
    _write_json(STATUS_PATH, payload)

    error_summary = [f"{k}:{v}" for k, v in sorted(stats["reason_counts"].items(), key=lambda kv: (-kv[1], kv[0]))[:20]]
    append_pipeline_event(
        source="telegram_attachment_extract_backfill",
        status=status,
        count=int(stats["extracted_ok"]),
        errors=error_summary,
        note=(
            f"legacy_candidates={stats['legacy_supported_candidates']} supported={stats['supported_candidates']} "
            f"attempted={stats['attempted']} reused={stats['reused_existing']} ok={stats['extracted_ok']} failed={stats['failed']}"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
