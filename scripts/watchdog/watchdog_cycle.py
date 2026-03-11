#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.context_lock import clear_context_lock, context_lock_mode, is_blocking_context_lock, load_context_lock, save_context_lock
from lib.task_runtime import is_nonterminal_wait_state

ROOT = Path(__file__).resolve().parents[2]
VALIDATE_SCRIPT = ROOT / "scripts/watchdog/watchdog_validate.py"
RECOVER_SCRIPT = ROOT / "scripts/watchdog/watchdog_recover.py"
CONTEXT_HYGIENE_SCRIPT = ROOT / "scripts/watchdog/context_hygiene.py"
STATE_PATH = ROOT / "runtime/tasks/watchdog_notify_state.json"
TASKS_DB = ROOT / "runtime/tasks/tasks.db"
MAINTENANCE_TASK_SPECS = {
    'task': {
        'id': 'WD-TASK-HYGIENE',
        'title': 'watchdog maintenance: task hygiene/stale 정리',
        'scope': 'watchdog stale/BLOCKED/task hygiene issue 정리 및 proof/상태전이 후속조치',
    },
    'context': {
        'id': 'WD-CONTEXT-HYGIENE',
        'title': 'watchdog maintenance: context handoff/작업연속성 정리',
        'scope': 'context threshold 초과/current-task mismatch/context-handoff 검증 시 메인을 깨워 현재 step 완료 후 reset·재개까지 정리',
    },
}


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_ts(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(payload: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_state() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()


def run_json_script(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    payload: dict[str, Any] | None = None

    for line in reversed(stdout.splitlines() if stdout else []):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            break
        except Exception:
            continue

    if payload is None:
        payload = {
            "ok": False,
            "script": str(path.relative_to(ROOT)),
            "returncode": proc.returncode,
            "parse_error": True,
            "stdout_tail": stdout[-1000:],
            "stderr_tail": stderr[-1000:],
        }
    payload.setdefault("script", str(path.relative_to(ROOT)))
    payload.setdefault("returncode", proc.returncode)
    payload.setdefault("stdout_tail", stdout[-1000:])
    payload.setdefault("stderr_tail", stderr[-1000:])
    return payload


def normalize_issues(validate_payload: dict[str, Any], recover_payload: dict[str, Any], context_payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for issue in validate_payload.get("issues", []) or []:
        text = str(issue).strip()
        if text:
            issues.append(text)
    for moved in recover_payload.get("moved", []) or []:
        tid = str(moved.get("id") or "").strip()
        reason = str(moved.get("reason") or "").strip()
        if tid and reason:
            issues.append(f"BLOCKED:{tid}:{reason}")
    for issue in context_payload.get("issues", []) or []:
        text = str(issue).strip()
        if text:
            issues.append(text)

    detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    if context_requires_reset(context_payload):
        current_ticket = str(detail.get('current_task_ticket_id') or '-').strip() or '-'
        token_info = str(detail.get('context_tokens_high') or '-').strip() or '-'
        issues.append(f'context_reset_required:{current_ticket}:{token_info}')

    if validate_payload.get("parse_error"):
        issues.append("watchdog_validate_parse_error")
    if recover_payload.get("parse_error"):
        issues.append("watchdog_recover_parse_error")
    if context_payload.get("parse_error"):
        issues.append("context_hygiene_parse_error")
    return issues


def classify_issue_groups(issues: list[str]) -> dict[str, list[str]]:
    grouped = {'task': [], 'context': []}
    for issue in issues:
        text = str(issue).strip()
        if not text:
            continue
        if text.startswith('context_') or text.startswith('current_task_') or text.startswith('blocked_with_proof_no_reason'):
            grouped['context'].append(text)
        elif text.endswith('context_hygiene_parse_error'):
            grouped['context'].append(text)
        elif text.startswith('BLOCKED:') or text.startswith('IN_PROGRESS ') or text.startswith('TODO ') or text.startswith('review_') or text.endswith('watchdog_validate_parse_error') or text.endswith('watchdog_recover_parse_error'):
            grouped['task'].append(text)
        else:
            grouped['context'].append(text)
    return grouped


def next_sort_order(conn: sqlite3.Connection, bucket: str) -> int:
    row = conn.execute('SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM tasks WHERE bucket=?', (bucket,)).fetchone()
    return int((row[0] if row else 0) or 0) + 1


def build_context_metadata(context_payload: dict[str, Any], grouped_issues: list[str]) -> dict[str, str]:
    detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    required_action = str(detail.get('context_handoff_required_action') or '').strip() or str(detail.get('required_action') or '').strip() or '-'
    return {
        'active_ticket_id': str(detail.get('current_task_ticket_id') or '-'),
        'business_goal': str(detail.get('current_goal') or '-'),
        'business_next_action': str(detail.get('current_next_action') or '-'),
        'latest_proof': str(detail.get('current_latest_proof') or '-'),
        'handoff_file': str(detail.get('context_handoff_path') or '-'),
        'handoff_valid': str(detail.get('context_handoff_valid') if 'context_handoff_valid' in detail else '-'),
        'required_action': required_action,
    }


def upsert_maintenance_task(kind: str, grouped_issues: list[str], notify_text: str, metadata: dict[str, str] | None = None) -> None:
    spec = MAINTENANCE_TASK_SPECS[kind]
    now = now_ts()
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT * FROM tasks WHERE id=?', (spec['id'],)).fetchone()
        issue_preview = ' | '.join(grouped_issues[:10])
        note_lines = [
            'phase: watchdog_alert',
            f'runtime_state: issues={len(grouped_issues)}',
            f'last_update: {now}',
            f'watchdog_kind: {kind}',
            f'watchdog_issues: {issue_preview}',
            f'watchdog_notify: {notify_text}',
        ]
        if metadata:
            for key, value in metadata.items():
                note_lines.append(f'{key}: {value}')
        note = '\n'.join(note_lines)
        if row is None:
            sort_order = next_sort_order(conn, 'active')
            conn.execute(
                '''
                INSERT INTO tasks(
                    id, status, title, scope, priority, bucket,
                    note, blocked_reason, proof, proof_pending, proof_last,
                    assigned_by, owner, assignee, assigned_run_id, assigned_at, review_status, review_note, closed_by,
                    started_at, last_activity_at, resume_due,
                    extra_lines, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    spec['id'], 'IN_PROGRESS', spec['title'], spec['scope'], 'P0', 'active',
                    note, '', '', '', '',
                    'watchdog', 'watchdog', 'watchdog', '', '', '', '', '',
                    '', now, '', '[]', sort_order, now, now,
                ),
            )
        else:
            conn.execute(
                '''
                UPDATE tasks
                SET status='IN_PROGRESS', bucket='active', title=?, scope=?, priority='P0', note=?, blocked_reason='',
                    assigned_by='watchdog', owner='watchdog', assignee='watchdog', closed_by='', last_activity_at=?, updated_at=?
                WHERE id=?
                ''',
                (spec['title'], spec['scope'], note, now, now, spec['id']),
            )
        conn.commit()
    finally:
        conn.close()


def close_maintenance_task(kind: str) -> None:
    spec = MAINTENANCE_TASK_SPECS[kind]
    now = now_ts()
    conn = sqlite3.connect(str(TASKS_DB))
    try:
        conn.execute(
            '''
            UPDATE tasks
            SET status='DONE', bucket='done', note=?, closed_by='watchdog', last_activity_at=?, updated_at=?
            WHERE id=? AND status != 'DONE'
            ''',
            ('phase: watchdog_clear\nruntime_state: clean\nlast_update: ' + now, now, now, spec['id']),
        )
        conn.commit()
    finally:
        conn.close()


def reconcile_maintenance_tasks(issues: list[str], notify_text: str, context_payload: dict[str, Any]) -> dict[str, list[str]]:
    grouped = classify_issue_groups(issues)
    context_metadata = build_context_metadata(context_payload, grouped['context'])
    for kind, grouped_issues in grouped.items():
        if grouped_issues:
            metadata = context_metadata if kind == 'context' else None
            upsert_maintenance_task(kind, grouped_issues, notify_text, metadata)
        else:
            close_maintenance_task(kind)
    return grouped


def normalize_context_issue(issue: str) -> str:
    text = str(issue or '').strip()
    if text.startswith('context_reset_required:'):
        parts = text.split(':', 2)
        ticket_id = parts[1] if len(parts) > 1 else '-'
        return f'context_reset_required:{ticket_id}'
    return text


def handoff_requests_unlock(context_payload: dict[str, Any]) -> bool:
    detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    candidates: list[str] = []
    for key in ('unlock_requested', 'context_handoff_notes', 'context_handoff_required_action', 'required_action'):
        value = detail.get(key)
        if value is not None:
            candidates.append(str(value).strip().lower())

    handoff = detail.get('context_handoff')
    if isinstance(handoff, dict):
        candidates.append(str(handoff.get('notes') or '').strip().lower())
        candidates.append(str(handoff.get('required_action') or '').strip().lower())

    return any('unlock' in text or '언락' in text for text in candidates if text)


def context_requires_reset(context_payload: dict[str, Any]) -> bool:
    detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    if handoff_requests_unlock(context_payload):
        return False
    if detail.get('context_tokens_high'):
        return True
    required_action = str(detail.get('required_action') or detail.get('context_handoff_required_action') or '').strip()
    return required_action == 'finish_current_step_then_reset'


def has_active_non_maintenance_work(context_payload: dict[str, Any] | None = None) -> bool:
    detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    if 'active_execution_remaining' in detail:
        return bool(detail.get('active_execution_remaining'))

    if not TASKS_DB.exists():
        return False
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, status, note
            FROM tasks
            WHERE id NOT LIKE 'WD-%'
              AND status IN ('IN_PROGRESS', 'BLOCKED')
            ORDER BY datetime(updated_at) DESC, id DESC
            LIMIT 64
            """
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        status = str(row['status'] or '').strip().upper()
        if status == 'IN_PROGRESS':
            return True
        note = str(row['note'] or '')
        phase = ''
        for line in note.splitlines():
            if line.startswith('phase:'):
                phase = line.split(':', 1)[1].strip().lower()
                break
        if is_nonterminal_wait_state(status, phase):
            return True
    return False


def build_context_lock_state(
    context_payload: dict[str, Any],
    grouped_context_issues: list[str],
    existing_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    existing = existing_lock if isinstance(existing_lock, dict) else {}
    locked_at = str(existing.get('locked_at') or '').strip() or now_ts()
    return {
        'active': True,
        'locked_at': locked_at,
        'updated_at': now_ts(),
        'ticket_id': str(detail.get('current_task_ticket_id') or '-').strip() or '-',
        'trigger': str(detail.get('context_handoff_trigger') or detail.get('trigger') or 'context_threshold').strip() or 'context_threshold',
        'required_action': str(detail.get('required_action') or detail.get('context_handoff_required_action') or 'finish_current_step_then_reset').strip() or 'finish_current_step_then_reset',
        'handoff_file': str(detail.get('context_handoff_path') or '-').strip() or '-',
        'active_execution_remaining': bool(detail.get('active_execution_remaining')),
        'issues': sorted({normalize_context_issue(issue) for issue in grouped_context_issues if str(issue).strip()}),
    }


def sync_context_lock(context_payload: dict[str, Any], grouped_context_issues: list[str]) -> dict[str, Any]:
    existing_lock = load_context_lock()
    reset_required = context_requires_reset(context_payload)
    should_activate = bool(grouped_context_issues) and reset_required and not has_active_non_maintenance_work(context_payload)

    if should_activate:
        context_lock = build_context_lock_state(context_payload, grouped_context_issues, existing_lock)
        save_context_lock(context_lock)
        return context_lock

    if bool(existing_lock.get('active')) and reset_required:
        return existing_lock

    clear_context_lock()
    return {'active': False}


def build_notify_text(
    validate_payload: dict[str, Any],
    recover_payload: dict[str, Any],
    context_payload: dict[str, Any],
    issues: list[str],
    context_lock: dict[str, Any] | None = None,
) -> str:
    moved = recover_payload.get("moved", []) or []
    moved_preview = ", ".join(
        f"{m.get('id')}:{m.get('reason')}" for m in moved[:5] if m.get("id") and m.get("reason")
    )
    issue_preview = " | ".join(issues[:3])
    context_detail = (context_payload.get('detail') or {}) if isinstance(context_payload, dict) else {}
    ticket_id = str(context_detail.get('current_task_ticket_id') or '').strip()
    lock_mode = context_lock_mode(context_lock or {})
    lock_active = lock_mode != 'inactive'
    lock_blocking = is_blocking_context_lock(context_lock or {})
    severity = 'CONTEXT LOCK' if lock_blocking else ('CONTEXT NUDGE' if lock_active else 'watchdog alert')
    parts = [severity]
    if ticket_id and ticket_id != '-':
        parts.append(f"ticket={ticket_id}")
    if lock_blocking:
        parts.append('new_work_blocked')
    elif lock_active:
        parts.append('soft_advisory')
    if moved_preview:
        parts.append(f"blocked={moved_preview}")
    parts.append(f"issues={len(issues)}")
    if issue_preview:
        parts.append(issue_preview)
    required_action = str(context_detail.get('required_action') or context_detail.get('context_handoff_required_action') or '').strip()
    if required_action == 'finish_current_step_then_reset':
        if lock_blocking:
            parts.append("reset 전까지 신규 task/spawn/dispatch 잠금. 지금 current step 정리 후 reset → 새 세션에서 runtime/context-handoff.md 읽고 next_action 재개 → WD-CONTEXT-HYGIENE 완료")
        else:
            parts.append("wake/remind/retry 우선. 현재 step 완료 후 reset → 새 세션에서 runtime/context-handoff.md 읽고 next_action 재개 → WD-CONTEXT-HYGIENE 완료")
    else:
        if lock_blocking:
            parts.append("hard lock active: current-task·context-handoff·proof 정리와 reset/unlock만 허용")
        elif lock_active:
            parts.append("soft advisory active: current-task·context-handoff·proof 정리 우선, 신규 진행은 허용")
        else:
            parts.append("현재 step 완료 후 reset·proof·보고·후속정리")
    return " / ".join(parts)


def emit_main_event(text: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["openclaw", "system", "event", "--text", text, "--mode", "now"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip()[-1000:],
        "stderr": (proc.stderr or "").strip()[-1000:],
    }


def main() -> int:
    validate_payload = run_json_script(VALIDATE_SCRIPT)
    recover_payload = run_json_script(RECOVER_SCRIPT)
    context_payload = run_json_script(CONTEXT_HYGIENE_SCRIPT)
    issues = normalize_issues(validate_payload, recover_payload, context_payload)
    last_state = load_state()

    notify = {"sent": False, "deduped": False, "text": "", "event": None, "severity": "info", "context_lock": None}
    grouped_tasks = {'task': [], 'context': []}
    if issues:
        grouped_tasks = classify_issue_groups(issues)
        context_lock = sync_context_lock(context_payload, grouped_tasks['context'])
        text = build_notify_text(validate_payload, recover_payload, context_payload, issues, context_lock)
        grouped_tasks = reconcile_maintenance_tasks(issues, text, context_payload)
        signature = json.dumps(
            {
                "issues": issues,
                "context_lock_mode": context_lock_mode(context_lock),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        last_signature = str(last_state.get("signature") or "")
        notify["text"] = text
        notify["severity"] = "critical" if is_blocking_context_lock(context_lock) else "warning"
        notify["context_lock"] = context_lock
        if signature != last_signature:
            event_result = emit_main_event(text)
            notify["event"] = event_result
            notify["sent"] = bool(event_result.get("ok"))
            save_state({
                "updated_at": now_ts(),
                "signature": signature,
                "text": text,
                "issues": issues,
                "sent": notify["sent"],
                "context_lock": context_lock,
            })
        else:
            notify["deduped"] = True
    else:
        clear_state()
        clear_context_lock()
        grouped_tasks = reconcile_maintenance_tasks([], '', context_payload)

    result = {
        "ok": bool(validate_payload.get("ok", False)) and bool(recover_payload.get("ok", False)),
        "checked_at": now_ts(),
        "validate": validate_payload,
        "recover": recover_payload,
        "context_hygiene": context_payload,
        "issues": issues,
        "maintenance_tasks": grouped_tasks,
        "notify": notify,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
