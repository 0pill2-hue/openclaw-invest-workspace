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

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.runtime_env import TASKS_DB
from lib.context_lock import format_lock_reason, is_blocking_context_lock, is_context_locked
from lib.task_runtime import is_nonterminal_wait_phase

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = TASKS_DB
DEFAULT_TASKS_MD_PATH = ROOT / "TASKS_ACTIVE.md"

ALLOWED_STATUS = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE"}
ALLOWED_BUCKET = {"active", "backlog", "done"}
ALLOWED_PRIORITY = {"", "P0", "P1", "P2", "P3"}
TASK_COLUMNS = [
    "id", "status", "title", "scope", "priority", "bucket",
    "note", "blocked_reason", "proof", "proof_pending", "proof_last",
    "assigned_by", "owner", "assignee", "assigned_run_id", "assigned_at", "review_status", "review_note", "closed_by",
    "started_at", "last_activity_at", "resume_due",
    "extra_lines", "sort_order", "created_at", "updated_at",
]


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


def _task_columns(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {row["name"]: row for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}


def _priority_check_ok(info: dict[str, sqlite3.Row]) -> bool:
    col = info.get("priority")
    if not col:
        return False
    return "'P0'" in str(col["dflt_value"] or "''") or True


def _needs_rebuild(conn: sqlite3.Connection) -> bool:
    info = _task_columns(conn)
    if not info:
        return False
    required = {"started_at", "last_activity_at", "resume_due", "assigned_by", "owner", "closed_by"}
    if not required.issubset(info):
        return True
    create_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
    ).fetchone()
    create_sql = (create_sql_row["sql"] if create_sql_row else "") or ""
    return "CHECK(status IN ('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE'))" not in create_sql or "CHECK(priority IN ('', 'P0', 'P1', 'P2', 'P3'))" not in create_sql


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK(status IN ('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE')),
            title TEXT NOT NULL,
            scope TEXT DEFAULT '',
            priority TEXT NOT NULL DEFAULT '' CHECK(priority IN ('', 'P0', 'P1', 'P2', 'P3')),
            bucket TEXT NOT NULL CHECK(bucket IN ('active', 'backlog', 'done')),
            note TEXT DEFAULT '',
            blocked_reason TEXT DEFAULT '',
            proof TEXT DEFAULT '',
            proof_pending TEXT DEFAULT '',
            proof_last TEXT DEFAULT '',
            assigned_by TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            assigned_run_id TEXT DEFAULT '',
            assigned_at TEXT DEFAULT '',
            review_status TEXT DEFAULT '',
            review_note TEXT DEFAULT '',
            closed_by TEXT DEFAULT '',
            started_at TEXT DEFAULT '',
            last_activity_at TEXT DEFAULT '',
            resume_due TEXT DEFAULT '',
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
        """
    )

    if _needs_rebuild(conn):
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        select_cols = []
        for col in TASK_COLUMNS:
            if col in existing:
                select_cols.append(col)
            else:
                select_cols.append(f"'' AS {col}")
        with conn:
            conn.execute("ALTER TABLE tasks RENAME TO tasks_old")
            conn.executescript(
                """
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE')),
                    title TEXT NOT NULL,
                    scope TEXT DEFAULT '',
                    priority TEXT NOT NULL DEFAULT '' CHECK(priority IN ('', 'P0', 'P1', 'P2', 'P3')),
                    bucket TEXT NOT NULL CHECK(bucket IN ('active', 'backlog', 'done')),
                    note TEXT DEFAULT '',
                    blocked_reason TEXT DEFAULT '',
                    proof TEXT DEFAULT '',
                    proof_pending TEXT DEFAULT '',
                    proof_last TEXT DEFAULT '',
                    assigned_by TEXT DEFAULT '',
                    owner TEXT DEFAULT '',
                    assignee TEXT DEFAULT '',
                    assigned_run_id TEXT DEFAULT '',
                    assigned_at TEXT DEFAULT '',
                    review_status TEXT DEFAULT '',
                    review_note TEXT DEFAULT '',
                    closed_by TEXT DEFAULT '',
                    started_at TEXT DEFAULT '',
                    last_activity_at TEXT DEFAULT '',
                    resume_due TEXT DEFAULT '',
                    extra_lines TEXT DEFAULT '[]',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_bucket_order ON tasks(bucket, sort_order);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee, assigned_run_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);
                CREATE INDEX IF NOT EXISTS idx_tasks_resume_due ON tasks(resume_due);
                """
            )
            conn.execute(
                f"INSERT INTO tasks ({', '.join(TASK_COLUMNS)}) SELECT {', '.join(select_cols)} FROM tasks_old"
            )
            conn.execute("DROP TABLE tasks_old")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_bucket_order ON tasks(bucket, sort_order)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee, assigned_run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner)")
    cols = _task_columns(conn)
    if "resume_due" in cols:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_resume_due ON tasks(resume_due)")

    normalize_closed_runtime_metadata(conn)
    conn.commit()


def normalize_priority(raw_priority: str) -> str:
    return (raw_priority or "").strip().upper()


def extract_phase(note: str | None) -> str:
    text = (note or "").strip()
    for line in text.splitlines():
        if line.startswith("phase:"):
            return line.split(":", 1)[1].strip() or "-"
    return "-"


def extract_note_value(note: str | None, key: str) -> str:
    prefix = f"{key}:"
    text = (note or "").strip()
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def infer_worker_kind(assignee: str) -> str:
    text = (assignee or "").strip().lower()
    if not text:
        return "main"
    return "subagent" if "subagent" in text or text.startswith("sub:") else "main"


def infer_task_difficulty(title: str | None, scope: str | None, note: str | None) -> str:
    explicit = extract_note_value(note, "difficulty").strip().lower()
    if explicit in {"easy", "normal", "hard"}:
        return explicit
    text = " ".join(x for x in [title or "", scope or "", note or ""] if x).lower()
    hard_keywords = ("hard", "complex", "debug", "root cause", "contract", "architecture", "refactor", "migration", "정렬", "정합")
    return "hard" if any(keyword in text for keyword in hard_keywords) else "normal"


def infer_task_duration(title: str | None, scope: str | None, note: str | None) -> str:
    explicit = extract_note_value(note, "duration").strip().lower()
    if explicit in {"short", "long"}:
        return explicit
    text = " ".join(x for x in [title or "", scope or "", note or ""] if x).lower()
    long_keywords = ("collect", "sync", "refresh", "scan", "backfill", "monitor", "crawl", "wait", "coverage", "import", "index", "batch", "수집", "동기화", "대기")
    return "long" if any(keyword in text for keyword in long_keywords) else "short"


def infer_execution_lane(title: str | None, scope: str | None, note: str | None) -> str:
    explicit = extract_note_value(note, "execution_lane").strip().lower()
    if explicit in {"main", "subagent", "auto"}:
        return explicit
    difficulty = infer_task_difficulty(title, scope, note)
    duration = infer_task_duration(title, scope, note)
    if difficulty == "hard":
        return "main"
    if duration == "long":
        return "subagent"
    return "auto"


def format_task_runtime_state(row: sqlite3.Row) -> str:
    parts: List[str] = []
    assigned_by = (row["assigned_by"] or "").strip() if "assigned_by" in row.keys() else ""
    owner = (row["owner"] or "").strip() if "owner" in row.keys() else ""
    assignee = (row["assignee"] or "").strip() if "assignee" in row.keys() else ""
    phase = extract_phase(row["note"] if "note" in row.keys() else "")
    review_status = (row["review_status"] or "").strip() if "review_status" in row.keys() else ""
    closed_by = (row["closed_by"] or "").strip() if "closed_by" in row.keys() else ""
    resume_due = (row["resume_due"] or "").strip() if "resume_due" in row.keys() else ""
    child_session = extract_note_value(row["note"] if "note" in row.keys() else "", "child_session")

    if assigned_by:
        parts.append(f"assigned_by={assigned_by}")
    if owner:
        parts.append(f"owner={owner}")
    if assignee:
        parts.append(f"assignee={assignee}")
    if phase != "-":
        parts.append(f"phase={phase}")
        if is_nonterminal_wait_phase(phase):
            parts.append("wait_state=nonterminal")
    if review_status:
        parts.append(f"review={review_status}")
    if closed_by:
        parts.append(f"closed_by={closed_by}")
    if child_session:
        parts.append(f"child={child_session}")
    if resume_due:
        parts.append(f"resume_due={resume_due}")
    return " | ".join(parts) if parts else "-"


def normalize_closed_runtime_metadata(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET blocked_reason='',
                resume_due='',
                proof_pending='',
                review_status=CASE
                    WHEN UPPER(COALESCE(review_status, ''))='PENDING' AND (COALESCE(assignee, '')!='' OR COALESCE(assigned_run_id, '')!='') THEN 'PASS'
                    WHEN UPPER(COALESCE(review_status, ''))='PENDING' THEN ''
                    ELSE review_status
                END,
                review_note=CASE
                    WHEN UPPER(COALESCE(review_status, ''))='PENDING' THEN ''
                    ELSE review_note
                END,
                closed_by=CASE
                    WHEN TRIM(COALESCE(closed_by, ''))='' AND TRIM(COALESCE(assignee, ''))!='' THEN assignee
                    ELSE closed_by
                END
            WHERE status='DONE'
            """
        )
        blocked_rows = conn.execute(
            "SELECT id, note, assignee, review_status, review_note FROM tasks WHERE status='BLOCKED'"
        ).fetchall()
        for row in blocked_rows:
            phase = extract_phase(row['note'])
            waiting_state = is_nonterminal_wait_phase(phase)
            review_status = row['review_status']
            review_note = row['review_note']
            if (review_status or '').upper() == 'PENDING':
                review_status = ''
                review_note = ''
            resume_due = None if waiting_state else ''
            closed_by = '' if waiting_state else ((row['assignee'] or '').strip() if not (row['assignee'] is None) else '')
            conn.execute(
                """
                UPDATE tasks
                SET resume_due=COALESCE(?, resume_due),
                    review_status=?,
                    review_note=?,
                    closed_by=CASE
                        WHEN ? THEN ''
                        WHEN TRIM(COALESCE(closed_by, ''))='' AND TRIM(COALESCE(assignee, ''))!='' THEN assignee
                        ELSE closed_by
                    END
                WHERE id=?
                """,
                (resume_due, review_status, review_note, 1 if waiting_state else 0, row['id']),
            )
        conn.execute(
            """
            UPDATE tasks
            SET closed_by=''
            WHERE status='IN_PROGRESS'
            """
        )


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
                    started_at, last_activity_at, resume_due,
                    extra_lines, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"], task["status"], task["title"], task["scope"], task["priority"], task["bucket"],
                    task["note"], task["blocked_reason"], task["proof"], task["proof_pending"], task["proof_last"],
                    "", "", "", task["extra_lines"], int(task["sort_order"]), now, now,
                ),
            )

    print(f"migrated: priority={len(priority_rows)} tasks={len(tasks)} from {src_path}")
    return 0


