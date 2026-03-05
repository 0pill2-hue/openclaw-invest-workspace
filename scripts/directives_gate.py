#!/usr/bin/env python3
"""Fail-close gate: directive must exist and be IN_PROGRESS."""

from __future__ import annotations

import argparse
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

    try:
        row = conn.execute("SELECT status FROM directives WHERE id=?", (args.id,)).fetchone()
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

    print(f"gate pass: {args.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
