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

from context_policy import PLACEHOLDER_VALUES, load_task_state, parse_current_task
from lib.runtime_env import TASKS_DB, context_handoff_path, current_task_path

CONTEXT_POLICY = ROOT / "scripts/context_policy.py"
CURRENT_TASK = current_task_path()
CONTEXT_HANDOFF = context_handoff_path()
CONTEXT_TOKEN_THRESHOLD = int(os.environ.get('WATCHDOG_CONTEXT_TOKEN_THRESHOLD', '120000'))


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
        'clean_reset',
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


def main() -> int:
    issues: list[str] = []
    detail: dict[str, object] = {
        'context_handoff_path': str(CONTEXT_HANDOFF),
    }

    rc, resume_payload = run_resume_check()
    detail['resume_check_rc'] = rc
    detail['resume_check'] = resume_payload
    if rc != 0:
        issues.append('context_resume_check_strict_failed')

    current_task = parse_current_task(CURRENT_TASK.read_text(encoding='utf-8') if CURRENT_TASK.exists() else '')
    ticket_id = (current_task.get('ticket_id') or '').strip()
    task_status = (current_task.get('task_status') or '').strip().upper()
    detail['current_task_ticket_id'] = ticket_id
    detail['current_task_status'] = task_status
    detail['current_goal'] = current_task.get('current_goal', '') or '-'
    detail['current_next_action'] = current_task.get('next_action', '') or '-'
    detail['current_latest_proof'] = current_task.get('latest_proof', '') or '-'

    status_rc, status_payload = run_openclaw_status_json()
    detail['openclaw_status_rc'] = status_rc
    primary_session = pick_primary_session(status_payload)
    detail['session_key'] = primary_session.get('key') or '-'
    detail['session_total_tokens'] = primary_session.get('totalTokens')
    detail['session_context_tokens'] = primary_session.get('contextTokens')
    detail['session_percent_used'] = primary_session.get('percentUsed')
    detail['context_token_threshold'] = CONTEXT_TOKEN_THRESHOLD
    total_tokens = primary_session.get('totalTokens')
    if isinstance(total_tokens, int) and total_tokens >= CONTEXT_TOKEN_THRESHOLD:
        issues.append(f'context_tokens_high:{total_tokens}>={CONTEXT_TOKEN_THRESHOLD}')
        detail['required_action'] = 'prepare_handoff'
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
    else:
        issues.append('tasks_db_missing')

    if ticket_id and ticket_id not in PLACEHOLDER_VALUES:
        db_task = load_task_state(ticket_id)
        db_status = (db_task.get('task_status') or '').strip().upper()
        detail['current_task_db_status'] = db_status or '-'
        detail['current_task_db_runtime_state'] = db_task.get('task_runtime_state', '') or '-'
        if not db_task:
            issues.append(f'current_task_ticket_missing_in_db:{ticket_id}')
        else:
            if task_status and task_status not in PLACEHOLDER_VALUES and task_status != db_status:
                issues.append(f'current_task_status_mismatch:{ticket_id}:snapshot={task_status}:db={db_status}')
            if db_status in {'DONE', 'BLOCKED'}:
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