def next_sort_order(conn: sqlite3.Connection, bucket: str) -> int:
    row = conn.execute("SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM tasks WHERE bucket=?", (bucket,)).fetchone()
    return int(row["max_order"]) + 1


def _context_lock_blocks_new_id(raw_id: str) -> bool:
    ticket_id = (raw_id or '').strip().upper()
    return not ticket_id.startswith('WD-')


def cmd_add(args: argparse.Namespace) -> int:
    locked, lock_payload = is_context_locked()
    if locked and is_blocking_context_lock(lock_payload) and _context_lock_blocks_new_id(args.id):
        print(format_lock_reason(lock_payload), file=sys.stderr)
        return 2

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
        print("invalid priority: must be one of ''|P0|P1|P2|P3", file=sys.stderr)
        return 1

    db_path = Path(args.db).expanduser().resolve()
    conn = connect(db_path)
    init_schema(conn)

    existing = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    sort_order = int(existing["sort_order"]) if existing and existing["bucket"] == bucket else next_sort_order(conn, bucket)
    now = now_ts()

    note = existing["note"] if existing else ""
    blocked_reason = existing["blocked_reason"] if existing else ""
    proof = existing["proof"] if existing else ""
    proof_pending = existing["proof_pending"] if existing else ""
    proof_last = existing["proof_last"] if existing else ""
    assigned_by = existing["assigned_by"] if existing and "assigned_by" in existing.keys() else ""
    owner = existing["owner"] if existing and "owner" in existing.keys() else ""
    assignee = existing["assignee"] if existing else ""
    assigned_run_id = existing["assigned_run_id"] if existing else ""
    assigned_at = existing["assigned_at"] if existing else ""
    review_status = existing["review_status"] if existing else ""
    review_note = existing["review_note"] if existing else ""
    closed_by = existing["closed_by"] if existing and "closed_by" in existing.keys() else ""
    if args.assigned_by:
        assigned_by = args.assigned_by
    if args.owner:
        owner = args.owner
    started_at = existing["started_at"] if existing else (now if status == "IN_PROGRESS" else "")
    last_activity_at = existing["last_activity_at"] if existing else (now if status == "IN_PROGRESS" else "")
    resume_due = existing["resume_due"] if existing else ""
    extra_lines = existing["extra_lines"] if existing else "[]"
    created_at = existing["created_at"] if existing else now

    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, status, title, scope, priority, bucket,
                note, blocked_reason, proof, proof_pending, proof_last,
                assigned_by, owner, assignee, assigned_run_id, assigned_at, review_status, review_note, closed_by,
                started_at, last_activity_at, resume_due,
                extra_lines, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.id, status, args.title, args.scope, priority, bucket,
                note, blocked_reason, proof, proof_pending, proof_last,
                assigned_by, owner, assignee, assigned_run_id, assigned_at, review_status, review_note, closed_by,
                started_at, last_activity_at, resume_due,
                extra_lines, sort_order, created_at, now,
            ),
        )

    print(f"added: {args.id} ({status}/{bucket})")
    return 0


