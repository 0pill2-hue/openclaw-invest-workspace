#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORKSPACE_VENV_PY = ROOT / ".venv/bin/python3"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from invest.stages.common.stage_pdf_artifacts import (
    PAGE_MARKER_FORMAT,
    build_pdf_page_marked_text_from_manifest,
    count_pdf_page_markers,
    ensure_pdf_support_artifacts,
    extract_pdf_text_with_page_markers,
    has_pdf_page_markers,
)
from invest.stages.common.stage_raw_db import index_pdf_artifacts_from_raw
from pipeline_logger import append_pipeline_event

STAGE1_DIR = ROOT / "invest/stages/stage1"
ATTACH_ARTIFACT_ROOT = STAGE1_DIR / "outputs/raw/qualitative/attachments/telegram"
TELEGRAM_TEXT_ROOT = STAGE1_DIR / "outputs/raw/qualitative/text/telegram"
RAW_OUTPUT_ROOT = STAGE1_DIR / "outputs/raw"
DB_PATH = STAGE1_DIR / "outputs/db/stage1_raw_archive.sqlite3"
STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_attachment_extract_backfill_status.json"
ENV_PATHS = [
    STAGE1_DIR / ".env",
    Path.home() / ".config/invest/invest_autocollect.env",
]


def _bootstrap_stage1_env() -> None:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_bootstrap_stage1_env()

