from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

ROOT_PATH = Path(__file__).resolve().parents[3]
STAGE1_OUTPUTS_DIR = ROOT_PATH / 'invest/stages/stage1/outputs'
DEFAULT_RAW_ROOT = STAGE1_OUTPUTS_DIR / 'raw'
DEFAULT_DB_DIR = STAGE1_OUTPUTS_DIR / 'db'
DEFAULT_DB_PATH = DEFAULT_DB_DIR / 'stage1_raw_archive.sqlite3'
SCHEMA_VERSION = 3


@dataclass(frozen=True)
class RawSyncSummary:
    sync_id: str
    scanned_files: int
    inserted_files: int
    updated_files: int
    unchanged_files: int
    inactive_files: int
    db_path: str
    raw_root: str
    finished_at: str

    def as_dict(self) -> dict:
        return {
            'sync_id': self.sync_id,
            'scanned_files': self.scanned_files,
            'inserted_files': self.inserted_files,
            'updated_files': self.updated_files,
            'unchanged_files': self.unchanged_files,
            'inactive_files': self.inactive_files,
            'db_path': self.db_path,
            'raw_root': self.raw_root,
            'finished_at': self.finished_at,
        }


@dataclass(frozen=True)
class PdfIndexSummary:
    indexed_documents: int
    indexed_pages: int
    documents_with_manifest: int
    documents_with_text: int
    documents_with_renders: int
    documents_page_marked: int
    documents_page_mapping_missing: int
    channels_seen: int
    earliest_message_date: str
    latest_message_date: str
    grade_counts: dict[str, int]
    month_counts: dict[str, int]
    kind_counts: dict[str, int]
    db_path: str
    raw_root: str
    finished_at: str

    def as_dict(self) -> dict:
        return {
            'indexed_documents': self.indexed_documents,
            'indexed_pages': self.indexed_pages,
            'documents_with_manifest': self.documents_with_manifest,
            'documents_with_text': self.documents_with_text,
            'documents_with_renders': self.documents_with_renders,
            'documents_page_marked': self.documents_page_marked,
            'documents_page_mapping_missing': self.documents_page_mapping_missing,
            'channels_seen': self.channels_seen,
            'earliest_message_date': self.earliest_message_date,
            'latest_message_date': self.latest_message_date,
            'grade_counts': dict(self.grade_counts),
            'month_counts': dict(self.month_counts),
            'kind_counts': dict(self.kind_counts),
            'db_path': self.db_path,
            'raw_root': self.raw_root,
            'finished_at': self.finished_at,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _posix_rel_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _sha1_bytes(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def _matches_prefix(rel_path: str, prefixes: Sequence[str]) -> bool:
    return any(rel_path == prefix or rel_path.startswith(f'{prefix}/') for prefix in prefixes)


def _should_track_path(rel_path: str, path: Path) -> bool:
    prefixes = stage2_default_prefixes()
    if not _matches_prefix(rel_path, prefixes):
        return False
    if rel_path.startswith('qualitative/attachments/telegram/'):
        name = path.name.lower()
        if name in {'meta.json', 'extracted.txt'}:
            return True
        if name.endswith('__meta.json') or name.endswith('__extracted.txt'):
            return True
        if name.endswith('__pdf_manifest.json') or name.endswith('__bundle.zip'):
            return True
        if '__page_' in name and (name.endswith('.txt') or name.endswith('.png')):
            return True
        if path.suffix.lower() == '.pdf':
            return True
        return False
    return True


def connect_raw_db(
    db_path: str | os.PathLike[str] | None = None,
    *,
    readonly: bool = False,
) -> sqlite3.Connection:
    path = Path(db_path or DEFAULT_DB_PATH)
    if readonly:
        if not path.exists():
            raise FileNotFoundError(path)
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    if readonly:
        conn.execute('PRAGMA query_only=ON')
    else:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS raw_artifacts (
            rel_path TEXT PRIMARY KEY,
            content BLOB NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            sha1 TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_seen_sync_id TEXT NOT NULL,
            stage1_run_id TEXT,
            stage1_profile TEXT,
            scheduler_origin TEXT,
            synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sync_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_raw_artifacts_active_rel_path
            ON raw_artifacts(is_active, rel_path);

        CREATE TABLE IF NOT EXISTS pdf_documents (
            doc_key TEXT PRIMARY KEY,
            source_family TEXT NOT NULL,
            channel_slug TEXT,
            message_id INTEGER,
            message_date TEXT,
            month_key TEXT,
            kind TEXT,
            artifact_bucket TEXT,
            meta_rel_path TEXT NOT NULL,
            original_rel_path TEXT,
            extract_rel_path TEXT,
            manifest_rel_path TEXT,
            bundle_rel_path TEXT,
            original_size_bytes INTEGER NOT NULL DEFAULT 0,
            page_count INTEGER NOT NULL DEFAULT 0,
            text_pages INTEGER NOT NULL DEFAULT 0,
            rendered_pages INTEGER NOT NULL DEFAULT 0,
            extraction_status TEXT,
            extraction_reason TEXT,
            render_status TEXT,
            render_reason TEXT,
            quality_grade TEXT,
            page_marked INTEGER NOT NULL DEFAULT 0,
            page_marker_count INTEGER NOT NULL DEFAULT 0,
            page_mapping_status TEXT,
            extract_format TEXT,
            human_review_window_active INTEGER NOT NULL DEFAULT 0,
            db_synced_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_pdf_documents_channel_month
            ON pdf_documents(channel_slug, month_key);
        CREATE INDEX IF NOT EXISTS idx_pdf_documents_kind
            ON pdf_documents(kind);

        CREATE TABLE IF NOT EXISTS pdf_pages (
            doc_key TEXT NOT NULL,
            page_no INTEGER NOT NULL,
            text_rel_path TEXT,
            render_rel_path TEXT,
            text_chars INTEGER NOT NULL DEFAULT 0,
            width REAL,
            height REAL,
            PRIMARY KEY(doc_key, page_no),
            FOREIGN KEY(doc_key) REFERENCES pdf_documents(doc_key) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_pdf_pages_doc_key ON pdf_pages(doc_key);
        '''
    )
    _ensure_column(conn, 'pdf_documents', 'page_marked', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(conn, 'pdf_documents', 'page_marker_count', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(conn, 'pdf_documents', 'page_mapping_status', 'TEXT')
    _ensure_column(conn, 'pdf_documents', 'extract_format', 'TEXT')
    _set_meta(conn, 'schema_version', str(SCHEMA_VERSION))
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, declaration: str) -> None:
    if column_name in _table_columns(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {declaration}")


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        'INSERT INTO sync_meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: str = '') -> str:
    row = conn.execute('SELECT value FROM sync_meta WHERE key = ?', (key,)).fetchone()
    if not row:
        return default
    return str(row['value'])


def latest_sync_id(db_path: str | os.PathLike[str] | None = None) -> str:
    with connect_raw_db(db_path, readonly=True) as conn:
        return get_meta(conn, 'last_sync_id', '')


def iter_active_rows(
    conn: sqlite3.Connection,
    prefixes: Sequence[str] | None = None,
) -> Iterable[sqlite3.Row]:
    sql = (
        'SELECT rel_path, content, size_bytes, mtime_ns, sha1 '
        'FROM raw_artifacts WHERE is_active = 1'
    )
    params: list[str] = []
    normalized = [p.strip('/').replace('\\', '/') for p in (prefixes or []) if p]
    if normalized:
        clauses = []
        for prefix in normalized:
            clauses.append('rel_path = ? OR rel_path LIKE ?')
            params.extend([prefix, f'{prefix}/%'])
        sql += ' AND (' + ' OR '.join(clauses) + ')'
    sql += ' ORDER BY rel_path'
    yield from conn.execute(sql, params)


def sync_raw_tree_to_db(
    *,
    raw_root: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
    stage1_run_id: str = '',
    stage1_profile: str = '',
    scheduler_origin: str = '',
) -> RawSyncSummary:
    raw_root_path = Path(raw_root or DEFAULT_RAW_ROOT)
    db_path_str = str(Path(db_path or DEFAULT_DB_PATH))
    sync_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    finished_at = _utc_now_iso()

    scanned_files = 0
    inserted_files = 0
    updated_files = 0
    unchanged_files = 0
    inactive_files = 0

    with connect_raw_db(db_path_str) as conn:
        if not raw_root_path.exists():
            _set_meta(conn, 'last_sync_id', sync_id)
            _set_meta(conn, 'last_sync_finished_at', finished_at)
            _set_meta(conn, 'last_sync_summary', json.dumps({
                'sync_id': sync_id,
                'scanned_files': 0,
                'inserted_files': 0,
                'updated_files': 0,
                'unchanged_files': 0,
                'inactive_files': 0,
                'raw_root_missing': True,
            }, ensure_ascii=False))
            conn.commit()
            return RawSyncSummary(
                sync_id=sync_id,
                scanned_files=0,
                inserted_files=0,
                updated_files=0,
                unchanged_files=0,
                inactive_files=0,
                db_path=db_path_str,
                raw_root=str(raw_root_path),
                finished_at=finished_at,
            )

        for path in sorted(p for p in raw_root_path.rglob('*') if p.is_file() and not p.name.startswith('.')):
            rel_path = _posix_rel_path(path, raw_root_path)
            if not _should_track_path(rel_path, path):
                continue
            stat = path.stat()
            size_bytes = int(stat.st_size)
            mtime_ns = int(stat.st_mtime_ns)
            scanned_files += 1

            prev = conn.execute(
                'SELECT sha1, size_bytes, mtime_ns FROM raw_artifacts WHERE rel_path = ?',
                (rel_path,),
            ).fetchone()

            if prev is not None and int(prev['size_bytes']) == size_bytes and int(prev['mtime_ns']) == mtime_ns:
                conn.execute(
                    '''
                    UPDATE raw_artifacts
                       SET is_active = 1,
                           last_seen_sync_id = ?,
                           stage1_run_id = ?,
                           stage1_profile = ?,
                           scheduler_origin = ?,
                           synced_at = ?
                     WHERE rel_path = ?
                    ''',
                    (
                        sync_id,
                        stage1_run_id,
                        stage1_profile,
                        scheduler_origin,
                        finished_at,
                        rel_path,
                    ),
                )
                unchanged_files += 1
                continue

            content = path.read_bytes()
            sha1 = _sha1_bytes(content)
            changed = not prev or str(prev['sha1']) != sha1

            conn.execute(
                '''
                INSERT INTO raw_artifacts(
                    rel_path, content, size_bytes, mtime_ns, sha1, is_active,
                    last_seen_sync_id, stage1_run_id, stage1_profile,
                    scheduler_origin, synced_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    content=excluded.content,
                    size_bytes=excluded.size_bytes,
                    mtime_ns=excluded.mtime_ns,
                    sha1=excluded.sha1,
                    is_active=1,
                    last_seen_sync_id=excluded.last_seen_sync_id,
                    stage1_run_id=excluded.stage1_run_id,
                    stage1_profile=excluded.stage1_profile,
                    scheduler_origin=excluded.scheduler_origin,
                    synced_at=excluded.synced_at
                ''',
                (
                    rel_path,
                    sqlite3.Binary(content),
                    size_bytes,
                    mtime_ns,
                    sha1,
                    sync_id,
                    stage1_run_id,
                    stage1_profile,
                    scheduler_origin,
                    finished_at,
                ),
            )

            if prev is None:
                inserted_files += 1
            elif changed:
                updated_files += 1
            else:
                unchanged_files += 1

        inactive_files = conn.execute(
            '''
            UPDATE raw_artifacts
               SET is_active = 0,
                   synced_at = ?
             WHERE is_active = 1
               AND last_seen_sync_id <> ?
            ''',
            (finished_at, sync_id),
        ).rowcount

        summary = {
            'sync_id': sync_id,
            'scanned_files': scanned_files,
            'inserted_files': inserted_files,
            'updated_files': updated_files,
            'unchanged_files': unchanged_files,
            'inactive_files': inactive_files,
            'db_path': db_path_str,
            'raw_root': str(raw_root_path),
            'finished_at': finished_at,
            'stage1_run_id': stage1_run_id,
            'stage1_profile': stage1_profile,
            'scheduler_origin': scheduler_origin,
        }
        _set_meta(conn, 'last_sync_id', sync_id)
        _set_meta(conn, 'last_sync_finished_at', finished_at)
        _set_meta(conn, 'last_sync_summary', json.dumps(summary, ensure_ascii=False))
        conn.commit()

    return RawSyncSummary(
        sync_id=sync_id,
        scanned_files=scanned_files,
        inserted_files=inserted_files,
        updated_files=updated_files,
        unchanged_files=unchanged_files,
        inactive_files=inactive_files,
        db_path=db_path_str,
        raw_root=str(raw_root_path),
        finished_at=finished_at,
    )


def materialize_snapshot_from_db(
    *,
    db_path: str | os.PathLike[str] | None = None,
    snapshot_root: str | os.PathLike[str],
    prefixes: Sequence[str] | None = None,
) -> dict:
    snapshot_root_path = Path(snapshot_root)
    raw_out_root = snapshot_root_path / 'raw'
    raw_out_root.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    with connect_raw_db(db_path, readonly=True) as conn:
        sync_id = get_meta(conn, 'last_sync_id', '')
        for row in iter_active_rows(conn, prefixes=prefixes):
            rel_path = str(row['rel_path'])
            content = bytes(row['content'])
            size_bytes = int(row['size_bytes'])
            mtime_ns = int(row['mtime_ns'])
            target = raw_out_root / Path(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            os.utime(target, ns=(mtime_ns, mtime_ns))
            file_count += 1
            total_bytes += size_bytes

        meta = {
            'materialized_at': _utc_now_iso(),
            'db_path': str(Path(db_path or DEFAULT_DB_PATH)),
            'sync_id': sync_id,
            'file_count': file_count,
            'total_bytes': total_bytes,
            'prefixes': [p.strip('/').replace('\\', '/') for p in (prefixes or []) if p],
        }
        (snapshot_root_path / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        return meta


def _safe_symlink_replace(target: Path, link_path: Path) -> None:
    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
    os.symlink(target, link_path, target_is_directory=True)


def prepare_stage2_raw_input_root(
    *,
    db_path: str | os.PathLike[str] | None = None,
    mirror_root: str | os.PathLike[str],
    prefixes: Sequence[str] | None = None,
) -> str:
    db_file = Path(db_path or DEFAULT_DB_PATH)
    if not db_file.exists():
        return ''

    mirror_root_path = Path(mirror_root)
    mirror_root_path.mkdir(parents=True, exist_ok=True)
    current_link = mirror_root_path / 'current'

    with connect_raw_db(db_file, readonly=True) as conn:
        sync_id = get_meta(conn, 'last_sync_id', '').strip()
        if not sync_id:
            return ''

    snapshot_root = mirror_root_path / 'snapshots' / sync_id
    if not snapshot_root.exists():
        materialize_snapshot_from_db(db_path=db_file, snapshot_root=snapshot_root, prefixes=prefixes)

    if not current_link.is_symlink() or os.readlink(current_link) != str(snapshot_root):
        current_link.parent.mkdir(parents=True, exist_ok=True)
        _safe_symlink_replace(snapshot_root, current_link)

    return str(current_link / 'raw')


def stage2_default_prefixes() -> list[str]:
    return [
        'signal/kr/ohlcv',
        'signal/kr/supply',
        'signal/us/ohlcv',
        'signal/market/macro',
        'signal/market/google_trends',
        'qualitative/kr/dart',
        'qualitative/market/rss',
        'qualitative/market/news/selected_articles',
        'qualitative/text/blog',
        'qualitative/text/telegram',
        'qualitative/text/premium/startale',
        'qualitative/attachments/telegram',
        'qualitative/link_enrichment',
    ]


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_message_date(raw: str) -> str:
    s = str(raw or '').strip()
    if not s:
        return ''
    digits = ''.join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return ''


def _month_key(raw: str) -> str:
    norm = _normalize_message_date(raw)
    return norm[:6] if len(norm) >= 6 else ''


def _text_chars(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        return len(path.read_text(encoding='utf-8', errors='ignore').strip())
    except Exception:
        return 0


def _pdf_quality_grade(page_count: int, text_pages: int, rendered_pages: int) -> str:
    if page_count > 0 and text_pages >= page_count and rendered_pages >= page_count:
        return 'A'
    if page_count > 0 and (text_pages >= page_count or rendered_pages >= page_count):
        return 'B'
    if text_pages > 0 or rendered_pages > 0:
        return 'C'
    return 'F'


def _resolve_stage1_or_raw_path(raw_root: Path, rel_path: str) -> Path:
    raw = str(rel_path or '').strip()
    if not raw:
        return Path('')
    p = Path(raw)
    if p.is_absolute():
        return p
    stage1_dir = raw_root.parent.parent if raw_root.name == 'raw' and raw_root.parent.name == 'outputs' else raw_root.parent
    candidates = [raw_root / raw, stage1_dir / raw]
    if raw.startswith('outputs/raw/'):
        candidates.append(stage1_dir / raw)
        candidates.append(raw_root / raw[len('outputs/raw/'):])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _iter_pdf_meta_paths(raw_root: Path) -> list[Path]:
    attach_root = raw_root / 'qualitative/attachments/telegram'
    if not attach_root.exists():
        return []
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in ('meta.json', '*__meta.json'):
        for path in sorted(attach_root.rglob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                out.append(path)
    return out


def _pdf_doc_identity(meta: dict) -> tuple[str, int]:
    channel_slug = str(meta.get('channel_slug') or '').strip()
    try:
        message_id = int(meta.get('message_id') or 0)
    except Exception:
        message_id = 0
    return channel_slug, message_id


def _path_exists_from_rel(raw_root: Path, rel_path: str) -> bool:
    raw = str(rel_path or '').strip()
    if not raw:
        return False
    try:
        return _resolve_stage1_or_raw_path(raw_root, raw).is_file()
    except Exception:
        return False


def _pdf_meta_rank(raw_root: Path, meta_path: Path, meta: dict) -> tuple[int, int, int, int, int, int, int]:
    schema_version = int(meta.get('artifact_schema_version') or 0)
    extract_ok = 1 if str(meta.get('extraction_status') or '').strip().lower() == 'ok' else 0
    extract_exists = 1 if _path_exists_from_rel(raw_root, str(meta.get('extract_path') or '')) else 0
    original_exists = 1 if _path_exists_from_rel(raw_root, str(meta.get('original_path') or '')) else 0
    manifest_exists = 1 if _path_exists_from_rel(raw_root, str(meta.get('pdf_manifest_path') or '')) else 0
    bucket_meta = 1 if meta_path.name.endswith('__meta.json') else 0
    richness = sum(1 for key in ('extract_path', 'original_path', 'pdf_manifest_path', 'pdf_quality_grade') if str(meta.get(key) or '').strip())
    return (extract_ok, extract_exists, original_exists, manifest_exists, schema_version, richness, bucket_meta)


def _iter_canonical_pdf_meta_entries(raw_root: Path) -> list[tuple[Path, dict]]:
    grouped: dict[tuple[str, int], list[tuple[Path, dict]]] = {}
    for meta_path in _iter_pdf_meta_paths(raw_root):
        meta = _read_json(meta_path)
        if str(meta.get('kind') or '').strip().lower() != 'pdf':
            continue
        key = _pdf_doc_identity(meta)
        if not key[0] or key[1] <= 0:
            continue
        grouped.setdefault(key, []).append((meta_path, meta))

    out: list[tuple[Path, dict]] = []
    for key, entries in grouped.items():
        ranked = sorted(entries, key=lambda item: _pdf_meta_rank(raw_root, item[0], item[1]))
        merged: dict = {}
        for _, meta in ranked:
            for one_key, value in meta.items():
                if value not in (None, '', [], {}):
                    merged[one_key] = value
                elif one_key not in merged:
                    merged[one_key] = value
        best_path, best_meta = ranked[-1]
        deleted_after_decompose = (
            str(merged.get('original_store_status') or '').strip().lower() == 'deleted_after_decompose'
            or str(merged.get('original_store_reason') or '').strip().lower() == 'deleted_after_decompose'
            or bool(merged.get('original_deleted_after_decompose'))
            or str(best_meta.get('original_store_status') or '').strip().lower() == 'deleted_after_decompose'
            or str(best_meta.get('original_store_reason') or '').strip().lower() == 'deleted_after_decompose'
            or bool(best_meta.get('original_deleted_after_decompose'))
        )
        if deleted_after_decompose:
            original_rel = str(merged.get('original_path') or '').strip()
            if original_rel and not str(merged.get('original_deleted_rel_path') or '').strip():
                merged['original_deleted_rel_path'] = original_rel
            merged['original_path'] = ''
        merged['channel_slug'] = key[0]
        merged['message_id'] = key[1]
        merged['kind'] = 'pdf'
        out.append((best_path, merged))
    out.sort(key=lambda item: item[0].as_posix())
    return out


def index_pdf_artifacts_from_raw(
    *,
    raw_root: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> PdfIndexSummary:
    raw_root_path = Path(raw_root or DEFAULT_RAW_ROOT)
    db_path_str = str(Path(db_path or DEFAULT_DB_PATH))
    finished_at = _utc_now_iso()

    indexed_documents = 0
    indexed_pages = 0
    documents_with_manifest = 0
    documents_with_text = 0
    documents_with_renders = 0
    documents_page_marked = 0
    documents_page_mapping_missing = 0
    channels_seen: set[str] = set()
    month_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    grade_counts: dict[str, int] = {}
    earliest_message_date = ''
    latest_message_date = ''

    with connect_raw_db(db_path_str) as conn:
        seen_doc_keys: set[str] = set()
        for meta_path, meta in _iter_canonical_pdf_meta_entries(raw_root_path):
            kind = str(meta.get('kind') or '').strip().lower()
            kind_counts[kind or 'unknown'] = int(kind_counts.get(kind or 'unknown', 0)) + 1
            if kind != 'pdf':
                continue

            channel_slug = str(meta.get('channel_slug') or '').strip()
            try:
                message_id = int(meta.get('message_id') or 0)
            except Exception:
                message_id = 0
            if not channel_slug or message_id <= 0:
                continue

            message_date = _normalize_message_date(str(meta.get('message_date') or ''))
            if message_date:
                earliest_message_date = message_date if not earliest_message_date or message_date < earliest_message_date else earliest_message_date
                latest_message_date = message_date if not latest_message_date or message_date > latest_message_date else latest_message_date
                month_key = message_date[:6]
                month_counts[month_key] = int(month_counts.get(month_key, 0)) + 1
            else:
                month_key = ''

            channels_seen.add(channel_slug)
            doc_key = f'telegram:{channel_slug}:{message_id}'
            seen_doc_keys.add(doc_key)

            manifest_rel = str(meta.get('pdf_manifest_path') or '').strip()
            bundle_rel = str(meta.get('compressed_bundle_path') or '').strip()
            original_rel = str(meta.get('original_path') or '').strip()
            extract_rel = str(meta.get('extract_path') or '').strip()
            manifest_path = _resolve_stage1_or_raw_path(raw_root_path, manifest_rel) if manifest_rel else None
            manifest = _read_json(manifest_path) if manifest_path is not None and manifest_path.exists() else {}
            pages = manifest.get('pages', []) if isinstance(manifest.get('pages'), list) else []
            page_count = int(manifest.get('page_count') or meta.get('pdf_page_count') or 0)
            text_pages = int(manifest.get('text_pages_written') or meta.get('pdf_text_pages') or 0)
            rendered_pages = int(manifest.get('rendered_pages_written') or meta.get('pdf_render_pages') or 0)
            if manifest:
                documents_with_manifest += 1
            if text_pages > 0:
                documents_with_text += 1
            if rendered_pages > 0:
                documents_with_renders += 1
            quality_grade = str(manifest.get('quality_grade') or meta.get('pdf_quality_grade') or _pdf_quality_grade(page_count, text_pages, rendered_pages)).strip() or 'F'
            grade_counts[quality_grade] = int(grade_counts.get(quality_grade, 0)) + 1
            page_marked = 1 if bool(meta.get('pdf_page_marked')) else 0
            try:
                page_marker_count = int(meta.get('pdf_page_marker_count') or 0)
            except Exception:
                page_marker_count = 0
            page_mapping_status = str(meta.get('pdf_page_mapping_status') or '').strip()
            extract_format = str(meta.get('extract_format') or '').strip()
            if page_marked:
                documents_page_marked += 1
            if page_mapping_status.startswith('missing'):
                documents_page_mapping_missing += 1

            original_path = _resolve_stage1_or_raw_path(raw_root_path, original_rel) if original_rel else None
            original_size_bytes = int(original_path.stat().st_size) if original_path is not None and original_path.exists() and original_path.is_file() else 0
            extraction_status = str(meta.get('extraction_status') or manifest.get('text_status') or '').strip()
            extraction_reason = str(meta.get('extraction_reason') or manifest.get('text_reason') or '').strip()
            render_status = str(manifest.get('render_status') or meta.get('pdf_render_status') or '').strip()
            render_reason = str(manifest.get('render_reason') or meta.get('pdf_render_reason') or '').strip()
            human_review_window_active = 1 if bool(meta.get('human_review_window_active')) else 0
            artifact_bucket = str(meta.get('attachment_bucket') or '').strip()

            conn.execute(
                '''
                INSERT INTO pdf_documents(
                    doc_key, source_family, channel_slug, message_id, message_date, month_key, kind,
                    artifact_bucket, meta_rel_path, original_rel_path, extract_rel_path,
                    manifest_rel_path, bundle_rel_path, original_size_bytes, page_count,
                    text_pages, rendered_pages, extraction_status, extraction_reason,
                    render_status, render_reason, quality_grade,
                    page_marked, page_marker_count, page_mapping_status, extract_format,
                    human_review_window_active, db_synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_key) DO UPDATE SET
                    source_family=excluded.source_family,
                    channel_slug=excluded.channel_slug,
                    message_id=excluded.message_id,
                    message_date=excluded.message_date,
                    month_key=excluded.month_key,
                    kind=excluded.kind,
                    artifact_bucket=excluded.artifact_bucket,
                    meta_rel_path=excluded.meta_rel_path,
                    original_rel_path=excluded.original_rel_path,
                    extract_rel_path=excluded.extract_rel_path,
                    manifest_rel_path=excluded.manifest_rel_path,
                    bundle_rel_path=excluded.bundle_rel_path,
                    original_size_bytes=excluded.original_size_bytes,
                    page_count=excluded.page_count,
                    text_pages=excluded.text_pages,
                    rendered_pages=excluded.rendered_pages,
                    extraction_status=excluded.extraction_status,
                    extraction_reason=excluded.extraction_reason,
                    render_status=excluded.render_status,
                    render_reason=excluded.render_reason,
                    quality_grade=excluded.quality_grade,
                    page_marked=excluded.page_marked,
                    page_marker_count=excluded.page_marker_count,
                    page_mapping_status=excluded.page_mapping_status,
                    extract_format=excluded.extract_format,
                    human_review_window_active=excluded.human_review_window_active,
                    db_synced_at=excluded.db_synced_at
                ''',
                (
                    doc_key,
                    'telegram_attachment',
                    channel_slug,
                    message_id,
                    message_date,
                    month_key,
                    'pdf',
                    artifact_bucket,
                    _posix_rel_path(meta_path, raw_root_path),
                    original_rel,
                    extract_rel,
                    _posix_rel_path(manifest_path, raw_root_path) if manifest_path is not None and manifest_path.exists() else manifest_rel,
                    bundle_rel,
                    original_size_bytes,
                    page_count,
                    text_pages,
                    rendered_pages,
                    extraction_status,
                    extraction_reason,
                    render_status,
                    render_reason,
                    quality_grade,
                    page_marked,
                    page_marker_count,
                    page_mapping_status,
                    extract_format,
                    human_review_window_active,
                    finished_at,
                ),
            )
            conn.execute('DELETE FROM pdf_pages WHERE doc_key = ?', (doc_key,))

            inserted_page_nos: set[int] = set()
            for page in pages:
                if not isinstance(page, dict):
                    continue
                try:
                    page_no = int(page.get('page_no') or 0)
                except Exception:
                    page_no = 0
                if page_no <= 0 or page_no in inserted_page_nos:
                    continue
                text_rel = str(page.get('text_rel_path') or '').strip()
                render_rel = str(page.get('render_rel_path') or '').strip()
                text_chars = int(page.get('text_chars') or 0)
                if text_chars <= 0 and text_rel:
                    text_chars = _text_chars(_resolve_stage1_or_raw_path(raw_root_path, text_rel))
                width = float(page.get('width') or 0.0)
                height = float(page.get('height') or 0.0)
                conn.execute(
                    '''
                    INSERT INTO pdf_pages(doc_key, page_no, text_rel_path, render_rel_path, text_chars, width, height)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (doc_key, page_no, text_rel, render_rel, text_chars, width, height),
                )
                inserted_page_nos.add(page_no)
                indexed_pages += 1

            if page_count > len(inserted_page_nos):
                for page_no in range(1, page_count + 1):
                    if page_no in inserted_page_nos:
                        continue
                    conn.execute(
                        '''
                        INSERT INTO pdf_pages(doc_key, page_no, text_rel_path, render_rel_path, text_chars, width, height)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (doc_key, page_no, '', '', 0, None, None),
                    )
                    indexed_pages += 1

            indexed_documents += 1

        conn.execute(
            'DELETE FROM pdf_documents WHERE source_family = ? AND doc_key NOT IN (%s)' % (','.join('?' for _ in seen_doc_keys) or "''"),
            tuple(['telegram_attachment', *sorted(seen_doc_keys)]) if seen_doc_keys else ('telegram_attachment',),
        )
        _set_meta(conn, 'last_pdf_index_summary', json.dumps({
            'indexed_documents': indexed_documents,
            'indexed_pages': indexed_pages,
            'documents_with_manifest': documents_with_manifest,
            'documents_with_text': documents_with_text,
            'documents_with_renders': documents_with_renders,
            'documents_page_marked': documents_page_marked,
            'documents_page_mapping_missing': documents_page_mapping_missing,
            'channels_seen': len(channels_seen),
            'earliest_message_date': earliest_message_date,
            'latest_message_date': latest_message_date,
            'grade_counts': grade_counts,
            'month_counts': month_counts,
            'kind_counts': kind_counts,
            'finished_at': finished_at,
        }, ensure_ascii=False))
        conn.commit()

    return PdfIndexSummary(
        indexed_documents=indexed_documents,
        indexed_pages=indexed_pages,
        documents_with_manifest=documents_with_manifest,
        documents_with_text=documents_with_text,
        documents_with_renders=documents_with_renders,
        documents_page_marked=documents_page_marked,
        documents_page_mapping_missing=documents_page_mapping_missing,
        channels_seen=len(channels_seen),
        earliest_message_date=earliest_message_date,
        latest_message_date=latest_message_date,
        grade_counts=grade_counts,
        month_counts=month_counts,
        kind_counts=kind_counts,
        db_path=db_path_str,
        raw_root=str(raw_root_path),
        finished_at=finished_at,
    )
