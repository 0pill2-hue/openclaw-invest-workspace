#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.runtime_env import ROOT, TASKS_DB

TASK_DOC_DIR = ROOT / 'runtime' / 'tasks'
TASKS_DB_CLI = ROOT / 'scripts' / 'tasks' / 'db.py'
KST = timezone(timedelta(hours=9))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def kst_now_label() -> str:
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')


def one_line(text: str, limit: int = 240) -> str:
    compact = ' '.join((text or '').split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + '...'


def task_row(task_id: str) -> sqlite3.Row | None:
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute('SELECT id, status, title FROM tasks WHERE id=?', (task_id,)).fetchone()
    finally:
        conn.close()


def ensure_task_doc(path: Path, task_id: str, status: str, title: str) -> None:
    if path.exists():
        return
    lines = [
        f'# {task_id}',
        '',
        f'- ticket: {task_id}',
        f'- status: {status or "미확인"}',
        f'- title: {title or "미확인"}',
        f'- created_by: auto task event bridge',
        f'- created_at: {kst_now_label()}',
        '',
        '## Auto updates',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def append_event_block(path: Path, *, event_id: str, source: str, summary: str, phase: str, details: list[str], proof_paths: list[str]) -> bool:
    existing = path.read_text(encoding='utf-8') if path.exists() else ''
    marker = f'<!-- task_event_id: {event_id} -->'
    if event_id and marker in existing:
        return False

    parts: list[str] = []
    if '## Auto updates' not in existing:
        if existing and not existing.endswith('\n'):
            existing += '\n'
        existing += '\n## Auto updates\n'

    parts.append(f'### {kst_now_label()} | {source}')
    if event_id:
        parts.append(marker)
    parts.append(f'- summary: {summary}')
    if phase:
        parts.append(f'- phase: {phase}')
    for detail in details:
        if detail.strip():
            parts.append(f'- detail: {detail.strip()}')
    if proof_paths:
        parts.append('- proof:')
        for proof in proof_paths:
            parts.append(f'  - `{proof}`')
    block = '\n'.join(parts) + '\n'

    text = existing
    if text and not text.endswith('\n'):
        text += '\n'
    text += '\n' + block
    path.write_text(text, encoding='utf-8')
    return True


def run_db_cli(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(TASKS_DB_CLI), *args]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)


def update_task_runtime(task_id: str, *, phase: str, source: str, summary: str) -> dict:
    if phase:
        note = f'auto_event: {source} | {one_line(summary, limit=180)}'
        proc = run_db_cli('mark-phase', '--id', task_id, '--phase', phase, '--note', note)
    else:
        proc = run_db_cli('touch', '--id', task_id)
    return {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'stdout': (proc.stdout or '').strip(),
        'stderr': (proc.stderr or '').strip(),
    }


def release_task_assignment(task_id: str) -> dict:
    proc = run_db_cli('release', '--id', task_id)
    return {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'stdout': (proc.stdout or '').strip(),
        'stderr': (proc.stderr or '').strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Append an event note/proof to a mapped task and touch its runtime state.')
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--summary', required=True)
    ap.add_argument('--event-id', default='')
    ap.add_argument('--phase', default='')
    ap.add_argument('--detail', action='append', default=[])
    ap.add_argument('--proof-path', action='append', default=[])
    ap.add_argument('--allow-missing-task', action='store_true')
    ap.add_argument('--release-assignee', action='store_true', help='Clear assignee/run metadata after recording the event (use for detached background waits).')
    args = ap.parse_args()

    row = task_row(args.task_id)
    if row is None and not args.allow_missing_task:
        print(json.dumps({'ok': False, 'error': 'task_not_found', 'task_id': args.task_id}, ensure_ascii=False, indent=2))
        return 1

    status = row['status'] if row else '미확인'
    title = row['title'] if row else '미확인'
    doc_path = TASK_DOC_DIR / f'{args.task_id}.md'
    ensure_task_doc(doc_path, args.task_id, status, title)
    appended = append_event_block(
        doc_path,
        event_id=(args.event_id or '').strip(),
        source=one_line(args.source, limit=80) or 'event',
        summary=one_line(args.summary, limit=300) or '-',
        phase=(args.phase or '').strip(),
        details=[one_line(item, limit=400) for item in (args.detail or []) if item.strip()],
        proof_paths=[item.strip() for item in (args.proof_path or []) if item.strip()],
    )

    runtime_update = {'ok': True, 'skipped': True}
    release_update = {'ok': True, 'skipped': True}
    if row is not None:
        runtime_update = update_task_runtime(
            args.task_id,
            phase=(args.phase or '').strip(),
            source=args.source,
            summary=args.summary,
        )
        if not runtime_update.get('ok'):
            print(json.dumps({
                'ok': False,
                'error': 'task_runtime_update_failed',
                'task_id': args.task_id,
                'doc_path': str(doc_path),
                'appended': appended,
                'runtime_update': runtime_update,
            }, ensure_ascii=False, indent=2))
            return 2
        if args.release_assignee:
            release_update = release_task_assignment(args.task_id)
            if not release_update.get('ok'):
                print(json.dumps({
                    'ok': False,
                    'error': 'task_release_failed',
                    'task_id': args.task_id,
                    'doc_path': str(doc_path),
                    'appended': appended,
                    'runtime_update': runtime_update,
                    'release_update': release_update,
                }, ensure_ascii=False, indent=2))
                return 3

    print(json.dumps({
        'ok': True,
        'task_id': args.task_id,
        'doc_path': str(doc_path),
        'event_id': (args.event_id or '').strip(),
        'appended': appended,
        'runtime_update': runtime_update,
        'release_update': release_update,
        'recorded_at': utc_now_iso(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
