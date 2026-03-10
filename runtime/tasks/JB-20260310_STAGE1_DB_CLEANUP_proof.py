#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/Users/jobiseu/.openclaw/workspace')
RAW_ROOT = ROOT / 'invest/stages/stage1/outputs/raw'
RUNTIME_ROOT = ROOT / 'invest/stages/stage1/outputs/runtime'
DB_PATH = ROOT / 'invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3'
OUT_JSON = ROOT / 'runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_proof.json'
OUT_TXT = ROOT / 'runtime/tasks/proofs/JB-20260310-STAGE1-DB-CLEANUP_commands.txt'


def now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime())


def norm_raw_rel(path: str | None) -> str:
    if not path:
        return ''
    p = path.replace('\\', '/').lstrip('./')
    for prefix in (
        'outputs/raw/',
        'invest/stages/stage1/outputs/raw/',
        str(RAW_ROOT).replace('\\', '/') + '/',
    ):
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    return p


def normalize_slug(value: str | None) -> str:
    return ''.join(ch for ch in (value or '').lower() if ch.isalnum())


def sample_append(bucket: list, item, limit: int = 50):
    if len(bucket) < limit:
        bucket.append(item)


def scan_tree(root: Path):
    file_count = 0
    dir_count = 0
    total_bytes = 0
    top1_count = Counter()
    top1_bytes = Counter()
    top2_count = Counter()
    top2_bytes = Counter()
    ext_count = Counter()
    ext_bytes = Counter()
    file_sizes: dict[str, int] = {}
    archive_dirs = []
    temp_dirs = []
    lock_files = []

    for cur, dirs, files in os.walk(root):
        dir_count += len(dirs)
        curp = Path(cur)
        rel_dir = '' if curp == root else curp.relative_to(root).as_posix()
        for d in dirs:
            rel = f'{rel_dir}/{d}' if rel_dir else d
            if 'archive' in rel.lower():
                archive_dirs.append(rel)
            if 'tmp' in d.lower():
                temp_dirs.append(rel)
        for name in files:
            p = curp / name
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            rel = p.relative_to(root).as_posix()
            size = st.st_size
            file_sizes[rel] = size
            file_count += 1
            total_bytes += size
            parts = rel.split('/')
            top1 = parts[0] if parts else ''
            top2 = '/'.join(parts[:2]) if len(parts) >= 2 else top1
            ext = p.suffix.lower() or '<no_ext>'
            top1_count[top1] += 1
            top1_bytes[top1] += size
            top2_count[top2] += 1
            top2_bytes[top2] += size
            ext_count[ext] += 1
            ext_bytes[ext] += size
            if name.endswith('.lock'):
                lock_files.append({'path': rel, 'size_bytes': size})

    def top(counter: Counter, limit: int = 20, key_name: str = 'key', val_name: str = 'count'):
        return [{key_name: k, val_name: v} for k, v in counter.most_common(limit)]

    return {
        'file_sizes': file_sizes,
        'summary': {
            'root': str(root),
            'file_count': file_count,
            'dir_count': dir_count,
            'total_bytes': total_bytes,
            'top1_count': top(top1_count),
            'top1_bytes': top(top1_bytes, val_name='bytes'),
            'top2_count': top(top2_count),
            'top2_bytes': top(top2_bytes, val_name='bytes'),
            'top_ext_count': top(ext_count),
            'top_ext_bytes': top(ext_bytes, val_name='bytes'),
            'archive_dirs': sorted(archive_dirs),
            'temp_dirs': sorted(temp_dirs),
            'lock_files': lock_files,
        },
    }


def parse_sync_meta(conn: sqlite3.Connection):
    out = {}
    for key, value in conn.execute('SELECT key, value FROM sync_meta ORDER BY key'):
        try:
            out[key] = json.loads(value)
        except Exception:
            out[key] = value
    return out


