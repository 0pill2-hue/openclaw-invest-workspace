from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from typing import Any

from lib.task_runtime import is_nonterminal_wait_phase

WATCHDOG_RETRY_SNIPPETS = (
    'watchdog_',
    'stale_in_progress',
    'resume_due_expired',
    'deadline_expired',
)
DEFER_KEYWORDS = (
    'deferred_by_owner_priority',
    'owner_priority',
    'deferred',
)
PREREQ_KEYWORDS = (
    'prereq_not_met',
    'prereq',
    'dependency',
    'depends_on',
    'blocked_by',
)
TEMPORAL_KEYWORDS = (
    'window',
    'until',
    'after',
    'deadline',
)
SYSTEM_GAP_KEYWORDS = (
    'not yet implemented',
    'not yet effective',
    'remains idle',
)
TICKET_REF_RE = re.compile(r'\b(?:JB|WD)-\d{8}-[A-Z0-9][A-Z0-9-]*\b')
FULL_DT_RE = re.compile(r'(?<!\d)\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?!\d)')
TIME_ONLY_RE = re.compile(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?!\d)')


def now_ts() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def parse_task_dt(value: str | None) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def extract_phase(note: str | None) -> str:
    text = str(note or '').strip()
    for line in text.splitlines():
        if line.startswith('phase:'):
            return line.split(':', 1)[1].strip()
    return ''


def extract_ticket_refs(text: str | None) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for token in TICKET_REF_RE.findall(str(text or '').upper()):
        if token not in seen:
            seen.add(token)
            refs.append(token)
    return refs


def referenced_ticket_statuses(conn: sqlite3.Connection, refs: list[str]) -> dict[str, str]:
    if not refs:
        return {}
    placeholders = ','.join(['?'] * len(refs))
    rows = conn.execute(
        f"SELECT id, status FROM tasks WHERE id IN ({placeholders})",
        refs,
    ).fetchall()
    statuses = {str(row['id']).strip(): str(row['status'] or '').upper() for row in rows}
    for ref in refs:
        statuses.setdefault(ref, '')
    return statuses


def infer_temporal_due(row: sqlite3.Row) -> datetime | None:
    reason = str(row['blocked_reason'] or '').strip()
    lowered = reason.lower()
    if not any(keyword in lowered for keyword in TEMPORAL_KEYWORDS):
        return None

    full_matches = [parse_task_dt(match.group(0)) for match in FULL_DT_RE.finditer(reason)]
    full_matches = [match for match in full_matches if match is not None]
    if full_matches:
        return max(full_matches)

    time_matches = list(TIME_ONLY_RE.finditer(reason))
    if not time_matches:
        return None
    anchor = parse_task_dt(row['updated_at'] if 'updated_at' in row.keys() else '')
    if anchor is None:
        anchor = parse_task_dt(row['created_at'] if 'created_at' in row.keys() else '')
    if anchor is None:
        return None
    due_candidates: list[datetime] = []
    for match in time_matches:
        hour = int(match.group(1))
        minute = int(match.group(2))
        second = int(match.group(3) or '0')
        due_candidates.append(anchor.replace(hour=hour, minute=minute, second=second, microsecond=0))
    return max(due_candidates) if due_candidates else None


def build_resumed_note(note: str | None, auto_note: str) -> str:
    existing = [
        line for line in str(note or '').splitlines()
        if not line.startswith('phase:') and not line.startswith('child_session:')
    ]
    lines = ['phase: main_resume', auto_note]
    lines.extend(line for line in existing if line.strip())
    return '\n'.join(lines)


def classify_blocked_row(conn: sqlite3.Connection, row: sqlite3.Row, now: datetime) -> tuple[str, str] | None:
    ticket_id = str(row['id'] or '').strip()
    if not ticket_id or ticket_id.startswith('WD-'):
        return None

    note = str(row['note'] or '')
    phase = extract_phase(note)
    if is_nonterminal_wait_phase(phase):
        return None

    reason = str(row['blocked_reason'] or '').strip()
    lowered = reason.lower()
    if not reason:
        return None

    if any(snippet in lowered for snippet in WATCHDOG_RETRY_SNIPPETS):
        return 'retryable_blocker', 'watchdog_or_timeout_blocker'
    if any(keyword in lowered for keyword in SYSTEM_GAP_KEYWORDS):
        return 'retryable_blocker', 'system_gap_fixed_by_runtime'

    refs = [ref for ref in extract_ticket_refs(reason) if ref != ticket_id]
    statuses = referenced_ticket_statuses(conn, refs)
    if refs and any(keyword in lowered for keyword in DEFER_KEYWORDS):
        if all(statuses.get(ref, '') != 'IN_PROGRESS' for ref in refs):
            detail = ','.join(f'{ref}={statuses.get(ref, "") or "missing"}' for ref in refs)
            return 'priority_cleared', f'deferred_refs_inactive:{detail}'

    if refs and any(keyword in lowered for keyword in PREREQ_KEYWORDS):
        if all(statuses.get(ref, '') == 'DONE' for ref in refs):
            detail = ','.join(f'{ref}=DONE' for ref in refs)
            return 'prereq_cleared', f'prereq_refs_done:{detail}'

    temporal_due = infer_temporal_due(row)
    if temporal_due is not None and now >= temporal_due:
        return 'temporal_hold_elapsed', f'temporal_hold_elapsed:{temporal_due.strftime("%Y-%m-%d %H:%M:%S")}'

    return None


def auto_requeue_blocked_tasks(conn: sqlite3.Connection, *, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    now_text = now.strftime('%Y-%m-%d %H:%M:%S')
    rows = conn.execute(
        """
        SELECT id, note, blocked_reason, created_at, updated_at
        FROM tasks
        WHERE status='BLOCKED'
        ORDER BY CASE UPPER(priority) WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                 datetime(updated_at) DESC,
                 id
        """
    ).fetchall()

    moved: list[dict[str, Any]] = []
    for row in rows:
        verdict = classify_blocked_row(conn, row, now)
        if verdict is None:
            continue
        category, detail = verdict
        previous_reason = str(row['blocked_reason'] or '').strip()
        auto_note = f'auto_requeue: {category} ({detail}) @ {now_text}'
        note = build_resumed_note(row['note'], auto_note)
        conn.execute(
            """
            UPDATE tasks
            SET status='TODO',
                bucket='active',
                note=?,
                blocked_reason='',
                assigned_by='',
                assignee='',
                assigned_run_id='',
                assigned_at='',
                review_status='',
                review_note='',
                closed_by='',
                resume_due='',
                last_activity_at=?,
                updated_at=?
            WHERE id=? AND status='BLOCKED'
            """,
            (note, now_text, now_text, row['id']),
        )
        moved.append(
            {
                'id': str(row['id']),
                'category': category,
                'detail': detail,
                'previous_reason': previous_reason,
            }
        )
    return moved
