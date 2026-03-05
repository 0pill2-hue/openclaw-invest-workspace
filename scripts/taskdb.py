#!/usr/bin/env python3
"""SQLite-backed TASK ledger CLI."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "runtime/tasks/tasks.db"
DEFAULT_TASKS_MD_PATH = ROOT / "TASKS_ACTIVE.md"

ALLOWED_STATUS = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE"}
ALLOWED_BUCKET = {"active", "backlog", "done"}
ALLOWED_PRIORITY = {"P0", "P1", "P2", "P3"}


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            title TEXT NOT NULL,
            scope TEXT DEFAULT '',
            priority TEXT DEFAULT '',
            bucket TEXT NOT NULL CHECK(bucket IN ('active', 'backlog', 'done')),
            note TEXT DEFAULT '',
            blocked_reason TEXT DEFAULT '',
            proof TEXT DEFAULT '',
            proof_pending TEXT DEFAULT '',
            proof_last TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            assigned_run_id TEXT DEFAULT '',
            assigned_at TEXT DEFAULT '',
            review_status TEXT DEFAULT '',
            review_note TEXT DEFAULT '',
            extra_lines TEXT DEFAULT '[]',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS priority_queue (
            rank INTEGER PRIMARY KEY,
            priority TEXT NOT NULL,
            raw_text TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_bucket_order ON tasks(bucket, sort_order);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        """
    )

    task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    missing_columns = {
        "assignee": "TEXT NOT NULL DEFAULT ''",
        "assigned_run_id": "TEXT NOT NULL DEFAULT ''",
        "assigned_at": "TEXT NOT NULL DEFAULT ''",
        "review_status": "TEXT NOT NULL DEFAULT ''",
        "review_note": "TEXT NOT NULL DEFAULT ''",
    }
    for column, ddl in missing_columns.items():
        if column not in task_columns:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} {ddl}")

    conn.commit()


def normalize_priority(raw_priority: str) -> str:
    return (raw_priority or "").strip().upper()


def extract_ticket_ids(text: str) -> List[str]:
    ids: List[str] = []
    seen = set()
    for token in re.findall(r"JB-\d{8}-[0-9/]{3,}", text):
        m = re.match(r"JB-(\d{8})-([0-9]{3}(?:/[0-9]{3})*)", token)
        if not m:
            continue
        date_part = m.group(1)
        serials = m.group(2).split("/")
        for serial in serials:
            tid = f"JB-{date_part}-{serial}"
            if tid not in seen:
                seen.add(tid)
                ids.append(tid)
    return ids


def parse_meta(meta_lines: List[str]) -> Dict[str, str]:
    scope = ""
    notes: List[str] = []
    blocked = ""
    proof = ""
    proof_pending = ""
    proof_last = ""
    extras: List[str] = []

    for meta in meta_lines:
        text = meta.strip()
        if text.startswith("scope:"):
            scope = text[len("scope:") :].strip()
        elif text.startswith("note:"):
            notes.append(text[len("note:") :].strip())
        elif text.startswith("blocked:"):
            blocked = text[len("blocked:") :].strip()
        elif text.startswith("proof(pending):"):
            proof_pending = text[len("proof(pending):") :].strip()
        elif text.startswith("proof(last):"):
            proof_last = text[len("proof(last):") :].strip()
        elif text.startswith("proof:"):
            proof = text[len("proof:") :].strip()
        else:
            extras.append(text)

    return {
        "scope": scope,
        "note": "\n".join([n for n in notes if n]),
        "blocked_reason": blocked,
        "proof": proof,
        "proof_pending": proof_pending,
        "proof_last": proof_last,
        "extra_lines": json.dumps(extras, ensure_ascii=False),
    }


