#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
TASKS_DB_PATH = WORKSPACE / 'runtime' / 'tasks' / 'tasks.db'
TASKS_DB_CLI = WORKSPACE / 'scripts' / 'tasks' / 'db.py'
TASK_EVENT_CLI = WORKSPACE / 'scripts' / 'tasks' / 'record_task_event.py'
RUNTIME_TASKS_DIR = WORKSPACE / 'runtime' / 'tasks'
PROOF_DIR = RUNTIME_TASKS_DIR / 'proofs' / 'watch-events'
TASK_ID_PATTERN = re.compile(r'\b(?:JB-\d{8}-[A-Z0-9-]+|WD-[A-Z0-9-]+)\b', re.I)
SPLIT_PROOF_PATTERN = re.compile(r'[\n,]+')


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def now_local_ts() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def connect_tasks_db() -> sqlite3.Connection:
    TASKS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TASKS_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def load_queue(path: Path) -> dict[str, Any]:
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


def write_queue(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_iso(value: str) -> datetime | None:
    text = (value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def sanitize_token(value: str, *, limit: int = 48) -> str:
    token = re.sub(r'[^A-Za-z0-9]+', '-', (value or '').strip()).strip('-')
    return token[:limit] or 'EVENT'


def compact_text(value: Any, *, limit: int = 200) -> str:
    text = ' '.join(str(value or '').split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + '...'


def task_exists(conn: sqlite3.Connection, task_id: str) -> bool:
    row = conn.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone()
    return row is not None


def extract_phase(note: str | None) -> str:
    text = (note or '').strip()
    for line in text.splitlines():
        if line.startswith('phase:'):
            return line.split(':', 1)[1].strip().lower()
    return ''


def is_nonterminal_wait_phase(phase: str | None) -> bool:
    normalized = str(phase or '').strip().lower().replace('-', '_').replace(' ', '_')
    if not normalized:
        return False
    if normalized in {
        'awaiting_callback',
        'awaiting_result',
        'delegated',
        'delegated_to_subagent',
        'long_running_active_execution',
        'long_running_execution',
        'subagent',
        'subagent_launched',
        'subagent_running',
        'waiting_child_completion',
        'waiting_subagent',
        'waiting_writer_and_subagent',
    }:
        return True
    if 'subagent' in normalized:
        return True
    if normalized.startswith('awaiting_') or normalized.startswith('delegated_to_'):
        return True
    return False


def task_resume_phase(task_id: str) -> str:
    with connect_tasks_db() as conn:
        row = conn.execute('SELECT status, note FROM tasks WHERE id=?', (task_id,)).fetchone()
    if row is None:
        return ''
    status = str(row['status'] or '').strip().upper()
    if status not in {'TODO', 'IN_PROGRESS', 'BLOCKED'}:
        return ''
    current_phase = extract_phase(row['note'] or '')
    return 'main_resume' if is_nonterminal_wait_phase(current_phase) else ''


def unique_proof_csv(existing: str, new_path: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for raw in SPLIT_PROOF_PATTERN.split(existing or ''):
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        parts.append(item)
    if new_path and new_path not in seen:
        parts.append(new_path)
    return ','.join(parts)


def append_note_line(existing_note: str, line: str, *, event_id: str) -> str:
    stripped = (existing_note or '').rstrip()
    if event_id and event_id in stripped:
        return stripped
    if not stripped:
        return line
    return stripped + '\n' + line


def stable_new_task_id(event: dict[str, Any]) -> str:
    observed = parse_iso(str(event.get('observed_at') or '')) or datetime.now(timezone.utc)
    ymd = observed.astimezone(timezone.utc).strftime('%Y%m%d')
    suffix = sanitize_token(str(event.get('id') or ''), limit=28).upper()
    return f'JB-{ymd}-WATCH-EVENT-{suffix}'


def build_new_task_id(conn: sqlite3.Connection, event: dict[str, Any]) -> str:
    base = stable_new_task_id(event)
    if not task_exists(conn, base):
        return base
    return base


def build_status_note(*, event: dict[str, Any], proof_path: str, matched_by: str, action: str) -> str:
    verdict = str(event.get('verdict') or '-').strip() or '-'
    status = str(event.get('status') or '-').strip() or '-'
    event_id = str(event.get('id') or '-')
    source = str(event.get('source') or '-')
    return (
        f"watch_event: {utc_now_iso()} | action={action} | event_id={event_id} | "
        f"source={source} | status={status} | verdict={verdict} | matched_by={matched_by} | proof={proof_path}"
    )


def proof_target_path(task_id: str, event: dict[str, Any], *, create_task_file: bool) -> Path:
    if create_task_file:
        return RUNTIME_TASKS_DIR / f'{task_id}.md'
    suffix = sanitize_token(str(event.get('id') or ''), limit=64)
    return PROOF_DIR / f'{task_id}--{suffix}.md'


def write_proof(path: Path, *, task_id: str, event: dict[str, Any], matched_by: str, action: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'# {task_id}',
        '',
        '## Watch event sync',
        f"- synced_at: {utc_now_iso()}",
        f"- action: {action}",
        f"- matched_by: {matched_by}",
        f"- event_id: {event.get('id', '')}",
        f"- source: {event.get('source', '')}",
        f"- observed_at: {event.get('observed_at', '')}",
        f"- status: {event.get('status', '')}",
        f"- verdict: {event.get('verdict', '')}",
        f"- title: {event.get('title', '')}",
        f"- url: {event.get('url', '')}",
        f"- result_json_path: {event.get('result_json_path', '')}",
        f"- follow_up_required: {bool(event.get('follow_up_required', False))}",
        '',
        '## Note',
        '- Watcher completion was synced into task tracking automatically.',
    ]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def extract_candidate_task_ids(*, event: dict[str, Any], result: dict[str, Any] | None = None, explicit_task_id: str = '') -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def push(raw: str, source: str) -> None:
        task_id = (raw or '').strip().upper()
        if not task_id or task_id in seen:
            return
        seen.add(task_id)
        candidates.append((task_id, source))

    explicit = (explicit_task_id or '').strip().upper()
    if explicit:
        push(explicit, 'explicit_task_id')

    event_task_id = str(event.get('task_id') or '').strip().upper()
    if event_task_id:
        push(event_task_id, 'event.task_id')

    texts: list[tuple[str, str]] = [
        (str(event.get('id') or ''), 'event.id'),
        (str(event.get('result_json_path') or ''), 'event.result_json_path'),
        (str(event.get('title') or ''), 'event.title'),
        (str(event.get('url') or ''), 'event.url'),
    ]
    if result:
        try:
            texts.append((json.dumps(result, ensure_ascii=False), 'result.json'))
        except Exception:
            pass
    else:
        result_json_path = Path(str(event.get('result_json_path') or '').strip())
        if result_json_path.exists():
            try:
                texts.append((result_json_path.read_text(encoding='utf-8'), 'result_json_path.file'))
            except Exception:
                pass

    for text, source in texts:
        for match in TASK_ID_PATTERN.finditer((text or '').upper()):
            push(match.group(0), source)

    return candidates


def resolve_existing_task(*, event: dict[str, Any], result: dict[str, Any] | None = None, explicit_task_id: str = '') -> tuple[str | None, str | None]:
    with connect_tasks_db() as conn:
        for candidate, source in extract_candidate_task_ids(event=event, result=result, explicit_task_id=explicit_task_id):
            if task_exists(conn, candidate):
                return candidate, source
    return None, None


def add_and_start_task(task_id: str, *, title: str, scope: str, priority: str = 'P1') -> None:
    add_cmd = [
        sys.executable,
        str(TASKS_DB_CLI),
        'add',
        '--id', task_id,
        '--status', 'TODO',
        '--title', title,
        '--scope', scope,
        '--priority', priority,
        '--bucket', 'active',
        '--assigned-by', 'watcher',
        '--owner', 'owner',
    ]
    start_cmd = [sys.executable, str(TASKS_DB_CLI), 'start', '--id', task_id]
    subprocess.run(add_cmd, cwd=str(WORKSPACE), check=True, capture_output=True, text=True)
    subprocess.run(start_cmd, cwd=str(WORKSPACE), check=True, capture_output=True, text=True)


def record_task_event(task_id: str, *, event: dict[str, Any], proof_path: str, summary: str, matched_by: str, phase: str = '', dry_run: bool = False) -> dict[str, Any]:
    payload = {
        'ok': True,
        'skipped': bool(dry_run),
        'stdout': '',
        'stderr': '',
    }
    if dry_run:
        return payload
    cmd = [
        sys.executable,
        str(TASK_EVENT_CLI),
        '--task-id', task_id,
        '--source', 'watcher',
        '--summary', summary,
        '--event-id', str(event.get('id') or ''),
        '--detail', f"status={event.get('status') or '-'} verdict={event.get('verdict') or '-'} matched_by={matched_by}",
        '--detail', f"url={event.get('url') or ''}",
        '--proof-path', proof_path,
    ]
    if phase:
        cmd.extend(['--phase', phase])
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True)
    payload.update({
        'ok': proc.returncode == 0,
        'stdout': (proc.stdout or '').strip(),
        'stderr': (proc.stderr or '').strip(),
        'returncode': proc.returncode,
    })
    return payload


def update_existing_task(task_id: str, *, event: dict[str, Any], matched_by: str, dry_run: bool = False) -> dict[str, Any]:
    proof_path = proof_target_path(task_id, event, create_task_file=False)
    note_line = build_status_note(event=event, proof_path=str(proof_path), matched_by=matched_by, action='updated_existing')
    phase = task_resume_phase(task_id)
    task_event = {
        'ok': True,
        'skipped': bool(dry_run),
    }
    if not dry_run:
        write_proof(proof_path, task_id=task_id, event=event, matched_by=matched_by, action='updated_existing')
        with connect_tasks_db() as conn:
            row = conn.execute('SELECT note, proof FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise RuntimeError(f'task_not_found:{task_id}')
            note = append_note_line(row['note'] or '', note_line, event_id=str(event.get('id') or ''))
            proof = unique_proof_csv(row['proof'] or '', str(proof_path))
            now = now_local_ts()
            conn.execute(
                'UPDATE tasks SET note=?, proof=?, last_activity_at=?, updated_at=? WHERE id=?',
                (note, proof, now, now, task_id),
            )
            conn.commit()
        summary = compact_text(
            f"watcher synced completion status={event.get('status') or '-'} verdict={event.get('verdict') or '-'}",
            limit=180,
        )
        task_event = record_task_event(
            task_id,
            event=event,
            proof_path=str(proof_path),
            summary=summary,
            matched_by=matched_by,
            phase=phase,
            dry_run=False,
        )
    return {
        'action': 'updated_existing',
        'task_id': task_id,
        'proof_path': str(proof_path),
        'matched_by': matched_by,
        'note_line': note_line,
        'resume_phase': phase if not dry_run else task_resume_phase(task_id),
        'task_event': task_event,
        'dry_run': bool(dry_run),
    }


def create_new_task(*, event: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    with connect_tasks_db() as conn:
        task_id = build_new_task_id(conn, event)
    proof_path = proof_target_path(task_id, event, create_task_file=True)
    title_hint = compact_text(event.get('title') or event.get('id') or 'watcher completion', limit=80)
    title = f'watcher completion follow-up: {title_hint}'
    scope = compact_text(
        f"source={event.get('source', '')} status={event.get('status', '')} verdict={event.get('verdict', '-') or '-'} url={event.get('url', '')}",
        limit=220,
    )
    note_line = build_status_note(event=event, proof_path=str(proof_path), matched_by='new_task_fallback', action='created_new')
    if not dry_run:
        write_proof(proof_path, task_id=task_id, event=event, matched_by='new_task_fallback', action='created_new')
        add_and_start_task(task_id, title=title, scope=scope, priority='P1')
        with connect_tasks_db() as conn:
            row = conn.execute('SELECT note, proof FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise RuntimeError(f'task_not_found_after_create:{task_id}')
            note = append_note_line(row['note'] or '', note_line, event_id=str(event.get('id') or ''))
            proof = unique_proof_csv(row['proof'] or '', str(proof_path))
            now = now_local_ts()
            conn.execute(
                'UPDATE tasks SET note=?, proof=?, last_activity_at=?, updated_at=? WHERE id=?',
                (note, proof, now, now, task_id),
            )
            conn.commit()
    return {
        'action': 'created_new',
        'task_id': task_id,
        'proof_path': str(proof_path),
        'matched_by': 'new_task_fallback',
        'note_line': note_line,
        'dry_run': bool(dry_run),
    }


def sync_event_to_task(
    event: dict[str, Any],
    *,
    result: dict[str, Any] | None = None,
    explicit_task_id: str = '',
    allow_create: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    mapped_task_id, matched_by = resolve_existing_task(event=event, result=result, explicit_task_id=explicit_task_id)
    if mapped_task_id:
        sync = update_existing_task(mapped_task_id, event=event, matched_by=matched_by or 'existing_task', dry_run=dry_run)
    elif allow_create:
        sync = create_new_task(event=event, dry_run=dry_run)
    else:
        sync = {
            'action': 'pending_unmapped',
            'task_id': '',
            'proof_path': '',
            'matched_by': 'none',
            'note_line': '',
            'dry_run': bool(dry_run),
        }
    sync['synced_at'] = utc_now_iso()
    return sync


def sync_queue_event(
    *,
    queue_file: Path,
    event_id: str,
    explicit_task_id: str = '',
    allow_create: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    queue = load_queue(queue_file)
    target = None
    for item in queue.get('events', []):
        if str(item.get('id') or '') == event_id:
            target = item
            break
    if target is None:
        raise SystemExit(f'event_not_found:{event_id}')

    sync = sync_event_to_task(
        target,
        explicit_task_id=explicit_task_id,
        allow_create=allow_create,
        dry_run=dry_run,
    )
    if not dry_run:
        target['task_sync_status'] = sync['action']
        target['task_sync_at'] = sync['synced_at']
        target['task_sync_match'] = sync['matched_by']
        if sync.get('task_id'):
            target['task_id'] = sync['task_id']
        if sync.get('proof_path'):
            target['proof_path'] = sync['proof_path']
        queue['updated_at'] = utc_now_iso()
        write_queue(queue_file, queue)
    return {
        'ok': True,
        'queue_file': str(queue_file),
        'event_id': event_id,
        'sync': sync,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Sync a queued watch event into task tracking.')
    ap.add_argument('--queue-file', required=True)
    ap.add_argument('--event-id', required=True)
    ap.add_argument('--task-id', default='')
    ap.add_argument('--allow-create', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    payload = sync_queue_event(
        queue_file=Path(args.queue_file),
        event_id=args.event_id,
        explicit_task_id=args.task_id,
        allow_create=args.allow_create,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
