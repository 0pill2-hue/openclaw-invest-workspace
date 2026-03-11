#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from context_policy import (
    PLACEHOLDER_VALUES,
    extract_phase,
    inspect_runtime_ticket_references,
    load_task_state,
    parse_context_handoff,
    parse_current_task,
    write_context_handoff_from_current,
    write_snapshot_pair,
)
from lib.runtime_env import TASKS_DB, context_handoff_path, current_task_path
from lib.task_runtime import is_nonterminal_wait_state

CONTEXT_POLICY = ROOT / "scripts/context_policy.py"
CURRENT_TASK = current_task_path()
CONTEXT_HANDOFF = context_handoff_path()
CONTEXT_TOKEN_THRESHOLD = int(os.environ.get('WATCHDOG_CONTEXT_TOKEN_THRESHOLD', '120000'))
CONTEXT_HYGIENE_TASK_ID = 'WD-CONTEXT-HYGIENE'
CONTEXT_HYGIENE_PATHS = 'runtime/current-task.md,runtime/context-handoff.md,runtime/tasks/tasks.db,scripts/watchdog/context_hygiene.py'


def is_waiting_callback_state(db_task: dict[str, str]) -> bool:
    status = (db_task.get('task_status') or '').strip().upper()
    phase = (db_task.get('task_phase') or '').strip().lower()
    return is_nonterminal_wait_state(status, phase)


def load_active_execution_rows() -> list[dict[str, str]]:
    if not TASKS_DB.exists():
        return []
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, status, note, assignee
            FROM tasks
            WHERE id NOT LIKE 'WD-%'
              AND status IN ('IN_PROGRESS', 'BLOCKED')
            ORDER BY datetime(updated_at) DESC, id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    active_rows: list[dict[str, str]] = []
    for row in rows:
        status = str(row['status'] or '').strip().upper()
        phase = extract_phase(row['note'])
        db_task = {
            'task_status': status,
            'task_phase': phase,
        }
        waiting_callback = is_waiting_callback_state(db_task)
        if status != 'IN_PROGRESS' and not waiting_callback:
            continue
        active_rows.append(
            {
                'id': str(row['id'] or '').strip(),
                'status': status,
                'phase': phase or '-',
                'assignee': str(row['assignee'] or '').strip() or '-',
            }
        )
    return active_rows


def text_requests_unlock(value: object) -> bool:
    text = str(value or '').strip().lower()
    return bool(text) and ('unlock' in text or '언락' in text)



def current_handoff_requests_unlock() -> bool:
    if not CONTEXT_HANDOFF.exists():
        return False
    handoff = parse_context_handoff(CONTEXT_HANDOFF.read_text(encoding='utf-8'))
    return any(text_requests_unlock(handoff.get(key)) for key in ('notes', 'required_action'))



