#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from read_tasks import ACTIVE_PROGRESS_STATUSES, CLOSED_STATUSES, build_task_stub, load_all_tasks, load_current_task_card

ROOT = Path(__file__).resolve().parents[2]
BRAINS_MD = ROOT / "docs/operations/runtime/BRAINS.md"
LOCAL_BRAIN_LOG = ROOT / "runtime/heartbeat/local_brain_guard.launchd.log"
WATCHDOG_STATE = ROOT / "runtime/tasks/watchdog_notify_state.json"
AUTO_DISPATCH_STATE = ROOT / "runtime/tasks/auto_dispatch_status.json"
PROVIDER_CACHE = ROOT / "runtime/dashboard/provider_usage_cache.json"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def tail_json_line(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > 65536:
                fh.seek(size - 65536)
            text = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return {}
    for raw in reversed(text.splitlines()):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def load_provider_cache() -> dict[str, Any]:
    default_payload = {
        "updated_at": "",
        "providers": [
            {
                "id": "main-brain",
                "label": "Main Brain",
                "used": 0,
                "limit": 100,
                "unit": "%",
                "window": "cached",
                "status": "unknown",
                "note": "No cached provider quota snapshot yet."
            },
            {
                "id": "local-brain",
                "label": "Local Brain",
                "used": 0,
                "limit": 100,
                "unit": "%",
                "window": "cached",
                "status": "unknown",
                "note": "No cached provider quota snapshot yet."
            }
        ]
    }
    payload = safe_load_json(PROVIDER_CACHE, default_payload)
    providers = payload.get("providers") if isinstance(payload, dict) else None
    if not isinstance(providers, list) or not providers:
        return default_payload

    normalized = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        used = provider.get("used", 0)
        limit = provider.get("limit", 100)
        try:
            used_value = float(used)
        except Exception:
            used_value = 0.0
        try:
            limit_value = float(limit)
        except Exception:
            limit_value = 100.0
        percent = 0.0 if limit_value <= 0 else max(0.0, min(100.0, (used_value / limit_value) * 100.0))
        normalized.append({
            "id": _clean(provider.get("id")) or _clean(provider.get("label")) or "provider",
            "label": _clean(provider.get("label")) or _clean(provider.get("id")) or "Provider",
            "used": used_value,
            "limit": limit_value,
            "percent": round(percent, 2),
            "unit": _clean(provider.get("unit")) or "%",
            "window": _clean(provider.get("window")) or "cached",
            "status": _clean(provider.get("status")) or "unknown",
            "note": _clean(provider.get("note")),
        })
    return {
        "updated_at": _clean(payload.get("updated_at")),
        "providers": normalized or default_payload["providers"],
    }


def load_brain_context(current_task: dict[str, Any]) -> dict[str, Any]:
    brains_doc = safe_read_text(BRAINS_MD)
    local_guard = tail_json_line(LOCAL_BRAIN_LOG)
    return {
        "main": {
            "label": "GPT-5.4 (메인)",
            "role": "설계·판단·코딩·검증·최종 결정",
            "current_ticket": _clean(current_task.get("ticket_id")),
            "current_goal": _clean(current_task.get("current_goal")),
            "next_action": _clean(current_task.get("next_action")),
            "latest_proof": _clean(current_task.get("latest_proof")),
        },
        "local": {
            "label": "로컬뇌 (보조)",
            "role": "폴백·요약·크롤링·배치·단순 지원",
            "ok": bool(local_guard.get("ok")) if local_guard else None,
            "checked_at": _clean(local_guard.get("checked_at")),
            "message": _clean(local_guard.get("message") or local_guard.get("alert")),
            "issues": local_guard.get("issues", []) if isinstance(local_guard.get("issues"), list) else [],
            "session_rotate_reason": _clean(local_guard.get("session_rotate_reason")),
        },
        "policy_excerpt": brains_doc.strip().splitlines()[:14],
        "quota": load_provider_cache(),
    }


def classify_tasks(tasks: list[dict[str, Any]], current_task: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    main_in_progress: list[dict[str, Any]] = []
    subagent_in_progress: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []

    for row in tasks:
        status = _clean(row.get("status")).upper()
        if status in CLOSED_STATUSES:
            continue
        stub = build_task_stub(row, current_task)
        assignee = _clean(row.get("assignee"))
        if status in ACTIVE_PROGRESS_STATUSES and assignee.startswith("subagent:"):
            subagent_in_progress.append(stub)
        elif status in ACTIVE_PROGRESS_STATUSES:
            main_in_progress.append(stub)
        else:
            remaining.append(stub)

    return {
        "mainInProgress": main_in_progress,
        "subagentInProgress": subagent_in_progress,
        "remaining": remaining,
    }


def build_overview() -> dict[str, Any]:
    current_task = load_current_task_card()
    tasks = load_all_tasks()
    grouped = classify_tasks(tasks, current_task)
    watchdog = safe_load_json(WATCHDOG_STATE, {})
    auto_dispatch = safe_load_json(AUTO_DISPATCH_STATE, {})

    payload = {
        "available": True,
        "currentTask": current_task,
        "taskGroups": grouped,
        "counts": {
            "mainInProgress": len(grouped["mainInProgress"]),
            "subagentInProgress": len(grouped["subagentInProgress"]),
            "remaining": len(grouped["remaining"]),
            "openTotal": sum(len(grouped[key]) for key in grouped),
        },
        "brains": load_brain_context(current_task),
        "guardCards": {
            "watchdog": {
                "label": "Watchdog",
                "status": "locked" if bool(((watchdog.get("context_lock") or {}).get("active"))) else ("warn" if watchdog.get("issues") else "ok"),
                "updated_at": _clean(watchdog.get("updated_at")),
                "text": _clean(watchdog.get("text")),
                "issues": watchdog.get("issues", []) if isinstance(watchdog.get("issues"), list) else [],
                "sent": bool(watchdog.get("sent")),
                "context_lock": bool(((watchdog.get("context_lock") or {}).get("active"))),
                "source": str(WATCHDOG_STATE.relative_to(ROOT)),
            },
            "autoDispatch": {
                "label": "Auto-dispatch",
                "status": _clean(auto_dispatch.get("status")) or "unknown",
                "assigned_ticket": _clean(auto_dispatch.get("assigned_ticket")),
                "orchestrator": _clean(auto_dispatch.get("orchestrator")),
                "error": _clean(auto_dispatch.get("error")),
                "updated_at": _clean(auto_dispatch.get("ts")),
                "source": str(AUTO_DISPATCH_STATE.relative_to(ROOT)),
            },
            "localGuard": {
                "label": "Local brain guard",
                **load_brain_context(current_task).get("local", {}),
                "source": str(LOCAL_BRAIN_LOG.relative_to(ROOT)),
            },
        },
        "sources": {
            "tasks_db": "runtime/tasks/tasks.db",
            "current_task": "runtime/current-task.md",
            "watchdog_state": str(WATCHDOG_STATE.relative_to(ROOT)),
            "auto_dispatch_state": str(AUTO_DISPATCH_STATE.relative_to(ROOT)),
            "provider_usage_cache": str(PROVIDER_CACHE.relative_to(ROOT)),
            "local_brain_log": str(LOCAL_BRAIN_LOG.relative_to(ROOT)),
        },
    }
    return payload


if __name__ == "__main__":
    print(json.dumps(build_overview(), ensure_ascii=False, indent=2))
