#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/jobiseu/.openclaw/workspace')
STAGE1_DIR = ROOT / 'invest/stages/stage1'
SCRIPT_DIR = STAGE1_DIR / 'scripts'
ATTACH_ROOT = STAGE1_DIR / 'outputs/raw/qualitative/attachments/telegram'
STATS_PATH = ROOT / 'runtime/tasks/JB-20260309_stage1_pdf_live_backfill_stats.json'
MAX_FETCH = int(os.environ.get('TELEGRAM_ATTACH_LIVE_FETCH_LIMIT', '2000'))
BATCH_SIZE = int(os.environ.get('TELEGRAM_ATTACH_LIVE_FETCH_BATCH', '100'))

sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location('tg_backfill', SCRIPT_DIR / 'stage01_telegram_attachment_extract_backfill.py')
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

from telethon import TelegramClient  # type: ignore
from telethon.errors import FloodWaitError  # type: ignore


def load_env() -> None:
    env_path = STAGE1_DIR / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


def write_stats(payload: dict) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def header_channel_ref(log_path: Path) -> str:
    try:
        first = log_path.open(encoding='utf-8', errors='ignore').readline().strip()
    except Exception:
        first = ''
    m = re.match(r'^# Telegram Log: .*\((.+)\)$', first)
    if m:
        return m.group(1).strip()
    stem = log_path.stem
    if stem.endswith('_full'):
        stem = stem[:-5]
    if '_' in stem:
        return stem.rsplit('_', 1)[-1].strip()
    return stem.strip()


def ref_candidates(log_path: Path) -> list[str | int]:
    raw = header_channel_ref(log_path)
    out: list[str | int] = []
    if raw:
        out.append(int(raw) if raw.isdigit() else raw)
    stem = log_path.stem
    if stem.endswith('_full'):
        stem = stem[:-5]
    if '_' in stem:
        last = stem.rsplit('_', 1)[-1].strip()
        cand: str | int = int(last) if last.isdigit() else last
        if cand not in out:
            out.append(cand)
    return out


def candidate_scan() -> tuple[list[dict], dict]:
    stats = {
        'scanned_logs': 0,
        'pdf_candidates_seen': 0,
        'skipped_existing_original': 0,
        'queued_missing_original': 0,
        'max_fetch': MAX_FETCH,
    }
    items: list[dict] = []
    for log_path in mod._iter_legacy_logs():
        stats['scanned_logs'] += 1
        try:
            content = log_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        channel_slug = mod._telegram_channel_slug_from_log_path(log_path)
        refs = ref_candidates(log_path)
        if not channel_slug or not refs:
            continue
        blocks = mod._split_telegram_blocks(content)
        for block in reversed(blocks):
            msg_id = getattr(mod, '_parse_message_id', lambda b: 0)(block)
            if msg_id <= 0:
                continue
            mime = mod._marker_value(block, 'MIME')
            file_name = mod._marker_value(block, 'FILE_NAME')
            kind = mod._infer_kind_from_markers(mod._marker_value(block, 'ATTACH_KIND'), mime, file_name)
            if kind != 'pdf':
                continue
            stats['pdf_candidates_seen'] += 1
            artifact_dir = ATTACH_ROOT / channel_slug / f'msg_{msg_id}'
            meta_path = artifact_dir / 'meta.json'
            meta = mod._read_json(meta_path) if meta_path.exists() else {}
            original_path = mod._infer_original_path(meta, meta_path) if meta else Path('')
            if original_path and original_path.exists() and original_path.suffix.lower() == '.pdf':
                stats['skipped_existing_original'] += 1
                continue
            items.append({
                'log_path': str(log_path),
                'channel_slug': channel_slug,
                'refs': refs,
                'msg_id': int(msg_id),
                'file_name': file_name,
                'mime': mime,
                'message_date': mod._parse_message_date(block),
                'artifact_dir': str(artifact_dir),
                'meta_path': str(meta_path),
            })
            if len(items) >= MAX_FETCH:
                stats['queued_missing_original'] = len(items)
                return items, stats
    stats['queued_missing_original'] = len(items)
    return items, stats


