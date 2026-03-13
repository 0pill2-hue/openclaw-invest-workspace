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

from lib.blocked_requeue import auto_requeue_blocked_tasks
from lib.runtime_env import TASKS_DB
from lib.task_runtime import is_nonterminal_wait_phase, normalize_phase_name

STALE_MINUTES = 30
EVIDENCE_REFORM_CUTOFF = datetime.strptime('2026-03-13 00:00:00', '%Y-%m-%d %H:%M:%S')
REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_CARD_PREFIX = 'runtime/tasks/evidence/cards/'


def parse_dt(v: str | None):
    v = (v or '').strip()
    if not v:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(v, fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(v)
    except Exception:
        return None


def extract_phase(note: str | None) -> str:
    text = (note or '').strip()
    for line in text.splitlines():
        if line.startswith('phase:'):
            return line.split(':', 1)[1].strip() or '-'
    return '-'


def parse_updated_at(value: str | None):
    v = (value or '').strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def is_raw_only_proof(text: str | None) -> bool:
    lower = (text or '').lower()
    if not lower.strip():
        return False
    has_raw = '/raw/' in lower or '/logs/' in lower or '/tmp/' in lower or 'stdout' in lower or 'stderr' in lower
    has_canonical = EVIDENCE_CARD_PREFIX in lower
    return has_raw and not has_canonical


def has_valid_evidence_card(proof: str | None) -> bool:
    text = (proof or '').strip()
    idx = text.find(EVIDENCE_CARD_PREFIX)
    if idx < 0:
        return False
    end = len(text)
    for sep in (' ', ',', ';', '#'):
        pos = text.find(sep, idx)
        if pos > idx:
            end = min(end, pos)
    rel = text[idx:end]
    path = REPO_ROOT / rel
    return path.exists()


def has_task_column(conn: sqlite3.Connection, column: str) -> bool:
    info = conn.execute('PRAGMA table_info(tasks)').fetchall()
    return any((row[1] if isinstance(row, tuple) else row['name']) == column for row in info)


def append_watchdog_note(note: str | None, *, reason: str, now: datetime, proof: str) -> str:
    text = (note or '').strip()
    entry = f"auto_recover: {reason} @ {now:%Y-%m-%d %H:%M:%S}\nwatchdog_proof: {proof}"
    if not text:
        return entry
    return f"{text}\n{entry}"


def main():
    if not TASKS_DB.exists():
        print(json.dumps({"ok": False, "changed": False, "reason": f"tasks db not found: {TASKS_DB}"}, ensure_ascii=False))
        return

    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    now = datetime.now()

    has_callback_token = has_task_column(conn, 'callback_token')
    has_callback_state = has_task_column(conn, 'callback_state')
    has_detached_at = has_task_column(conn, 'detached_at')
    has_heartbeat_at = has_task_column(conn, 'heartbeat_at')

    select_cols = [
        'id',
        'status',
        'started_at',
        'last_activity_at',
        'resume_due',
        'note',
        'blocked_reason',
    ]
    select_cols.append('callback_token' if has_callback_token else "'' AS callback_token")
    select_cols.append('callback_state' if has_callback_state else "'' AS callback_state")
    select_cols.append('detached_at' if has_detached_at else "'' AS detached_at")
    select_cols.append('heartbeat_at' if has_heartbeat_at else "'' AS heartbeat_at")
    rows = conn.execute(
        f"SELECT {', '.join(select_cols)} FROM tasks WHERE status IN ('IN_PROGRESS','BLOCKED')"
    ).fetchall()

    moved = []
    for row in rows:
        tid = row['id']
        status = (row['status'] or '').upper()
        started = parse_dt(row['started_at'])
        last_act = parse_dt(row['last_activity_at']) or started
        resume_due = parse_dt(row['resume_due'])
        phase = extract_phase(row['note'])
        normalized_phase = normalize_phase_name(phase)
        waiting_state = is_nonterminal_wait_phase(phase)

        callback_token = (row['callback_token'] or '').strip() if has_callback_token else ''
        callback_state = (row['callback_state'] or '').strip().lower() if has_callback_state else ''
        detached_at = parse_dt(row['detached_at']) if has_detached_at else None
        heartbeat_at = parse_dt(row['heartbeat_at']) if has_heartbeat_at else None

        reason = ''
        proof = ''

        if waiting_state and not resume_due:
            reason = 'watchdog_waiting_missing_resume_due'
            proof = f'phase={normalized_phase or "waiting"}; resume_due_missing=1'
        elif waiting_state and not callback_token:
            reason = 'watchdog_waiting_missing_callback_token'
            proof = f'phase={normalized_phase or "waiting"}; callback_token_missing=1'
        elif callback_state == 'detached':
            if not callback_token or not detached_at or not waiting_state:
                reason = 'watchdog_detached_invalid_metadata'
                proof = (
                    f'phase={normalized_phase or "-"}; waiting_state={int(waiting_state)}; '
                    f'callback_token_set={int(bool(callback_token))}; detached_at_set={int(bool(detached_at))}'
                )
        if not reason:
            hb_ref = heartbeat_at or last_act
            if (waiting_state or callback_state == 'detached') and hb_ref and now - hb_ref > timedelta(minutes=STALE_MINUTES):
                reason = f'watchdog_stale_heartbeat>{STALE_MINUTES}m'
                proof = (
                    f'phase={normalized_phase or "-"}; callback_state={callback_state or "-"}; '
                    f'heartbeat_ref={hb_ref:%Y-%m-%d %H:%M:%S}'
                )
            elif waiting_state and resume_due and now > resume_due:
                reason = f"watchdog_{normalized_phase or 'waiting'}_deadline_expired"
                proof = f'phase={normalized_phase or "waiting"}; resume_due={resume_due:%Y-%m-%d %H:%M:%S}'
            elif status == 'IN_PROGRESS' and not waiting_state and last_act and now - last_act > timedelta(minutes=STALE_MINUTES):
                reason = f'watchdog_stale_in_progress>{STALE_MINUTES}m'
                proof = f'last_activity_at={last_act:%Y-%m-%d %H:%M:%S}'
            elif status == 'BLOCKED' and resume_due and now > resume_due:
                reason = 'watchdog_resume_due_expired'
                proof = f'resume_due={resume_due:%Y-%m-%d %H:%M:%S}'

        if not reason:
            continue

        if status == 'BLOCKED' and (row['blocked_reason'] or '').strip() == reason:
            continue

        note = append_watchdog_note(row['note'], reason=reason, now=now, proof=proof or '미확인')
        update_sql = (
            """
            UPDATE tasks
            SET status='BLOCKED', bucket='backlog', blocked_reason=?, note=?, resume_due='',
                closed_by='watchdog', updated_at=?
            WHERE id=?
            """
            if not has_callback_state else
            """
            UPDATE tasks
            SET status='BLOCKED', bucket='backlog', blocked_reason=?, note=?, resume_due='',
                callback_state=CASE WHEN LOWER(COALESCE(callback_state,''))='detached' THEN 'failed' ELSE callback_state END,
                closed_by='watchdog', updated_at=?
            WHERE id=?
            """
        )
        with conn:
            conn.execute(update_sql, (reason, note, now.strftime('%Y-%m-%d %H:%M:%S'), tid))
        moved.append({"id": tid, "reason": reason, "proof": proof or '미확인'})

    try:
        with conn:
            requeued = auto_requeue_blocked_tasks(conn, now=now)
    except sqlite3.OperationalError as exc:
        requeued = []
        moved.append({"id": "watchdog", "reason": "auto_requeue_skipped", "proof": str(exc)})

    violations: list[dict[str, str]] = []
    closed_rows = conn.execute(
        "SELECT id, status, proof, updated_at FROM tasks WHERE status IN ('DONE', 'BLOCKED')"
    ).fetchall()
    for row in closed_rows:
        updated_at = parse_updated_at(row['updated_at'])
        if not updated_at or updated_at < EVIDENCE_REFORM_CUTOFF:
            continue
        if not has_valid_evidence_card(row['proof']):
            violations.append({"id": row['id'], "status": row['status'], "reason": "evidence_card_missing"})
        elif is_raw_only_proof(row['proof']):
            violations.append({"id": row['id'], "status": row['status'], "reason": "raw_only_closure"})

    print(
        json.dumps(
            {
                "ok": True,
                "changed": bool(moved or requeued),
                "moved": moved,
                "requeued": requeued,
                "violations": violations,
                "db": str(TASKS_DB),
            },
            ensure_ascii=False,
        )
    )


if __name__ == '__main__':
    main()