def update_status(conn: sqlite3.Connection, ticket_id: str, *, status: str, bucket: str, blocked_reason: str | None = None, proof: str | None = None, resume_due: str | None = None, closed_by: str | None = None) -> bool:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        return False

    now = now_ts()
    new_blocked = row["blocked_reason"]
    new_proof = row["proof"]
    new_proof_pending = row["proof_pending"]
    new_started_at = row["started_at"]
    new_last_activity = now
    new_resume_due = row["resume_due"]
    new_review_status = row["review_status"]
    new_review_note = row["review_note"]
    new_closed_by = row["closed_by"] if "closed_by" in row.keys() else ""

    if blocked_reason is not None:
        new_blocked = blocked_reason
    if proof is not None:
        new_proof = proof
        new_proof_pending = ""
    if closed_by is not None:
        new_closed_by = closed_by
    if status == "IN_PROGRESS":
        if not new_started_at:
            new_started_at = now
        if blocked_reason is None:
            new_blocked = ""
        new_closed_by = ""
    elif status == "BLOCKED":
        if (new_review_status or "").upper() == "PENDING":
            new_review_status = ""
            new_review_note = ""
        if not new_closed_by:
            new_closed_by = (row["assignee"] or "").strip() if "assignee" in row.keys() else ""
    elif status == "DONE":
        new_blocked = ""
        new_proof_pending = ""
        if (new_review_status or "").upper() == "PENDING":
            new_review_status = "PASS"
            new_review_note = ""
        if not new_closed_by:
            new_closed_by = (row["assignee"] or "").strip() if "assignee" in row.keys() else ""

    if status != "BLOCKED":
        new_resume_due = ""
    if resume_due is not None:
        new_resume_due = resume_due

    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET status=?, bucket=?, blocked_reason=?, proof=?, proof_pending=?, review_status=?, review_note=?, closed_by=?, started_at=?, last_activity_at=?, resume_due=?, updated_at=?
            WHERE id=?
            """,
            (status, bucket, new_blocked, new_proof, new_proof_pending, new_review_status, new_review_note, new_closed_by, new_started_at, new_last_activity, new_resume_due, now, ticket_id),
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
    ok = update_status(conn, args.id, status="BLOCKED", bucket="backlog", blocked_reason=args.reason, resume_due=args.resume_due)
    if not ok:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"blocked: {args.id}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    ok = update_status(conn, args.id, status="DONE", bucket="done", proof=args.proof, closed_by=args.closed_by)
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
        ORDER BY CASE UPPER(priority) WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                 CASE bucket WHEN 'active' THEN 0 WHEN 'backlog' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
                 sort_order, id
        LIMIT 1
        """
    ).fetchone()


