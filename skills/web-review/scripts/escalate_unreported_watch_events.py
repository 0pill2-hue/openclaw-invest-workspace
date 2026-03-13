#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sync_watch_event_to_task import load_queue, parse_iso, sync_event_to_task, utc_now_iso, write_queue

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
DEFAULT_QUEUE_FILE = WORKSPACE / 'runtime' / 'watch' / 'unreported_watch_events.json'


def main() -> int:
    ap = argparse.ArgumentParser(description='Backfill queued watch events into taskdb and create fallback tasks when needed.')
    ap.add_argument('--queue-file', default=str(DEFAULT_QUEUE_FILE))
    ap.add_argument('--older-than-seconds', type=int, default=90)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    queue_path = Path(args.queue_file)
    queue = load_queue(queue_path)
    now = datetime.now(timezone.utc)
    synced = []

    for event in queue.get('events', []):
        if event.get('acked_at'):
            continue
        if str(event.get('task_sync_status') or '') in {'updated_existing', 'created_new'} and str(event.get('task_id') or '').strip():
            continue

        observed = parse_iso(str(event.get('observed_at') or ''))
        if observed is None:
            continue
        age_seconds = int((now - observed).total_seconds())
        allow_create = bool(event.get('follow_up_required')) or age_seconds >= args.older_than_seconds

        sync = sync_event_to_task(
            event,
            allow_create=allow_create,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            event['task_sync_status'] = sync['action']
            event['task_sync_at'] = sync['synced_at']
            event['task_sync_match'] = sync.get('matched_by', '')
            if sync.get('task_id'):
                event['task_id'] = sync['task_id']
            if sync.get('proof_path'):
                event['proof_path'] = sync['proof_path']
            if sync['action'] == 'created_new':
                event['escalated_at'] = sync['synced_at']
            event['updated_at'] = sync['synced_at']

        synced.append({
            'event_id': event.get('id'),
            'age_seconds': age_seconds,
            'allow_create': allow_create,
            'action': sync['action'],
            'task_id': sync.get('task_id', ''),
            'proof_path': sync.get('proof_path', ''),
            'matched_by': sync.get('matched_by', ''),
            'dry_run': bool(args.dry_run),
        })

    if not args.dry_run:
        queue['updated_at'] = utc_now_iso()
        write_queue(queue_path, queue)
    print(json.dumps({'ok': True, 'queue_file': str(queue_path), 'synced': synced, 'count': len(synced)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
