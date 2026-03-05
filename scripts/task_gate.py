#!/usr/bin/env python3
"""Fail-close gate: ticket must exist and be IN_PROGRESS."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (args.ticket,)).fetchone()
    except sqlite3.Error as exc:
        print(f"gate fail: db error ({exc})", file=sys.stderr)
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

    print(f"gate pass: {args.ticket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
