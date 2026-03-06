#!/usr/bin/env python3
"""Fail-close gate: directive must exist and be IN_PROGRESS."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "runtime/directives/directives.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="DIRECTIVES execution gate")
    parser.add_argument("--id", required=True, help="Directive ID")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"gate fail: db not found ({db_path})", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    strict = os.environ.get("OPENCLAW_GATE_STRICT", "0").strip() == "1"
    expected_assignee = os.environ.get("OPENCLAW_ASSIGNEE", "main").strip() or "main"
    expected_run_id = os.environ.get("OPENCLAW_RUN_ID", "").strip()

    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(directives)").fetchall()}
        selected = ["status"]
        if "assignee" in cols:
            selected.append("assignee")
        if "assigned_run_id" in cols:
            selected.append("assigned_run_id")
        if "review_status" in cols:
            selected.append("review_status")
        row = conn.execute(f"SELECT {', '.join(selected)} FROM directives WHERE id=?", (args.id,)).fetchone()
    except sqlite3.Error as exc:
        print(f"gate fail: db error ({exc})", file=sys.stderr)
        return 2

    if row is None:
        print(f"gate fail: directive not found ({args.id})", file=sys.stderr)
        return 2

    if row["status"] != "IN_PROGRESS":
        print(
            f"gate fail: directive status must be IN_PROGRESS (id={args.id}, status={row['status']})",
            file=sys.stderr,
        )
        return 2

    if strict:
        if "assignee" in row.keys():
            assignee = (row["assignee"] or "").strip()
            if assignee and assignee != expected_assignee:
                print(f"gate fail: assignee mismatch (expected={expected_assignee}, actual={assignee})", file=sys.stderr)
                return 2
        if expected_run_id and "assigned_run_id" in row.keys():
            assigned_run_id = (row["assigned_run_id"] or "").strip()
            if assigned_run_id and assigned_run_id != expected_run_id:
                print(f"gate fail: run_id mismatch (expected={expected_run_id}, actual={assigned_run_id})", file=sys.stderr)
                return 2
        if "review_status" in row.keys():
            review_status = (row["review_status"] or "").strip().upper()
            if review_status == "REJECTED":
                print("gate fail: review_status is REJECTED", file=sys.stderr)
                return 2

    print(f"gate pass: {args.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