def run_json_command(command: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    payload = {}
    stdout = (proc.stdout or '').strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except Exception:
            for line in reversed(stdout.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    break
                except Exception:
                    continue
    return proc.returncode, payload


def run_resume_check() -> tuple[int, dict]:
    return run_json_command([sys.executable, str(CONTEXT_POLICY), 'resume-check', '--strict'])


def run_handoff_validate() -> tuple[int, dict]:
    return run_json_command([sys.executable, str(CONTEXT_POLICY), 'handoff-validate', '--strict'])


def refresh_handoff(total_tokens: int | None) -> tuple[int, dict]:
    command = [
        sys.executable,
        str(CONTEXT_POLICY),
        'handoff-from-current',
        '--handoff-reason',
        'context_threshold',
        '--trigger',
        'context_tokens_high',
        '--required-action',
        'finish_current_step_then_reset',
        '--threshold',
        str(CONTEXT_TOKEN_THRESHOLD),
        '--notes',
        'prepared_by=context_hygiene',
    ]
    if isinstance(total_tokens, int):
        command.extend(['--observed-total-tokens', str(total_tokens)])
    return run_json_command(command)


def run_openclaw_status_json() -> tuple[int, dict]:
    proc = subprocess.run(
        ['openclaw', 'status', '--json'],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    payload = {}
    stdout = (proc.stdout or '').strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except Exception:
            payload = {}
    return proc.returncode, payload


def pick_primary_session(status_payload: dict) -> dict:
    recent = (((status_payload or {}).get('sessions') or {}).get('recent') or [])
    if not recent:
        return {}
    candidates = [row for row in recent if row.get('agentId') == 'main']
    if not candidates:
        candidates = recent
    return max(candidates, key=lambda row: row.get('updatedAt') or 0)


def compact_note(value: str | None, limit: int = 220) -> str:
    text = str(value or '').strip()
    if len(text) <= limit:
        return text or '-'
    return text[: limit - 3].rstrip() + '...'


def self_heal_closed_ticket_reference(
    *,
    ticket_id: str,
    db_status: str,
    current_task: dict[str, str],
    detail: dict[str, object],
) -> dict[str, object] | None:
    refs = inspect_runtime_ticket_references(ticket_id)
    if not refs['current_task_points'] and not refs['context_handoff_points']:
        return None

    if refs['current_task_points']:
        if ticket_id == CONTEXT_HYGIENE_TASK_ID:
            return None
        maintenance = load_task_state(CONTEXT_HYGIENE_TASK_ID)
        maintenance_status = (maintenance.get('task_status') or '').strip().upper()
        if maintenance_status != 'IN_PROGRESS':
            return None
        write_snapshot_pair(
            ticket_id=CONTEXT_HYGIENE_TASK_ID,
            directive_ids=CONTEXT_HYGIENE_TASK_ID,
            goal=f'{ticket_id} {db_status} 잔여 포인터 self-heal',
            last=f'context_hygiene가 닫힌 ticket {ticket_id}를 가리키는 current-task/context-handoff를 감지했다.',
            next_action='다음 실제 작업 ticket으로 snapshot을 교체하고, WD-CONTEXT-HYGIENE를 마무리한다.',
            touched_paths=CONTEXT_HYGIENE_PATHS,
            latest_proof=compact_note(current_task.get('latest_proof') or f'{ticket_id}:{db_status}'),
            paths=CONTEXT_HYGIENE_PATHS,
            notes=f'prepared_by=context_hygiene_self_heal; source_ticket={ticket_id}; source_status={db_status}',
            handoff_reason='closed_ticket_self_heal',
            trigger='closed_ticket_pointer_detected',
            required_action='read_then_resume',
            observed_total_tokens='-',
            threshold='-',
            reset_guard='valid_handoff_required_before_clean_reset',
        )
        detail['self_heal_action'] = f'repointed_to_{CONTEXT_HYGIENE_TASK_ID}'
        detail['self_heal_ticket'] = ticket_id
        return {'mode': 'maintenance', 'ticket_id': ticket_id}

    current_ticket = str(refs.get('current_task_ticket_id') or '').strip()
    if current_ticket and current_ticket != ticket_id and current_ticket not in PLACEHOLDER_VALUES:
        write_context_handoff_from_current(
            handoff_reason='closed_ticket_self_heal',
            trigger='closed_ticket_pointer_detected',
            required_action='read_then_resume',
            observed_total_tokens='-',
            threshold='-',
            reset_guard='valid_handoff_required_before_clean_reset',
            notes=f'prepared_by=context_hygiene_self_heal; realigned_from={ticket_id}; closed_status={db_status}',
        )
        detail['self_heal_action'] = 'handoff_realigned_from_current_task'
        detail['self_heal_ticket'] = ticket_id
        return {'mode': 'handoff_realign', 'ticket_id': ticket_id}
    return None


def main() -> int:
    issues: list[str] = []
    detail: dict[str, object] = {
        'context_handoff_path': str(CONTEXT_HANDOFF),
    }

    current_task = parse_current_task(CURRENT_TASK.read_text(encoding='utf-8') if CURRENT_TASK.exists() else '')
    ticket_id = (current_task.get('ticket_id') or '').strip()
    task_status = (current_task.get('task_status') or '').strip().upper()
    detail['current_task_ticket_id'] = ticket_id
    detail['current_task_status'] = task_status
    detail['current_goal'] = current_task.get('current_goal', '') or '-'
    detail['current_next_action'] = current_task.get('next_action', '') or '-'
    detail['current_latest_proof'] = current_task.get('latest_proof', '') or '-'

    if ticket_id and ticket_id not in PLACEHOLDER_VALUES:
        precheck_db_task = load_task_state(ticket_id)
        precheck_status = (precheck_db_task.get('task_status') or '').strip().upper()
        precheck_waiting = is_waiting_callback_state(precheck_db_task)
        if precheck_status in {'DONE', 'BLOCKED'} and not precheck_waiting:
            heal_result = self_heal_closed_ticket_reference(
                ticket_id=ticket_id,
                db_status=precheck_status,
                current_task=current_task,
                detail=detail,
            )
            if heal_result:
                detail['self_healed_closed_ticket_reference'] = heal_result
                current_task = parse_current_task(CURRENT_TASK.read_text(encoding='utf-8') if CURRENT_TASK.exists() else '')
                ticket_id = (current_task.get('ticket_id') or '').strip()
                task_status = (current_task.get('task_status') or '').strip().upper()
                detail['current_task_ticket_id'] = ticket_id
                detail['current_task_status'] = task_status
                detail['current_goal'] = current_task.get('current_goal', '') or '-'
                detail['current_next_action'] = current_task.get('next_action', '') or '-'
                detail['current_latest_proof'] = current_task.get('latest_proof', '') or '-'

    handoff_precheck = parse_context_handoff(CONTEXT_HANDOFF.read_text(encoding='utf-8') if CONTEXT_HANDOFF.exists() else '')
    handoff_ticket_id = (handoff_precheck.get('source_ticket_id') or '').strip()
    if handoff_ticket_id and handoff_ticket_id not in PLACEHOLDER_VALUES and handoff_ticket_id != ticket_id:
        handoff_db_task = load_task_state(handoff_ticket_id)
        handoff_db_status = (handoff_db_task.get('task_status') or '').strip().upper()
        handoff_waiting = is_waiting_callback_state(handoff_db_task)
        if handoff_db_status in {'DONE', 'BLOCKED'} and not handoff_waiting:
            heal_result = self_heal_closed_ticket_reference(
                ticket_id=handoff_ticket_id,
                db_status=handoff_db_status,
                current_task=current_task,
                detail=detail,
            )
            if heal_result:
                detail['self_healed_closed_handoff_reference'] = heal_result

    rc, resume_payload = run_resume_check()
    detail['resume_check_rc'] = rc
    detail['resume_check'] = resume_payload
    if rc != 0:
        issues.append('context_resume_check_strict_failed')

    status_rc, status_payload = run_openclaw_status_json()
    detail['openclaw_status_rc'] = status_rc
    primary_session = pick_primary_session(status_payload)
    detail['session_key'] = primary_session.get('key') or '-'
    detail['session_total_tokens'] = primary_session.get('totalTokens')
    detail['session_context_tokens'] = primary_session.get('contextTokens')
    detail['session_percent_used'] = primary_session.get('percentUsed')
    detail['context_token_threshold'] = CONTEXT_TOKEN_THRESHOLD
    unlock_requested = current_handoff_requests_unlock()
    detail['unlock_requested'] = unlock_requested
    total_tokens = primary_session.get('totalTokens')
    if isinstance(total_tokens, int) and total_tokens >= CONTEXT_TOKEN_THRESHOLD:
        detail['context_tokens_high'] = f'{total_tokens}>={CONTEXT_TOKEN_THRESHOLD}'
        if unlock_requested:
            detail['handoff_refresh_skipped'] = 'unlock_requested'
        else:
            detail['required_action'] = 'finish_current_step_then_reset'
            refresh_rc, refresh_payload = refresh_handoff(total_tokens)
            detail['handoff_refresh_rc'] = refresh_rc
            detail['handoff_refresh'] = refresh_payload

    handoff_rc, handoff_payload = run_handoff_validate()
    handoff_status = (handoff_payload or {}).get('context_handoff_status') or {}
    detail['context_handoff_rc'] = handoff_rc
    detail['context_handoff'] = handoff_status
    detail['context_handoff_valid'] = handoff_rc == 0
    detail['context_handoff_source_ticket_id'] = handoff_status.get('source_ticket_id') or '-'
    detail['context_handoff_required_action'] = handoff_status.get('required_action') or '-'
    detail['context_handoff_trigger'] = handoff_status.get('trigger') or '-'
    detail['context_handoff_notes'] = handoff_status.get('notes') or '-'
    if handoff_rc != 0:
        issues.append('context_handoff_invalid')
    if handoff_status.get('ticket_mismatch_vs_current_task'):
        issues.append(
            f"context_handoff_ticket_mismatch:{handoff_status.get('source_ticket_id', '-')}:current={handoff_status.get('current_task_ticket_id', '-')}"
        )

    if TASKS_DB.exists():
        conn = sqlite3.connect(str(TASKS_DB))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT id, title
                FROM tasks
                WHERE status='BLOCKED'
                  AND TRIM(COALESCE(proof, '')) != ''
                  AND TRIM(COALESCE(blocked_reason, '')) = ''
                ORDER BY datetime(updated_at) DESC, id DESC
                LIMIT 10
                """
            ).fetchall()
            blocked_with_proof = [dict(row) for row in rows]
            detail['blocked_with_proof_no_reason'] = blocked_with_proof
            if blocked_with_proof:
                issues.append(f"blocked_with_proof_no_reason:{len(blocked_with_proof)}")
        finally:
            conn.close()
        active_execution_rows = load_active_execution_rows()
        detail['active_execution_remaining'] = bool(active_execution_rows)
        detail['active_execution_count'] = len(active_execution_rows)
        detail['active_execution_tickets'] = active_execution_rows[:10]
    else:
        issues.append('tasks_db_missing')
        detail['active_execution_remaining'] = False
        detail['active_execution_count'] = 0
        detail['active_execution_tickets'] = []

    if ticket_id and ticket_id not in PLACEHOLDER_VALUES:
        db_task = load_task_state(ticket_id)
        db_status = (db_task.get('task_status') or '').strip().upper()
        db_phase = (db_task.get('task_phase') or '').strip().lower()
        waiting_callback = is_waiting_callback_state(db_task)
        detail['current_task_db_status'] = db_status or '-'
        detail['current_task_db_phase'] = db_phase or '-'
        detail['current_task_db_runtime_state'] = db_task.get('task_runtime_state', '') or '-'
        detail['current_task_waiting_callback'] = waiting_callback
        if not db_task:
            issues.append(f'current_task_ticket_missing_in_db:{ticket_id}')
        else:
            closed_maintenance_snapshot_ok = (
                ticket_id.startswith('WD-')
                and db_status in {'DONE', 'BLOCKED'}
                and not waiting_callback
                and not bool(detail.get('active_execution_remaining'))
                and str(detail.get('context_handoff_required_action') or '').strip() == 'read_then_resume'
            )
            detail['current_task_closed_maintenance_snapshot_ok'] = closed_maintenance_snapshot_ok
            if task_status and task_status not in PLACEHOLDER_VALUES and task_status != db_status:
                if not (waiting_callback and task_status in {'IN_PROGRESS', 'BLOCKED'}) and not closed_maintenance_snapshot_ok:
                    issues.append(f'current_task_status_mismatch:{ticket_id}:snapshot={task_status}:db={db_status}')
            if db_status in {'DONE', 'BLOCKED'} and not waiting_callback and not closed_maintenance_snapshot_ok:
                issues.append(f'current_task_points_to_closed_db_task:{ticket_id}:{db_status}')

    result = {
        'ok': len(issues) == 0,
        'issues': issues,
        'detail': detail,
        'script': 'scripts/watchdog/context_hygiene.py',
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
