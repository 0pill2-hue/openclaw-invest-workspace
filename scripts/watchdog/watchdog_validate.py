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

NOW = datetime.now()
STALE_MINUTES = 30


def parse_dt(v: str | None):
    v = (v or '').strip()
    if not v or v in {'-', 'none', 'None', 'N/A'}:
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


issues: list[str] = []
if not TASKS_DB.exists():
    issues.append(f'tasks db not found: {TASKS_DB}')
else:
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, status, started_at, last_activity_at, resume_due, review_status, note FROM tasks"
    ).fetchall()
    for row in rows:
        tid = row['id']
        status = (row['status'] or '').upper()
        review_status = (row['review_status'] or '').upper()
        if status == 'IN_PROGRESS':
            started = parse_dt(row['started_at'])
            last_act = parse_dt(row['last_activity_at']) or started
            resume_due = parse_dt(row['resume_due'])
            phase = extract_phase(row['note'])
            if started is None:
                issues.append(f'IN_PROGRESS started_at 누락: {tid}')
            if last_act is None:
                issues.append(f'IN_PROGRESS last_activity_at 누락: {tid}')
            elif NOW - last_act > timedelta(minutes=STALE_MINUTES):
                issues.append(f'IN_PROGRESS 무활동 {STALE_MINUTES}분 초과: {tid}')
            if phase in {'subagent_running', 'awaiting_callback'} and resume_due and NOW > resume_due:
                issues.append(f'{phase} callback deadline 초과: {tid}')
        if status == 'BLOCKED':
            resume_due = parse_dt(row['resume_due'])
            if resume_due and NOW > resume_due:
                issues.append(f'BLOCKED resume_due 초과: {tid}')
        if review_status == 'REJECTED':
            issues.append(f'review_status=REJECTED: {tid}')

result = {
    'ok': len(issues) == 0,
    'issues': issues,
    'checked_at': NOW.strftime('%Y-%m-%d %H:%M:%S'),
    'stale_minutes': STALE_MINUTES,
    'db': str(TASKS_DB),
}
print(json.dumps(result, ensure_ascii=False))
