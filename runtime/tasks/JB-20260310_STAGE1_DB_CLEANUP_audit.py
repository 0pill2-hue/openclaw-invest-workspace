#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path('/Users/jobiseu/.openclaw/workspace')
STAGE1 = ROOT / 'invest/stages/stage1/outputs'
RAW_ROOT = STAGE1 / 'raw'
RUNTIME_ROOT = STAGE1 / 'runtime'
DB_PATH = STAGE1 / 'db/stage1_raw_archive.sqlite3'
REPORT_JSON = ROOT / 'runtime/tasks/JB-20260310-STAGE1-DB-CLEANUP_inventory.json'
CANDIDATES_JSON = ROOT / 'runtime/tasks/JB-20260310-STAGE1-DB-CLEANUP_candidates.json'


def iso_epoch(ts: float) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(ts))


def norm_raw_rel(path: str | None) -> str:
    if not path:
        return ''
    p = path.replace('\\', '/').lstrip('./')
    if p.startswith('outputs/raw/'):
        p = p[len('outputs/raw/'):]
    elif p.startswith('invest/stages/stage1/outputs/raw/'):
        p = p[len('invest/stages/stage1/outputs/raw/'):]
    elif p.startswith(str(RAW_ROOT).replace('\\', '/') + '/'):
        p = p[len(str(RAW_ROOT).replace('\\', '/')) + 1:]
    return p


def path_exists_in_raw(rel: str) -> bool:
    if not rel:
        return False
    return (RAW_ROOT / rel).exists()


def top_counter(counter: Counter, limit: int = 20):
    return [{"key": k, "count": v} for k, v in counter.most_common(limit)]


def bytes_counter(counter: Counter, limit: int = 20):
    return [{"key": k, "bytes": v} for k, v in counter.most_common(limit)]


def first_n(seq: Iterable, limit: int = 50):
    out = []
    for i, item in enumerate(seq):
        if i >= limit:
            break
        out.append(item)
    return out


def walk_tree(root: Path):
    file_sizes: dict[str, int] = {}
    file_count = 0
    dir_count = 0
    total_bytes = 0
    by_top1_count = Counter()
    by_top1_bytes = Counter()
    by_top2_count = Counter()
    by_top2_bytes = Counter()
    ext_count = Counter()
    ext_bytes = Counter()
    archive_dirs = []

    for cur, dirs, files in os.walk(root):
        dir_count += len(dirs)
        cur_path = Path(cur)
        rel_dir = cur_path.relative_to(root).as_posix() if cur_path != root else ''
        for d in dirs:
            rel = f'{rel_dir}/{d}' if rel_dir else d
            if 'archive' in d.lower() or 'archive' in rel.lower():
                archive_dirs.append(rel)
        for name in files:
            full = cur_path / name
            try:
                st = full.stat()
            except FileNotFoundError:
                continue
            rel = full.relative_to(root).as_posix()
            size = st.st_size
            file_sizes[rel] = size
            file_count += 1
            total_bytes += size
            parts = rel.split('/')
            top1 = parts[0] if parts else ''
            top2 = '/'.join(parts[:2]) if len(parts) >= 2 else top1
            by_top1_count[top1] += 1
            by_top1_bytes[top1] += size
            by_top2_count[top2] += 1
            by_top2_bytes[top2] += size
            ext = Path(name).suffix.lower() or '<no_ext>'
            ext_count[ext] += 1
            ext_bytes[ext] += size
    return {
        'file_sizes': file_sizes,
        'summary': {
            'root': str(root),
            'file_count': file_count,
            'dir_count': dir_count,
            'total_bytes': total_bytes,
            'top1_count': top_counter(by_top1_count),
            'top1_bytes': bytes_counter(by_top1_bytes),
            'top2_count': top_counter(by_top2_count),
            'top2_bytes': bytes_counter(by_top2_bytes),
            'top_ext_count': top_counter(ext_count),
            'top_ext_bytes': bytes_counter(ext_bytes),
            'archive_dirs': sorted(archive_dirs)[:100],
        },
    }


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return {'_error': str(e), '_path': str(path)}