def main():
    started_at = now_iso()
    raw_scan = scan_tree(RAW_ROOT)
    runtime_scan = scan_tree(RUNTIME_ROOT)
    raw_sizes = raw_scan['file_sizes']
    raw_set = set(raw_sizes)
    manifest_disk = {p for p in raw_set if p.endswith('__pdf_manifest.json')}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    table_counts = {}
    table_names = [row['name'] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    for table_name in table_names:
        table_counts[table_name] = cur.execute(f'SELECT COUNT(*) AS c FROM "{table_name}"').fetchone()['c']

    sync_meta = parse_sync_meta(conn)

    db_set = set()
    db_sizes = {}
    inactive_count = 0
    for row in cur.execute('SELECT rel_path, size_bytes, is_active FROM raw_artifacts'):
        if row['is_active']:
            db_set.add(row['rel_path'])
            db_sizes[row['rel_path']] = row['size_bytes']
        else:
            inactive_count += 1

    disk_only_top2 = Counter()
    disk_only_ext = Counter()
    disk_only_samples = []
    disk_only_count = 0
    for rel in sorted(raw_set - db_set):
        disk_only_count += 1
        top2 = '/'.join(rel.split('/')[:2]) if '/' in rel else rel
        disk_only_top2[top2] += 1
        disk_only_ext[Path(rel).suffix.lower() or '<no_ext>'] += 1
        sample_append(disk_only_samples, rel, 100)

    db_only_samples = []
    db_only_count = 0
    for rel in sorted(db_set - raw_set):
        db_only_count += 1
        sample_append(db_only_samples, rel, 100)

    size_mismatch_top2 = Counter()
    size_mismatch_ext = Counter()
    size_mismatch_samples = []
    size_mismatch_count = 0
    for rel in sorted(raw_set & db_set):
        if raw_sizes[rel] != db_sizes[rel]:
            size_mismatch_count += 1
            top2 = '/'.join(rel.split('/')[:2]) if '/' in rel else rel
            size_mismatch_top2[top2] += 1
            size_mismatch_ext[Path(rel).suffix.lower() or '<no_ext>'] += 1
            sample_append(size_mismatch_samples, {
                'rel_path': rel,
                'disk_size_bytes': raw_sizes[rel],
                'db_size_bytes': db_sizes[rel],
            }, 100)

    pdf_summary = {
        'pdf_documents': cur.execute('SELECT COUNT(*) FROM pdf_documents').fetchone()[0],
        'pdf_pages': cur.execute('SELECT COUNT(*) FROM pdf_pages').fetchone()[0],
        'docs_with_manifest_rel_path': cur.execute("SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(manifest_rel_path,'')<>''").fetchone()[0],
        'docs_with_original_rel_path': cur.execute("SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(original_rel_path,'')<>''").fetchone()[0],
        'docs_with_extract_rel_path': cur.execute("SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(extract_rel_path,'')<>''").fetchone()[0],
        'docs_with_bundle_rel_path': cur.execute("SELECT COUNT(*) FROM pdf_documents WHERE COALESCE(bundle_rel_path,'')<>''").fetchone()[0],
    }
    for key, sql in (
        ('extraction_status', 'SELECT COALESCE(extraction_status,\'<empty>\') AS k, COUNT(*) AS c FROM pdf_documents GROUP BY COALESCE(extraction_status,\'<empty>\') ORDER BY c DESC'),
        ('render_status', 'SELECT COALESCE(render_status,\'<empty>\') AS k, COUNT(*) AS c FROM pdf_documents GROUP BY COALESCE(render_status,\'<empty>\') ORDER BY c DESC'),
        ('quality_grade', 'SELECT COALESCE(quality_grade,\'<empty>\') AS k, COUNT(*) AS c FROM pdf_documents GROUP BY COALESCE(quality_grade,\'<empty>\') ORDER BY c DESC'),
        ('source_family', 'SELECT COALESCE(source_family,\'<empty>\') AS k, COUNT(*) AS c FROM pdf_documents GROUP BY COALESCE(source_family,\'<empty>\') ORDER BY c DESC'),
        ('kind', 'SELECT COALESCE(kind,\'<empty>\') AS k, COUNT(*) AS c FROM pdf_documents GROUP BY COALESCE(kind,\'<empty>\') ORDER BY c DESC'),
    ):
        pdf_summary[key] = {row['k']: row['c'] for row in cur.execute(sql)}

    manifest_table = set()
    missing_db = Counter()
    missing_db_samples = defaultdict(list)
    missing_disk = Counter()
    missing_disk_samples = defaultdict(list)
    channel_groups = defaultdict(list)

    for row in cur.execute('SELECT doc_key, channel_slug, message_id, meta_rel_path, original_rel_path, extract_rel_path, manifest_rel_path, bundle_rel_path FROM pdf_documents'):
        channel_groups[(normalize_slug(row['channel_slug']), row['message_id'])].append({'doc_key': row['doc_key'], 'channel_slug': row['channel_slug'], 'message_id': row['message_id']})
        for label, raw_rel in (
            ('meta', norm_raw_rel(row['meta_rel_path'])),
            ('original', norm_raw_rel(row['original_rel_path'])),
            ('extract', norm_raw_rel(row['extract_rel_path'])),
            ('manifest', norm_raw_rel(row['manifest_rel_path'])),
            ('bundle', norm_raw_rel(row['bundle_rel_path'])),
        ):
            if not raw_rel:
                continue
            if label == 'manifest':
                manifest_table.add(raw_rel)
            if raw_rel not in db_set:
                missing_db[label] += 1
                sample_append(missing_db_samples[label], {'doc_key': row['doc_key'], 'rel_path': raw_rel}, 50)
            if raw_rel not in raw_set:
                missing_disk[label] += 1
                sample_append(missing_disk_samples[label], {'doc_key': row['doc_key'], 'rel_path': raw_rel}, 50)

    page_count_vs_rows_total = cur.execute(
        'SELECT COUNT(*) FROM pdf_documents d LEFT JOIN (SELECT doc_key, COUNT(*) AS c FROM pdf_pages GROUP BY doc_key) p ON d.doc_key=p.doc_key WHERE d.page_count <> COALESCE(p.c,0)'
    ).fetchone()[0]
    page_mismatch = {
        'page_count_vs_rows_total': page_count_vs_rows_total,
        'text_pages_vs_rows': cur.execute(
            "SELECT COUNT(*) FROM pdf_documents d LEFT JOIN (SELECT doc_key, SUM(CASE WHEN COALESCE(text_rel_path,'')<>'' THEN 1 ELSE 0 END) AS c FROM pdf_pages GROUP BY doc_key) p ON d.doc_key=p.doc_key WHERE d.text_pages <> COALESCE(p.c,0)"
        ).fetchone()[0],
        'rendered_pages_vs_rows': cur.execute(
            "SELECT COUNT(*) FROM pdf_documents d LEFT JOIN (SELECT doc_key, SUM(CASE WHEN COALESCE(render_rel_path,'')<>'' THEN 1 ELSE 0 END) AS c FROM pdf_pages GROUP BY doc_key) p ON d.doc_key=p.doc_key WHERE d.rendered_pages <> COALESCE(p.c,0)"
        ).fetchone()[0],
    }
    page_mismatch_cap_expected_samples = []
    page_mismatch_unexpected_samples = []
    page_mismatch_cap_expected_count = 0
    for row in cur.execute(
        '''
        SELECT d.doc_key, d.manifest_rel_path, d.page_count,
               COALESCE(p.c,0) AS page_rows
          FROM pdf_documents d
          LEFT JOIN (SELECT doc_key, COUNT(*) AS c FROM pdf_pages GROUP BY doc_key) p
            ON d.doc_key=p.doc_key
         WHERE d.page_count <> COALESCE(p.c,0)
         ORDER BY d.doc_key
        '''
    ):
        manifest_rel = norm_raw_rel(row['manifest_rel_path'])
        manifest_path = RAW_ROOT / manifest_rel if manifest_rel else None
        manifest = {}
        if manifest_path and manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except Exception:
                manifest = {}
        pages = manifest.get('pages') if isinstance(manifest, dict) else []
        pages_len = len(pages) if isinstance(pages, list) else 0
        max_pages_applied = 0
        try:
            max_pages_applied = int((manifest or {}).get('max_pages_applied') or 0)
        except Exception:
            max_pages_applied = 0
        expected_cap = (
            max_pages_applied > 0
            and int(row['page_count']) > int(row['page_rows'])
            and int(row['page_rows']) == min(int(row['page_count']), max_pages_applied)
            and pages_len == int(row['page_rows'])
        )
        sample = {
            'doc_key': row['doc_key'],
            'manifest_rel_path': manifest_rel,
            'page_count': int(row['page_count']),
            'page_rows': int(row['page_rows']),
            'max_pages_applied': max_pages_applied,
            'manifest_pages_len': pages_len,
        }
        if expected_cap:
            page_mismatch_cap_expected_count += 1
            sample_append(page_mismatch_cap_expected_samples, sample, 100)
        else:
            sample_append(page_mismatch_unexpected_samples, sample, 100)
    page_mismatch['page_count_vs_rows_expected_cap_count'] = page_mismatch_cap_expected_count
    page_mismatch['page_count_vs_rows_unexpected_count'] = page_count_vs_rows_total - page_mismatch_cap_expected_count
    page_mismatch['page_count_vs_rows'] = page_mismatch['page_count_vs_rows_unexpected_count']

    page_missing = Counter()
    page_missing_samples = defaultdict(list)
    for row in cur.execute('SELECT doc_key, page_no, text_rel_path, render_rel_path FROM pdf_pages'):
        text_rel = norm_raw_rel(row['text_rel_path'])
        render_rel = norm_raw_rel(row['render_rel_path'])
        if text_rel and text_rel not in raw_set:
            page_missing['text_missing_disk'] += 1
            sample_append(page_missing_samples['text_missing_disk'], {'doc_key': row['doc_key'], 'page_no': row['page_no'], 'rel_path': text_rel}, 50)
        if text_rel and text_rel not in db_set:
            page_missing['text_missing_db'] += 1
            sample_append(page_missing_samples['text_missing_db'], {'doc_key': row['doc_key'], 'page_no': row['page_no'], 'rel_path': text_rel}, 50)
        if render_rel and render_rel not in raw_set:
            page_missing['render_missing_disk'] += 1
            sample_append(page_missing_samples['render_missing_disk'], {'doc_key': row['doc_key'], 'page_no': row['page_no'], 'rel_path': render_rel}, 50)
        if render_rel and render_rel not in db_set:
            page_missing['render_missing_db'] += 1
            sample_append(page_missing_samples['render_missing_db'], {'doc_key': row['doc_key'], 'page_no': row['page_no'], 'rel_path': render_rel}, 50)

    duplicate_message_groups = []
    for (_slug, msg_id), docs in channel_groups.items():
        slugs = sorted({d['channel_slug'] for d in docs})
        if len(docs) > 1 and len(slugs) > 1:
            duplicate_message_groups.append({
                'normalized_slug': _slug,
                'message_id': msg_id,
                'doc_count': len(docs),
                'channel_slugs': slugs,
                'docs': docs[:10],
            })
    duplicate_message_groups.sort(key=lambda x: (-x['doc_count'], x['normalized_slug'], x['message_id']))

    duplicate_sha1_groups = []
    duplicate_sha1_rows = cur.execute(
        'SELECT sha1, size_bytes, COUNT(*) AS cnt FROM raw_artifacts WHERE is_active=1 AND size_bytes>0 GROUP BY sha1, size_bytes HAVING COUNT(*)>1 ORDER BY cnt DESC, size_bytes DESC LIMIT 20'
    ).fetchall()
    for row in duplicate_sha1_rows:
        examples = [r['rel_path'] for r in cur.execute(
            'SELECT rel_path FROM raw_artifacts WHERE is_active=1 AND sha1=? AND size_bytes=? ORDER BY rel_path LIMIT 10',
            (row['sha1'], row['size_bytes'])
        ).fetchall()]
        duplicate_sha1_groups.append({'sha1': row['sha1'], 'size_bytes': row['size_bytes'], 'count': row['cnt'], 'examples': examples})

    raw_db_sync_status = {}
    raw_db_status_path = RUNTIME_ROOT / 'raw_db_sync_status.json'
    if raw_db_status_path.exists():
        raw_db_sync_status = json.loads(raw_db_status_path.read_text(encoding='utf-8'))

    result = {
        'generated_at': now_iso(),
        'started_at': started_at,
        'paths': {
            'raw_root': str(RAW_ROOT),
            'runtime_root': str(RUNTIME_ROOT),
            'db_path': str(DB_PATH),
        },
        'inventory': {
            'raw_tree': raw_scan['summary'],
            'runtime_tree': runtime_scan['summary'],
            'db_tables': table_counts,
            'db_sync_meta': sync_meta,
            'raw_artifacts_active_count': len(db_set),
            'raw_artifacts_inactive_count': inactive_count,
            'pdf_summary': pdf_summary,
        },
        'integrity_checks': {
            'raw_db_alignment': {
                'runtime_status_sync_id': raw_db_sync_status.get('sync_id'),
                'sync_meta_last_sync_id': sync_meta.get('last_sync_id'),
                'runtime_status_finished_at': raw_db_sync_status.get('finished_at'),
                'sync_meta_last_sync_finished_at': sync_meta.get('last_sync_finished_at'),
                'runtime_status_scanned_files': raw_db_sync_status.get('scanned_files'),
                'sync_meta_last_sync_summary_scanned_files': (sync_meta.get('last_sync_summary') or {}).get('scanned_files') if isinstance(sync_meta.get('last_sync_summary'), dict) else None,
                'actual_raw_disk_file_count': len(raw_set),
                'actual_raw_db_active_count': len(db_set),
            },
            'raw_vs_db': {
                'disk_only_count': disk_only_count,
                'disk_only_samples': disk_only_samples,
                'disk_only_top2': [{ 'key': k, 'count': v } for k, v in disk_only_top2.most_common(20)],
                'disk_only_ext': [{ 'key': k, 'count': v } for k, v in disk_only_ext.most_common(20)],
                'db_only_count': db_only_count,
                'db_only_samples': db_only_samples,
                'size_mismatch_count': size_mismatch_count,
                'size_mismatch_samples': size_mismatch_samples,
                'size_mismatch_top2': [{ 'key': k, 'count': v } for k, v in size_mismatch_top2.most_common(20)],
                'size_mismatch_ext': [{ 'key': k, 'count': v } for k, v in size_mismatch_ext.most_common(20)],
            },
            'manifest_vs_pdf_documents': {
                'manifest_disk_count': len(manifest_disk),
                'manifest_table_count': len(manifest_table),
                'manifest_missing_in_pdf_documents_count': len(manifest_disk - manifest_table),
                'manifest_missing_in_pdf_documents_samples': sorted(list(manifest_disk - manifest_table))[:100],
                'manifest_missing_on_disk_count': len(manifest_table - manifest_disk),
                'manifest_missing_on_disk_samples': sorted(list(manifest_table - manifest_disk))[:100],
            },
            'pdf_document_path_checks': {
                'missing_in_db_counts': dict(missing_db),
                'missing_in_db_samples': dict(missing_db_samples),
                'missing_on_disk_counts': dict(missing_disk),
                'missing_on_disk_samples': dict(missing_disk_samples),
            },
            'pdf_page_checks': {
                'page_mismatch_counts': page_mismatch,
                'page_mismatch_cap_expected_samples': page_mismatch_cap_expected_samples,
                'page_mismatch_unexpected_samples': page_mismatch_unexpected_samples,
                'page_file_missing_counts': dict(page_missing),
                'page_file_missing_samples': dict(page_missing_samples),
            },
            'duplicate_candidates': {
                'duplicate_message_groups_count': len(duplicate_message_groups),
                'duplicate_message_groups': duplicate_message_groups[:20],
                'same_sha1_groups_top20_count': len(duplicate_sha1_groups),
                'same_sha1_groups_top20': duplicate_sha1_groups,
            },
        },
        'safe_cleanup_actions': [
            {
                'action': 'index_reinforce_only',
                'target': 'raw_artifacts / pdf_documents coverage gaps',
                'method': 'raw_db_sync_status 기반 재동기화 dry-run + pdf manifest 재색인',
                'destructive': False,
            },
            {
                'action': 'rename_plan_only',
                'target': 'normalized channel_slug duplicates',
                'method': 'slug alias map 작성 후 move/rename manifest만 생성, 실제 rename 금지',
                'destructive': False,
            },
            {
                'action': 'quarantine_manifest_only',
                'target': 'disk_only artifacts (.DS_Store, mp4, orphan manifest, url_index history)',
                'method': '이동 후보 목록만 JSON/MD로 저장, 실제 이동 금지',
                'destructive': False,
            },
            {
                'action': 'runtime_hygiene_plan_only',
                'target': 'runtime/telegram_attach_tmp and telegram_scrape.lock',
                'method': '실행 중 프로세스 확인 후 보관/정리 기준 문서화, 실제 삭제 금지',
                'destructive': False,
            },
        ],
        'unverified_items': [
            'disk_only 및 size_mismatch의 직접 원인(동시 실행/후속 수집/인덱스 누락 등)은 미확인',
            'same_sha1 중복 파일군의 업무상 동일본/중복본 여부는 미확인',
f"manifest_missing_in_pdf_documents {len(manifest_disk - manifest_table)}건의 생성 시점과 누락 사유는 미확인",
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    commands = f'''# JB-20260310 STAGE1 DB CLEANUP PROOF COMMANDS
# snapshot_generated_at={result['generated_at']}

# 1) raw/runtime inventory
python3 - <<'PY'
from pathlib import Path
import os
root=Path("{RAW_ROOT}")
files=0; dirs=0
for cur,dirnames,filenames in os.walk(root):
    dirs += len(dirnames)
    files += len(filenames)
print(files, dirs)
PY
# observed: raw files={result['inventory']['raw_tree']['file_count']}, raw dirs={result['inventory']['raw_tree']['dir_count']}

python3 - <<'PY'
from pathlib import Path
import os
root=Path("{RUNTIME_ROOT}")
files=0; dirs=0
for cur,dirnames,filenames in os.walk(root):
    dirs += len(dirnames)
    files += len(filenames)
print(files, dirs)
PY
# observed: runtime files={result['inventory']['runtime_tree']['file_count']}, runtime dirs={result['inventory']['runtime_tree']['dir_count']}

# 2) sqlite core counts
python3 - <<'PY'
import sqlite3
conn=sqlite3.connect("{DB_PATH}")
cur=conn.cursor()
for sql in [
    "SELECT COUNT(*) FROM raw_artifacts",
    "SELECT COUNT(*) FROM pdf_documents",
    "SELECT COUNT(*) FROM pdf_pages",
    "SELECT COUNT(*) FROM sync_meta",
]:
    print(sql, cur.execute(sql).fetchone()[0])
conn.close()
PY
# observed: raw_artifacts={table_counts.get('raw_artifacts')}, pdf_documents={table_counts.get('pdf_documents')}, pdf_pages={table_counts.get('pdf_pages')}, sync_meta={table_counts.get('sync_meta')}

# 3) proof JSON
python3 runtime/tasks/JB-20260310_STAGE1_DB_CLEANUP_proof.py
# observed output file: {OUT_JSON}
'''
    OUT_TXT.write_text(commands, encoding='utf-8')
    conn.close()
    print(json.dumps({
        'proof_json': str(OUT_JSON),
        'proof_commands': str(OUT_TXT),
        'raw_files': result['inventory']['raw_tree']['file_count'],
        'db_active': len(db_set),
        'disk_only': disk_only_count,
        'size_mismatch': size_mismatch_count,
        'manifest_missing_in_pdf_documents': len(manifest_disk - manifest_table),
        'duplicate_message_groups': len(duplicate_message_groups),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
