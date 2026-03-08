#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.runtime_env import TASKS_DB

STALE_MINUTES = 30


def parse_dt(v: str | None):
    v = (v or '').strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def extract_phase(note: str | None) -> str:
    text = (note or '').strip()
    for line in text.splitlines():
        if line.startswith('phase:'):
            return line.split(':', 1)[1].strip() or '-'
    return '-'


def main():
    if not TASKS_DB.exists():
        print(json.dumps({"ok": False, "changed": False, "reason": f"tasks db not found: {TASKS_DB}"}, ensure_ascii=False))
        return

    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    now = datetime.now()
    rows = conn.execute(
        "SELECT id, status, started_at, last_activity_at, resume_due, note, blocked_reason FROM tasks WHERE status IN ('IN_PROGRESS','BLOCKED')"
    ).fetchall()

    moved = []
    for row in rows:
        tid = row['id']
        status = (row['status'] or '').upper()
        started = parse_dt(row['started_at'])
        last_act = parse_dt(row['last_activity_at']) or started
        resume_due = parse_dt(row['resume_due'])
        phase = extract_phase(row['note'])
        reason = ''
        if status == 'IN_PROGRESS' and phase in {'subagent_running', 'awaiting_callback'} and resume_due and now > resume_due:
            reason = f'watchdog_{phase}_deadline_expired'
        elif status == 'IN_PROGRESS' and last_act and now - last_act > timedelta(minutes=STALE_MINUTES):
            reason = f'watchdog_stale_in_progress>{STALE_MINUTES}m'
        elif status == 'BLOCKED' and resume_due and now > resume_due:
            reason = 'watchdog_resume_due_expired'
        if not reason:
            continue
        note = (row['note'] or '').strip()
        note = (note + '\n' if note else '') + f'auto_recover: {reason} @ {now:%Y-%m-%d %H:%M:%S}'
        if status == 'BLOCKED' and (row['blocked_reason'] or '').strip() == reason:
            continue
        with conn:
            conn.execute(
                """
                UPDATE tasks
                SET status='BLOCKED', bucket='backlog', blocked_reason=?, note=?, resume_due='', updated_at=?
                WHERE id=?
                """,
                (reason, note, now.strftime('%Y-%m-%d %H:%M:%S'), tid),
            )
        moved.append({"id": tid, "reason": reason})

    print(json.dumps({"ok": True, "changed": bool(moved), "moved": moved, "db": str(TASKS_DB)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
