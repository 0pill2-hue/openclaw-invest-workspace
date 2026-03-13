#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
DEFAULT_QUEUE_FILE = WORKSPACE / 'runtime' / 'watch' / 'unreported_watch_events.json'


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_queue(path: Path) -> dict:
    if not path.exists():
        return {'version': 1, 'events': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'version': 1, 'events': []}
    if not isinstance(data, dict):
        return {'version': 1, 'events': []}
    if not isinstance(data.get('events'), list):
        data['events'] = []
    data.setdefault('version', 1)
    return data


def write_queue(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Acknowledge a queued watch event after reporting it.')
    ap.add_argument('--event-id', required=True)
    ap.add_argument('--queue-file', default=str(DEFAULT_QUEUE_FILE))
    ap.add_argument('--ack-note', default='')
    args = ap.parse_args()

    queue_path = Path(args.queue_file)
    queue = load_queue(queue_path)
    now = utc_now_iso()
    target = None
    for event in queue.get('events', []):
        if str(event.get('id') or '') == args.event_id:
            target = event
            break

    if target is None:
        print(json.dumps({'ok': False, 'error': 'event_not_found', 'event_id': args.event_id}, ensure_ascii=False))
        return 1

    target['acked_at'] = now
    if args.ack_note:
        target['ack_note'] = args.ack_note
    target['updated_at'] = now
    queue['updated_at'] = now
    write_queue(queue_path, queue)
    print(json.dumps({'ok': True, 'event_id': args.event_id, 'queue_file': str(queue_path), 'acked_at': now}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
