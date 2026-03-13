#!/usr/bin/env python3
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TASK_DB = ROOT / "runtime/tasks/tasks.db"
TASKS_DIR = ROOT / "runtime/tasks"
CURRENT_TASK_PATH = ROOT / "runtime/current-task.md"

CLOSED_STATUSES = {"DONE", "CANCELLED", "ARCHIVED"}
ACTIVE_PROGRESS_STATUSES = {"IN_PROGRESS", "RUNNING", "VERIFYING", "READY_FOR_REVIEW"}

STATUS_LAMP = {
    "IN_PROGRESS": "blue",
    "RUNNING": "blue",
    "READY_FOR_REVIEW": "green",
    "VERIFIED": "green",
    "DONE": "green",
    "BLOCKED": "red",
    "FAILED": "red",
    "CANCELLED": "slate",
    "ARCHIVED": "slate",
    "READY": "amber",
    "PENDING": "amber",
    "WAITING": "amber",
}

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
KV_RE = re.compile(r"^-\s+([A-Za-z0-9_]+):\s*(.*)$")
BACKTICK_PATH_RE = re.compile(r"`([^`\n]+(?:/[^`\n]+)+)`")
PATHISH_RE = re.compile(r"(?<![A-Za-z0-9_./-])((?:docs|scripts|runtime|invest|memory|review_repo)/[A-Za-z0-9_./:-]+)")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _sanitize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_") or "section"


