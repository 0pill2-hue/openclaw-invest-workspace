#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.runtime_env import (
    DIRECTIVES_DB,
    TASKS_DB,
    agents_path,
    context_handoff_path,
    current_task_path,
    directives_md_path,
    memory_path,
    repo_root,
    soul_path,
    tasks_md_path,
    user_path,
)
from lib.task_runtime import is_nonterminal_wait_phase

ROOT = repo_root()
CURRENT_TASK = current_task_path()
CONTEXT_HANDOFF = context_handoff_path()
FILES = {
    'soul': soul_path(),
    'user': user_path(),
    'agents': agents_path(),
    'tasks': tasks_md_path(),
    'directives': directives_md_path(),
    'memory': memory_path(),
    'current_task': CURRENT_TASK,
    'context_handoff': CONTEXT_HANDOFF,
}
PLACEHOLDER_VALUES = {'', '미정', '미확인', '-', '정책 적용 전용 초기 상태'}
REQUIRED_CURRENT_TASK_KEYS = [
    'ticket_id',
    'directive_ids',
    'current_goal',
    'last_completed_step',
    'next_action',
    'touched_paths',
    'latest_proof',
]
REQUIRED_CONTEXT_HANDOFF_KEYS = [
    'source_ticket_id',
    'source_directive_ids',
    'business_goal',
    'last_completed_step',
    'next_action',
    'latest_proof',
    'touched_paths',
    'required_action',
    'reset_guard',
]