def task_priority_rank(priority: str) -> int:
    value = (priority or "").strip().upper()
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(value, 4)


def bucket_rank(bucket: str) -> int:
    value = (bucket or "").strip().lower()
    return {"active": 0, "backlog": 1, "done": 2}.get(value, 3)


def pick_next_assignable_task(conn: sqlite3.Connection, assignee: str) -> sqlite3.Row | None:
    worker_kind = infer_worker_kind(assignee)
    rows = conn.execute(
        """
        SELECT id, status, bucket, priority, title, scope, sort_order, note
        FROM tasks
        WHERE status IN ('TODO', 'IN_PROGRESS') AND COALESCE(assignee, '')=''
        ORDER BY CASE status WHEN 'TODO' THEN 0 ELSE 1 END,
                 CASE UPPER(priority) WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                 CASE bucket WHEN 'active' THEN 0 WHEN 'backlog' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
                 sort_order, id
        """
    ).fetchall()
    candidates: list[tuple[tuple[int, int, int, int, str], sqlite3.Row]] = []
    for row in rows:
        note = row['note'] or ''
        title = row['title'] or ''
        scope = row['scope'] or ''
        difficulty = infer_task_difficulty(title, scope, note)
        duration = infer_task_duration(title, scope, note)
        lane = infer_execution_lane(title, scope, note)
        if worker_kind == 'subagent':
            if lane == 'main' or difficulty == 'hard':
                continue
            lane_pref = 0 if lane == 'subagent' else 1 if duration == 'long' else 2
        else:
            lane_pref = 0 if difficulty == 'hard' or lane == 'main' else 1 if duration == 'short' else 2
        sort_key = (
            lane_pref,
            0 if (row['status'] or '').upper() == 'TODO' else 1,
            task_priority_rank(row['priority'] or ''),
            bucket_rank(row['bucket'] or ''),
            f"{int(row['sort_order']) if row['sort_order'] is not None else 0:06d}:{row['id']}",
        )
        candidates.append((sort_key, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def assign_next_task(conn: sqlite3.Connection, assignee: str, run_id: str, assigned_by: str = "") -> sqlite3.Row | None:
    in_progress = conn.execute(
        "SELECT id FROM tasks WHERE assignee=? AND status='IN_PROGRESS' LIMIT 1",
        (assignee,),
    ).fetchone()
    if in_progress:
        return None

    for _ in range(5):
        row = pick_next_assignable_task(conn, assignee=assignee)
        if not row:
            return None
        now = now_ts()
        with conn:
            cur = conn.execute(
                """
                UPDATE tasks
                SET status='IN_PROGRESS', bucket='active', assigned_by=?, owner=CASE WHEN COALESCE(owner,'')='' THEN ? ELSE owner END, assignee=?, assigned_run_id=?, assigned_at=?,
                    review_status='PENDING', review_note='', closed_by='',
                    started_at=CASE WHEN COALESCE(started_at,'')='' THEN ? ELSE started_at END,
                    last_activity_at=?, updated_at=?
                WHERE id=? AND COALESCE(assignee, '')=''
                """,
                (assigned_by, assignee, assignee, run_id, now, now, now, now, row["id"]),
            )
        if cur.rowcount == 1:
            return row
    return None


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
    locked, lock_payload = is_context_locked()
    if locked and is_blocking_context_lock(lock_payload):
        print(format_lock_reason(lock_payload), file=sys.stderr)
        return 2

    assignee = (args.assignee or "").strip()
    run_id = (args.run_id or "").strip()
    assigned_by = (args.assigned_by or "").strip()
    if not assignee:
        print("--assignee is required", file=sys.stderr)
        return 1
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = assign_next_task(conn, assignee=assignee, run_id=run_id, assigned_by=assigned_by)
    if not row:
        print("no assignable ticket", file=sys.stderr)
        return 1
    print(f"assigned {row['id']}")
    return 0


def cmd_assign_pool(args: argparse.Namespace) -> int:
    locked, lock_payload = is_context_locked()
    if locked and is_blocking_context_lock(lock_payload):
        print(format_lock_reason(lock_payload), file=sys.stderr)
        return 2

    workers = [worker.strip() for worker in (args.worker or []) if worker.strip()]
    if not workers:
        print("--worker is required", file=sys.stderr)
        return 1
    base_run_id = (args.run_id or "").strip() or datetime.now().strftime("%Y%m%d%H%M%S")
    assigned_by = (args.assigned_by or "").strip()

    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)

    assigned_count = 0
    for idx, worker in enumerate(workers, start=1):
        row = assign_next_task(conn, assignee=worker, run_id=f"{base_run_id}-{idx}", assigned_by=assigned_by)
        if row is None:
            print(f"idle {worker}")
            continue
        assigned_count += 1
        print(f"assigned {row['id']} -> {worker}")

    return 0


def cmd_review_pass(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT id, assignee FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    closed_by = (args.closed_by or "").strip() or (row["assignee"] or "").strip()
    with conn:
        conn.execute(
            "UPDATE tasks SET status='DONE', bucket='done', proof=?, proof_pending='', review_status='PASS', review_note='', closed_by=?, last_activity_at=?, updated_at=? WHERE id=?",
            (args.proof, closed_by, now_ts(), now_ts(), args.id),
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
            "UPDATE tasks SET status='IN_PROGRESS', bucket='active', review_status='REWORK', review_note=?, closed_by='', last_activity_at=?, updated_at=? WHERE id=?",
            (args.note, now_ts(), now_ts(), args.id),
        )
    print(f"review-rework: {args.id}")
    return 0


def cmd_touch(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    with conn:
        cur = conn.execute("UPDATE tasks SET last_activity_at=?, updated_at=? WHERE id=?", (now_ts(), now_ts(), args.id))
    if cur.rowcount != 1:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"touched: {args.id}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    now = now_ts()
    with conn:
        cur = conn.execute(
            """
            UPDATE tasks
            SET assigned_by='', assignee='', assigned_run_id='', assigned_at='', review_status='', review_note='', updated_at=?
            WHERE id=?
            """,
            (now, args.id),
        )
    if cur.rowcount != 1:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"released: {args.id}")
    return 0


def cmd_mark_phase(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT status, note FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1

    existing_lines = [line for line in (row["note"] or "").splitlines() if not line.startswith("phase:") and not line.startswith("child_session:")]
    new_lines = [f"phase: {args.phase}"]
    if args.child_session:
        new_lines.append(f"child_session: {args.child_session}")
    if args.note:
        new_lines.append(args.note)
    if existing_lines:
        new_lines.extend(existing_lines)
    note = "\n".join(line for line in new_lines if line.strip())
    now = now_ts()
    resume_due = args.resume_due or ""
    waiting_state = is_nonterminal_wait_phase(args.phase)
    status = (row["status"] or "").upper()
    with conn:
        if waiting_state and status in {"TODO", "BLOCKED"}:
            conn.execute(
                """
                UPDATE tasks
                SET status='IN_PROGRESS', bucket='active', blocked_reason='', closed_by='',
                    note=?, last_activity_at=?, resume_due=?, updated_at=?
                WHERE id=?
                """,
                (note, now, resume_due, now, args.id),
            )
        else:
            conn.execute(
                "UPDATE tasks SET note=?, last_activity_at=?, resume_due=?, updated_at=? WHERE id=?",
                (note, now, resume_due, now, args.id),
            )
    print(f"phase-updated: {args.id} -> {args.phase}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    with conn:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (args.id,))
    if cur.rowcount != 1:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"removed: {args.id}")
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
    sql = "SELECT id, status, bucket, priority, title, note, assigned_by, owner, assignee, review_status, resume_due, closed_by FROM tasks"
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
    sql += " ORDER BY CASE bucket WHEN 'active' THEN 1 WHEN 'backlog' THEN 2 WHEN 'done' THEN 3 ELSE 4 END, sort_order, id"
    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        p = r["priority"] if r["priority"] else "-"
        phase = extract_phase(r["note"])
        runtime_state = format_task_runtime_state(r)
        line = f"{r['id']}\t{r['status']}\t{phase}\t{r['bucket']}\t{p}\t{r['title']}"
        if runtime_state != "-":
            line += f"\t{runtime_state}"
        print(line)
    print(f"count={len(rows)}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    if args.top < 0 or args.recent < 0:
        print("--top/--recent must be >= 0", file=sys.stderr)
        return 1
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    counts = conn.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress, SUM(CASE WHEN status='TODO' THEN 1 ELSE 0 END) AS todo, SUM(CASE WHEN status='BLOCKED' THEN 1 ELSE 0 END) AS blocked, SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS done FROM tasks").fetchone()
    assignment_counts = conn.execute("SELECT SUM(CASE WHEN status='IN_PROGRESS' AND assignee != '' AND review_status='PENDING' THEN 1 ELSE 0 END) AS assigned, SUM(CASE WHEN status='IN_PROGRESS' AND review_status='REWORK' THEN 1 ELSE 0 END) AS rework FROM tasks").fetchone()
    active_rows = conn.execute("SELECT id, priority, status, title, note, assigned_by, owner, assignee, assigned_run_id, review_status, resume_due, closed_by FROM tasks WHERE bucket='active' ORDER BY CASE UPPER(priority) WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, sort_order, id LIMIT ?", (args.top,)).fetchall()
    recent_rows = conn.execute("SELECT id, status, updated_at, title FROM tasks ORDER BY datetime(updated_at) DESC, id DESC LIMIT ?", (args.recent,)).fetchall()
    hygiene_rows = conn.execute(
        """
        SELECT id, updated_at, title
        FROM tasks
        WHERE status='BLOCKED'
          AND TRIM(COALESCE(proof, '')) != ''
          AND TRIM(COALESCE(blocked_reason, '')) = ''
        ORDER BY datetime(updated_at) DESC, id DESC
        LIMIT 10
        """
    ).fetchall()
    print("== TASK SUMMARY ==")
    print("total={total} | IN_PROGRESS={in_progress} | TODO={todo} | BLOCKED={blocked} | DONE={done}".format(total=counts["total"] or 0, in_progress=counts["in_progress"] or 0, todo=counts["todo"] or 0, blocked=counts["blocked"] or 0, done=counts["done"] or 0))
    print("assigned_pending={assigned} | rework={rework}".format(assigned=assignment_counts["assigned"] or 0, rework=assignment_counts["rework"] or 0))
    print("")
    print(f"[active top {args.top} by priority: P0>P1>P2>others]")
    if active_rows:
        for row in active_rows:
            priority = row["priority"] if row["priority"] else "-"
            runtime_state = format_task_runtime_state(row)
            line = f"- {row['id']} | {priority} | {row['status']} | {row['title']}"
            if runtime_state != "-":
                line += f" | {runtime_state}"
            print(line)
    else:
        print("- (empty)")
    print("")
    print(f"[recent {args.recent} updates]")
    if recent_rows:
        for row in recent_rows:
            print(f"- {row['id']} | {row['status']} | {row['updated_at']} | {row['title']}")
    else:
        print("- (empty)")
    print("")
    print("[hygiene alerts]")
    if hygiene_rows:
        print("- blocked_with_proof_no_reason: reconcile to DONE/remove or add explicit blocker")
        for row in hygiene_rows:
            print(f"  - {row['id']} | {row['updated_at']} | {row['title']}")
    else:
        print("- (clean)")
    return 0


def load_bucket_rows(conn: sqlite3.Connection, bucket: str) -> List[sqlite3.Row]:
    return conn.execute("SELECT * FROM tasks WHERE bucket=? ORDER BY sort_order, id", (bucket,)).fetchall()


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
    runtime_state = format_task_runtime_state(row)
    if runtime_state != "-":
        lines.append(f"  - task_state: {runtime_state}")
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
    priority_rows = conn.execute("SELECT rank, priority, raw_text FROM priority_queue ORDER BY rank").fetchall()
    active_rows = load_bucket_rows(conn, "active")
    backlog_rows = load_bucket_rows(conn, "backlog")
    done_rows = load_bucket_rows(conn, "done")
    lines: List[str] = ["# TASKS_ACTIVE.md", "", "## PRIORITY QUEUE (오늘)"]
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
        lines += ["- (empty)", ""]
    lines.append("## BACKLOG (의미 있는 미완)")
    if backlog_rows:
        for row in backlog_rows:
            lines.extend(render_task_lines(row))
    else:
        lines += ["- (empty)", ""]
    lines.append("## DONE (recent)")
    if done_rows:
        for row in done_rows:
            lines.extend(render_task_lines(row))
    else:
        lines += ["- (empty)", ""]
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
    p_migrate.add_argument("--source", default=str(DEFAULT_TASKS_MD_PATH), help="Source TASKS_ACTIVE.md path")
    p_add = sub.add_parser("add", help="Add or update task")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--status", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--scope", required=True)
    p_add.add_argument("--priority", default="", help="P0|P1|P2|P3")
    p_add.add_argument("--bucket", required=True, choices=sorted(ALLOWED_BUCKET))
    p_add.add_argument("--assigned-by", default="")
    p_add.add_argument("--owner", default="")
    p_start = sub.add_parser("start", help="Set ticket IN_PROGRESS")
    p_start.add_argument("--id", required=True)
    p_block = sub.add_parser("block", help="Set ticket BLOCKED")
    p_block.add_argument("--id", required=True)
    p_block.add_argument("--reason", required=True)
    p_block.add_argument("--resume-due", default="")
    p_done = sub.add_parser("done", help="Set ticket DONE")
    p_done.add_argument("--id", required=True)
    p_done.add_argument("--proof", required=True)
    p_done.add_argument("--closed-by", default="")
    sub.add_parser("pick-next", help="Pick next ticket by priority")
    p_assign_next = sub.add_parser("assign-next", help="Assign next ticket by priority")
    p_assign_next.add_argument("--assignee", required=True)
    p_assign_next.add_argument("--run-id", default="")
    p_assign_next.add_argument("--assigned-by", default="")
    p_assign_pool = sub.add_parser("assign-pool", help="Assign multiple idle workers from the task pool")
    p_assign_pool.add_argument("--worker", nargs="+", required=True)
    p_assign_pool.add_argument("--run-id", default="")
    p_assign_pool.add_argument("--assigned-by", default="")
    p_review_pass = sub.add_parser("review-pass", help="Mark review pass and close ticket")
    p_review_pass.add_argument("--id", required=True)
    p_review_pass.add_argument("--proof", required=True)
    p_review_pass.add_argument("--closed-by", default="")
    p_review_rework = sub.add_parser("review-rework", help="Mark review rework")
    p_review_rework.add_argument("--id", required=True)
    p_review_rework.add_argument("--note", required=True)
    p_touch = sub.add_parser("touch", help="Update last_activity_at for active ticket")
    p_touch.add_argument("--id", required=True)
    p_phase = sub.add_parser("mark-phase", help="Mark orchestration phase on a ticket")
    p_phase.add_argument("--id", required=True)
    p_phase.add_argument("--phase", required=True)
    p_phase.add_argument("--child-session", default="")
    p_phase.add_argument("--resume-due", default="")
    p_phase.add_argument("--note", default="")
    p_release = sub.add_parser("release", help="Clear task assignee/run metadata")
    p_release.add_argument("--id", required=True)
    p_remove = sub.add_parser("remove", help="Delete task from ledger")
    p_remove.add_argument("--id", required=True)
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", nargs="*", help="Status filter(s)")
    p_list.add_argument("--bucket", nargs="*", help="Bucket filter(s)")
    p_summary = sub.add_parser("summary", help="Human-friendly task summary")
    p_summary.add_argument("--top", type=int, default=5, help="Top N active tasks (default: 5)")
    p_summary.add_argument("--recent", type=int, default=5, help="Recent N updates (default: 5)")
    p_render = sub.add_parser("render-md", help="Render TASKS_ACTIVE.md from DB")
    p_render.add_argument("--output", default=str(DEFAULT_TASKS_MD_PATH), help="Output TASKS_ACTIVE.md path")
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
    if args.command == "assign-pool":
        return cmd_assign_pool(args)
    if args.command == "review-pass":
        return cmd_review_pass(args)
    if args.command == "review-rework":
        return cmd_review_rework(args)
    if args.command == "touch":
        return cmd_touch(args)
    if args.command == "mark-phase":
        return cmd_mark_phase(args)
    if args.command == "release":
        return cmd_release(args)
    if args.command == "remove":
        return cmd_remove(args)
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