def parse_markdown_report(text: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current = "head"
    sections[current] = []

    for raw in text.splitlines():
        heading = SECTION_RE.match(raw)
        if heading:
            current = _sanitize_heading(heading.group(1))
            sections.setdefault(current, [])
            continue
        bullet = KV_RE.match(raw)
        if bullet and current == "head":
            key = _sanitize_heading(bullet.group(1))
            fields[key] = bullet.group(2).strip()
            continue
        sections.setdefault(current, []).append(raw)

    normalized_sections = {
        key: "\n".join(lines).strip()
        for key, lines in sections.items()
        if "\n".join(lines).strip()
    }
    return {"fields": fields, "sections": normalized_sections}


def section_items(text: str) -> list[str]:
    items: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[-*]\s+", "", stripped)
        stripped = re.sub(r"^\d+[.)]\s+", "", stripped)
        if stripped:
            items.append(stripped)
    return items


def extract_paths(text: str) -> list[str]:
    found = BACKTICK_PATH_RE.findall(text)
    found.extend(PATHISH_RE.findall(text))
    return unique_preserve(found)


def status_lamp(status: str) -> str:
    return STATUS_LAMP.get(_clean(status).upper(), "slate")


def load_current_task_card() -> dict[str, Any]:
    text = safe_read_text(CURRENT_TASK_PATH)
    if not text:
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = KV_RE.match(line)
        if not match:
            continue
        fields[_sanitize_heading(match.group(1))] = match.group(2).strip()
    touched = [part.strip() for part in fields.get("touched_paths", "").split(",") if part.strip()]
    fields["touched_paths"] = touched
    fields["source_path"] = str(CURRENT_TASK_PATH.relative_to(ROOT))
    return fields


def load_all_tasks() -> list[dict[str, Any]]:
    if not TASK_DB.exists():
        return []
    try:
        con = sqlite3.connect(TASK_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select
                id, status, title, scope, priority, bucket, note,
                blocked_reason, proof, proof_pending, proof_last,
                owner, assignee, assigned_run_id, review_status,
                started_at, last_activity_at, resume_due,
                created_at, updated_at
            from tasks
            order by updated_at desc, created_at desc
            """
        ).fetchall()
    except Exception:
        return []
    finally:
        try:
            con.close()
        except Exception:
            pass
    return [dict(row) for row in rows]


def compact_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", _clean(value))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_task_stub(row: dict[str, Any], current_task: dict[str, Any] | None = None) -> dict[str, Any]:
    ticket_id = _clean(row.get("id"))
    current_task = current_task or {}
    is_current = _clean(current_task.get("ticket_id")) == ticket_id
    summary = compact_text(first_non_empty(
        current_task.get("current_goal") if is_current else "",
        row.get("note"),
        row.get("scope"),
        row.get("blocked_reason"),
    ))
    return {
        "ticket_id": ticket_id,
        "title": _clean(row.get("title")) or ticket_id,
        "status": _clean(row.get("status")) or "미확인",
        "lamp": status_lamp(row.get("status", "")),
        "priority": _clean(row.get("priority")),
        "bucket": _clean(row.get("bucket")),
        "owner": _clean(row.get("owner")),
        "assignee": _clean(row.get("assignee")),
        "assigned_run_id": _clean(row.get("assigned_run_id")),
        "updated_at": _clean(row.get("updated_at")),
        "last_activity_at": _clean(row.get("last_activity_at")),
        "summary": summary,
        "is_current": is_current,
    }


def get_task_row(ticket_id: str) -> dict[str, Any]:
    target = _clean(ticket_id)
    if not target:
        return {}
    for row in load_all_tasks():
        if _clean(row.get("id")) == target:
            return row
    return {}


def get_task_report_path(ticket_id: str) -> Path:
    return TASKS_DIR / f"{ticket_id}.md"


def get_task_detail(ticket_id: str) -> dict[str, Any]:
    target = _clean(ticket_id)
    row = get_task_row(target)
    current_task = load_current_task_card()
    report_path = get_task_report_path(target)
    report_text = safe_read_text(report_path)
    parsed = parse_markdown_report(report_text) if report_text else {"fields": {}, "sections": {}}
    fields = parsed.get("fields", {})
    sections = parsed.get("sections", {})
    is_current = _clean(current_task.get("ticket_id")) == target

    accomplished_items = section_items(first_non_empty(sections.get("actions_done"), sections.get("accomplished"), sections.get("result")))
    next_items = section_items(first_non_empty(sections.get("next"), sections.get("next_action")))
    proof_items = section_items(first_non_empty(sections.get("proof_log"), sections.get("verification"), sections.get("proof")))

    touched_paths = []
    if is_current:
        touched_paths.extend(current_task.get("touched_paths", []))
    touched_paths.extend(extract_paths(report_text))
    touched_paths = unique_preserve(touched_paths)[:24]

    latest_proof = first_non_empty(
        current_task.get("latest_proof") if is_current else "",
        row.get("proof_last"),
        row.get("proof"),
        fields.get("proof"),
        proof_items[-1] if proof_items else "",
        str(report_path.relative_to(ROOT)) if report_text else "",
    )

    detail = {
        "ticket_id": target,
        "title": first_non_empty(row.get("title"), target),
        "status": first_non_empty(row.get("status"), fields.get("status"), "미확인"),
        "lamp": status_lamp(first_non_empty(row.get("status"), fields.get("status"))),
        "priority": _clean(row.get("priority")),
        "bucket": _clean(row.get("bucket")),
        "owner": _clean(row.get("owner")),
        "assignee": _clean(row.get("assignee")),
        "assigned_run_id": _clean(row.get("assigned_run_id")),
        "updated_at": first_non_empty(row.get("updated_at"), fields.get("updated_at")),
        "last_activity_at": _clean(row.get("last_activity_at")),
        "resume_due": _clean(row.get("resume_due")),
        "review_status": _clean(row.get("review_status")),
        "current_goal": first_non_empty(current_task.get("current_goal") if is_current else "", fields.get("goal"), sections.get("goal")),
        "last_completed_step": first_non_empty(
            current_task.get("last_completed_step") if is_current else "",
            accomplished_items[-1] if accomplished_items else "",
            fields.get("close_recommendation"),
        ),
        "next_action": first_non_empty(
            current_task.get("next_action") if is_current else "",
            next_items[0] if next_items else "",
            fields.get("next"),
        ),
        "latest_proof": latest_proof,
        "touched_paths": touched_paths,
        "blocked_reason": first_non_empty(row.get("blocked_reason"), fields.get("blocked_reason")),
        "notes": first_non_empty(current_task.get("notes") if is_current else "", fields.get("why"), sections.get("notes"), row.get("note")),
        "report_path": str(report_path.relative_to(ROOT)) if report_text else "",
        "proof_paths": unique_preserve(extract_paths(latest_proof + "\n" + first_non_empty(sections.get("verification"), sections.get("proof"))))[:12],
        "raw_fields": fields,
        "raw_sections": sections,
        "available": bool(row or report_text or is_current),
        "degraded_fields": [
            name for name, value in {
                "current_goal": first_non_empty(current_task.get("current_goal") if is_current else "", fields.get("goal"), sections.get("goal")),
                "last_completed_step": first_non_empty(current_task.get("last_completed_step") if is_current else "", accomplished_items[-1] if accomplished_items else "", fields.get("close_recommendation")),
                "next_action": first_non_empty(current_task.get("next_action") if is_current else "", next_items[0] if next_items else "", fields.get("next")),
                "latest_proof": latest_proof,
                "touched_paths": ",".join(touched_paths),
            }.items() if not _clean(value)
        ],
    }
    return detail


if __name__ == "__main__":
    import json
    import sys

    ticket = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = get_task_detail(ticket) if ticket else {
        "current_task": load_current_task_card(),
        "tasks": [build_task_stub(row, load_current_task_card()) for row in load_all_tasks()[:20]],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
