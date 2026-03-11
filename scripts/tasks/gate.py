#!/usr/bin/env python3
"""Fail-close gate: ticket must exist and be IN_PROGRESS."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.context_lock import format_lock_reason, is_blocking_context_lock, is_context_locked

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT / "runtime/tasks/tasks.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="TASK execution gate")
    parser.add_argument("--ticket", required=True, help="Ticket ID (JB-YYYYMMDD-###)")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"gate fail: db not found ({db_path})", file=sys.stderr)
        return 2

    locked, lock_payload = is_context_locked()
    if locked and is_blocking_context_lock(lock_payload) and not args.ticket.upper().startswith("WD-"):
        print(f"gate fail: {format_lock_reason(lock_payload)}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    strict = os.environ.get("OPENCLAW_GATE_STRICT", "0").strip() == "1"
    expected_assignee = os.environ.get("OPENCLAW_ASSIGNEE", "main").strip() or "main"
    expected_run_id = os.environ.get("OPENCLAW_RUN_ID", "").strip()

    try:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (args.ticket,)).fetchone()
        maintenance_rows = conn.execute(
            """
            SELECT id, status, title, note
            FROM tasks
            WHERE id LIKE 'WD-%'
              AND bucket='active'
              AND status IN ('TODO', 'IN_PROGRESS')
            ORDER BY id
            """
        ).fetchall()
    except sqlite3.Error as exc:
        print(f"gate fail: db error ({exc})", file=sys.stderr)
        return 2

    blocking_maintenance_ids: list[str] = []
    for maintenance_row in maintenance_rows:
        maintenance_id = str(maintenance_row['id'])
        note = str(maintenance_row['note'] or '')
        if maintenance_id == 'WD-CONTEXT-HYGIENE':
            if 'required_action: clean_reset' not in note and 'required_action: hard_reset' not in note:
                continue
        blocking_maintenance_ids.append(maintenance_id)

    if blocking_maintenance_ids:
        if args.ticket not in blocking_maintenance_ids:
            print(
                f"gate fail: maintenance task active (active={','.join(blocking_maintenance_ids)}; requested={args.ticket})",
                file=sys.stderr,
            )
            return 2

    if row is None:
        print(f"gate fail: ticket not found ({args.ticket})", file=sys.stderr)
        return 2

    if row["status"] != "IN_PROGRESS":
        print(
            f"gate fail: ticket status must be IN_PROGRESS (ticket={args.ticket}, status={row['status']})",
            file=sys.stderr,
        )
        return 2

    if strict:
        assignee = (row["assignee"] or "").strip() if "assignee" in row.keys() else ""
        assigned_run_id = (row["assigned_run_id"] or "").strip() if "assigned_run_id" in row.keys() else ""
        review_status = (row["review_status"] or "").strip().upper() if "review_status" in row.keys() else ""

        if assignee and assignee != expected_assignee:
            print(f"gate fail: assignee mismatch (expected={expected_assignee}, actual={assignee})", file=sys.stderr)
            return 2
        if expected_run_id and assigned_run_id and assigned_run_id != expected_run_id:
            print(f"gate fail: run_id mismatch (expected={expected_run_id}, actual={assigned_run_id})", file=sys.stderr)
            return 2
        if review_status == "REJECTED":
            print("gate fail: review_status is REJECTED", file=sys.stderr)
            return 2

    print(f"gate pass: {args.ticket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