def summarize_runtime(runtime_root: Path):
    json_files = []
    lock_files = []
    temp_dirs = []
    for cur, dirs, files in os.walk(runtime_root):
        curp = Path(cur)
        rel_dir = curp.relative_to(runtime_root).as_posix() if curp != runtime_root else ''
        for d in dirs:
            if 'tmp' in d.lower() or d.lower().endswith('_tmp'):
                temp_dirs.append(f'{rel_dir}/{d}' if rel_dir else d)
        for name in files:
            full = curp / name
            rel = full.relative_to(runtime_root).as_posix()
            if name.endswith('.json'):
                try:
                    st = full.stat()
                    payload = load_json(full)
                    json_files.append({
                        'path': rel,
                        'size_bytes': st.st_size,
                        'mtime': iso_epoch(st.st_mtime),
                        'keys': list(payload.keys())[:12] if isinstance(payload, dict) else [],
                        'timestamp_like': {k: payload.get(k) for k in ['timestamp', 'saved_at', 'started_at', 'finished_at', 'updated_at', 'run_id', 'sync_id', 'status', 'result'] if isinstance(payload, dict) and k in payload},
                    })
                except Exception:
                    continue
            if name.endswith('.lock'):
                try:
                    st = full.stat()
                    lock_files.append({'path': rel, 'size_bytes': st.st_size, 'mtime': iso_epoch(st.st_mtime)})
                except Exception:
                    pass
    return {
        'json_files_count': len(json_files),
        'json_files': sorted(json_files, key=lambda x: x['path']),
        'lock_files': sorted(lock_files, key=lambda x: x['path']),
        'temp_dirs': sorted(temp_dirs),
    }


def normalize_slug(s: str | None) -> str:
    if not s:
        return ''
    return ''.join(ch for ch in s.lower() if ch.isalnum())


