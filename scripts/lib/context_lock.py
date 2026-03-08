from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.runtime_env import context_lock_path

LOCK_PATH = context_lock_path()


def now_ts() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_context_lock() -> dict[str, Any]:
    if not LOCK_PATH.exists():
        return {}
    try:
        payload = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def save_context_lock(payload: dict[str, Any]) -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def clear_context_lock() -> None:
    if LOCK_PATH.exists():
        LOCK_PATH.unlink()


def is_context_locked() -> tuple[bool, dict[str, Any]]:
    payload = load_context_lock()
    return bool(payload.get('active')), payload


def format_lock_reason(payload: dict[str, Any]) -> str:
    if not payload:
        return 'context_lock_active'
    ticket = str(payload.get('ticket_id') or '-').strip() or '-'
    trigger = str(payload.get('trigger') or 'context_threshold').strip() or 'context_threshold'
    required_action = str(payload.get('required_action') or 'reset_required').strip() or 'reset_required'
    return f'context_lock_active ticket={ticket} trigger={trigger} required_action={required_action}'