def chunked(seq: list[dict], size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


async def main() -> int:
    load_env()
    api_id = int(os.environ.get('TELEGRAM_API_ID', '0'))
    api_hash = os.environ.get('TELEGRAM_API_HASH', '')
    started_at = datetime.now(timezone.utc)
    items, scan_stats = candidate_scan()
    stats: dict = {
        'saved_at': started_at.isoformat(),
        'status': 'RUNNING',
        **scan_stats,
        'entity_resolve_ok': 0,
        'entity_resolve_failed': 0,
        'messages_fetched': 0,
        'messages_missing': 0,
        'downloads_ok': 0,
        'downloads_failed': 0,
        'extract_ok': 0,
        'extract_failed': 0,
        'flood_wait_events': 0,
        'errors': [],
    }
    write_stats(stats)
    if not items:
        stats['status'] = 'OK'
        stats['finished_at'] = datetime.now(timezone.utc).isoformat()
        stats['duration_sec'] = round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)
        write_stats(stats)
        return 0
    if not api_id or not api_hash:
        stats['status'] = 'FAILED'
        stats['errors'].append('missing_telegram_credentials')
        stats['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_stats(stats)
        return 2

    grouped: dict[str, list[dict]] = defaultdict(list)
    ref_map: dict[str, list[str | int]] = {}
    for item in items:
        key = item['channel_slug']
        grouped[key].append(item)
        ref_map[key] = item['refs']

    session_name = str(SCRIPT_DIR / 'jobis_mtproto_session')
    client = TelegramClient(session_name, api_id, api_hash)
    entity_cache: dict[str, object] = {}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            stats['status'] = 'FAILED'
            stats['errors'].append('telegram_authorization_failed')
            return 3

        for slug, group in grouped.items():
            entity = None
            for ref in ref_map.get(slug, []):
                key = str(ref)
                if key in entity_cache:
                    entity = entity_cache[key]
                    break
                try:
                    entity = await client.get_entity(ref)
                    entity_cache[key] = entity
                    stats['entity_resolve_ok'] += 1
                    break
                except Exception as e:
                    stats['entity_resolve_failed'] += 1
                    stats['errors'].append(f'entity:{slug}:{ref}:{type(e).__name__}')
            if entity is None:
                continue

            id_map = {int(item['msg_id']): item for item in group}
            for batch in chunked(group, max(1, BATCH_SIZE)):
                ids = [int(x['msg_id']) for x in batch]
                try:
                    messages = await client.get_messages(entity, ids=ids)
                except FloodWaitError as e:
                    stats['flood_wait_events'] += 1
                    wait_sec = int(getattr(e, 'seconds', 5) or 5)
                    time.sleep(min(wait_sec, 300))
                    messages = await client.get_messages(entity, ids=ids)
                except Exception as e:
                    stats['errors'].append(f'get_messages:{slug}:{type(e).__name__}')
                    continue

                if not isinstance(messages, list):
                    messages = [messages]
                seen_ids = set()
                for msg in messages:
                    if not msg:
                        continue
                    msg_id = int(getattr(msg, 'id', 0) or 0)
                    seen_ids.add(msg_id)
                    item = id_map.get(msg_id)
                    if not item:
                        continue
                    stats['messages_fetched'] += 1
                    fobj = getattr(msg, 'file', None)
                    mime = str(getattr(fobj, 'mime_type', '') or item.get('mime') or '').lower()
                    name = str(getattr(fobj, 'name', '') or item.get('file_name') or '')
                    ext = Path(name).suffix or '.pdf'
                    artifact_dir = Path(item['artifact_dir'])
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    target_name = mod._safe_component(Path(name).name if name else f'msg_{msg_id}{ext}', f'msg_{msg_id}{ext}')
                    original_path = artifact_dir / target_name
                    meta_path = Path(item['meta_path'])
                    meta = mod._read_json(meta_path) if meta_path.exists() else {}
                    try:
                        dl_path = await client.download_media(msg, file=str(original_path))
                        actual = Path(dl_path) if dl_path else original_path
                        if not actual.exists():
                            raise FileNotFoundError('download_missing')
                        if actual.resolve() != original_path.resolve():
                            import shutil
                            shutil.copy2(actual, original_path)
                        stats['downloads_ok'] += 1
                        text, reason = mod._extract_pdf_text(str(original_path))
                        text = mod._clip_text(text)
                        extract_path = artifact_dir / 'extracted.txt'
                        if text:
                            extract_path.write_text(text, encoding='utf-8')
                            stats['extract_ok'] += 1
                            meta['extract_path'] = mod._rel_stage1_path(extract_path)
                            meta['extraction_status'] = 'ok'
                            meta['extraction_reason'] = 'ok'
                            meta['extraction_origin'] = 'runtime_live_pdf_backfill'
                        else:
                            stats['extract_failed'] += 1
                            meta['extraction_status'] = 'failed'
                            meta['extraction_reason'] = reason or 'pdf_text_empty'
                            meta['extraction_origin'] = 'runtime_live_pdf_backfill'
                        meta['saved_at'] = str(meta.get('saved_at') or datetime.now(timezone.utc).isoformat())
                        meta['channel_slug'] = item['channel_slug']
                        meta['message_id'] = msg_id
                        meta['message_date'] = str(meta.get('message_date') or item.get('message_date') or '')
                        meta['kind'] = 'pdf'
                        meta['mime'] = mime or 'application/pdf'
                        meta['artifact_dir'] = mod._rel_stage1_path(artifact_dir)
                        meta['meta_path'] = mod._rel_stage1_path(meta_path)
                        meta['original_name'] = original_path.name
                        meta['original_path'] = mod._rel_stage1_path(original_path)
                        meta['original_size'] = int(original_path.stat().st_size)
                        meta['original_store_status'] = 'ok'
                        meta['original_store_reason'] = 'ok'
                        meta['channel_title'] = str(meta.get('channel_title') or getattr(entity, 'title', '') or '')
                        meta['channel_username'] = str(meta.get('channel_username') or getattr(entity, 'username', '') or ref_map.get(slug, [''])[0])
                        meta['extraction_updated_at'] = datetime.now(timezone.utc).isoformat()
                        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
                    except FloodWaitError as e:
                        stats['flood_wait_events'] += 1
                        stats['downloads_failed'] += 1
                        stats['errors'].append(f'floodwait:{slug}:{msg_id}:{int(getattr(e, "seconds", 0) or 0)}')
                        time.sleep(min(int(getattr(e, 'seconds', 5) or 5), 300))
                    except Exception as e:
                        stats['downloads_failed'] += 1
                        stats['errors'].append(f'download:{slug}:{msg_id}:{type(e).__name__}')
                missing = set(ids) - seen_ids
                stats['messages_missing'] += len(missing)
                if stats['downloads_ok'] and stats['downloads_ok'] % 25 == 0:
                    stats['updated_at'] = datetime.now(timezone.utc).isoformat()
                    write_stats(stats)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    finished = datetime.now(timezone.utc)
    stats['status'] = 'OK' if not stats['downloads_failed'] else 'WARN'
    stats['finished_at'] = finished.isoformat()
    stats['duration_sec'] = round((finished - started_at).total_seconds(), 3)
    write_stats(stats)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