def main():
    raw_walk = walk_tree(RAW_ROOT)
    runtime_walk = walk_tree(RUNTIME_ROOT)
    runtime_meta = summarize_runtime(RUNTIME_ROOT)

    raw_files = raw_walk['file_sizes']
    raw_rel_set = set(raw_files.keys())

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = [dict(r) for r in cur.execute("SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY type,name")]
    table_counts = {}
    for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        name = row['name']
        table_counts[name] = cur.execute(f'SELECT COUNT(*) AS c FROM "{name}"').fetchone()['c']

    sync_meta = {r['key']: r['value'] for r in cur.execute('SELECT key, value FROM sync_meta ORDER BY key')}
    sync_meta_parsed = {}
    for k, v in sync_meta.items():
        try:
            sync_meta_parsed[k] = json.loads(v)
        except Exception:
            sync_meta_parsed[k] = v

    raw_active = {}
    raw_inactive_count = 0
    raw_db_top1_count = Counter()
    raw_db_top1_bytes = Counter()
    raw_db_top2_count = Counter()
    raw_db_top2_bytes = Counter()
    sha1_dupe_groups = []

    for row in cur.execute('SELECT rel_path, size_bytes, sha1, is_active FROM raw_artifacts'):
        rel = row['rel_path']
        size = row['size_bytes']
        is_active = row['is_active']
        parts = rel.split('/')
        top1 = parts[0] if parts else ''
        top2 = '/'.join(parts[:2]) if len(parts) >= 2 else top1
        raw_db_top1_count[top1] += 1
        raw_db_top1_bytes[top1] += size
        raw_db_top2_count[top2] += 1
        raw_db_top2_bytes[top2] += size
        if is_active:
            raw_active[rel] = {'size_bytes': size, 'sha1': row['sha1']}
        else:
            raw_inactive_count += 1

    db_rel_set = set(raw_active.keys())
    disk_only = sorted(raw_rel_set - db_rel_set)
    db_only = sorted(db_rel_set - raw_rel_set)
    size_mismatch = []
    for rel in sorted(raw_rel_set & db_rel_set):
        if raw_files[rel] != raw_active[rel]['size_bytes']:
            size_mismatch.append({
                'rel_path': rel,
                'disk_size_bytes': raw_files[rel],
                'db_size_bytes': raw_active[rel]['size_bytes'],
            })

    sha_dupe_query = cur.execute(
        """
        SELECT sha1, size_bytes, COUNT(*) AS cnt
        FROM raw_artifacts
        WHERE is_active = 1 AND size_bytes > 0
        GROUP BY sha1, size_bytes
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, size_bytes DESC
        LIMIT 200
        """
    ).fetchall()
    for row in sha_dupe_query:
        examples = [r['rel_path'] for r in cur.execute(
            'SELECT rel_path FROM raw_artifacts WHERE is_active=1 AND sha1=? AND size_bytes=? ORDER BY rel_path LIMIT 10',
            (row['sha1'], row['size_bytes'])
        )]
        sha1_dupe_groups.append({
            'sha1': row['sha1'],
            'size_bytes': row['size_bytes'],
            'count': row['cnt'],
            'examples': examples,
        })

    pdf_rows = list(cur.execute(
        'SELECT doc_key, source_family, channel_slug, message_id, message_date, month_key, kind, artifact_bucket, meta_rel_path, original_rel_path, extract_rel_path, manifest_rel_path, bundle_rel_path, original_size_bytes, page_count, text_pages, rendered_pages, extraction_status, extraction_reason, render_status, render_reason, quality_grade FROM pdf_documents'
    ))
    page_rows = list(cur.execute('SELECT doc_key, page_no, text_rel_path, render_rel_path, text_chars FROM pdf_pages'))

    pages_by_doc = defaultdict(list)
    for r in page_rows:
        pages_by_doc[r['doc_key']].append(r)

    pdf_status_counts = {
        'source_family': Counter(),
        'kind': Counter(),
        'extraction_status': Counter(),
        'render_status': Counter(),
        'quality_grade': Counter(),
    }
    pdf_path_missing = {
        'meta_missing_disk': [],
        'meta_missing_raw_artifacts': [],
        'manifest_missing_disk': [],
        'manifest_missing_raw_artifacts': [],
        'original_missing_disk': [],
        'original_missing_raw_artifacts': [],
        'extract_missing_disk': [],
        'extract_missing_raw_artifacts': [],
        'bundle_missing_disk': [],
        'bundle_missing_raw_artifacts': [],
    }
    pdf_page_mismatch = {
        'page_count_vs_rows': [],
        'text_pages_vs_rows': [],
        'rendered_pages_vs_rows': [],
    }
    channel_msg_groups = defaultdict(list)
    doc_manifest_set = set()
    for r in pdf_rows:
        doc = dict(r)
        pdf_status_counts['source_family'][doc['source_family'] or '<empty>'] += 1
        pdf_status_counts['kind'][doc['kind'] or '<empty>'] += 1
        pdf_status_counts['extraction_status'][doc['extraction_status'] or '<empty>'] += 1
        pdf_status_counts['render_status'][doc['render_status'] or '<empty>'] += 1
        pdf_status_counts['quality_grade'][doc['quality_grade'] or '<empty>'] += 1

        meta_rel = norm_raw_rel(doc['meta_rel_path'])
        manifest_rel = norm_raw_rel(doc['manifest_rel_path'])
        original_rel = norm_raw_rel(doc['original_rel_path'])
        extract_rel = norm_raw_rel(doc['extract_rel_path'])
        bundle_rel = norm_raw_rel(doc['bundle_rel_path'])

        if manifest_rel:
            doc_manifest_set.add(manifest_rel)

        checks = [
            ('meta', meta_rel),
            ('manifest', manifest_rel),
            ('original', original_rel),
            ('extract', extract_rel),
            ('bundle', bundle_rel),
        ]
        for label, rel in checks:
            if not rel:
                continue
            if not path_exists_in_raw(rel):
                pdf_path_missing[f'{label}_missing_disk'].append({'doc_key': doc['doc_key'], 'rel_path': rel})
            if rel not in raw_active:
                pdf_path_missing[f'{label}_missing_raw_artifacts'].append({'doc_key': doc['doc_key'], 'rel_path': rel})

        page_list = pages_by_doc.get(doc['doc_key'], [])
        actual_page_rows = len(page_list)
        actual_text_rows = sum(1 for p in page_list if norm_raw_rel(p['text_rel_path']))
        actual_render_rows = sum(1 for p in page_list if norm_raw_rel(p['render_rel_path']))
        if doc['page_count'] != actual_page_rows:
            pdf_page_mismatch['page_count_vs_rows'].append({
                'doc_key': doc['doc_key'],
                'declared_page_count': doc['page_count'],
                'actual_page_rows': actual_page_rows,
            })
        if doc['text_pages'] != actual_text_rows:
            pdf_page_mismatch['text_pages_vs_rows'].append({
                'doc_key': doc['doc_key'],
                'declared_text_pages': doc['text_pages'],
                'actual_text_rows': actual_text_rows,
            })
        if doc['rendered_pages'] != actual_render_rows:
            pdf_page_mismatch['rendered_pages_vs_rows'].append({
                'doc_key': doc['doc_key'],
                'declared_rendered_pages': doc['rendered_pages'],
                'actual_render_rows': actual_render_rows,
            })

        group_key = (normalize_slug(doc['channel_slug']), doc['message_id'])
        channel_msg_groups[group_key].append({
            'doc_key': doc['doc_key'],
            'channel_slug': doc['channel_slug'],
            'message_id': doc['message_id'],
            'message_date': doc['message_date'],
            'manifest_rel_path': doc['manifest_rel_path'],
            'meta_rel_path': doc['meta_rel_path'],
        })

    pdf_pages_missing_files = {
        'text_missing_disk': [],
        'text_missing_raw_artifacts': [],
        'render_missing_disk': [],
        'render_missing_raw_artifacts': [],
    }
    for r in page_rows:
        text_rel = norm_raw_rel(r['text_rel_path'])
        render_rel = norm_raw_rel(r['render_rel_path'])
        if text_rel:
            if not path_exists_in_raw(text_rel):
                pdf_pages_missing_files['text_missing_disk'].append({'doc_key': r['doc_key'], 'page_no': r['page_no'], 'rel_path': text_rel})
            if text_rel not in raw_active:
                pdf_pages_missing_files['text_missing_raw_artifacts'].append({'doc_key': r['doc_key'], 'page_no': r['page_no'], 'rel_path': text_rel})
        if render_rel:
            if not path_exists_in_raw(render_rel):
                pdf_pages_missing_files['render_missing_disk'].append({'doc_key': r['doc_key'], 'page_no': r['page_no'], 'rel_path': render_rel})
            if render_rel not in raw_active:
                pdf_pages_missing_files['render_missing_raw_artifacts'].append({'doc_key': r['doc_key'], 'page_no': r['page_no'], 'rel_path': render_rel})

    manifest_files_on_disk = sorted(rel for rel in raw_rel_set if rel.endswith('__pdf_manifest.json'))
    doc_manifest_missing_in_table = sorted(set(manifest_files_on_disk) - doc_manifest_set)
    doc_manifest_missing_on_disk = sorted(doc_manifest_set - set(manifest_files_on_disk))

    duplicate_message_candidates = []
    for (_norm_slug, message_id), docs in channel_msg_groups.items():
        slugs = sorted({d['channel_slug'] for d in docs})
        if len(docs) > 1 and len(slugs) > 1:
            duplicate_message_candidates.append({
                'message_id': message_id,
                'normalized_slug_group': _norm_slug,
                'doc_count': len(docs),
                'channel_slugs': slugs,
                'docs': docs[:10],
            })
    duplicate_message_candidates.sort(key=lambda x: (-x['doc_count'], x['normalized_slug_group'], x['message_id']))

    raw_db_status = load_json(RUNTIME_ROOT / 'raw_db_sync_status.json')
    raw_db_alignment = {
        'runtime_status_sync_id': raw_db_status.get('sync_id') if isinstance(raw_db_status, dict) else None,
        'sync_meta_last_sync_id': sync_meta_parsed.get('last_sync_id'),
        'runtime_status_finished_at': raw_db_status.get('finished_at') if isinstance(raw_db_status, dict) else None,
        'sync_meta_last_sync_finished_at': sync_meta_parsed.get('last_sync_finished_at'),
        'runtime_status_scanned_files': raw_db_status.get('scanned_files') if isinstance(raw_db_status, dict) else None,
        'sync_meta_last_sync_summary_scanned_files': (sync_meta_parsed.get('last_sync_summary') or {}).get('scanned_files') if isinstance(sync_meta_parsed.get('last_sync_summary'), dict) else None,
        'actual_raw_disk_file_count': len(raw_rel_set),
        'raw_artifacts_active_count': len(db_rel_set),
    }

    inventory = {
        'generated_at': iso_epoch(time.time()),
        'paths': {
            'workspace_root': str(ROOT),
            'stage1_outputs': str(STAGE1),
            'raw_root': str(RAW_ROOT),
            'runtime_root': str(RUNTIME_ROOT),
            'db_path': str(DB_PATH),
        },
        'db_file': {
            'exists': DB_PATH.exists(),
            'size_bytes': DB_PATH.stat().st_size if DB_PATH.exists() else None,
            'mtime': iso_epoch(DB_PATH.stat().st_mtime) if DB_PATH.exists() else None,
        },
        'raw_tree': raw_walk['summary'],
        'runtime_tree': runtime_walk['summary'],
        'runtime_meta': runtime_meta,
        'db': {
            'tables': tables,
            'table_counts': table_counts,
            'sync_meta': sync_meta_parsed,
            'raw_artifacts_summary': {
                'active_count': len(db_rel_set),
                'inactive_count': raw_inactive_count,
                'top1_count': top_counter(raw_db_top1_count),
                'top1_bytes': bytes_counter(raw_db_top1_bytes),
                'top2_count': top_counter(raw_db_top2_count),
                'top2_bytes': bytes_counter(raw_db_top2_bytes),
            },
            'pdf_documents_summary': {
                'source_family': pdf_status_counts['source_family'],
                'kind': pdf_status_counts['kind'],
                'extraction_status': pdf_status_counts['extraction_status'],
                'render_status': pdf_status_counts['render_status'],
                'quality_grade': pdf_status_counts['quality_grade'],
                'docs_with_manifest_rel_path': sum(1 for r in pdf_rows if norm_raw_rel(r['manifest_rel_path'])),
                'docs_with_original_rel_path': sum(1 for r in pdf_rows if norm_raw_rel(r['original_rel_path'])),
                'docs_with_extract_rel_path': sum(1 for r in pdf_rows if norm_raw_rel(r['extract_rel_path'])),
                'docs_with_bundle_rel_path': sum(1 for r in pdf_rows if norm_raw_rel(r['bundle_rel_path'])),
            },
        },
        'cross_checks': {
            'raw_db_alignment': raw_db_alignment,
            'raw_vs_db': {
                'disk_only_count': len(disk_only),
                'db_only_count': len(db_only),
                'size_mismatch_count': len(size_mismatch),
            },
            'manifest_vs_pdf_documents': {
                'manifest_files_on_disk_count': len(manifest_files_on_disk),
                'manifest_paths_in_pdf_documents_count': len(doc_manifest_set),
                'manifest_missing_in_pdf_documents_count': len(doc_manifest_missing_in_table),
                'manifest_missing_on_disk_count': len(doc_manifest_missing_on_disk),
            },
            'pdf_document_path_missing_counts': {k: len(v) for k, v in pdf_path_missing.items()},
            'pdf_page_mismatch_counts': {k: len(v) for k, v in pdf_page_mismatch.items()},
            'pdf_page_file_missing_counts': {k: len(v) for k, v in pdf_pages_missing_files.items()},
            'duplicate_message_candidate_group_count': len(duplicate_message_candidates),
            'duplicate_sha1_group_count_top200': len(sha1_dupe_groups),
        },
    }

    candidates = {
        'duplicates': {
            'message_coordinate_groups': {
                'count': len(duplicate_message_candidates),
                'samples': duplicate_message_candidates[:100],
            },
            'same_sha1_active_files_top200': {
                'count': len(sha1_dupe_groups),
                'samples': sha1_dupe_groups,
            },
        },
        'orphans': {
            'raw_disk_only': {
                'count': len(disk_only),
                'samples': first_n(disk_only, 200),
            },
            'raw_db_only_active': {
                'count': len(db_only),
                'samples': first_n(db_only, 200),
            },
            'runtime_temp_dirs': {
                'count': len(runtime_meta['temp_dirs']),
                'samples': runtime_meta['temp_dirs'][:200],
            },
            'runtime_lock_files': {
                'count': len(runtime_meta['lock_files']),
                'samples': runtime_meta['lock_files'][:50],
            },
        },
        'inconsistencies': {
            'raw_size_mismatches': {
                'count': len(size_mismatch),
                'samples': size_mismatch[:200],
            },
            'pdf_document_path_missing': {
                **{k: {'count': len(v), 'samples': v[:100]} for k, v in pdf_path_missing.items()},
            },
            'pdf_page_count_mismatches': {
                **{k: {'count': len(v), 'samples': v[:100]} for k, v in pdf_page_mismatch.items()},
            },
            'pdf_page_file_missing': {
                **{k: {'count': len(v), 'samples': v[:100]} for k, v in pdf_pages_missing_files.items()},
            },
            'manifest_missing_in_pdf_documents': {
                'count': len(doc_manifest_missing_in_table),
                'samples': first_n(doc_manifest_missing_in_table, 200),
            },
            'manifest_missing_on_disk': {
                'count': len(doc_manifest_missing_on_disk),
                'samples': first_n(doc_manifest_missing_on_disk, 200),
            },
            'raw_db_alignment': raw_db_alignment,
            'pdf_index_summary_count': sync_meta_parsed.get('last_pdf_index_summary'),
        },
        'missing': {
            'pdf_manifest_paths_in_table_missing_disk': {
                'count': len(pdf_path_missing['manifest_missing_disk']),
                'samples': pdf_path_missing['manifest_missing_disk'][:100],
            },
            'pdf_meta_paths_in_table_missing_disk': {
                'count': len(pdf_path_missing['meta_missing_disk']),
                'samples': pdf_path_missing['meta_missing_disk'][:100],
            },
            'pdf_page_text_missing_disk': {
                'count': len(pdf_pages_missing_files['text_missing_disk']),
                'samples': pdf_pages_missing_files['text_missing_disk'][:100],
            },
            'pdf_page_render_missing_disk': {
                'count': len(pdf_pages_missing_files['render_missing_disk']),
                'samples': pdf_pages_missing_files['render_missing_disk'][:100],
            },
        },
        'archive': {
            'raw_archive_dirs': raw_walk['summary']['archive_dirs'],
            'runtime_archive_dirs': runtime_walk['summary']['archive_dirs'],
        },
        'recommended_non_destructive_actions': [
            '실삭제 전용 명령은 만들지 말고, 경로별 후보를 JSON/Markdown 보고서로만 분류 유지.',
            'raw_disk_only, raw_db_only_active, pdf manifest/document 불일치 항목은 별도 quarantine manifest를 먼저 생성한 뒤 수동 승인 단계로 넘길 것.',
            'normalized channel_slug + message_id 중복군은 slug 정규화 규칙을 먼저 확정한 뒤 재색인 전용 dry-run을 수행할 것.',
            'runtime/telegram_attach_tmp 및 lock 파일은 점유 프로세스 확인 후 snapshot 목록 기반으로만 정리 검토할 것.',
            'sync_meta.last_pdf_index_summary 와 pdf_documents/pdf_pages 실테이블 수 차이는 재색인/요약 산출물 순서 문제 가능성이 있어 원인 확인 전 삭제 금지.',
        ],
    }

    REPORT_JSON.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    CANDIDATES_JSON.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
    conn.close()
    print(json.dumps({
        'inventory_json': str(REPORT_JSON),
        'candidates_json': str(CANDIDATES_JSON),
        'raw_files': len(raw_rel_set),
        'raw_db_active': len(db_rel_set),
        'disk_only': len(disk_only),
        'db_only': len(db_only),
        'size_mismatch': len(size_mismatch),
        'duplicate_message_groups': len(duplicate_message_candidates),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