def parse_tasks_active(md_path: Path) -> Tuple[List[Tuple[int, str, str]], List[Dict[str, str]]]:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    priority_rows: List[Tuple[int, str, str]] = []
    priority_by_ticket: Dict[str, str] = {}
    tasks: List[Dict[str, str]] = []

    section = ""
    current = None
    bucket_order = {"active": 0, "backlog": 0, "done": 0}

    def close_current() -> None:
        nonlocal current
        if not current:
            return
        meta = parse_meta(current["meta_lines"])
        row = {
            "id": current["id"],
            "status": current["status"],
            "title": current["title"],
            "scope": meta["scope"],
            "priority": priority_by_ticket.get(current["id"], ""),
            "bucket": current["bucket"],
            "note": meta["note"],
            "blocked_reason": meta["blocked_reason"],
            "proof": meta["proof"],
            "proof_pending": meta["proof_pending"],
            "proof_last": meta["proof_last"],
            "extra_lines": meta["extra_lines"],
            "sort_order": str(current["sort_order"]),
        }
        if row["id"]:
            tasks.append(row)
        current = None

    for line in lines:
        if line.startswith("## "):
            close_current()
            heading = line.strip()
            if heading.startswith("## PRIORITY QUEUE"):
                section = "priority"
            elif heading == "## ACTIVE NOW":
                section = "active"
            elif heading.startswith("## BACKLOG"):
                section = "backlog"
            elif heading.startswith("## DONE"):
                section = "done"
            else:
                section = ""
            continue

        if section == "priority":
            m = re.match(r"^\s*\d+\)\s*(P\d+)\s*:\s*(.+)$", line)
            if m:
                priority = m.group(1).strip()
                raw_text = m.group(2).strip()
                rank = len(priority_rows) + 1
                priority_rows.append((rank, priority, raw_text))
                for ticket_id in extract_ticket_ids(raw_text):
                    priority_by_ticket[ticket_id] = priority
            continue

        if section in ALLOWED_BUCKET:
            m = re.match(r"^- \[[ xX]\]\s+([A-Z_]+):\s+(.+)$", line)
            if m:
                close_current()
                status = m.group(1).strip().upper()
                rest = m.group(2).strip()
                tid_match = re.match(r"^(JB-\d{8}-\d{3})\s*(.*)$", rest)
                ticket_id = tid_match.group(1) if tid_match else ""
                title = (tid_match.group(2) if tid_match else rest).strip()
                bucket_order[section] += 1
                current = {
                    "bucket": section,
                    "status": status,
                    "id": ticket_id,
                    "title": title,
                    "meta_lines": [],
                    "sort_order": bucket_order[section],
                }
                continue

            if current:
                sub = re.match(r"^\s{2}-\s+(.+)$", line)
                if sub:
                    current["meta_lines"].append(sub.group(1).rstrip())

    close_current()
    return priority_rows, tasks


