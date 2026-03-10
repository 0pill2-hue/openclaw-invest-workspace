from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

MACOS_SWIFT_BIN = '/usr/bin/swift'
SWIFT_PDF_PAGE_ARTIFACT_SCRIPT = r'''
import Foundation
import PDFKit
import AppKit

struct PagePayload: Codable {
    let page_no: Int
    let width: Double
    let height: Double
    let text: String
    let render_file: String?
}

struct Payload: Codable {
    let page_count: Int
    let rendered_count: Int
    let pages: [PagePayload]
}

func clip(_ raw: String, maxChars: Int) -> String {
    var s = raw.replacingOccurrences(of: "\r\n", with: "\n")
    s = s.replacingOccurrences(of: "\r", with: "\n")
    while s.contains("\n\n\n") {
        s = s.replacingOccurrences(of: "\n\n\n", with: "\n\n")
    }
    s = s.trimmingCharacters(in: .whitespacesAndNewlines)
    if s.count > maxChars {
        return String(s.prefix(maxChars))
    }
    return s
}

let args = CommandLine.arguments
if args.count < 7 {
    fputs("usage: pdf_page_artifacts.swift <pdf_path> <out_dir> <prefix> <max_pages> <max_width> <max_chars>\n", stderr)
    exit(64)
}

let pdfPath = args[1]
let outDir = args[2]
let prefix = args[3]
let maxPages = max(1, Int(args[4]) ?? 1)
let maxWidth = max(320, Int(args[5]) ?? 1200)
let maxChars = max(256, Int(args[6]) ?? 6000)
let fm = FileManager.default
let outURL = URL(fileURLWithPath: outDir, isDirectory: true)
try? fm.createDirectory(at: outURL, withIntermediateDirectories: true)

guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
    fputs("open_failed\n", stderr)
    exit(65)
}

var pages: [PagePayload] = []
var renderedCount = 0
let upper = min(doc.pageCount, maxPages)

if upper > 0 {
    for idx in 0..<upper {
        guard let page = doc.page(at: idx) else { continue }
        let bounds = page.bounds(for: .mediaBox)
        let width = max(bounds.width, 1.0)
        let height = max(bounds.height, 1.0)
        let scale = Double(maxWidth) / Double(width)
        let targetHeight = max(1, Int(round(Double(height) * scale)))
        let image = page.thumbnail(of: NSSize(width: maxWidth, height: targetHeight), for: .mediaBox)
        var renderFile: String? = nil
        if let tiff = image.tiffRepresentation,
           let rep = NSBitmapImageRep(data: tiff),
           let png = rep.representation(using: .png, properties: [:]) {
            let fileName = String(format: "%@__page_%03d.png", prefix, idx + 1)
            let url = outURL.appendingPathComponent(fileName)
            do {
                try png.write(to: url)
                renderFile = fileName
                renderedCount += 1
            } catch {}
        }

        let text = clip(page.string ?? "", maxChars: maxChars)
        pages.append(PagePayload(
            page_no: idx + 1,
            width: Double(width),
            height: Double(height),
            text: text,
            render_file: renderFile
        ))
    }
}

let payload = Payload(page_count: doc.pageCount, rendered_count: renderedCount, pages: pages)
let enc = JSONEncoder()
if let data = try? enc.encode(payload), let out = String(data: data, encoding: .utf8) {
    FileHandle.standardOutput.write(out.data(using: .utf8) ?? Data())
}
'''


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _rel_path(stage1_dir: Path, path: Path) -> str:
    return os.path.relpath(path, stage1_dir).replace('\\', '/')


def _clip_text(text: str, max_chars: int) -> str:
    x = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    x = re.sub(r'\n{3,}', '\n\n', x)
    x = re.sub(r'[ \t]+', ' ', x)
    return x.strip()[:max_chars]


def _msg_stem(message_id: int) -> str:
    return f'msg_{int(message_id)}'


def _manifest_path(artifact_dir: Path, message_id: int) -> Path:
    return artifact_dir / f'{_msg_stem(message_id)}__pdf_manifest.json'


def _bundle_path(artifact_dir: Path, message_id: int) -> Path:
    return artifact_dir / f'{_msg_stem(message_id)}__bundle.zip'


