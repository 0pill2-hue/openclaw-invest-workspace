#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
STAGE1_DIR = ROOT / "invest/stages/stage1"
ATTACH_ARTIFACT_ROOT = STAGE1_DIR / "outputs/raw/qualitative/attachments/telegram"
STATUS_PATH = STAGE1_DIR / "outputs/runtime/telegram_attachment_extract_backfill_status.json"

ATTACH_MAX_FILE_BYTES = int(os.environ.get("TELEGRAM_ATTACH_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
ATTACH_MAX_TEXT_CHARS = int(os.environ.get("TELEGRAM_ATTACH_MAX_TEXT_CHARS", "6000"))
ATTACH_PDF_MAX_PAGES = int(os.environ.get("TELEGRAM_ATTACH_PDF_MAX_PAGES", "25"))
MACOS_SWIFT_BIN = "/usr/bin/swift"
SUPPORTED_KINDS = {"pdf", "docx", "text_doc"}
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
    return STAGE1_DIR / raw


def _clip_text(text: str) -> str:
    x = (text or "").replace("\r", "\n")
    x = re.sub(r"\n{3,}", "\n\n", x)
    x = re.sub(r"[ \t]+", " ", x)
    return x.strip()[:ATTACH_MAX_TEXT_CHARS]


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
    original = _resolve_stage1_path(meta.get("original_path"), fallback=Path(""))
    if original and original.exists():
        return original

    candidates = []
    for one in meta_path.parent.iterdir():
        if one.name in {"meta.json", "extracted.txt"}:
            continue
        if one.is_file():
            candidates.append(one)
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


def main() -> int:
    started_at = datetime.now(timezone.utc)
    stats = {
        "saved_at": started_at.isoformat(),
        "artifact_root": _rel_stage1_path(ATTACH_ARTIFACT_ROOT),
        "meta_scanned": 0,
        "supported_candidates": 0,
        "attempted": 0,
        "reused_existing": 0,
        "extracted_ok": 0,
        "failed": 0,
        "skipped_missing_original": 0,
        "updated_meta": 0,
        "reason_counts": {},
    }

    if not ATTACH_ARTIFACT_ROOT.exists():
        _write_json(STATUS_PATH, {**stats, "finished_at": datetime.now(timezone.utc).isoformat(), "status": "OK", "note": "artifact_root_missing"})
        return 0

    for meta_path in sorted(ATTACH_ARTIFACT_ROOT.rglob("meta.json")):
        stats["meta_scanned"] += 1
        meta = _read_json(meta_path)
        if not meta:
            continue

        original_path = _infer_original_path(meta, meta_path)
        kind = _infer_kind(meta, original_path)
        if kind not in SUPPORTED_KINDS:
            continue

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
            if changed:
                meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
                _write_json(meta_path, meta)
                stats["updated_meta"] += 1
            stats["reused_existing"] += 1
            continue

        if not original_path or not original_path.exists():
            meta["extraction_status"] = "failed"
            meta["extraction_reason"] = "missing_original"
            meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_json(meta_path, meta)
            stats["updated_meta"] += 1
            stats["skipped_missing_original"] += 1
            stats["failed"] += 1
            stats["reason_counts"]["missing_original"] = int(stats["reason_counts"].get("missing_original", 0)) + 1
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
            _write_json(meta_path, meta)
            stats["updated_meta"] += 1
            stats["extracted_ok"] += 1
            continue

        fail_reason = reason or f"empty_text:{kind}"
        meta["extraction_status"] = "failed"
        meta["extraction_reason"] = fail_reason
        meta["extraction_updated_at"] = datetime.now(timezone.utc).isoformat()
        meta["extraction_origin"] = "stage01_telegram_attachment_extract_backfill"
        _write_json(meta_path, meta)
        stats["updated_meta"] += 1
        stats["failed"] += 1
        stats["reason_counts"][fail_reason] = int(stats["reason_counts"].get(fail_reason, 0)) + 1

    finished_at = datetime.now(timezone.utc)
    status = "OK" if stats["failed"] == 0 else "WARN"
    payload = {
        **stats,
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
            f"supported={stats['supported_candidates']} attempted={stats['attempted']} "
            f"reused={stats['reused_existing']} ok={stats['extracted_ok']} failed={stats['failed']}"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