def now_ts() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def db_connect(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def parse_key_value_doc(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r'^-\s+([a-zA-Z0-9_]+):\s*(.*)$', line.strip())
        if m:
            data[m.group(1)] = m.group(2)
    return data


def parse_current_task(text: str) -> dict[str, str]:
    return parse_key_value_doc(text)


def parse_context_handoff(text: str) -> dict[str, str]:
    return parse_key_value_doc(text)


def _clean(value: str) -> str:
    text = (value or '').strip()
    return text if text else '미정'


def extract_note_value(note: str | None, key: str) -> str:
    prefix = f'{key}:'
    text = (note or '').strip()
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(':', 1)[1].strip()
    return ''


def extract_phase(note: str | None) -> str:
    phase = extract_note_value(note, 'phase')
    return phase if phase else '-'


def format_task_runtime_state(row: sqlite3.Row) -> str:
    parts: list[str] = []
    assigned_by = (row['assigned_by'] or '').strip() if 'assigned_by' in row.keys() else ''
    owner = (row['owner'] or '').strip() if 'owner' in row.keys() else ''
    assignee = (row['assignee'] or '').strip() if 'assignee' in row.keys() else ''
    phase = extract_phase(row['note'] if 'note' in row.keys() else '')
    review_status = (row['review_status'] or '').strip() if 'review_status' in row.keys() else ''
    closed_by = (row['closed_by'] or '').strip() if 'closed_by' in row.keys() else ''
    resume_due = (row['resume_due'] or '').strip() if 'resume_due' in row.keys() else ''
    child_session = extract_note_value(row['note'] if 'note' in row.keys() else '', 'child_session')

    if assigned_by:
        parts.append(f'assigned_by={assigned_by}')
    if owner:
        parts.append(f'owner={owner}')
    if assignee:
        parts.append(f'assignee={assignee}')
    if phase != '-':
        parts.append(f'phase={phase}')
        if is_nonterminal_wait_phase(phase):
            parts.append('wait_state=nonterminal')
    if review_status:
        parts.append(f'review={review_status}')
    if closed_by:
        parts.append(f'closed_by={closed_by}')
    if child_session:
        parts.append(f'child={child_session}')
    if resume_due:
        parts.append(f'resume_due={resume_due}')
    return ' | '.join(parts) if parts else '-'


def load_task_state(ticket_id: str) -> dict[str, str]:
    ticket_id = (ticket_id or '').strip()
    if not ticket_id or ticket_id in PLACEHOLDER_VALUES:
        return {}
    conn = db_connect(TASKS_DB)
    if conn is None:
        return {}
    try:
        row = conn.execute(
            """
            SELECT id, status, bucket, note, blocked_reason, assigned_by, owner, assignee, assigned_run_id, review_status, resume_due, closed_by
            FROM tasks
            WHERE id=?
            """,
            (ticket_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {}
    phase = extract_phase(row['note'])
    return {
        'task_status': row['status'] or '미정',
        'task_bucket': row['bucket'] or '미정',
        'task_phase': phase if phase != '-' else '미정',
        'task_assigned_by': (row['assigned_by'] or '').strip() or '미정',
        'task_owner': (row['owner'] or '').strip() or '미정',
        'task_assignee': (row['assignee'] or '').strip() or '미정',
        'task_review_status': (row['review_status'] or '').strip() or '미정',
        'task_closed_by': (row['closed_by'] or '').strip() or '미정',
        'task_resume_due': (row['resume_due'] or '').strip() or '미정',
        'task_runtime_state': format_task_runtime_state(row),
        'task_blocked_reason': (row['blocked_reason'] or '').strip() or '미정',
        'task_assigned_run_id': (row['assigned_run_id'] or '').strip() or '미정',
    }


def merged_task_state(ticket_id: str, task_state_override: dict[str, str] | None = None) -> dict[str, str]:
    task_state = load_task_state(ticket_id)
    if task_state_override:
        for key, value in task_state_override.items():
            task_state[key] = value
    return task_state


def atomic_write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
            handle.write(content)
            tmp_path = Path(handle.name)
        tmp_path.replace(path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def render_current_task_content(
    *,
    ticket_id: str,
    directive_ids: str,
    goal: str,
    last: str,
    next_action: str,
    touched_paths: str,
    latest_proof: str,
    paths: str,
    notes: str,
    task_state_override: dict[str, str] | None = None,
) -> str:
    task_state = merged_task_state(ticket_id, task_state_override)
    return (
        '# current-task\n\n'
        f'- ticket_id: {_clean(ticket_id)}\n'
        f'- directive_ids: {_clean(directive_ids)}\n'
        f"- task_status: {_clean(task_state.get('task_status', ''))}\n"
        f"- task_bucket: {_clean(task_state.get('task_bucket', ''))}\n"
        f"- task_phase: {_clean(task_state.get('task_phase', ''))}\n"
        f"- task_assigned_by: {_clean(task_state.get('task_assigned_by', ''))}\n"
        f"- task_owner: {_clean(task_state.get('task_owner', ''))}\n"
        f"- task_assignee: {_clean(task_state.get('task_assignee', ''))}\n"
        f"- task_review_status: {_clean(task_state.get('task_review_status', ''))}\n"
        f"- task_closed_by: {_clean(task_state.get('task_closed_by', ''))}\n"
        f"- task_resume_due: {_clean(task_state.get('task_resume_due', ''))}\n"
        f"- task_assigned_run_id: {_clean(task_state.get('task_assigned_run_id', ''))}\n"
        f"- task_runtime_state: {_clean(task_state.get('task_runtime_state', ''))}\n"
        f"- task_blocked_reason: {_clean(task_state.get('task_blocked_reason', ''))}\n"
        f'- current_goal: {_clean(goal)}\n'
        f'- last_completed_step: {_clean(last)}\n'
        f'- next_action: {_clean(next_action)}\n'
        f'- touched_paths: {_clean(touched_paths)}\n'
        f'- latest_proof: {_clean(latest_proof)}\n'
        f'- required_paths_or_params: {_clean(paths)}\n'
        f"- notes: {_clean(notes) if notes.strip() else '-'}\n"
    )


def render_context_handoff_content(
    *,
    ticket_id: str,
    directive_ids: str,
    goal: str,
    last: str,
    next_action: str,
    touched_paths: str,
    latest_proof: str,
    paths: str,
    notes: str,
    handoff_reason: str,
    trigger: str,
    required_action: str,
    observed_total_tokens: str,
    threshold: str,
    reset_guard: str,
    task_state_override: dict[str, str] | None = None,
) -> str:
    task_state = merged_task_state(ticket_id, task_state_override)
    return (
        '# context-handoff\n\n'
        f'- handoff_version: v1\n'
        f'- generated_at: {now_ts()}\n'
        f'- source: scripts/context_policy.py\n'
        f'- source_ticket_id: {_clean(ticket_id)}\n'
        f'- source_directive_ids: {_clean(directive_ids)}\n'
        f'- task_status: {_clean(task_state.get("task_status", ""))}\n'
        f'- task_assigned_by: {_clean(task_state.get("task_assigned_by", ""))}\n'
        f'- task_owner: {_clean(task_state.get("task_owner", ""))}\n'
        f'- task_assignee: {_clean(task_state.get("task_assignee", ""))}\n'
        f'- task_closed_by: {_clean(task_state.get("task_closed_by", ""))}\n'
        f'- task_runtime_state: {_clean(task_state.get("task_runtime_state", ""))}\n'
        f'- handoff_reason: {_clean(handoff_reason)}\n'
        f'- trigger: {_clean(trigger)}\n'
        f'- required_action: {_clean(required_action)}\n'
        f'- observed_total_tokens: {_clean(observed_total_tokens)}\n'
        f'- threshold: {_clean(threshold)}\n'
        f'- business_goal: {_clean(goal)}\n'
        f'- last_completed_step: {_clean(last)}\n'
        f'- next_action: {_clean(next_action)}\n'
        f'- latest_proof: {_clean(latest_proof)}\n'
        f'- touched_paths: {_clean(touched_paths)}\n'
        f'- required_paths_or_params: {_clean(paths)}\n'
        f'- reset_guard: {_clean(reset_guard)}\n'
        f"- notes: {_clean(notes) if notes.strip() else '-'}\n"
    )


def write_current_task(
    *,
    ticket_id: str,
    directive_ids: str,
    goal: str,
    last: str,
    next_action: str,
    touched_paths: str,
    latest_proof: str,
    paths: str,
    notes: str,
    task_state_override: dict[str, str] | None = None,
) -> None:
    atomic_write_text(
        CURRENT_TASK,
        render_current_task_content(
            ticket_id=ticket_id,
            directive_ids=directive_ids,
            goal=goal,
            last=last,
            next_action=next_action,
            touched_paths=touched_paths,
            latest_proof=latest_proof,
            paths=paths,
            notes=notes,
            task_state_override=task_state_override,
        ),
    )


def write_context_handoff(
    *,
    ticket_id: str,
    directive_ids: str,
    goal: str,
    last: str,
    next_action: str,
    touched_paths: str,
    latest_proof: str,
    paths: str,
    notes: str,
    handoff_reason: str,
    trigger: str,
    required_action: str,
    observed_total_tokens: str,
    threshold: str,
    reset_guard: str,
    task_state_override: dict[str, str] | None = None,
) -> None:
    atomic_write_text(
        CONTEXT_HANDOFF,
        render_context_handoff_content(
            ticket_id=ticket_id,
            directive_ids=directive_ids,
            goal=goal,
            last=last,
            next_action=next_action,
            touched_paths=touched_paths,
            latest_proof=latest_proof,
            paths=paths,
            notes=notes,
            handoff_reason=handoff_reason,
            trigger=trigger,
            required_action=required_action,
            observed_total_tokens=observed_total_tokens,
            threshold=threshold,
            reset_guard=reset_guard,
            task_state_override=task_state_override,
        ),
    )


def write_snapshot_pair(
    *,
    ticket_id: str,
    directive_ids: str,
    goal: str,
    last: str,
    next_action: str,
    touched_paths: str,
    latest_proof: str,
    paths: str,
    notes: str,
    handoff_reason: str = 'steady_state',
    trigger: str = 'work_update',
    required_action: str = 'read_then_resume',
    observed_total_tokens: str = '-',
    threshold: str = '-',
    reset_guard: str = 'valid_handoff_required_before_clean_reset',
    task_state_override: dict[str, str] | None = None,
) -> None:
    write_current_task(
        ticket_id=ticket_id,
        directive_ids=directive_ids,
        goal=goal,
        last=last,
        next_action=next_action,
        touched_paths=touched_paths,
        latest_proof=latest_proof,
        paths=paths,
        notes=notes,
        task_state_override=task_state_override,
    )
    write_context_handoff(
        ticket_id=ticket_id,
        directive_ids=directive_ids,
        goal=goal,
        last=last,
        next_action=next_action,
        touched_paths=touched_paths,
        latest_proof=latest_proof,
        paths=paths,
        notes=notes,
        handoff_reason=handoff_reason,
        trigger=trigger,
        required_action=required_action,
        observed_total_tokens=observed_total_tokens,
        threshold=threshold,
        reset_guard=reset_guard,
        task_state_override=task_state_override,
    )


def write_context_handoff_from_current(
    *,
    handoff_reason: str,
    trigger: str,
    required_action: str,
    observed_total_tokens: str,
    threshold: str,
    reset_guard: str,
    notes: str = '',
) -> dict[str, str]:
    current = parse_current_task(read_text(CURRENT_TASK))
    write_context_handoff(
        ticket_id=current.get('ticket_id', '미정'),
        directive_ids=current.get('directive_ids', '미정'),
        goal=current.get('current_goal', '미정'),
        last=current.get('last_completed_step', '미정'),
        next_action=current.get('next_action', '미정'),
        touched_paths=current.get('touched_paths', '미정'),
        latest_proof=current.get('latest_proof', '미정'),
        paths=current.get('required_paths_or_params', '미정'),
        notes=notes or current.get('notes', ''),
        handoff_reason=handoff_reason,
        trigger=trigger,
        required_action=required_action,
        observed_total_tokens=observed_total_tokens,
        threshold=threshold,
        reset_guard=reset_guard,
    )
    return current


def inspect_runtime_ticket_references(ticket_id: str) -> dict[str, object]:
    current = parse_current_task(read_text(CURRENT_TASK))
    handoff = parse_context_handoff(read_text(CONTEXT_HANDOFF))
    target = (ticket_id or '').strip()
    current_ticket = (current.get('ticket_id') or '').strip()
    handoff_ticket = (handoff.get('source_ticket_id') or '').strip()
    return {
        'ticket_id': target,
        'current_task': current,
        'context_handoff': handoff,
        'current_task_ticket_id': current_ticket,
        'context_handoff_ticket_id': handoff_ticket,
        'current_task_points': bool(target) and current_ticket == target,
        'context_handoff_points': bool(target) and handoff_ticket == target,
    }


def compact(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + '...'


def summarize_tasks(top: int, recent: int) -> dict:
    conn = db_connect(TASKS_DB)
    if conn is None:
        return {'available': False, 'db': str(TASKS_DB)}

    counts = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress,
               SUM(CASE WHEN status='TODO' THEN 1 ELSE 0 END) AS todo,
               SUM(CASE WHEN status='BLOCKED' THEN 1 ELSE 0 END) AS blocked,
               SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS done
        FROM tasks
        """
    ).fetchone()
    active_rows = conn.execute(
        """
        SELECT id, priority, status, title, note, assigned_by, owner, assignee, review_status, resume_due, closed_by
        FROM tasks
        WHERE bucket='active'
        ORDER BY CASE UPPER(priority)
                    WHEN 'P0' THEN 0
                    WHEN 'P1' THEN 1
                    WHEN 'P2' THEN 2
                    WHEN 'P3' THEN 3
                    ELSE 4
                 END,
                 sort_order,
                 id
        LIMIT ?
        """,
        (top,),
    ).fetchall()
    recent_rows = conn.execute(
        """
        SELECT id, status, updated_at, title
        FROM tasks
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT ?
        """,
        (recent,),
    ).fetchall()
    return {
        'available': True,
        'counts': {
            'total': counts['total'] or 0,
            'in_progress': counts['in_progress'] or 0,
            'todo': counts['todo'] or 0,
            'blocked': counts['blocked'] or 0,
            'done': counts['done'] or 0,
        },
        'active_top': [
            {
                'id': row['id'],
                'priority': row['priority'] or '-',
                'status': row['status'],
                'title': row['title'],
                'assigned_by': (row['assigned_by'] or '').strip() if 'assigned_by' in row.keys() else '',
                'owner': (row['owner'] or '').strip() if 'owner' in row.keys() else '',
                'assignee': (row['assignee'] or '').strip() if 'assignee' in row.keys() else '',
                'closed_by': (row['closed_by'] or '').strip() if 'closed_by' in row.keys() else '',
                'runtime_state': format_task_runtime_state(row),
            }
            for row in active_rows
        ],
        'recent': [
            {
                'id': row['id'],
                'status': row['status'],
                'updated_at': row['updated_at'],
                'title': row['title'],
            }
            for row in recent_rows
        ],
    }


def summarize_directives(top: int, recent: int) -> dict:
    conn = db_connect(DIRECTIVES_DB)
    if conn is None:
        return {'available': False, 'db': str(DIRECTIVES_DB)}

    counts = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress,
               SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open,
               SUM(CASE WHEN status='BLOCKED' THEN 1 ELSE 0 END) AS blocked,
               SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS done
        FROM directives
        """
    ).fetchone()
    in_progress_rows = conn.execute(
        """
        SELECT id, due, directive
        FROM directives
        WHERE status='IN_PROGRESS'
        ORDER BY due, COALESCE(source_line, 999999), id
        LIMIT ?
        """,
        (top,),
    ).fetchall()
    recent_rows = conn.execute(
        """
        SELECT id, status, updated_at, directive
        FROM directives
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT ?
        """,
        (recent,),
    ).fetchall()
    return {
        'available': True,
        'counts': {
            'total': counts['total'] or 0,
            'in_progress': counts['in_progress'] or 0,
            'open': counts['open'] or 0,
            'blocked': counts['blocked'] or 0,
            'done': counts['done'] or 0,
        },
        'in_progress_top': [
            {
                'id': row['id'],
                'due': row['due'],
                'directive': row['directive'],
            }
            for row in in_progress_rows
        ],
        'recent': [
            {
                'id': row['id'],
                'status': row['status'],
                'updated_at': row['updated_at'],
                'directive': row['directive'],
            }
            for row in recent_rows
        ],
    }


def current_task_status(task: dict[str, str]) -> dict:
    exists = CURRENT_TASK.exists()
    missing_keys: list[str] = []
    for key in REQUIRED_CURRENT_TASK_KEYS:
        value = (task.get(key) or '').strip()
        if value in PLACEHOLDER_VALUES:
            missing_keys.append(key)

    ticket_id = (task.get('ticket_id') or '').strip()
    snapshot_status = (task.get('task_status') or '').strip()
    db_state = load_task_state(ticket_id)
    db_status = (db_state.get('task_status') or '').strip()
    notes_value = (task.get('notes') or '').strip()
    placeholder = (not exists) or bool(missing_keys)
    status_mismatch = (
        ticket_id not in PLACEHOLDER_VALUES
        and snapshot_status not in PLACEHOLDER_VALUES
        and db_status not in PLACEHOLDER_VALUES
        and snapshot_status.upper() != db_status.upper()
    )
    return {
        'exists': exists,
        'placeholder': placeholder,
        'missing_keys': missing_keys,
        'ticket_id': ticket_id,
        'directive_ids': task.get('directive_ids', ''),
        'task_status': snapshot_status,
        'task_runtime_state': task.get('task_runtime_state', ''),
        'db_task_status': db_status,
        'db_task_phase': db_state.get('task_phase', ''),
        'db_task_runtime_state': db_state.get('task_runtime_state', ''),
        'status_mismatch_vs_taskdb': status_mismatch,
        'closed_in_taskdb': db_status.upper() in {'DONE', 'BLOCKED'},
        'next_action': task.get('next_action', ''),
        'latest_proof': task.get('latest_proof', ''),
        'notes_empty': notes_value in {'', '-'},
    }


def current_handoff_status(handoff: dict[str, str], task: dict[str, str] | None = None) -> dict:
    exists = CONTEXT_HANDOFF.exists()
    missing_keys: list[str] = []
    for key in REQUIRED_CONTEXT_HANDOFF_KEYS:
        value = (handoff.get(key) or '').strip()
        if value in PLACEHOLDER_VALUES:
            missing_keys.append(key)

    task = task or parse_current_task(read_text(CURRENT_TASK))
    current_ticket_id = (task.get('ticket_id') or '').strip()
    source_ticket_id = (handoff.get('source_ticket_id') or '').strip()
    ticket_mismatch = (
        current_ticket_id not in PLACEHOLDER_VALUES
        and source_ticket_id not in PLACEHOLDER_VALUES
        and current_ticket_id != source_ticket_id
    )
    placeholder = (not exists) or bool(missing_keys)
    return {
        'exists': exists,
        'placeholder': placeholder,
        'missing_keys': missing_keys,
        'generated_at': handoff.get('generated_at', ''),
        'source_ticket_id': source_ticket_id,
        'source_directive_ids': handoff.get('source_directive_ids', ''),
        'current_task_ticket_id': current_ticket_id,
        'ticket_mismatch_vs_current_task': ticket_mismatch,
        'required_action': handoff.get('required_action', ''),
        'trigger': handoff.get('trigger', ''),
        'next_action': handoff.get('next_action', ''),
        'latest_proof': handoff.get('latest_proof', ''),
        'notes': handoff.get('notes', ''),
    }


def build_reload_bundle(mode: str, top: int, recent: int) -> dict:
    soul = read_text(FILES['soul'])
    user = read_text(FILES['user'])
    agents = read_text(FILES['agents'])
    tasks_md = read_text(FILES['tasks'])
    directives_md = read_text(FILES['directives'])
    current = read_text(FILES['current_task'])
    handoff_text = read_text(FILES['context_handoff'])
    memory = read_text(FILES['memory']) if mode == 'main' else ''
    task = parse_current_task(current)
    handoff = parse_context_handoff(handoff_text)

    bundle = {
        'mode': mode,
        'policy': {
            'main_soft_target': 120000,
            'main_hard_target': 120000,
            'main_action_at_hard': 'finish_current_step_then_reset',
            'main_reset_style': 'validated_handoff_then_reset_if_needed',
            'local_action_at_task_end': 'flush',
            'daily_memory_reload': 'forbidden',
            'db_summary_reload': 'required',
            'current_task_snapshot': 'required before substantive work',
            'context_handoff': 'read only after reset/cutover or when watchdog asks',
        },
        'reload_order': [
            'SOUL.md',
            'USER.md',
            'AGENTS.md',
            'TASKS.md',
            'DIRECTIVES.md',
            'runtime/current-task.md',
            'runtime/context-handoff.md',
        ] + (['MEMORY.md'] if mode == 'main' else []),
        'startup_checks': [
            'python3 scripts/tasks/db.py summary --top 5 --recent 5',
            'python3 scripts/directives/db.py summary --top 5 --recent 5',
            'python3 scripts/context_policy.py resume-check --strict',
            'python3 scripts/context_policy.py handoff-validate --strict',
        ],
        'current_task': task,
        'current_task_status': current_task_status(task),
        'context_handoff': handoff,
        'context_handoff_status': current_handoff_status(handoff, task),
        'task_summary': summarize_tasks(top, recent),
        'directive_summary': summarize_directives(top, recent),
        'snippets': {
            'soul': compact(soul, 1200),
            'user': compact(user, 1200),
            'agents': compact(agents, 3500),
            'tasks': compact(tasks_md, 1200),
            'directives': compact(directives_md, 1200),
            'current_task': compact(current, 1200),
            'context_handoff': compact(handoff_text, 1200),
        },
    }
    if mode == 'main':
        bundle['snippets']['memory'] = compact(memory, 1200)
    return bundle


def cmd_snapshot(args: argparse.Namespace) -> int:
    write_snapshot_pair(
        ticket_id=args.ticket_id,
        directive_ids=args.directive_ids,
        goal=args.goal,
        last=args.last,
        next_action=args.next_action,
        touched_paths=args.touched_paths,
        latest_proof=args.proof,
        paths=args.paths,
        notes=args.notes,
    )
    print(json.dumps({'ok': True, 'files': [str(CURRENT_TASK), str(CONTEXT_HANDOFF)], 'action': 'snapshot_and_handoff_written'}, ensure_ascii=False))
    return 0


def cmd_show(_: argparse.Namespace) -> int:
    print(read_text(CURRENT_TASK))
    return 0


def cmd_handoff_show(_: argparse.Namespace) -> int:
    print(read_text(CONTEXT_HANDOFF))
    return 0


def cmd_handoff_from_current(args: argparse.Namespace) -> int:
    write_context_handoff_from_current(
        handoff_reason=args.handoff_reason,
        trigger=args.trigger,
        required_action=args.required_action,
        observed_total_tokens=args.observed_total_tokens,
        threshold=args.threshold,
        reset_guard=args.reset_guard,
        notes=args.notes,
    )
    print(json.dumps({'ok': True, 'file': str(CONTEXT_HANDOFF), 'action': 'handoff_written_from_current'}, ensure_ascii=False))
    return 0


def cmd_reload(args: argparse.Namespace) -> int:
    print(json.dumps(build_reload_bundle(args.mode, args.top, args.recent), ensure_ascii=False, indent=2))
    return 0


def cmd_resume_check(args: argparse.Namespace) -> int:
    current = read_text(CURRENT_TASK)
    task = parse_current_task(current)
    status = current_task_status(task)
    handoff = parse_context_handoff(read_text(CONTEXT_HANDOFF))
    handoff_status = current_handoff_status(handoff, task)
    payload = {
        'current_task_status': status,
        'context_handoff_status': handoff_status,
        'task_summary': summarize_tasks(args.top, args.recent),
        'directive_summary': summarize_directives(args.top, args.recent),
        'required_commands': [
            'python3 scripts/tasks/db.py summary --top 5 --recent 5',
            'python3 scripts/directives/db.py summary --top 5 --recent 5',
            'python3 scripts/context_policy.py snapshot ...',
            'python3 scripts/context_policy.py handoff-validate --strict',
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and status['placeholder']:
        return 2
    return 0


def cmd_handoff_validate(args: argparse.Namespace) -> int:
    task = parse_current_task(read_text(CURRENT_TASK))
    handoff = parse_context_handoff(read_text(CONTEXT_HANDOFF))
    status = current_handoff_status(handoff, task)
    payload = {
        'context_handoff_status': status,
        'current_task_status': current_task_status(task),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and (status['placeholder'] or status['ticket_mismatch_vs_current_task']):
        return 2
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    tokens = args.tokens
    if args.mode == 'main':
        if tokens >= args.hard:
            action = 'finish_current_step_then_reset'
        else:
            action = 'keep'
    else:
        if tokens >= args.hard:
            action = 'flush'
        elif tokens >= args.soft:
            action = 'warn'
        else:
            action = 'keep'
    print(json.dumps({'mode': args.mode, 'tokens': tokens, 'soft': args.soft, 'hard': args.hard, 'action': action}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Context policy helper for main/local brain reload flow')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('snapshot', help='Write runtime/current-task.md and runtime/context-handoff.md')
    s.add_argument('--ticket-id', default='미정')
    s.add_argument('--directive-ids', default='미정')
    s.add_argument('--goal', required=True)
    s.add_argument('--last', required=True)
    s.add_argument('--next-action', required=True)
    s.add_argument('--touched-paths', default='미정')
    s.add_argument('--proof', default='미정')
    s.add_argument('--paths', default='미정')
    s.add_argument('--notes', default='')
    s.set_defaults(func=cmd_snapshot)

    sh = sub.add_parser('show', help='Show runtime/current-task.md')
    sh.set_defaults(func=cmd_show)

    hs = sub.add_parser('handoff-show', help='Show runtime/context-handoff.md')
    hs.set_defaults(func=cmd_handoff_show)

    hf = sub.add_parser('handoff-from-current', help='Refresh runtime/context-handoff.md from runtime/current-task.md')
    hf.add_argument('--handoff-reason', default='steady_state')
    hf.add_argument('--trigger', default='work_update')
    hf.add_argument('--required-action', default='read_then_resume')
    hf.add_argument('--observed-total-tokens', default='-')
    hf.add_argument('--threshold', default='-')
    hf.add_argument('--reset-guard', default='valid_handoff_required_before_clean_reset')
    hf.add_argument('--notes', default='')
    hf.set_defaults(func=cmd_handoff_from_current)

    r = sub.add_parser('reload', help='Build minimal reload bundle')
    r.add_argument('--mode', choices=['main', 'local'], required=True)
    r.add_argument('--top', type=int, default=5)
    r.add_argument('--recent', type=int, default=5)
    r.set_defaults(func=cmd_reload)

    rc = sub.add_parser('resume-check', help='Check whether DB summaries/current-task are ready for resume')
    rc.add_argument('--top', type=int, default=5)
    rc.add_argument('--recent', type=int, default=5)
    rc.add_argument('--strict', action='store_true')
    rc.set_defaults(func=cmd_resume_check)

    hv = sub.add_parser('handoff-validate', help='Check whether runtime/context-handoff.md is valid for clean reset/cutover')
    hv.add_argument('--strict', action='store_true')
    hv.set_defaults(func=cmd_handoff_validate)

    d = sub.add_parser('decide', help='Decide keep/reset/flush from token usage')
    d.add_argument('--mode', choices=['main', 'local'], required=True)
    d.add_argument('--tokens', type=int, required=True)
    d.add_argument('--soft', type=int, required=True)
    d.add_argument('--hard', type=int, required=True)
    d.set_defaults(func=cmd_decide)

    return p


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
