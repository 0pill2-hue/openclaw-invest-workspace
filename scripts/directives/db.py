#!/usr/bin/env python3
"""SQLite-backed DIRECTIVES ledger CLI."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.runtime_env import DIRECTIVES_DB
from lib.context_lock import format_lock_reason, is_context_locked

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = DIRECTIVES_DB
DEFAULT_DIRECTIVES_MD_PATH = ROOT / "DIRECTIVES.md"
DEFAULT_ARCHIVE_MD_PATH = ROOT / "runtime/directives/directives_archive.md"

ALLOWED_STATUS = {"OPEN", "IN_PROGRESS", "BLOCKED", "DONE"}
JB_ID_RE = re.compile(r"JB-\d{8}-\d{3}")


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS directives (
            id TEXT PRIMARY KEY,
            directive TEXT NOT NULL,
            due TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('OPEN', 'IN_PROGRESS', 'BLOCKED', 'DONE')),
            first_action TEXT NOT NULL,
            proof TEXT NOT NULL,
            blocked_reason TEXT NOT NULL DEFAULT '',
            source_line INTEGER,
            source_raw TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_directives_status ON directives(status);
        """
    )
    conn.commit()


def normalize_status(raw_status: str) -> str:
    text = (raw_status or "").strip().upper()
    if text in ALLOWED_STATUS:
        return text
    for candidate in ALLOWED_STATUS:
        if candidate in text:
            return candidate
    return "OPEN"


def strip_prefix(text: str, key: str) -> str:
    raw = (text or "").strip()
    if raw.lower().startswith(key.lower()):
        return raw[len(key) :].strip()
    return raw


def choose_source_path(raw_source: Optional[str]) -> Path:
    if raw_source:
        return Path(raw_source).expanduser().resolve()
    if DEFAULT_ARCHIVE_MD_PATH.exists():
        return DEFAULT_ARCHIVE_MD_PATH
    return DEFAULT_DIRECTIVES_MD_PATH


def parse_line(raw_line: str, line_no: int, seen_ids: set[str]) -> Dict[str, str]:
    parts = [p.strip() for p in raw_line.split("|")]

    def field(idx: int) -> str:
        return parts[idx] if idx < len(parts) else ""

    raw_id = field(1)
    directive = field(2)
    due = field(3)
    status = normalize_status(field(4))
    first_action = strip_prefix(field(5), "first_action:")
    proof = strip_prefix(" | ".join(parts[6:]).strip(), "proof:")

    directive_id = raw_id.strip()
    if directive_id in {"", "미확인", "-"}:
        ticket_match = JB_ID_RE.search(raw_line)
        directive_id = ticket_match.group(0) if ticket_match else "미확인"

    if not directive_id:
        directive_id = "미확인"

    if directive_id == "미확인":
        directive_id = f"미확인-{line_no:04d}"
        while directive_id in seen_ids:
            directive_id = f"{directive_id}-dup"

    seen_ids.add(directive_id)

    return {
        "id": directive_id,
        "directive": directive if directive else "미확인",
        "due": due if due else "미확인",
        "status": status,
        "first_action": first_action if first_action else "미확인",
        "proof": proof if proof else "미확인",
        "source_line": str(line_no),
        "source_raw": raw_line,
    }


def upsert_directive(
    conn: sqlite3.Connection,
    *,
    directive_id: str,
    directive: str,
    due: str,
    status: str,
    first_action: str,
    proof: str,
    blocked_reason: str,
    source_line: Optional[int],
    source_raw: str,
) -> None:
    existing = conn.execute("SELECT created_at FROM directives WHERE id=?", (directive_id,)).fetchone()
    created_at = existing["created_at"] if existing else now_ts()

    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO directives(
                id, directive, due, status, first_action, proof,
                blocked_reason, source_line, source_raw, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                directive_id,
                directive,
                due,
                status,
                first_action,
                proof,
                blocked_reason,
                source_line,
                source_raw,
                created_at,
                now_ts(),
            ),
        )