def _page_text_path(artifact_dir: Path, message_id: int, page_no: int) -> Path:
    return artifact_dir / f'{_msg_stem(message_id)}__page_{int(page_no):03d}.txt'


def _parse_message_date(raw: str) -> datetime | None:
    s = str(raw or '').strip()
    digits = ''.join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        try:
            return datetime.strptime(digits[:8], '%Y%m%d').replace(tzinfo=timezone.utc)
        except Exception:
            return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def _window_info(message_date: str, hot_window_days: int) -> tuple[bool, str]:
    dt = _parse_message_date(message_date)
    if dt is None:
        return False, ''
    until = dt + timedelta(days=max(1, hot_window_days))
    return datetime.now(timezone.utc) <= until, until.isoformat()


def _all_manifest_files_exist(stage1_dir: Path, manifest: dict) -> bool:
    pages = manifest.get('pages', []) if isinstance(manifest.get('pages'), list) else []
    for key in ('compressed_bundle_path', 'original_rel_path', 'manifest_rel_path'):
        rel = str(manifest.get(key) or '').strip()
        if rel and not (stage1_dir / rel).exists():
            return False
    for page in pages:
        if not isinstance(page, dict):
            return False
        text_rel = str(page.get('text_rel_path') or '').strip()
        render_rel = str(page.get('render_rel_path') or '').strip()
        if text_rel and not (stage1_dir / text_rel).exists():
            return False
        if render_rel and not (stage1_dir / render_rel).exists():
            return False
    return True


def _run_swift_page_artifacts(
    *,
    original_path: Path,
    artifact_dir: Path,
    message_id: int,
    max_pages: int,
    max_width: int,
    max_text_chars: int,
) -> dict:
    if os.uname().sysname.lower() != 'darwin':
        return {'ok': False, 'reason': 'swift_pdfkit_non_darwin'}
    if not os.path.exists(MACOS_SWIFT_BIN):
        return {'ok': False, 'reason': 'swift_unavailable'}

    script_path = ''
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.swift', delete=False) as tf:
            tf.write(SWIFT_PDF_PAGE_ARTIFACT_SCRIPT)
            script_path = tf.name
        proc = subprocess.run(
            [
                MACOS_SWIFT_BIN,
                script_path,
                str(original_path),
                str(artifact_dir),
                _msg_stem(message_id),
                str(max(1, max_pages)),
                str(max(320, max_width)),
                str(max(256, max_text_chars)),
            ],
            capture_output=True,
            text=True,
            timeout=max(30, min(600, max_pages * 14)),
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'reason': 'swift_timeout'}
    except Exception as e:
        return {'ok': False, 'reason': f'swift_run_error:{type(e).__name__}'}
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except Exception:
                pass

    if proc.returncode != 0:
        stderr = (proc.stderr or '').lower()
        if 'open_failed' in stderr:
            return {'ok': False, 'reason': 'swift_pdf_open_failed'}
        if 'no such module' in stderr and 'pdfkit' in stderr:
            return {'ok': False, 'reason': 'swift_pdfkit_unavailable'}
        return {'ok': False, 'reason': f'swift_pdfkit_error:{proc.returncode}'}

    try:
        payload = json.loads(proc.stdout or '{}')
    except Exception:
        return {'ok': False, 'reason': 'swift_payload_parse_failed'}
    if not isinstance(payload, dict):
        return {'ok': False, 'reason': 'swift_payload_invalid'}
    return {'ok': True, 'payload': payload}