def cmd_init(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser().resolve()
    conn = connect(db_path)
    init_schema(conn)
    print(f"initialized: {db_path}")
    return 0


def cmd_migrate_md(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser().resolve()
    src_path = Path(args.source).expanduser().resolve()

    if not src_path.exists():
        print(f"source not found: {src_path}", file=sys.stderr)
        return 1

    priority_rows, tasks = parse_tasks_active(src_path)

    conn = connect(db_path)
    init_schema(conn)

    now = now_ts()
    with conn:
        conn.execute("DELETE FROM priority_queue")
        conn.execute("DELETE FROM tasks")

        for rank, priority, raw_text in priority_rows:
            conn.execute(
                "INSERT INTO priority_queue(rank, priority, raw_text) VALUES (?, ?, ?)",
                (rank, priority, raw_text),
            )

        for task in tasks:
            conn.execute(
                """
                INSERT INTO tasks(
                    id, status, title, scope, priority, bucket,
                    note, blocked_reason, proof, proof_pending, proof_last,
                    extra_lines, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    task["status"],
                    task["title"],
                    task["scope"],
                    task["priority"],
                    task["bucket"],
                    task["note"],
                    task["blocked_reason"],
                    task["proof"],
                    task["proof_pending"],
                    task["proof_last"],
                    task["extra_lines"],
                    int(task["sort_order"]),
                    now,
                    now,
                ),
            )

    print(f"migrated: priority={len(priority_rows)} tasks={len(tasks)} from {src_path}")
    return 0


def next_sort_order(conn: sqlite3.Connection, bucket: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM tasks WHERE bucket=?", (bucket,)
    ).fetchone()
    return int(row["max_order"]) + 1


def cmd_add(args: argparse.Namespace) -> int:
    status = args.status.upper()
    bucket = args.bucket.lower()
    priority = normalize_priority(args.priority)

    if status not in ALLOWED_STATUS:
        print(f"invalid status: {status}", file=sys.stderr)
        return 1
    if bucket not in ALLOWED_BUCKET:
        print(f"invalid bucket: {bucket}", file=sys.stderr)
        return 1
    if priority not in ALLOWED_PRIORITY:
        print("invalid priority: must be one of P0|P1|P2|P3", file=sys.stderr)
        return 1

    db_path = Path(args.db).expanduser().resolve()
    conn = connect(db_path)
    init_schema(conn)

    existing = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    sort_order = (
        int(existing["sort_order"]) if existing and existing["bucket"] == bucket else next_sort_order(conn, bucket)
    )
    now = now_ts()

    note = existing["note"] if existing else ""
    blocked_reason = existing["blocked_reason"] if existing else ""
    proof = existing["proof"] if existing else ""
    proof_pending = existing["proof_pending"] if existing else ""
    proof_last = existing["proof_last"] if existing else ""
    assignee = existing["assignee"] if existing else ""
    assigned_run_id = existing["assigned_run_id"] if existing else ""
    assigned_at = existing["assigned_at"] if existing else ""
    review_status = existing["review_status"] if existing else ""
    review_note = existing["review_note"] if existing else ""
    extra_lines = existing["extra_lines"] if existing else "[]"
    created_at = existing["created_at"] if existing else now

    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, status, title, scope, priority, bucket,
                note, blocked_reason, proof, proof_pending, proof_last,
                assignee, assigned_run_id, assigned_at, review_status, review_note,
                extra_lines, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.id,
                status,
                args.title,
                args.scope,
                priority,
                bucket,
                note,
                blocked_reason,
                proof,
                proof_pending,
                proof_last,
                assignee,
                assigned_run_id,
                assigned_at,
                review_status,
                review_note,
                extra_lines,
                sort_order,
                created_at,
                now,
            ),
        )

    print(f"added: {args.id} ({status}/{bucket})")
    return 0


def update_status(
    conn: sqlite3.Connection,
    ticket_id: str,
    *,
    status: str,
    bucket: str,
    blocked_reason: str | None = None,
    proof: str | None = None,
) -> bool:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        return False

    new_blocked = row["blocked_reason"]
    new_proof = row["proof"]
    new_proof_pending = row["proof_pending"]

    if blocked_reason is not None:
        new_blocked = blocked_reason
    if proof is not None:
        new_proof = proof
        new_proof_pending = ""

    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET status=?, bucket=?, blocked_reason=?, proof=?, proof_pending=?, updated_at=?
            WHERE id=?
            """,
            (status, bucket, new_blocked, new_proof, new_proof_pending, now_ts(), ticket_id),
        )
    return True


def cmd_start(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    ok = update_status(conn, args.id, status="IN_PROGRESS", bucket="active")
    if not ok:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"started: {args.id}")
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    ok = update_status(
        conn,
        args.id,
        status="BLOCKED",
        bucket="backlog",
        blocked_reason=args.reason,
    )
    if not ok:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"blocked: {args.id}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    ok = update_status(conn, args.id, status="DONE", bucket="done", proof=args.proof)
    if not ok:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"done: {args.id}")
    return 0


def pick_next_task(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, status, bucket, priority, title, scope, sort_order
        FROM tasks
        WHERE status IN ('IN_PROGRESS', 'TODO')
        ORDER BY
            CASE UPPER(priority)
                WHEN 'P0' THEN 0
                WHEN 'P1' THEN 1
                WHEN 'P2' THEN 2
                WHEN 'P3' THEN 3
                ELSE 4
            END,
            CASE bucket
                WHEN 'active' THEN 0
                WHEN 'backlog' THEN 1
                WHEN 'done' THEN 2
                ELSE 3
            END,
            sort_order,
            id
        LIMIT 1
        """
    ).fetchone()


def cmd_pick_next(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = pick_next_task(conn)
    if not row:
        print("(empty)")
        return 0

    priority = row["priority"] if row["priority"] else "-"
    scope = row["scope"] if row["scope"] else ""
    print(f"{row['id']}\t{row['status']}\t{row['bucket']}\t{priority}\t{row['title']}\t{scope}")
    return 0


def cmd_assign_next(args: argparse.Namespace) -> int:
    assignee = (args.assignee or "").strip()
    run_id = (args.run_id or "").strip()
    if not assignee:
        print("--assignee is required", file=sys.stderr)
        return 1

    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = pick_next_task(conn)
    if not row:
        print("no assignable ticket", file=sys.stderr)
        return 1

    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET assignee=?, assigned_run_id=?, assigned_at=?, review_status='PENDING', review_note='', updated_at=?
            WHERE id=?
            """,
            (assignee, run_id, now_ts(), now_ts(), row["id"]),
        )

    print(f"assigned {row['id']}")
    return 0


def cmd_review_pass(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT id FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1

    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET status='DONE', bucket='done', proof=?, proof_pending='', review_status='PASS', review_note='', updated_at=?
            WHERE id=?
            """,
            (args.proof, now_ts(), args.id),
        )

    print(f"review-pass: {args.id}")
    return 0


def cmd_review_rework(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT id FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1

    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET status='IN_PROGRESS', bucket='active', review_status='REWORK', review_note=?, updated_at=?
            WHERE id=?
            """,
            (args.note, now_ts(), args.id),
        )

    print(f"review-rework: {args.id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)

    statuses = [s.upper() for s in (args.status or [])]
    buckets = [b.lower() for b in (args.bucket or [])]

    for s in statuses:
        if s not in ALLOWED_STATUS:
            print(f"invalid status filter: {s}", file=sys.stderr)
            return 1
    for b in buckets:
        if b not in ALLOWED_BUCKET:
            print(f"invalid bucket filter: {b}", file=sys.stderr)
            return 1

    sql = """
        SELECT id, status, bucket, priority, title
        FROM tasks
    """
    conds: List[str] = []
    params: List[str] = []

    if statuses:
        conds.append("status IN ({})".format(",".join(["?"] * len(statuses))))
        params.extend(statuses)
    if buckets:
        conds.append("bucket IN ({})".format(",".join(["?"] * len(buckets))))
        params.extend(buckets)

    if conds:
        sql += " WHERE " + " AND ".join(conds)

    sql += """
        ORDER BY
            CASE bucket WHEN 'active' THEN 1 WHEN 'backlog' THEN 2 WHEN 'done' THEN 3 ELSE 4 END,
            sort_order,
            id
    """

    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        p = r["priority"] if r["priority"] else "-"
        print(f"{r['id']}\t{r['status']}\t{r['bucket']}\t{p}\t{r['title']}")
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
            SUM(CASE WHEN status='TODO' THEN 1 ELSE 0 END) AS todo,
            SUM(CASE WHEN status='BLOCKED' THEN 1 ELSE 0 END) AS blocked,
            SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS done
        FROM tasks
        """
    ).fetchone()

    assignment_counts = conn.execute(
        """
        SELECT
            SUM(CASE WHEN assignee != '' AND review_status='PENDING' THEN 1 ELSE 0 END) AS assigned,
            SUM(CASE WHEN review_status='REWORK' THEN 1 ELSE 0 END) AS rework
        FROM tasks
        """
    ).fetchone()

    active_rows = conn.execute(
        """
        SELECT id, priority, status, title
        FROM tasks
        WHERE bucket='active'
        ORDER BY
            CASE UPPER(priority)
                WHEN 'P0' THEN 0
                WHEN 'P1' THEN 1
                WHEN 'P2' THEN 2
                ELSE 3
            END,
            sort_order,
            id
        LIMIT ?
        """,
        (args.top,),
    ).fetchall()

    recent_rows = conn.execute(
        """
        SELECT id, status, updated_at, title
        FROM tasks
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT ?
        """,
        (args.recent,),
    ).fetchall()

    print("== TASK SUMMARY ==")
    print(
        "total={total} | IN_PROGRESS={in_progress} | TODO={todo} | BLOCKED={blocked} | DONE={done}".format(
            total=counts["total"] or 0,
            in_progress=counts["in_progress"] or 0,
            todo=counts["todo"] or 0,
            blocked=counts["blocked"] or 0,
            done=counts["done"] or 0,
        )
    )
    print(
        "assigned_pending={assigned} | rework={rework}".format(
            assigned=assignment_counts["assigned"] or 0,
            rework=assignment_counts["rework"] or 0,
        )
    )
    print("")

    print(f"[active top {args.top} by priority: P0>P1>P2>others]")
    if active_rows:
        for row in active_rows:
            priority = row["priority"] if row["priority"] else "-"
            print(f"- {row['id']} | {priority} | {row['status']} | {row['title']}")
    else:
        print("- (empty)")

    print("")
    print(f"[recent {args.recent} updates]")
    if recent_rows:
        for row in recent_rows:
            print(f"- {row['id']} | {row['status']} | {row['updated_at']} | {row['title']}")
    else:
        print("- (empty)")

    return 0


def load_bucket_rows(conn: sqlite3.Connection, bucket: str) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tasks WHERE bucket=? ORDER BY sort_order, id",
        (bucket,),
    ).fetchall()


def render_task_lines(row: sqlite3.Row) -> List[str]:
    lines: List[str] = []
    checkbox = "x" if row["status"] == "DONE" else " "
    title_suffix = f" {row['title']}" if row["title"] else ""
    lines.append(f"- [{checkbox}] {row['status']}: {row['id']}{title_suffix}")

    if row["scope"]:
        lines.append(f"  - scope: {row['scope']}")

    if row["note"]:
        for note_line in row["note"].splitlines():
            lines.append(f"  - note: {note_line}")

    if row["blocked_reason"]:
        lines.append(f"  - blocked: {row['blocked_reason']}")

    if row["status"] == "DONE":
        if row["proof"]:
            lines.append(f"  - proof: {row['proof']}")
        elif row["proof_last"]:
            lines.append(f"  - proof(last): {row['proof_last']}")
    else:
        if row["proof_pending"]:
            lines.append(f"  - proof(pending): {row['proof_pending']}")
        if row["proof_last"]:
            lines.append(f"  - proof(last): {row['proof_last']}")
        if row["proof"] and not row["proof_last"]:
            lines.append(f"  - proof: {row['proof']}")

    extras: List[str] = []
    try:
        extras = json.loads(row["extra_lines"] or "[]")
        if not isinstance(extras, list):
            extras = []
    except json.JSONDecodeError:
        extras = []

    for extra in extras:
        lines.append(f"  - {extra}")

    lines.append("")
    return lines


def cmd_render_md(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    conn = connect(db_path)
    init_schema(conn)

    priority_rows = conn.execute(
        "SELECT rank, priority, raw_text FROM priority_queue ORDER BY rank"
    ).fetchall()

    active_rows = load_bucket_rows(conn, "active")
    backlog_rows = load_bucket_rows(conn, "backlog")
    done_rows = load_bucket_rows(conn, "done")

    lines: List[str] = [
        "# TASKS_ACTIVE.md",
        "",
        "## PRIORITY QUEUE (오늘)",
    ]

    if priority_rows:
        for idx, row in enumerate(priority_rows, start=1):
            lines.append(f"{idx}) {row['priority']}: {row['raw_text']}")
    else:
        lines.append("미확인")

    lines.extend(["", "## ACTIVE NOW"])
    if active_rows:
        for row in active_rows:
            lines.extend(render_task_lines(row))
    else:
        lines.append("- (empty)")
        lines.append("")

    lines.append("## BACKLOG (의미 있는 미완)")
    if backlog_rows:
        for row in backlog_rows:
            lines.extend(render_task_lines(row))
    else:
        lines.append("- (empty)")
        lines.append("")

    lines.append("## DONE (recent)")
    if done_rows:
        for row in done_rows:
            lines.extend(render_task_lines(row))
    else:
        lines.append("- (empty)")
        lines.append("")

    ensure_parent(out_path)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"rendered: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TASKS SQLite ledger CLI")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create schema")

    p_migrate = sub.add_parser("migrate-md", help="Migrate from TASKS_ACTIVE.md")
    p_migrate.add_argument(
        "--source",
        default=str(DEFAULT_TASKS_MD_PATH),
        help="Source TASKS_ACTIVE.md path",
    )

    p_add = sub.add_parser("add", help="Add or update task")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--status", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--scope", required=True)
    p_add.add_argument("--priority", required=True, help="P0|P1|P2|P3")
    p_add.add_argument("--bucket", required=True, choices=sorted(ALLOWED_BUCKET))

    p_start = sub.add_parser("start", help="Set ticket IN_PROGRESS")
    p_start.add_argument("--id", required=True)

    p_block = sub.add_parser("block", help="Set ticket BLOCKED")
    p_block.add_argument("--id", required=True)
    p_block.add_argument("--reason", required=True)

    p_done = sub.add_parser("done", help="Set ticket DONE")
    p_done.add_argument("--id", required=True)
    p_done.add_argument("--proof", required=True)

    sub.add_parser("pick-next", help="Pick next ticket by priority")

    p_assign_next = sub.add_parser("assign-next", help="Assign next ticket by priority")
    p_assign_next.add_argument("--assignee", required=True)
    p_assign_next.add_argument("--run-id", default="")

    p_review_pass = sub.add_parser("review-pass", help="Mark review pass and close ticket")
    p_review_pass.add_argument("--id", required=True)
    p_review_pass.add_argument("--proof", required=True)

    p_review_rework = sub.add_parser("review-rework", help="Mark review rework")
    p_review_rework.add_argument("--id", required=True)
    p_review_rework.add_argument("--note", required=True)

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", nargs="*", help="Status filter(s)")
    p_list.add_argument("--bucket", nargs="*", help="Bucket filter(s)")

    p_summary = sub.add_parser("summary", help="Human-friendly task summary")
    p_summary.add_argument("--top", type=int, default=5, help="Top N active tasks (default: 5)")
    p_summary.add_argument("--recent", type=int, default=5, help="Recent N updates (default: 5)")

    p_render = sub.add_parser("render-md", help="Render TASKS_ACTIVE.md from DB")
    p_render.add_argument(
        "--output",
        default=str(DEFAULT_TASKS_MD_PATH),
        help="Output TASKS_ACTIVE.md path",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        return cmd_init(args)
    if args.command == "migrate-md":
        return cmd_migrate_md(args)
    if args.command == "add":
        return cmd_add(args)
    if args.command == "start":
        return cmd_start(args)
    if args.command == "block":
        return cmd_block(args)
    if args.command == "done":
        return cmd_done(args)
    if args.command == "pick-next":
        return cmd_pick_next(args)
    if args.command == "assign-next":
        return cmd_assign_next(args)
    if args.command == "review-pass":
        return cmd_review_pass(args)
    if args.command == "review-rework":
        return cmd_review_rework(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "summary":
        return cmd_summary(args)
    if args.command == "render-md":
        return cmd_render_md(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