ATTACH_BUCKET_COUNT = max(1, int(os.environ.get("TELEGRAM_ATTACH_BUCKET_COUNT", "128")))
ATTACH_MAX_FILE_BYTES = int(os.environ.get("TELEGRAM_ATTACH_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
ATTACH_MAX_TEXT_CHARS = int(os.environ.get("TELEGRAM_ATTACH_MAX_TEXT_CHARS", "6000"))
ATTACH_PDF_MAX_PAGES = int(os.environ.get("TELEGRAM_ATTACH_PDF_MAX_PAGES", "25"))
ATTACH_RENDER_MAX_WIDTH = int(os.environ.get("TELEGRAM_ATTACH_RENDER_MAX_WIDTH", "1200"))
ATTACH_HOT_WINDOW_DAYS = int(os.environ.get("TELEGRAM_ATTACH_HOT_WINDOW_DAYS", "31"))
ATTACH_RECOVER_ENABLED = str(os.environ.get("TELEGRAM_ATTACH_RECOVER_MISSING_ORIGINALS", "0")).strip().lower() in {"1", "true", "yes", "on"}
ATTACH_RECOVER_LIMIT = max(0, int(os.environ.get("TELEGRAM_ATTACH_RECOVER_LIMIT", "0") or "0"))
ATTACH_RECOVER_MAX_FILE_BYTES = int(os.environ.get("TELEGRAM_ATTACH_RECOVER_MAX_FILE_BYTES", str(50 * 1024 * 1024)))
if ATTACH_RECOVER_ENABLED and WORKSPACE_VENV_PY.exists() and os.path.realpath(sys.executable) != os.path.realpath(str(WORKSPACE_VENV_PY)):
    try:
        import telethon  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        os.execv(str(WORKSPACE_VENV_PY), [str(WORKSPACE_VENV_PY)] + sys.argv)
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


def _pdf_doc_identity(meta: dict) -> tuple[str, int]:
    channel_slug = str(meta.get("channel_slug") or "").strip()
    try:
        msg_id = int(meta.get("message_id") or 0)
    except Exception:
        msg_id = 0
    return channel_slug, msg_id


def _stage1_rel_exists(rel_path: str | None) -> bool:
    path = _resolve_stage1_path(rel_path, fallback=None)
    return path is not None and str(path) not in {"", "."} and path.exists() and path.is_file()


def _pdf_meta_rank(meta_path: Path, meta: dict) -> tuple[int, int, int, int, int, int, int]:
    schema_version = int(meta.get("artifact_schema_version") or 0)
    extract_ok = 1 if str(meta.get("extraction_status") or "").strip().lower() == "ok" else 0
    extract_exists = 1 if _stage1_rel_exists(str(meta.get("extract_path") or "")) else 0
    original_exists = 1 if _stage1_rel_exists(str(meta.get("original_path") or "")) else 0
    manifest_exists = 1 if _stage1_rel_exists(str(meta.get("pdf_manifest_path") or "")) else 0
    bucket_meta = 1 if meta_path.name.endswith("__meta.json") else 0
    richness = sum(1 for key in ("extract_path", "original_path", "pdf_manifest_path", "pdf_quality_grade") if str(meta.get(key) or "").strip())
    return (extract_ok, extract_exists, original_exists, manifest_exists, schema_version, richness, bucket_meta)


def _canonical_pdf_meta_path_set() -> set[Path]:
    grouped: dict[tuple[str, int], list[tuple[Path, dict]]] = {}
    for meta_path in _iter_attachment_meta_paths():
        meta = _read_json(meta_path)
        if str(meta.get("kind") or "").strip().lower() != "pdf":
            continue
        key = _pdf_doc_identity(meta)
        if not key[0] or key[1] <= 0:
            continue
        grouped.setdefault(key, []).append((meta_path, meta))

    out: set[Path] = set()
    for entries in grouped.values():
        ranked = sorted(entries, key=lambda item: _pdf_meta_rank(item[0], item[1]))
        if ranked:
            out.add(ranked[-1][0])
    return out


def _load_stage1_env() -> None:
    _bootstrap_stage1_env()


def _collect_missing_original_meta_records() -> tuple[list[dict], int]:
    best: dict[tuple[str, int], tuple[tuple[int, int, int], dict]] = {}
    total_missing = 0
    canonical_pdf_meta_paths = _canonical_pdf_meta_path_set()

    for meta_path in _iter_attachment_meta_paths():
        meta = _read_json(meta_path)
        channel_slug = str(meta.get("channel_slug") or "").strip()
        try:
            msg_id = int(meta.get("message_id") or 0)
        except Exception:
            msg_id = 0
        if not channel_slug or msg_id <= 0:
            continue
        kind = str(meta.get("kind") or "").strip().lower()
        if kind not in SUPPORTED_KINDS:
            continue
        if kind == "pdf":
            key = _pdf_doc_identity(meta)
            if key[0] and key[1] > 0 and meta_path not in canonical_pdf_meta_paths:
                continue
            if _pdf_manifest_ready(meta) or _is_deleted_after_decompose(meta):
                continue
        original_path = _infer_original_path(meta, meta_path)
        if original_path.exists() and original_path.is_file():
            continue
        total_missing += 1
        rank = (
            int(meta.get("artifact_schema_version") or 0),
            1 if meta_path.name.endswith("__meta.json") else 0,
            int(meta_path.stat().st_mtime_ns),
        )
        key = (channel_slug, msg_id)
        prev = best.get(key)
        if prev is None or rank > prev[0]:
            best[key] = (rank, {"meta_path": meta_path, "meta": meta, "channel_slug": channel_slug, "message_id": msg_id})

    records = [payload for _, payload in best.values()]
    records.sort(key=lambda row: (row["message_id"], row["channel_slug"]), reverse=True)
    return records, total_missing


def _dialog_aliases(dialog) -> set[str]:
    entity = getattr(dialog, "entity", None)
    if entity is None:
        return set()
    title = str(getattr(entity, "title", "") or getattr(dialog, "name", "") or "").strip()
    username = str(getattr(entity, "username", "") or "").strip()
    entity_id = getattr(entity, "id", None)

    safe_title = _safe_component(title, "") if title else ""
    safe_username = _safe_component(username, "") if username else ""
    aliases: set[str] = set()
    if safe_title:
        aliases.add(safe_title.casefold())
    if safe_username:
        aliases.add(safe_username.casefold())
    if safe_title and safe_username:
        aliases.add(f"{safe_title}_{safe_username}".casefold())
    if entity_id:
        aliases.add(str(int(entity_id)).casefold())
        if safe_title:
            aliases.add(f"{safe_title}_{int(entity_id)}".casefold())
    return aliases


async def _recover_missing_originals_async(records: list[dict], stats: dict) -> None:
    if not records:
        return

    try:
        from telethon import TelegramClient  # type: ignore
    except ModuleNotFoundError:
        stats["telegram_recovery_skipped"] += len(records)
        _bump_reason(stats, "telegram_recovery_telethon_unavailable")
        return

    _load_stage1_env()
    try:
        api_id = int(os.environ.get("TELEGRAM_API_ID", "0") or "0")
    except Exception:
        api_id = 0
    api_hash = str(os.environ.get("TELEGRAM_API_HASH", "") or "").strip()
    if not api_id or not api_hash:
        stats["telegram_recovery_skipped"] += len(records)
        _bump_reason(stats, "telegram_recovery_missing_credentials")
        return

    session_name = str(STAGE1_DIR / "scripts/jobis_mtproto_session")
    client = TelegramClient(session_name, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            stats["telegram_recovery_skipped"] += len(records)
            _bump_reason(stats, "telegram_recovery_unauthorized")
            return

        alias_map: dict[str, object] = {}
        async for dialog in client.iter_dialogs():
            input_entity = getattr(dialog, "input_entity", None) or getattr(dialog, "entity", None)
            if input_entity is None:
                continue
            stats["telegram_recovery_dialogs_scanned"] += 1
            for alias in _dialog_aliases(dialog):
                alias_map.setdefault(alias, input_entity)

        for rec in records:
            channel_slug = str(rec.get("channel_slug") or "").strip()
            msg_id = int(rec.get("message_id") or 0)
            meta_path = rec.get("meta_path")
            meta = dict(rec.get("meta") or {})
            stats["telegram_recovery_attempted"] += 1

            entity = alias_map.get(channel_slug.casefold())
            if entity is None and "_" in channel_slug:
                suffix = channel_slug.rsplit("_", 1)[-1].strip()
                if suffix.isdigit():
                    entity = alias_map.get(suffix.casefold())
            if entity is None:
                stats["telegram_recovery_failed"] += 1
                _bump_reason(stats, "telegram_recovery_entity_unresolved")
                continue

            try:
                message = await client.get_messages(entity, ids=msg_id)
            except Exception as e:
                stats["telegram_recovery_failed"] += 1
                _bump_reason(stats, f"telegram_recovery_get_messages_error:{type(e).__name__}")
                continue
            if not message or not getattr(message, "media", None):
                stats["telegram_recovery_failed"] += 1
                _bump_reason(stats, "telegram_recovery_media_missing")
                continue

            file_obj = getattr(message, "file", None)
            try:
                file_size = int(getattr(file_obj, "size", 0) or 0)
            except Exception:
                file_size = 0
            if file_size > 0 and file_size > ATTACH_RECOVER_MAX_FILE_BYTES:
                stats["telegram_recovery_failed"] += 1
                _bump_reason(stats, "telegram_recovery_file_too_large")
                continue

            kind = str(meta.get("kind") or "").strip().lower()
            file_name = str(meta.get("original_name") or getattr(file_obj, "name", "") or "").strip()
            suffix = Path(file_name).suffix.lower()
            if not suffix:
                suffix = str(getattr(file_obj, "ext", "") or "").strip().lower()
            if not suffix:
                suffix = ".pdf" if kind == "pdf" else (".docx" if kind == "docx" else ".txt")
            if not file_name:
                file_name = f"msg_{msg_id}{suffix}"

            target_name = _build_original_target_name(file_name, None, msg_id)
            target_path = _attachment_original_path(channel_slug, msg_id, target_name)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if not target_path.exists():
                runtime_dir = STAGE1_DIR / "outputs/runtime"
                runtime_dir.mkdir(parents=True, exist_ok=True)
                tmp_dir = Path(tempfile.mkdtemp(prefix="tg_recover_", dir=str(runtime_dir)))
                try:
                    temp_target = tmp_dir / target_name
                    downloaded = await client.download_media(message, file=str(temp_target))
                    src = Path(str(downloaded or "")).resolve() if downloaded else Path("")
                    if not src.exists() or not src.is_file():
                        stats["telegram_recovery_failed"] += 1
                        _bump_reason(stats, "telegram_recovery_download_failed")
                        continue
                    target_name = _build_original_target_name(file_name or src.name, src, msg_id)
                    target_path = _attachment_original_path(channel_slug, msg_id, target_name)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    if not target_path.exists():
                        shutil.move(str(src), str(target_path))
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

            if not target_path.exists() or not target_path.is_file():
                stats["telegram_recovery_failed"] += 1
                _bump_reason(stats, "telegram_recovery_target_missing")
                continue

            now_iso = datetime.now(timezone.utc).isoformat()
            meta["artifact_schema_version"] = max(2, int(meta.get("artifact_schema_version") or 0))
            meta["artifact_layout"] = str(meta.get("artifact_layout") or "bucketed_v2")
            meta["channel_slug"] = channel_slug
            meta["message_id"] = msg_id
            meta["original_name"] = target_name
            meta["original_path"] = _rel_stage1_path(target_path)
            meta["original_store_status"] = "ok"
            meta["original_store_reason"] = "ok"
            meta["original_store_origin"] = "telegram_redownload"
            meta["declared_size"] = int(meta.get("declared_size") or target_path.stat().st_size)
            meta["original_recovered_at"] = now_iso
            if meta_path:
                _write_json(meta_path, meta)
            stats["telegram_recovery_ok"] += 1
            stats["telegram_recovery_bytes"] += int(target_path.stat().st_size)
    finally:
        await client.disconnect()


def _recover_missing_originals(stats: dict) -> None:
    records, total_missing = _collect_missing_original_meta_records()
    stats["telegram_recovery_candidates_total"] = len(records)
    stats["telegram_recovery_missing_meta_total"] = int(total_missing)
    if not ATTACH_RECOVER_ENABLED:
        return
    if ATTACH_RECOVER_LIMIT > 0:
        records = records[:ATTACH_RECOVER_LIMIT]
    stats["telegram_recovery_candidates_selected"] = len(records)
    if not records:
        return
    try:
        import asyncio
        asyncio.run(_recover_missing_originals_async(records, stats))
    except Exception as e:
        stats["telegram_recovery_failed"] += len(records)
        _bump_reason(stats, f"telegram_recovery_runtime_error:{type(e).__name__}")


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
            allow_original_restore = not (kind == "pdf" and (_pdf_manifest_ready(meta) or _is_deleted_after_decompose(meta)))
            original_src = _resolve_marker_path(marker_original, log_path=log_path) if allow_original_restore else None
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


def _pdf_manifest_ready(meta: dict) -> bool:
    manifest_path = _resolve_stage1_path(meta.get("pdf_manifest_path"), fallback=None)
    if manifest_path is None or str(manifest_path) in {"", "."} or not manifest_path.exists() or not manifest_path.is_file():
        return False
    try:
        page_count = int(meta.get("pdf_page_count") or 0)
    except Exception:
        page_count = 0
    if page_count > 0:
        return True
    manifest = _read_json(manifest_path)
    try:
        manifest_page_count = int(manifest.get("page_count") or 0)
    except Exception:
        manifest_page_count = 0
    return manifest_page_count > 0


def _is_deleted_after_decompose(meta: dict) -> bool:
    status = str(meta.get("original_store_status") or "").strip().lower()
    reason = str(meta.get("original_store_reason") or "").strip().lower()
    return status == "deleted_after_decompose" or reason == "deleted_after_decompose" or bool(meta.get("original_deleted_after_decompose"))


def _mark_original_deleted_after_decompose(meta: dict) -> bool:
    now_iso = datetime.now(timezone.utc).isoformat()
    changed = False
    original_rel = str(meta.get("original_path") or "").strip()
    deleted_rel = str(meta.get("original_deleted_rel_path") or "").strip()
    if original_rel and deleted_rel != original_rel:
        meta["original_deleted_rel_path"] = original_rel
        changed = True
    if original_rel:
        meta["original_path"] = ""
        changed = True
    if meta.get("original_store_status") != "deleted_after_decompose":
        meta["original_store_status"] = "deleted_after_decompose"
        changed = True
    if meta.get("original_store_reason") != "deleted_after_decompose":
        meta["original_store_reason"] = "deleted_after_decompose"
        changed = True
    if meta.get("original_deleted_after_decompose") is not True:
        meta["original_deleted_after_decompose"] = True
        changed = True
    if not str(meta.get("original_deleted_at") or "").strip():
        meta["original_deleted_at"] = now_iso
        changed = True
    return changed


def _bump_reason(stats: dict, reason: str) -> None:
    stats["reason_counts"][reason] = int(stats["reason_counts"].get(reason, 0)) + 1


def _set_pdf_extract_contract(meta: dict, *, page_marked: bool, marker_count: int, mapping_status: str, extract_format: str) -> bool:
    desired = {
        "extract_format": str(extract_format or ""),
        "pdf_page_marked": bool(page_marked),
        "pdf_page_marker_format": PAGE_MARKER_FORMAT,
        "pdf_page_marker_count": int(marker_count if page_marked else 0),
        "pdf_page_mapping_status": str(mapping_status or ""),
    }
    changed = False
    for key, value in desired.items():
        if meta.get(key) != value:
            meta[key] = value
            changed = True
    return changed


def _build_page_marked_text_from_manifest(meta: dict) -> dict:
    manifest_path = _resolve_stage1_path(meta.get("pdf_manifest_path"), fallback=None)
    if manifest_path is None or str(manifest_path) in {"", "."} or not manifest_path.exists() or not manifest_path.is_file():
        return {
            "text": "",
            "reason": "missing_manifest",
            "page_marked": False,
            "page_marker_count": 0,
            "page_marker_format": PAGE_MARKER_FORMAT,
            "page_mapping_status": "missing_original_and_page_artifacts",
        }
    manifest = _read_json(manifest_path)
    return build_pdf_page_marked_text_from_manifest(stage1_dir=STAGE1_DIR, manifest=manifest, max_text_chars=ATTACH_MAX_TEXT_CHARS)


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


def _collect_pdf_db_totals(db_path: Path) -> dict:
    payload = {
        "pdf_db_status": "missing",
        "pdf_db_error": "",
        "pdf_db_documents_total": 0,
        "pdf_db_extract_ok_total": 0,
        "pdf_db_decomposed_total": 0,
        "pdf_db_text_ready_total": 0,
        "pdf_db_render_ready_total": 0,
        "pdf_db_pages_total": 0,
        "pdf_db_quality_a_total": 0,
        "pdf_db_missing_original_total": 0,
        "pdf_db_page_marked_total": 0,
        "pdf_db_page_mapping_missing_total": 0,
    }
    if not db_path.exists():
        return payload

    queries = {
        "pdf_db_documents_total": "SELECT COUNT(*) FROM pdf_documents",
        "pdf_db_extract_ok_total": "SELECT COUNT(*) FROM pdf_documents WHERE extraction_status = 'ok'",
        "pdf_db_decomposed_total": "SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(manifest_rel_path, '') <> ''",
        "pdf_db_text_ready_total": "SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(text_pages, 0) > 0",
        "pdf_db_render_ready_total": "SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(rendered_pages, 0) > 0",
        "pdf_db_pages_total": "SELECT COUNT(*) FROM pdf_pages",
        "pdf_db_quality_a_total": "SELECT COUNT(*) FROM pdf_documents WHERE quality_grade = 'A'",
        "pdf_db_missing_original_total": "SELECT COUNT(*) FROM pdf_documents WHERE extraction_reason = 'missing_original'",
        "pdf_db_page_marked_total": "SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(page_marked, 0) = 1",
        "pdf_db_page_mapping_missing_total": "SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(page_mapping_status, '') LIKE 'missing%'",
    }
    try:
        with sqlite3.connect(str(db_path)) as conn:
            for key, sql in queries.items():
                row = conn.execute(sql).fetchone()
                payload[key] = int(row[0] or 0) if row else 0
    except Exception as e:
        payload["pdf_db_status"] = "error"
        payload["pdf_db_error"] = type(e).__name__
        return payload

    payload["pdf_db_status"] = "ok"
    return payload


def _sync_pdf_db(stats: dict) -> dict:
    stats["pdf_db_reindex_attempted"] += 1
    try:
        summary = index_pdf_artifacts_from_raw(raw_root=RAW_OUTPUT_ROOT, db_path=DB_PATH)
    except Exception as e:
        stats["pdf_db_reindex_failed"] += 1
        _bump_reason(stats, f"pdf_db_index_error:{type(e).__name__}")
        out = _collect_pdf_db_totals(DB_PATH)
        out["pdf_db_status"] = "error"
        out["pdf_db_error"] = type(e).__name__
        out["pdf_db_index_summary"] = {}
        return out

    stats["pdf_db_reindex_ok"] += 1
    out = _collect_pdf_db_totals(DB_PATH)
    out["pdf_db_index_summary"] = summary.as_dict()
    return out


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
        "telegram_recovery_candidates_total": 0,
        "telegram_recovery_missing_meta_total": 0,
        "telegram_recovery_candidates_selected": 0,
        "telegram_recovery_dialogs_scanned": 0,
        "telegram_recovery_attempted": 0,
        "telegram_recovery_ok": 0,
        "telegram_recovery_failed": 0,
        "telegram_recovery_skipped": 0,
        "telegram_recovery_bytes": 0,
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
        "pdf_page_marked_written": 0,
        "pdf_page_marked_rebuilt_from_manifest": 0,
        "pdf_plaintext_preserved_missing_mapping": 0,
        "pdf_db_reindex_attempted": 0,
        "pdf_db_reindex_ok": 0,
        "pdf_db_reindex_failed": 0,
        "reason_counts": {},
    }

    ATTACH_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    _reconcile_from_legacy_logs(stats)
    _recover_missing_originals(stats)
    canonical_pdf_meta_paths = _canonical_pdf_meta_path_set()

    for meta_path in _iter_attachment_meta_paths():
        stats["meta_scanned"] += 1
        meta = _read_json(meta_path)
        if not meta:
            continue

        original_path = _infer_original_path(meta, meta_path)
        kind = _infer_kind(meta, original_path)
        if kind not in SUPPORTED_KINDS:
            continue
        if kind == "pdf":
            key = _pdf_doc_identity(meta)
            if key[0] and key[1] > 0 and meta_path not in canonical_pdf_meta_paths:
                continue

        original_ready = bool(original_path and original_path.exists() and original_path.is_file())
        manifest_ready = kind == "pdf" and _pdf_manifest_ready(meta)
        stats["supported_candidates"] += 1
        extract_path = _resolve_stage1_path(meta.get("extract_path"), fallback=meta_path.parent / "extracted.txt")
        if extract_path and extract_path.exists() and extract_path.stat().st_size > 0:
            changed = False
            try:
                current_text = extract_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                current_text = ""
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
                if has_pdf_page_markers(current_text):
                    changed |= _set_pdf_extract_contract(
                        meta,
                        page_marked=True,
                        marker_count=count_pdf_page_markers(current_text),
                        mapping_status=(
                            "available_from_original"
                            if original_ready
                            else ("available_from_manifest_pages" if manifest_ready else "available_from_extract_text")
                        ),
                        extract_format="pdf_page_marked_text_v1",
                    )
                else:
                    rebuilt_text = ""
                    rebuilt_marker_count = 0
                    rebuilt_mapping_status = ""
                    if original_ready and original_path.stat().st_size <= ATTACH_MAX_FILE_BYTES:
                        pdf_extract = extract_pdf_text_with_page_markers(
                            path=original_path,
                            max_pages=ATTACH_PDF_MAX_PAGES,
                            max_text_chars=ATTACH_MAX_TEXT_CHARS,
                        )
                        rebuilt_text = str(pdf_extract.get("text") or "")
                        rebuilt_marker_count = int(pdf_extract.get("page_marker_count") or 0)
                        rebuilt_mapping_status = "available_from_original"
                    elif manifest_ready:
                        manifest_extract = _build_page_marked_text_from_manifest(meta)
                        rebuilt_text = str(manifest_extract.get("text") or "")
                        rebuilt_marker_count = int(manifest_extract.get("page_marker_count") or 0)
                        rebuilt_mapping_status = str(manifest_extract.get("page_mapping_status") or "available_from_manifest_pages")
                    else:
                        rebuilt_mapping_status = "missing_original_and_page_artifacts"

                    if rebuilt_text:
                        extract_path.write_text(rebuilt_text, encoding="utf-8")
                        changed = True
                        changed |= _set_pdf_extract_contract(
                            meta,
                            page_marked=True,
                            marker_count=rebuilt_marker_count or count_pdf_page_markers(rebuilt_text),
                            mapping_status=rebuilt_mapping_status or "available_from_extract_text",
                            extract_format="pdf_page_marked_text_v1",
                        )
                        stats["pdf_page_marked_written"] += 1
                        if rebuilt_mapping_status == "available_from_manifest_pages":
                            stats["pdf_page_marked_rebuilt_from_manifest"] += 1
                    else:
                        changed |= _set_pdf_extract_contract(
                            meta,
                            page_marked=False,
                            marker_count=0,
                            mapping_status=(
                                "available_from_original"
                                if original_ready
                                else (
                                    rebuilt_mapping_status
                                    or ("missing_manifest_text_pages" if manifest_ready else "missing_original_and_page_artifacts")
                                )
                            ),
                            extract_format="plain_text_legacy",
                        )
                        if not original_ready:
                            stats["pdf_plaintext_preserved_missing_mapping"] += 1
                if original_ready:
                    _apply_pdf_support_artifacts(meta, meta_path, original_path, extract_path, stats)
                    changed = True
                elif manifest_ready:
                    if _mark_original_deleted_after_decompose(meta):
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
            if kind == "pdf" and manifest_ready:
                manifest_extract = _build_page_marked_text_from_manifest(meta)
                manifest_text = str(manifest_extract.get("text") or "")
                changed = False
                if manifest_text:
                    extract_path.parent.mkdir(parents=True, exist_ok=True)
                    extract_path.write_text(manifest_text, encoding="utf-8")
                    meta["extract_path"] = _rel_stage1_path(extract_path)
                    meta["extraction_status"] = "ok"
                    meta["extraction_reason"] = "ok"
                    meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
                    meta["extraction_origin"] = "stage01_telegram_attachment_extract_backfill"
                    changed = True
                    changed |= _set_pdf_extract_contract(
                        meta,
                        page_marked=True,
                        marker_count=int(manifest_extract.get("page_marker_count") or count_pdf_page_markers(manifest_text)),
                        mapping_status=str(manifest_extract.get("page_mapping_status") or "available_from_manifest_pages"),
                        extract_format="pdf_page_marked_text_v1",
                    )
                    stats["pdf_page_marked_written"] += 1
                    stats["pdf_page_marked_rebuilt_from_manifest"] += 1
                    stats["extracted_ok"] += 1
                else:
                    fail_reason = str(manifest_extract.get("reason") or "missing_original")
                    meta["extraction_status"] = "failed"
                    meta["extraction_reason"] = fail_reason
                    meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
                    changed = True
                    changed |= _set_pdf_extract_contract(
                        meta,
                        page_marked=False,
                        marker_count=0,
                        mapping_status=str(manifest_extract.get("page_mapping_status") or "missing_manifest_text_pages"),
                        extract_format="",
                    )
                    stats["failed"] += 1
                    stats["skipped_missing_original"] += 1
                    _bump_reason(stats, fail_reason)
                if _mark_original_deleted_after_decompose(meta):
                    changed = True
                if changed:
                    _write_json(meta_path, meta)
                    stats["updated_meta"] += 1
                continue
            meta["extraction_status"] = "failed"
            meta["extraction_reason"] = "missing_original"
            if kind == "pdf":
                _clear_pdf_support_fields(meta)
                _set_pdf_extract_contract(
                    meta,
                    page_marked=False,
                    marker_count=0,
                    mapping_status="missing_original_and_page_artifacts",
                    extract_format="",
                )
            meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_json(meta_path, meta)
            stats["updated_meta"] += 1
            stats["skipped_missing_original"] += 1
            stats["failed"] += 1
            _bump_reason(stats, "missing_original")
            continue

        stats["attempted"] += 1
        pdf_extract: dict = {}
        if original_path.stat().st_size > ATTACH_MAX_FILE_BYTES:
            text, reason = "", f"file_too_large:{kind}"
        elif kind == "pdf":
            pdf_extract = extract_pdf_text_with_page_markers(
                path=original_path,
                max_pages=ATTACH_PDF_MAX_PAGES,
                max_text_chars=ATTACH_MAX_TEXT_CHARS,
            )
            text = str(pdf_extract.get("text") or "")
            reason = str(pdf_extract.get("reason") or "")
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
                _set_pdf_extract_contract(
                    meta,
                    page_marked=True,
                    marker_count=int(pdf_extract.get("page_marker_count") or count_pdf_page_markers(text)),
                    mapping_status="available_from_original",
                    extract_format="pdf_page_marked_text_v1",
                )
                _apply_pdf_support_artifacts(meta, meta_path, original_path, extract_path, stats)
                stats["pdf_page_marked_written"] += 1
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
            _set_pdf_extract_contract(
                meta,
                page_marked=False,
                marker_count=0,
                mapping_status="available_from_original",
                extract_format="",
            )
            _apply_pdf_support_artifacts(meta, meta_path, original_path, extract_path, stats)
        _write_json(meta_path, meta)
        stats["updated_meta"] += 1
        stats["failed"] += 1
        _bump_reason(stats, fail_reason)

    pdf_local_total, pdf_local_ok = _collect_pdf_totals()
    pdf_db = _sync_pdf_db(stats)

    finished_at = datetime.now(timezone.utc)
    status = "OK" if stats["failed"] == 0 and pdf_db.get("pdf_db_status") == "ok" else "WARN"
    payload = {
        **stats,
        **pdf_db,
        "pdf_progress_basis": "db.pdf_documents/pdf_pages",
        "pdf_local_meta_total": int(pdf_local_total),
        "pdf_local_extract_ok_total": int(pdf_local_ok),
        "pdf_meta_total": int(pdf_db.get("pdf_db_documents_total") or pdf_local_total),
        "pdf_extract_ok_total": int(pdf_db.get("pdf_db_extract_ok_total") or pdf_local_ok),
        "pdf_decompose_ok_total": int(pdf_db.get("pdf_db_decomposed_total") or 0),
        "pdf_pages_total": int(pdf_db.get("pdf_db_pages_total") or 0),
        "pdf_page_marked_total": int(pdf_db.get("pdf_db_page_marked_total") or 0),
        "pdf_page_mapping_missing_total": int(pdf_db.get("pdf_db_page_mapping_missing_total") or 0),
        "finished_at": finished_at.isoformat(),
        "duration_sec": round((finished_at - started_at).total_seconds(), 3),
        "status": status,
    }
    _write_json(STATUS_PATH, payload)

    error_summary = [f"{k}:{v}" for k, v in sorted(stats["reason_counts"].items(), key=lambda kv: (-kv[1], kv[0]))[:20]]
    append_pipeline_event(
        source="telegram_attachment_extract_backfill",
        status=status,
        count=int(payload["pdf_decompose_ok_total"]),
        errors=error_summary,
        note=(
            f"progress_basis={payload['pdf_progress_basis']} db_docs={payload['pdf_meta_total']} "
            f"db_extract_ok={payload['pdf_extract_ok_total']} db_manifest={payload['pdf_decompose_ok_total']} db_pages={payload['pdf_pages_total']} "
            f"recover_ok={stats['telegram_recovery_ok']} recover_failed={stats['telegram_recovery_failed']} "
            f"attempted={stats['attempted']} reused={stats['reused_existing']} failed={stats['failed']}"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