def _bundle_files(
    *,
    stage1_dir: Path,
    artifact_dir: Path,
    message_id: int,
    meta_path: Path,
    original_path: Path,
    extract_path: Path | None,
    manifest_path: Path,
    pages: list[dict],
) -> tuple[str, str]:
    bundle_path = _bundle_path(artifact_dir, message_id)
    files: list[Path] = []
    for one in [meta_path, original_path, extract_path, manifest_path]:
        if one is not None and Path(one).exists() and Path(one).is_file():
            files.append(Path(one))
    for page in pages:
        if not isinstance(page, dict):
            continue
        text_rel = str(page.get('text_rel_path') or '').strip()
        render_rel = str(page.get('render_rel_path') or '').strip()
        if text_rel:
            p = stage1_dir / text_rel
            if p.exists() and p.is_file():
                files.append(p)
        if render_rel:
            p = stage1_dir / render_rel
            if p.exists() and p.is_file():
                files.append(p)
    if not files:
        return '', 'no_files_for_bundle'

    latest_src_ns = max(int(p.stat().st_mtime_ns) for p in files)
    if bundle_path.exists() and int(bundle_path.stat().st_mtime_ns) >= latest_src_ns:
        return _rel_path(stage1_dir, bundle_path), 'ok'

    with zipfile.ZipFile(bundle_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, arcname=path.name)
    return _rel_path(stage1_dir, bundle_path), 'ok'