def cmd_init(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    print(f"initialized: {Path(args.db).expanduser().resolve()}")
    return 0


def _context_lock_blocks_new_id(raw_id: str) -> bool:
    directive_id = (raw_id or '').strip().upper()
    return not directive_id.startswith('WD-')


def cmd_add(args: argparse.Namespace) -> int:
    locked, lock_payload = is_context_locked()
    if locked and _context_lock_blocks_new_id(args.id):
        print(format_lock_reason(lock_payload), file=sys.stderr)
        return 2

    status = args.status.upper()
    if status not in ALLOWED_STATUS:
        print(f"invalid status: {status}", file=sys.stderr)
        return 1

    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    upsert_directive(
        conn,
        directive_id=args.id,
        directive=args.directive,
        due=args.due,
        status=status,
        first_action=args.first_action,
        proof=args.proof,
        blocked_reason="",
        source_line=None,
        source_raw="",
    )
    print(f"added: {args.id}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT blocked_reason FROM directives WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"directive not found: {args.id}", file=sys.stderr)
        return 1

    with conn:
        conn.execute(
            "UPDATE directives SET status='IN_PROGRESS', blocked_reason='', updated_at=? WHERE id=?",
            (now_ts(), args.id),
        )
    print(f"started: {args.id}")
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT id FROM directives WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"directive not found: {args.id}", file=sys.stderr)
        return 1

    with conn:
        conn.execute(
            "UPDATE directives SET status='BLOCKED', blocked_reason=?, updated_at=? WHERE id=?",
            (args.reason, now_ts(), args.id),
        )
    print(f"blocked: {args.id}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT id FROM directives WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"directive not found: {args.id}", file=sys.stderr)
        return 1

    with conn:
        conn.execute(
            "UPDATE directives SET status='DONE', proof=?, blocked_reason='', updated_at=? WHERE id=?",
            (args.proof, now_ts(), args.id),
        )
    print(f"done: {args.id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)

    statuses = [s.upper() for s in (args.status or [])]
    for status in statuses:
        if status not in ALLOWED_STATUS:
            print(f"invalid status filter: {status}", file=sys.stderr)
            return 1

    sql = "SELECT id, status, due, directive FROM directives"
    params: List[str] = []
    if statuses:
        sql += " WHERE status IN ({})".format(",".join(["?"] * len(statuses)))
        params.extend(statuses)

    sql += " ORDER BY CASE status WHEN 'IN_PROGRESS' THEN 1 WHEN 'OPEN' THEN 2 WHEN 'BLOCKED' THEN 3 WHEN 'DONE' THEN 4 ELSE 5 END, COALESCE(source_line, 999999), id"

    rows = conn.execute(sql, params).fetchall()
    for row in rows:
        print(f"{row['id']}\t{row['status']}\t{row['due']}\t{row['directive']}")
    print(f"count={len(rows)}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    if args.top < 0 or args.recent < 0:
        print("--top/--recent must be >= 0", file=sys.stderr)
        return 1

    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)

    counts = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress,
            SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open,
            SUM(CASE WHEN status='BLOCKED' THEN 1 ELSE 0 END) AS blocked,
            SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS done
        FROM directives
        """
    ).fetchone()

    in_progress_rows = conn.execute(
        """
        SELECT id, due, directive
        FROM directives
        WHERE status='IN_PROGRESS'
        ORDER BY due, COALESCE(source_line, 999999), id
        LIMIT ?
        """,
        (args.top,),
    ).fetchall()

    recent_rows = conn.execute(
        """
        SELECT id, status, updated_at, directive
        FROM directives
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT ?
        """,
        (args.recent,),
    ).fetchall()

    print("== DIRECTIVES SUMMARY ==")
    print(
        "total={total} | IN_PROGRESS={in_progress} | OPEN={open} | BLOCKED={blocked} | DONE={done}".format(
            total=counts["total"] or 0,
            in_progress=counts["in_progress"] or 0,
            open=counts["open"] or 0,
            blocked=counts["blocked"] or 0,
            done=counts["done"] or 0,
        )
    )
    print("")

    print(f"[in-progress top {args.top}]")
    if in_progress_rows:
        for row in in_progress_rows:
            print(f"- {row['id']} | {row['due']} | {row['directive']}")
    else:
        print("- (empty)")

    print("")
    print(f"[recent {args.recent} updates]")
    if recent_rows:
        for row in recent_rows:
            print(f"- {row['id']} | {row['status']} | {row['updated_at']} | {row['directive']}")
    else:
        print("- (empty)")

    return 0


def cmd_import_md(args: argparse.Namespace) -> int:
    source_path = choose_source_path(args.source)
    if not source_path.exists():
        print(f"source not found: {source_path}", file=sys.stderr)
        return 1

    lines = source_path.read_text(encoding="utf-8").splitlines()
    rows: List[Dict[str, str]] = []
    seen_ids: set[str] = set()

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        if "|" not in stripped:
            continue
        rows.append(parse_line(stripped[2:].strip(), line_no, seen_ids))

    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)

    with conn:
        conn.execute("DELETE FROM directives")

    for row in rows:
        upsert_directive(
            conn,
            directive_id=row["id"],
            directive=row["directive"],
            due=row["due"],
            status=row["status"],
            first_action=row["first_action"],
            proof=row["proof"],
            blocked_reason="",
            source_line=int(row["source_line"]),
            source_raw=row["source_raw"],
        )

    unconfirmed = sum(1 for row in rows if row["id"].startswith("미확인-"))
    print(f"imported: {len(rows)} from {source_path}")
    if unconfirmed:
        print(f"unconfirmed={unconfirmed}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DIRECTIVES SQLite ledger CLI")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create schema")

    p_add = sub.add_parser("add", help="Add or update directive")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--directive", required=True)
    p_add.add_argument("--due", required=True)
    p_add.add_argument("--status", required=True)
    p_add.add_argument("--first_action", required=True)
    p_add.add_argument("--proof", required=True)

    p_start = sub.add_parser("start", help="Set directive to IN_PROGRESS")
    p_start.add_argument("--id", required=True)

    p_block = sub.add_parser("block", help="Set directive to BLOCKED")
    p_block.add_argument("--id", required=True)
    p_block.add_argument("--reason", required=True)

    p_done = sub.add_parser("done", help="Set directive to DONE")
    p_done.add_argument("--id", required=True)
    p_done.add_argument("--proof", required=True)

    p_list = sub.add_parser("list", help="List directives")
    p_list.add_argument("--status", nargs="*", help="Status filter(s)")

    p_summary = sub.add_parser("summary", help="Human-friendly directives summary")
    p_summary.add_argument("--top", type=int, default=5, help="Top N in-progress directives (default: 5)")
    p_summary.add_argument("--recent", type=int, default=5, help="Recent N updates (default: 5)")

    p_import = sub.add_parser("import-md", help="Import directives from markdown ledger")
    p_import.add_argument(
        "--source",
        default="",
        help="Source markdown path (default: runtime/directives/directives_archive.md if exists, else DIRECTIVES.md)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        return cmd_init(args)
    if args.command == "add":
        return cmd_add(args)
    if args.command == "start":
        return cmd_start(args)
    if args.command == "block":
        return cmd_block(args)
    if args.command == "done":
        return cmd_done(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "summary":
        return cmd_summary(args)
    if args.command == "import-md":
        return cmd_import_md(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