def ensure_pdf_support_artifacts(
    *,
    stage1_dir: Path,
    artifact_dir: Path,
    meta_path: Path,
    original_path: Path,
    extract_path: Path | None,
    message_id: int,
    message_date: str,
    max_pages: int,
    max_text_chars: int,
    max_width: int,
    hot_window_days: int,
) -> dict:
    manifest_path = _manifest_path(artifact_dir, message_id)
    human_review_window_active, human_review_window_until = _window_info(message_date, hot_window_days)
    if not original_path.exists() or not original_path.is_file():
        return {
            'artifact_schema_version': 3,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'generator': 'stage_pdf_artifacts.ensure_pdf_support_artifacts',
            'source_original_rel_path': '',
            'source_original_mtime_ns': 0,
            'manifest_rel_path': '',
            'page_count': 0,
            'text_pages_written': 0,
            'rendered_pages_written': 0,
            'text_status': 'failed',
            'text_reason': 'missing_original',
            'render_status': 'failed',
            'render_reason': 'missing_original',
            'quality_grade': 'F',
            'compressed_bundle_path': '',
            'compressed_bundle_status': 'failed',
            'compressed_bundle_reason': 'missing_original',
            'human_review_window_active': human_review_window_active,
            'human_review_window_until': human_review_window_until,
            'pages': [],
        }

    source_original_rel_path = _rel_path(stage1_dir, original_path)
    source_original_mtime_ns = int(original_path.stat().st_mtime_ns)

    existing = _read_json(manifest_path)
    if existing and int(existing.get('source_original_mtime_ns') or 0) == source_original_mtime_ns and str(existing.get('source_original_rel_path') or '') == source_original_rel_path and _all_manifest_files_exist(stage1_dir, existing):
        bundle_rel, bundle_reason = _bundle_files(
            stage1_dir=stage1_dir,
            artifact_dir=artifact_dir,
            message_id=message_id,
            meta_path=meta_path,
            original_path=original_path,
            extract_path=extract_path,
            manifest_path=manifest_path,
            pages=existing.get('pages', []) if isinstance(existing.get('pages'), list) else [],
        )
        human_review_window_active, human_review_window_until = _window_info(message_date, hot_window_days)
        if bundle_rel:
            existing['compressed_bundle_path'] = bundle_rel
            existing['compressed_bundle_status'] = 'ok'
            existing['compressed_bundle_reason'] = bundle_reason
        existing['human_review_window_active'] = human_review_window_active
        existing['human_review_window_until'] = human_review_window_until
        _write_json(manifest_path, existing)
        return existing

    run = _run_swift_page_artifacts(
        original_path=original_path,
        artifact_dir=artifact_dir,
        message_id=message_id,
        max_pages=max_pages,
        max_width=max_width,
        max_text_chars=max_text_chars,
    )
    if not run.get('ok'):
        human_review_window_active, human_review_window_until = _window_info(message_date, hot_window_days)
        payload = {
            'artifact_schema_version': 3,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'generator': 'stage_pdf_artifacts.ensure_pdf_support_artifacts',
            'source_original_rel_path': source_original_rel_path,
            'source_original_mtime_ns': source_original_mtime_ns,
            'manifest_rel_path': _rel_path(stage1_dir, manifest_path),
            'page_count': 0,
            'text_pages_written': 0,
            'rendered_pages_written': 0,
            'text_status': 'failed',
            'text_reason': str(run.get('reason') or 'pdf_page_extract_failed'),
            'render_status': 'failed',
            'render_reason': str(run.get('reason') or 'pdf_page_render_failed'),
            'quality_grade': 'F',
            'compressed_bundle_path': '',
            'compressed_bundle_status': 'failed',
            'compressed_bundle_reason': str(run.get('reason') or 'pdf_page_render_failed'),
            'human_review_window_active': human_review_window_active,
            'human_review_window_until': human_review_window_until,
            'pages': [],
        }
        _write_json(manifest_path, payload)
        return payload

    payload = run.get('payload') or {}
    pages_in = payload.get('pages', []) if isinstance(payload.get('pages'), list) else []
    pages_out: list[dict] = []
    text_pages_written = 0
    rendered_pages_written = 0

    for page in pages_in:
        if not isinstance(page, dict):
            continue
        try:
            page_no = int(page.get('page_no') or 0)
        except Exception:
            page_no = 0
        if page_no <= 0:
            continue
        text = _clip_text(str(page.get('text') or ''), max_text_chars)
        text_rel_path = ''
        if text:
            text_path = _page_text_path(artifact_dir, message_id, page_no)
            text_path.write_text(text, encoding='utf-8')
            text_rel_path = _rel_path(stage1_dir, text_path)
            text_pages_written += 1
        render_rel_path = ''
        render_file = str(page.get('render_file') or '').strip()
        if render_file:
            render_path = artifact_dir / render_file
            if render_path.exists() and render_path.is_file():
                render_rel_path = _rel_path(stage1_dir, render_path)
                rendered_pages_written += 1
        pages_out.append({
            'page_no': page_no,
            'width': float(page.get('width') or 0.0),
            'height': float(page.get('height') or 0.0),
            'text_rel_path': text_rel_path,
            'render_rel_path': render_rel_path,
            'text_chars': len(text),
        })

    page_count = int(payload.get('page_count') or len(pages_out) or 0)
    text_status = 'ok' if page_count > 0 and text_pages_written >= min(page_count, max_pages) else ('partial' if text_pages_written > 0 else 'failed')
    render_status = 'ok' if page_count > 0 and rendered_pages_written >= min(page_count, max_pages) else ('partial' if rendered_pages_written > 0 else 'failed')
    quality_grade = 'A' if text_status == 'ok' and render_status == 'ok' else ('B' if text_status == 'ok' or render_status == 'ok' else ('C' if text_pages_written > 0 or rendered_pages_written > 0 else 'F'))
    human_review_window_active, human_review_window_until = _window_info(message_date, hot_window_days)

    manifest = {
        'artifact_schema_version': 3,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generator': 'stage_pdf_artifacts.ensure_pdf_support_artifacts',
        'source_original_rel_path': source_original_rel_path,
        'source_original_mtime_ns': source_original_mtime_ns,
        'manifest_rel_path': _rel_path(stage1_dir, manifest_path),
        'page_count': page_count,
        'max_pages_applied': max_pages,
        'max_text_chars_applied': max_text_chars,
        'max_width_applied': max_width,
        'text_pages_written': text_pages_written,
        'rendered_pages_written': rendered_pages_written,
        'text_status': text_status,
        'text_reason': 'ok' if text_pages_written > 0 else 'pdf_page_text_empty',
        'render_status': render_status,
        'render_reason': 'ok' if rendered_pages_written > 0 else 'pdf_page_render_empty',
        'quality_grade': quality_grade,
        'human_review_window_active': human_review_window_active,
        'human_review_window_until': human_review_window_until,
        'pages': pages_out,
    }
    _write_json(manifest_path, manifest)

    bundle_rel, bundle_reason = _bundle_files(
        stage1_dir=stage1_dir,
        artifact_dir=artifact_dir,
        message_id=message_id,
        meta_path=meta_path,
        original_path=original_path,
        extract_path=extract_path,
        manifest_path=manifest_path,
        pages=pages_out,
    )
    manifest['compressed_bundle_path'] = bundle_rel
    manifest['compressed_bundle_status'] = 'ok' if bundle_rel else 'failed'
    manifest['compressed_bundle_reason'] = bundle_reason if bundle_rel else bundle_reason
    _write_json(manifest_path, manifest)
    return manifest
