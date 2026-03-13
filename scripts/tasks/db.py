#!/usr/bin/env python3
"""SQLite-backed TASK ledger CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from context_policy import (
    CONTEXT_HANDOFF,
    CURRENT_TASK,
    atomic_write_text,
    inspect_runtime_ticket_references,
    read_text,
    write_context_handoff_from_current,
    write_snapshot_pair,
)
from lib.runtime_env import TASKS_DB
from lib.context_lock import format_lock_reason, is_blocking_context_lock, is_context_locked
from lib.blocked_requeue import auto_requeue_blocked_tasks
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
    "callback_token", "callback_state", "detached_at", "job_ref", "child_session", "resource_keys", "heartbeat_at",
    "extra_lines", "sort_order", "created_at", "updated_at",
]
CONTEXT_HYGIENE_TASK_ID = "WD-CONTEXT-HYGIENE"
CONTEXT_HYGIENE_TASK_TITLE = "watchdog maintenance: context handoff/작업연속성 정리"
CONTEXT_HYGIENE_TASK_SCOPE = "close guard/current-task mismatch/context-handoff 정리를 atomic하게 수행하고 후속 snapshot 전환을 마무리"
CONTEXT_HYGIENE_TASK_PATHS = "runtime/current-task.md,runtime/context-handoff.md,runtime/tasks/tasks.db,scripts/tasks/db.py,scripts/context_policy.py"
EVIDENCE_ROOT = ROOT / "runtime" / "tasks" / "evidence"
EVIDENCE_CARDS_DIR = EVIDENCE_ROOT / "cards"
EVIDENCE_PROOF_INDEX = EVIDENCE_ROOT / "proof-index.jsonl"
EVIDENCE_RAW_HOT = EVIDENCE_ROOT / "raw-hot.jsonl"
EVIDENCE_RAW_WARM = EVIDENCE_ROOT / "raw-warm.jsonl"
EVIDENCE_RAW_COLD = EVIDENCE_ROOT / "raw-cold.jsonl"
EVIDENCE_ARCHIVE_HOOKS = EVIDENCE_ROOT / "archive-hooks.jsonl"


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def to_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def compact_text(value: str | None, limit: int = 220) -> str:
    text = " ".join((value or "").split())
    if not text:
        return "-"
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def parse_csv_tokens(value: str | None) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    return [item.strip(" `") for item in raw.split(",") if item.strip(" `")]


def parse_path_tokens(value: str | None) -> list[str]:
    text = value or ""
    tokens = re.split(r"[,\s]+", text)
    result: list[str] = []
    for raw in tokens:
        token = raw.strip(" `\"'")
        if not token:
            continue
        if "/" not in token and "." not in token:
            continue
        if token.startswith("http://") or token.startswith("https://"):
            continue
        result.append(token)
    return result


def normalize_path_list(values: list[str], *, limit: int = 12) -> list[str]:
    uniq: list[str] = []
    seen: set[str] = set()
    for item in values:
        clean = item.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        uniq.append(clean)
        if len(uniq) >= limit:
            break
    return uniq


def path_temperature(path_text: str) -> str:
    lower = (path_text or "").lower()
    if "/tmp/" in lower or lower.startswith("tmp/") or "/logs/" in lower or "stdout" in lower or "stderr" in lower:
        return "hot"
    if "/raw/" in lower or lower.startswith("raw/"):
        return "warm"
    if "/archive/" in lower or lower.startswith("archive/"):
        return "cold"
    return ""


def extract_runtime_touched_paths(row: sqlite3.Row, *, proof_text: str, blocked_reason: str) -> list[str]:
    values: list[str] = []
    values.extend(parse_csv_tokens(extract_note_value(row["note"] if "note" in row.keys() else "", "touched_paths")))
    values.extend(parse_path_tokens(proof_text))
    values.extend(parse_path_tokens(blocked_reason))
    return normalize_path_list(values, limit=10)


def ensure_evidence_dirs() -> None:
    EVIDENCE_CARDS_DIR.mkdir(parents=True, exist_ok=True)


def build_evidence_card(
    row: sqlite3.Row,
    *,
    status: str,
    proof_text: str,
    blocked_reason: str,
    closed_by: str,
    closed_at: str,
) -> tuple[dict[str, Any], list[str]]:
    touched_paths = extract_runtime_touched_paths(row, proof_text=proof_text, blocked_reason=blocked_reason)
    decisive_proof = touched_paths[0] if touched_paths else compact_text(proof_text or blocked_reason, 140)
    proof_excerpt = compact_text(proof_text or blocked_reason, 240)
    objective = compact_text((row["scope"] or "").strip() or (row["title"] or "").strip(), 240)
    final_summary = compact_text(proof_text if status == "DONE" else (blocked_reason or proof_text), 280)
    card = {
        "schema_version": "evidence_card_v1",
        "ticket_id": row["id"],
        "status": status,
        "objective": objective,
        "result": status,
        "final_summary": final_summary,
        "touched_paths": touched_paths,
        "decisive_proof": decisive_proof,
        "proof_excerpt": proof_excerpt,
        "index_pointer": f"{to_rel(EVIDENCE_PROOF_INDEX)}#ticket_id={row['id']}",
        "timestamps": {
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or "",
            "closed_at": closed_at,
        },
        "closed_by": closed_by or "",
    }
    raw_refs: list[str] = []
    for item in touched_paths:
        if path_temperature(item):
            raw_refs.append(item)
    if not raw_refs:
        for item in parse_path_tokens(proof_text):
            if path_temperature(item):
                raw_refs.append(item)
    return card, normalize_path_list(raw_refs, limit=20)


def write_evidence_artifacts(
    row: sqlite3.Row,
    *,
    status: str,
    proof_text: str,
    blocked_reason: str,
    closed_by: str,
    closed_at: str,
) -> tuple[str, list[Path]]:
    ensure_evidence_dirs()
    card, raw_refs = build_evidence_card(
        row,
        status=status,
        proof_text=proof_text,
        blocked_reason=blocked_reason,
        closed_by=closed_by,
        closed_at=closed_at,
    )
    created_paths: list[Path] = []
    card_path = EVIDENCE_CARDS_DIR / f"{row['id']}.json"
    atomic_write_text(card_path, json.dumps(card, ensure_ascii=False, indent=2) + "\n")
    created_paths.append(card_path)
    card_rel = to_rel(card_path)

    proof_index_entry = {
        "ts": closed_at,
        "ticket_id": row["id"],
        "status": status,
        "canonical_summary": True,
        "evidence_card": card_rel,
        "objective": card["objective"],
        "final_summary": card["final_summary"],
        "decisive_proof": card["decisive_proof"],
        "proof_excerpt": card["proof_excerpt"],
        "touched_paths": card["touched_paths"],
        "closed_by": closed_by or "",
    }
    append_jsonl(EVIDENCE_PROOF_INDEX, proof_index_entry)

    for temp, path in (("hot", EVIDENCE_RAW_HOT), ("warm", EVIDENCE_RAW_WARM), ("cold", EVIDENCE_RAW_COLD)):
        refs = [item for item in raw_refs if path_temperature(item) == temp]
        if not refs:
            continue
        append_jsonl(
            path,
            {
                "ts": closed_at,
                "ticket_id": row["id"],
                "status": status,
                "refs": refs,
                "source": card_rel,
            },
        )

    append_jsonl(
        EVIDENCE_ARCHIVE_HOOKS,
        {
            "ts": closed_at,
            "ticket_id": row["id"],
            "hook": "archive_compaction_candidate",
            "policy": "non_destructive_metadata_only",
            "proof_index": to_rel(EVIDENCE_PROOF_INDEX),
            "evidence_card": card_rel,
            "raw_ref_count": len(raw_refs),
        },
    )
    return f"{card_rel}#canonical_summary", created_paths


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
    required = {
        "started_at",
        "last_activity_at",
        "resume_due",
        "assigned_by",
        "owner",
        "closed_by",
        "callback_token",
        "callback_state",
        "detached_at",
        "job_ref",
        "child_session",
        "resource_keys",
        "heartbeat_at",
    }
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
            callback_token TEXT DEFAULT '',
            callback_state TEXT DEFAULT '',
            detached_at TEXT DEFAULT '',
            job_ref TEXT DEFAULT '',
            child_session TEXT DEFAULT '',
            resource_keys TEXT DEFAULT '',
            heartbeat_at TEXT DEFAULT '',
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
                    callback_token TEXT DEFAULT '',
                    callback_state TEXT DEFAULT '',
                    detached_at TEXT DEFAULT '',
                    job_ref TEXT DEFAULT '',
                    child_session TEXT DEFAULT '',
                    resource_keys TEXT DEFAULT '',
                    heartbeat_at TEXT DEFAULT '',
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
    if "resource_keys" in cols:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_resource_keys ON tasks(resource_keys)")
    if "callback_state" in cols:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_callback_state ON tasks(callback_state)")

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


def normalize_resource_keys(raw: str | None) -> str:
    parts = [item.strip() for item in (raw or "").split(",") if item.strip()]
    if not parts:
        return "repo:global"
    unique_sorted = sorted(set(parts))
    return ",".join(unique_sorted)


def parse_resource_keys(raw: str | None) -> set[str]:
    normalized = normalize_resource_keys(raw)
    return {item for item in normalized.split(",") if item}


def note_with_runtime_fields(
    existing_note: str | None,
    *,
    phase: str | None = None,
    child_session: str | None = None,
    append_note: str | None = None,
) -> str:
    clean_lines: list[str] = []
    for line in (existing_note or "").splitlines():
        if line.startswith("phase:") or line.startswith("child_session:"):
            continue
        clean_lines.append(line)
    new_lines: list[str] = []
    if phase:
        new_lines.append(f"phase: {phase}")
    if child_session:
        new_lines.append(f"child_session: {child_session}")
    if append_note:
        new_lines.append(append_note)
    if clean_lines:
        new_lines.extend(clean_lines)
    return "\n".join(line for line in new_lines if line.strip())


def callback_state_of(row: sqlite3.Row) -> str:
    return (row["callback_state"] or "").strip().lower() if "callback_state" in row.keys() else ""


def is_detached_state(row: sqlite3.Row) -> bool:
    return callback_state_of(row) == "detached"


def validate_waiting_invariants(
    *,
    task_id: str,
    note: str | None,
    resume_due: str | None,
    callback_state: str | None,
    callback_token: str | None,
) -> str | None:
    phase = extract_phase(note)
    waiting_state = is_nonterminal_wait_phase(phase)
    resume_due_text = (resume_due or "").strip()
    callback_state_text = (callback_state or "").strip().lower()
    callback_token_text = (callback_token or "").strip()
    if waiting_state and not resume_due_text:
        return f"waiting phase requires --resume-due: {task_id} phase={phase}"
    if callback_state_text == "detached" and not callback_token_text:
        return f"detached state requires callback_token: {task_id}"
    return None


def resource_conflict_with_active(conn: sqlite3.Connection, ticket_id: str, resource_keys: str) -> tuple[str, list[str]]:
    keys = parse_resource_keys(resource_keys)
    if not keys:
        return "", []
    rows = conn.execute(
        """
        SELECT id, resource_keys
        FROM tasks
        WHERE status='IN_PROGRESS' AND id<>?
        """,
        (ticket_id,),
    ).fetchall()
    conflicts: list[str] = []
    overlap_keys: set[str] = set()
    for row in rows:
        other_keys = parse_resource_keys(row["resource_keys"] if "resource_keys" in row.keys() else "")
        overlap = keys.intersection(other_keys)
        if overlap:
            conflicts.append(row["id"])
            overlap_keys.update(overlap)
    if not conflicts:
        return "", []
    return ",".join(sorted(overlap_keys)), sorted(conflicts)


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


def waiting_capacity_for_assignee(assignee: str) -> int:
    worker_kind = infer_worker_kind(assignee)
    env_key = "OPENCLAW_SUBAGENT_WAITING_CAP" if worker_kind == "subagent" else "OPENCLAW_MAIN_WAITING_CAP"
    default_value = "2" if worker_kind == "subagent" else "4"
    raw = os.environ.get(env_key, default_value).strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return int(default_value)


def active_assignment_state(conn: sqlite3.Connection, assignee: str) -> tuple[list[str], list[str]]:
    rows = conn.execute(
        """
        SELECT id, status, note
        FROM tasks
        WHERE assignee=? AND status IN ('IN_PROGRESS', 'BLOCKED')
        ORDER BY updated_at DESC, id DESC
        """,
        (assignee,),
    ).fetchall()
    blocking_ids: list[str] = []
    waiting_ids: list[str] = []
    for row in rows:
        phase = extract_phase(row["note"])
        if is_nonterminal_wait_phase(phase):
            waiting_ids.append(row["id"])
        else:
            blocking_ids.append(row["id"])
    return blocking_ids, waiting_ids


def is_task_ready_for_assignment(status: str | None, note: str | None) -> bool:
    normalized_status = (status or "").strip().upper()
    if normalized_status not in {"TODO", "IN_PROGRESS"}:
        return False
    return not is_nonterminal_wait_phase(extract_phase(note))


def format_task_runtime_state(row: sqlite3.Row) -> str:
    parts: List[str] = []
    assigned_by = (row["assigned_by"] or "").strip() if "assigned_by" in row.keys() else ""
    owner = (row["owner"] or "").strip() if "owner" in row.keys() else ""
    assignee = (row["assignee"] or "").strip() if "assignee" in row.keys() else ""
    phase = extract_phase(row["note"] if "note" in row.keys() else "")
    review_status = (row["review_status"] or "").strip() if "review_status" in row.keys() else ""
    closed_by = (row["closed_by"] or "").strip() if "closed_by" in row.keys() else ""
    resume_due = (row["resume_due"] or "").strip() if "resume_due" in row.keys() else ""
    child_session = (row["child_session"] or "").strip() if "child_session" in row.keys() else ""
    if not child_session:
        child_session = extract_note_value(row["note"] if "note" in row.keys() else "", "child_session")
    callback_state = (row["callback_state"] or "").strip() if "callback_state" in row.keys() else ""
    resource_keys = normalize_resource_keys(row["resource_keys"] if "resource_keys" in row.keys() else "")
    callback_token = (row["callback_token"] or "").strip() if "callback_token" in row.keys() else ""
    heartbeat_at = (row["heartbeat_at"] or "").strip() if "heartbeat_at" in row.keys() else ""

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
    if callback_state:
        parts.append(f"callback={callback_state}")
    if callback_token:
        parts.append("callback_token=set")
    if heartbeat_at:
        parts.append(f"heartbeat_at={heartbeat_at}")
    if resource_keys:
        parts.append(f"resource_keys={resource_keys}")
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
                callback_state=CASE
                    WHEN LOWER(COALESCE(callback_state, ''))='detached' THEN 'completed'
                    ELSE callback_state
                END,
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
    callback_token = existing["callback_token"] if existing and "callback_token" in existing.keys() else ""
    callback_state = existing["callback_state"] if existing and "callback_state" in existing.keys() else ""
    detached_at = existing["detached_at"] if existing and "detached_at" in existing.keys() else ""
    job_ref = existing["job_ref"] if existing and "job_ref" in existing.keys() else ""
    child_session = existing["child_session"] if existing and "child_session" in existing.keys() else ""
    resource_keys = normalize_resource_keys(existing["resource_keys"] if existing and "resource_keys" in existing.keys() else "")
    heartbeat_at = existing["heartbeat_at"] if existing and "heartbeat_at" in existing.keys() else ""
    if args.resource_keys:
        resource_keys = normalize_resource_keys(args.resource_keys)
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
                callback_token, callback_state, detached_at, job_ref, child_session, resource_keys, heartbeat_at,
                extra_lines, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.id, status, args.title, args.scope, priority, bucket,
                note, blocked_reason, proof, proof_pending, proof_last,
                assigned_by, owner, assignee, assigned_run_id, assigned_at, review_status, review_note, closed_by,
                started_at, last_activity_at, resume_due,
                callback_token, callback_state, detached_at, job_ref, child_session, resource_keys, heartbeat_at,
                extra_lines, sort_order, created_at, now,
            ),
        )

    print(f"added: {args.id} ({status}/{bucket})")
    return 0


def build_status_update_payload(
    row: sqlite3.Row,
    *,
    status: str,
    bucket: str,
    blocked_reason: str | None = None,
    proof: str | None = None,
    resume_due: str | None = None,
    closed_by: str | None = None,
    force_review_pass: bool = False,
) -> dict[str, str]:
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
        if force_review_pass or (new_review_status or "").upper() == "PENDING":
            new_review_status = "PASS"
            new_review_note = ""
        if not new_closed_by:
            new_closed_by = (row["assignee"] or "").strip() if "assignee" in row.keys() else ""

    if status != "BLOCKED":
        new_resume_due = ""
    if resume_due is not None:
        new_resume_due = resume_due

    return {
        "status": status,
        "bucket": bucket,
        "blocked_reason": new_blocked,
        "proof": new_proof,
        "proof_pending": new_proof_pending,
        "review_status": new_review_status,
        "review_note": new_review_note,
        "closed_by": new_closed_by,
        "started_at": new_started_at,
        "last_activity_at": new_last_activity,
        "resume_due": new_resume_due,
        "updated_at": now,
    }


def apply_status_update(conn: sqlite3.Connection, ticket_id: str, payload: dict[str, str]) -> None:
    conn.execute(
        """
        UPDATE tasks
        SET status=?, bucket=?, blocked_reason=?, proof=?, proof_pending=?, review_status=?, review_note=?, closed_by=?, started_at=?, last_activity_at=?, resume_due=?, updated_at=?
        WHERE id=?
        """,
        (
            payload["status"],
            payload["bucket"],
            payload["blocked_reason"],
            payload["proof"],
            payload["proof_pending"],
            payload["review_status"],
            payload["review_note"],
            payload["closed_by"],
            payload["started_at"],
            payload["last_activity_at"],
            payload["resume_due"],
            payload["updated_at"],
            ticket_id,
        ),
    )


def update_status(conn: sqlite3.Connection, ticket_id: str, *, status: str, bucket: str, blocked_reason: str | None = None, proof: str | None = None, resume_due: str | None = None, closed_by: str | None = None, force_review_pass: bool = False) -> bool:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        return False
    payload = build_status_update_payload(
        row,
        status=status,
        bucket=bucket,
        blocked_reason=blocked_reason,
        proof=proof,
        resume_due=resume_due,
        closed_by=closed_by,
        force_review_pass=force_review_pass,
    )
    with conn:
        apply_status_update(conn, ticket_id, payload)
    return True


def compact_context_text(value: str | None, limit: int = 220) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text or "-"
    return text[: limit - 3].rstrip() + "..."


def close_guard_task_state(source_ticket_id: str, target_status: str) -> dict[str, str]:
    runtime_state = "assigned_by=close_guard | owner=close_guard | assignee=close_guard | phase=close_guard"
    return {
        "task_status": "IN_PROGRESS",
        "task_bucket": "active",
        "task_phase": "close_guard",
        "task_assigned_by": "close_guard",
        "task_owner": "close_guard",
        "task_assignee": "close_guard",
        "task_review_status": "미정",
        "task_closed_by": "미정",
        "task_resume_due": "미정",
        "task_assigned_run_id": f"close-guard:{source_ticket_id}",
        "task_runtime_state": runtime_state,
        "task_blocked_reason": f"close_guard source={source_ticket_id} status={target_status}",
    }


def ensure_context_hygiene_ticket(
    conn: sqlite3.Connection,
    *,
    source_ticket_id: str,
    target_status: str,
    latest_proof: str,
    blocked_reason: str,
) -> None:
    now = now_ts()
    note_lines = [
        "phase: close_guard",
        f"close_guard_source_ticket: {source_ticket_id}",
        f"close_guard_source_status: {target_status}",
        f"close_guard_latest_proof: {compact_context_text(latest_proof)}",
    ]
    if blocked_reason:
        note_lines.append(f"close_guard_blocked_reason: {compact_context_text(blocked_reason)}")
    note = "\n".join(note_lines)
    row = conn.execute("SELECT id, created_at, started_at FROM tasks WHERE id=?", (CONTEXT_HYGIENE_TASK_ID,)).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO tasks(
                id, status, title, scope, priority, bucket,
                note, blocked_reason, proof, proof_pending, proof_last,
                assigned_by, owner, assignee, assigned_run_id, assigned_at, review_status, review_note, closed_by,
                started_at, last_activity_at, resume_due,
                extra_lines, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                CONTEXT_HYGIENE_TASK_ID,
                "IN_PROGRESS",
                CONTEXT_HYGIENE_TASK_TITLE,
                CONTEXT_HYGIENE_TASK_SCOPE,
                "P0",
                "active",
                note,
                "",
                "",
                "",
                "",
                "close_guard",
                "close_guard",
                "close_guard",
                f"close-guard:{source_ticket_id}",
                now,
                "",
                "",
                "",
                now,
                now,
                "",
                json.dumps([], ensure_ascii=False),
                next_sort_order(conn, "active"),
                now,
                now,
            ),
        )
        return
    conn.execute(
        """
        UPDATE tasks
        SET status='IN_PROGRESS', bucket='active', title=?, scope=?, priority='P0',
            note=?, blocked_reason='',
            assigned_by='close_guard', owner='close_guard', assignee='close_guard', assigned_run_id=?, assigned_at=?,
            review_status='', review_note='', closed_by='',
            started_at=CASE WHEN COALESCE(started_at,'')='' THEN ? ELSE started_at END,
            last_activity_at=?, resume_due='', updated_at=?
        WHERE id=?
        """,
        (
            CONTEXT_HYGIENE_TASK_TITLE,
            CONTEXT_HYGIENE_TASK_SCOPE,
            note,
            f"close-guard:{source_ticket_id}",
            now,
            now,
            now,
            now,
            CONTEXT_HYGIENE_TASK_ID,
        ),
    )


def restore_runtime_file(path: Path, original_text: str, existed: bool) -> None:
    if existed:
        atomic_write_text(path, original_text)
        return
    if path.exists():
        path.unlink()


def write_close_guard_context(
    conn: sqlite3.Connection,
    *,
    ticket_id: str,
    target_status: str,
    latest_proof: str,
    blocked_reason: str,
    closed_by: str,
    refs: dict[str, object],
) -> None:
    if not refs["current_task_points"] and not refs["context_handoff_points"]:
        return
    if refs["current_task_points"] and ticket_id == CONTEXT_HYGIENE_TASK_ID:
        raise RuntimeError(
            "close gate blocked: runtime/current-task.md still points to WD-CONTEXT-HYGIENE; snapshot the successor task before closing it"
        )
    if not refs["current_task_points"] and refs["context_handoff_points"]:
        current_ticket = str(refs.get("current_task_ticket_id") or "").strip()
        if current_ticket and current_ticket != ticket_id:
            write_context_handoff_from_current(
                handoff_reason="close_guard_realign",
                trigger="task_close",
                required_action="read_then_resume",
                observed_total_tokens="-",
                threshold="-",
                reset_guard="valid_handoff_required_before_clean_reset",
                notes=(
                    f"close_guard_realign_from={ticket_id}; "
                    f"closed_status={target_status}; closed_by={closed_by or '-'}"
                ),
            )
            return
    ensure_context_hygiene_ticket(
        conn,
        source_ticket_id=ticket_id,
        target_status=target_status,
        latest_proof=latest_proof,
        blocked_reason=blocked_reason,
    )
    write_snapshot_pair(
        ticket_id=CONTEXT_HYGIENE_TASK_ID,
        directive_ids=CONTEXT_HYGIENE_TASK_ID,
        goal=f"{ticket_id} {target_status} close 이후 current-task/context-handoff 정리",
        last=(
            f"taskdb close guard가 {ticket_id}를 {target_status}로 전환하기 직전에 "
            "runtime 포인터를 maintenance ticket으로 넘길 준비를 완료했다."
        ),
        next_action=(
            "다음 실제 작업 ticket을 정해 snapshot으로 교체하고, 닫힌 ticket을 가리키는 잔여 포인터가 없는지 확인한 뒤 "
            "WD-CONTEXT-HYGIENE를 정리한다."
        ),
        touched_paths=CONTEXT_HYGIENE_TASK_PATHS,
        latest_proof=compact_context_text(latest_proof),
        paths=CONTEXT_HYGIENE_TASK_PATHS,
        notes=(
            f"close_guard_source_ticket={ticket_id}; close_guard_source_status={target_status}; "
            f"close_guard_closed_by={closed_by or '-'}; close_guard_blocked_reason={compact_context_text(blocked_reason)}"
        ),
        handoff_reason="task_close_guard",
        trigger="task_close",
        required_action="read_then_resume",
        observed_total_tokens="-",
        threshold="-",
        reset_guard="valid_handoff_required_before_clean_reset",
        task_state_override=close_guard_task_state(ticket_id, target_status),
    )


def close_status_with_context_guard(
    conn: sqlite3.Connection,
    ticket_id: str,
    *,
    status: str,
    bucket: str,
    blocked_reason: str | None = None,
    proof: str | None = None,
    resume_due: str | None = None,
    closed_by: str | None = None,
    force_review_pass: bool = False,
    allow_detached_terminal: bool = False,
) -> tuple[bool, str | None]:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        return False, f"ticket not found: {ticket_id}"
    if status in {"DONE", "BLOCKED"} and is_detached_state(row) and not allow_detached_terminal:
        return False, f"detached ticket cannot be terminally closed without callback-complete/fail: {ticket_id}"
    payload = build_status_update_payload(
        row,
        status=status,
        bucket=bucket,
        blocked_reason=blocked_reason,
        proof=proof,
        resume_due=resume_due,
        closed_by=closed_by,
        force_review_pass=force_review_pass,
    )
    created_evidence_paths: list[Path] = []
    if status in {"DONE", "BLOCKED"}:
        proof_text = proof if proof is not None else (row["proof"] or "")
        blocked_text = blocked_reason if blocked_reason is not None else (row["blocked_reason"] or "")
        try:
            canonical_proof, created_evidence_paths = write_evidence_artifacts(
                row,
                status=status,
                proof_text=proof_text,
                blocked_reason=blocked_text,
                closed_by=payload["closed_by"],
                closed_at=payload["updated_at"],
            )
        except Exception as exc:
            return False, f"evidence artifact generation failed: {ticket_id} ({exc})"
        payload["proof"] = canonical_proof
        payload["proof_pending"] = ""
    refs = inspect_runtime_ticket_references(ticket_id)
    current_original = read_text(CURRENT_TASK)
    handoff_original = read_text(CONTEXT_HANDOFF)
    current_existed = CURRENT_TASK.exists()
    handoff_existed = CONTEXT_HANDOFF.exists()
    try:
        conn.execute("BEGIN IMMEDIATE")
        write_close_guard_context(
            conn,
            ticket_id=ticket_id,
            target_status=status,
            latest_proof=proof or payload["proof"] or blocked_reason or "-",
            blocked_reason=blocked_reason or payload["blocked_reason"] or "",
            closed_by=payload["closed_by"],
            refs=refs,
        )
        apply_status_update(conn, ticket_id, payload)
        conn.commit()
        return True, None
    except Exception as exc:
        conn.rollback()
        for created in created_evidence_paths:
            try:
                created.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            restore_runtime_file(CURRENT_TASK, current_original, current_existed)
            restore_runtime_file(CONTEXT_HANDOFF, handoff_original, handoff_existed)
        except Exception:
            pass
        return False, str(exc)


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
    ok, error = close_status_with_context_guard(
        conn,
        args.id,
        status="BLOCKED",
        bucket="backlog",
        blocked_reason=args.reason,
        resume_due=args.resume_due,
    )
    if not ok:
        print(error or f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"blocked: {args.id}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    ok, error = close_status_with_context_guard(
        conn,
        args.id,
        status="DONE",
        bucket="done",
        proof=args.proof,
        closed_by=args.closed_by,
    )
    if not ok:
        print(error or f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    print(f"done: {args.id}")
    return 0


def pick_next_task(conn: sqlite3.Connection) -> sqlite3.Row | None:
    rows = conn.execute(
        """
        SELECT id, status, bucket, priority, title, scope, sort_order, note
        FROM tasks
        WHERE status IN ('IN_PROGRESS', 'TODO')
        ORDER BY CASE UPPER(priority) WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                 CASE bucket WHEN 'active' THEN 0 WHEN 'backlog' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
                 sort_order, id
        """
    ).fetchall()
    for row in rows:
        if is_task_ready_for_assignment(row['status'], row['note']):
            return row
    return None


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
               , resource_keys
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
        if not is_task_ready_for_assignment(row['status'], note):
            continue
        overlap_keys, conflict_ids = resource_conflict_with_active(
            conn,
            ticket_id=row["id"],
            resource_keys=row["resource_keys"] if "resource_keys" in row.keys() else "",
        )
        if conflict_ids:
            continue
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
    with conn:
        auto_requeue_blocked_tasks(conn)
    blocking_ids, waiting_ids = active_assignment_state(conn, assignee)
    if blocking_ids:
        return None
    if len(waiting_ids) >= waiting_capacity_for_assignee(assignee):
        return None

    for _ in range(5):
        row = pick_next_assignable_task(conn, assignee=assignee)
        if not row:
            return None
        resource_keys = normalize_resource_keys(row["resource_keys"] if "resource_keys" in row.keys() else "")
        overlap_keys, conflict_ids = resource_conflict_with_active(conn, ticket_id=row["id"], resource_keys=resource_keys)
        if conflict_ids:
            continue
        now = now_ts()
        with conn:
            cur = conn.execute(
                """
                UPDATE tasks
                SET status='IN_PROGRESS', bucket='active', assigned_by=?, owner=CASE WHEN COALESCE(owner,'')='' THEN ? ELSE owner END, assignee=?, assigned_run_id=?, assigned_at=?,
                    review_status='PENDING', review_note='', closed_by='',
                    resource_keys=?,
                    started_at=CASE WHEN COALESCE(started_at,'')='' THEN ? ELSE started_at END,
                    last_activity_at=?, updated_at=?
                WHERE id=? AND COALESCE(assignee, '')=''
                """,
                (assigned_by, assignee, assignee, run_id, now, resource_keys, now, now, now, row["id"]),
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
    ok, error = close_status_with_context_guard(
        conn,
        args.id,
        status="DONE",
        bucket="done",
        proof=args.proof,
        closed_by=closed_by,
        force_review_pass=True,
    )
    if not ok:
        print(error or f"ticket not found: {args.id}", file=sys.stderr)
        return 1
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


def cmd_requeue_blocked(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    with conn:
        moved = auto_requeue_blocked_tasks(conn)
    payload = {
        "ok": True,
        "changed": bool(moved),
        "requeued": moved,
        "count": len(moved),
        "db": str(Path(args.db).expanduser().resolve()),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def cmd_mark_phase(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute(
        "SELECT status, note, resume_due, callback_token, callback_state, child_session FROM tasks WHERE id=?",
        (args.id,),
    ).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1

    phase = (args.phase or "").strip()
    child_session = (args.child_session or "").strip() or (row["child_session"] or "").strip()
    note = note_with_runtime_fields(
        row["note"],
        phase=phase,
        child_session=child_session,
        append_note=args.note,
    )
    now = now_ts()
    resume_due = args.resume_due or ""
    waiting_state = is_nonterminal_wait_phase(phase)
    callback_token = (row["callback_token"] or "").strip()
    callback_state = (row["callback_state"] or "").strip()
    error = validate_waiting_invariants(
        task_id=args.id,
        note=note,
        resume_due=resume_due if waiting_state else row["resume_due"] if "resume_due" in row.keys() else "",
        callback_state=callback_state,
        callback_token=callback_token,
    )
    if error:
        print(error, file=sys.stderr)
        return 1
    if waiting_state and not callback_token:
        print(f"waiting phase requires callback_token (use db.py detach): {args.id}", file=sys.stderr)
        return 1
    status = (row["status"] or "").upper()
    with conn:
        if waiting_state and status in {"TODO", "BLOCKED"}:
            conn.execute(
                """
                UPDATE tasks
                SET status='IN_PROGRESS', bucket='active', blocked_reason='', closed_by='',
                    note=?, child_session=?, last_activity_at=?, resume_due=?, updated_at=?
                WHERE id=?
                """,
                (note, child_session, now, resume_due, now, args.id),
            )
        else:
            conn.execute(
                "UPDATE tasks SET note=?, child_session=?, last_activity_at=?, resume_due=?, updated_at=? WHERE id=?",
                (note, child_session, now, resume_due, now, args.id),
            )
    print(f"phase-updated: {args.id} -> {args.phase}")
    return 0


def _assert_callback_token(row: sqlite3.Row, token: str, task_id: str) -> tuple[bool, str]:
    expected = (row["callback_token"] or "").strip() if "callback_token" in row.keys() else ""
    if not expected:
        return False, f"callback_token missing on ticket: {task_id}"
    if expected != token:
        return False, f"callback_token mismatch: {task_id}"
    return True, ""


def _detach_task_row(
    conn: sqlite3.Connection,
    *,
    ticket_id: str,
    token: str,
    resume_due: str,
    job_ref: str,
    child_session: str,
    resource_keys: str,
    note: str,
    release_assignee: bool,
) -> None:
    now = now_ts()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (ticket_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"ticket not found: {ticket_id}")
    detached_at = (row["detached_at"] or "").strip() if "detached_at" in row.keys() else ""
    if not detached_at:
        detached_at = now
    assignee = '' if release_assignee else (row["assignee"] or "")
    assigned_run_id = '' if release_assignee else (row["assigned_run_id"] or "")
    assigned_at = '' if release_assignee else (row["assigned_at"] or "")
    review_status = '' if release_assignee else (row["review_status"] or "")
    review_note = '' if release_assignee else (row["review_note"] or "")
    conn.execute(
        """
        UPDATE tasks
        SET status='IN_PROGRESS', bucket='active', blocked_reason='', closed_by='',
            note=?, resume_due=?, callback_token=?, callback_state='detached',
            detached_at=?, job_ref=?, child_session=?, resource_keys=?, heartbeat_at=?,
            assignee=?, assigned_run_id=?, assigned_at=?, review_status=?, review_note=?,
            last_activity_at=?, updated_at=?
        WHERE id=?
        """,
        (
            note,
            resume_due,
            token,
            detached_at,
            job_ref,
            child_session,
            resource_keys,
            now,
            assignee,
            assigned_run_id,
            assigned_at,
            review_status,
            review_note,
            now,
            now,
            ticket_id,
        ),
    )


def cmd_detach(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    token = (args.callback_token or "").strip()
    if not token:
        print("--callback-token is required", file=sys.stderr)
        return 1
    resume_due = (args.resume_due or "").strip()
    if not resume_due:
        print("--resume-due is required", file=sys.stderr)
        return 1
    existing_token = (row["callback_token"] or "").strip() if "callback_token" in row.keys() else ""
    if existing_token and existing_token != token:
        print(f"detach token conflict: {args.id}", file=sys.stderr)
        return 1

    phase = "awaiting_callback"
    child_session = (args.child_session or "").strip() or (row["child_session"] or "").strip()
    note = note_with_runtime_fields(row["note"], phase=phase, child_session=child_session, append_note=args.note)
    callback_state = "detached"
    job_ref = (args.job_ref or "").strip() or (row["job_ref"] or "").strip()
    resource_keys = normalize_resource_keys(args.resource_keys or row["resource_keys"] if "resource_keys" in row.keys() else "")
    error = validate_waiting_invariants(
        task_id=args.id,
        note=note,
        resume_due=resume_due,
        callback_state=callback_state,
        callback_token=token,
    )
    if error:
        print(error, file=sys.stderr)
        return 1

    with conn:
        _detach_task_row(
            conn,
            ticket_id=args.id,
            token=token,
            resume_due=resume_due,
            job_ref=job_ref,
            child_session=child_session,
            resource_keys=resource_keys,
            note=note,
            release_assignee=False,
        )
    print(f"detached: {args.id}")
    return 0


def cmd_detach_watch(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    token = (args.callback_token or "").strip()
    if not token:
        print("--callback-token is required", file=sys.stderr)
        return 1
    event_id = (args.event_id or "").strip()
    if not event_id:
        print("--event-id is required", file=sys.stderr)
        return 1
    resume_due = (args.resume_due or "").strip()
    if not resume_due:
        print("--resume-due is required", file=sys.stderr)
        return 1
    existing_token = (row["callback_token"] or "").strip() if "callback_token" in row.keys() else ""
    if existing_token and existing_token != token:
        print(f"detach-watch token conflict: {args.id}", file=sys.stderr)
        return 1

    phase = "awaiting_callback"
    child_session = (args.child_session or "").strip() or (row["child_session"] or "").strip()
    appended_note = "\n".join(
        item
        for item in [
            f"watch_event_id={event_id}",
            f"watch_kind={((args.watch_kind or '').strip() or 'web-review')}",
            args.note,
        ]
        if str(item or '').strip()
    )
    note = note_with_runtime_fields(row["note"], phase=phase, child_session=child_session, append_note=appended_note)
    callback_state = "detached"
    job_ref = (args.job_ref or "").strip() or f"watch:{event_id}"
    resource_keys = normalize_resource_keys(args.resource_keys or row["resource_keys"] if "resource_keys" in row.keys() else "")
    error = validate_waiting_invariants(
        task_id=args.id,
        note=note,
        resume_due=resume_due,
        callback_state=callback_state,
        callback_token=token,
    )
    if error:
        print(error, file=sys.stderr)
        return 1

    with conn:
        _detach_task_row(
            conn,
            ticket_id=args.id,
            token=token,
            resume_due=resume_due,
            job_ref=job_ref,
            child_session=child_session,
            resource_keys=resource_keys,
            note=note,
            release_assignee=True,
        )
    print(f"detached-watch: {args.id} event_id={event_id}")
    return 0


def cmd_callback_heartbeat(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    ok, token_error = _assert_callback_token(row, (args.callback_token or "").strip(), args.id)
    if not ok:
        print(token_error, file=sys.stderr)
        return 1
    state = callback_state_of(row)
    if state in {"completed", "failed"}:
        print(f"callback-heartbeat: already terminal callback state ({state}) {args.id}")
        return 0
    now = now_ts()
    resume_due = (args.resume_due or "").strip() or (row["resume_due"] or "").strip()
    note = row["note"] or ""
    if args.note:
        note = note_with_runtime_fields(
            row["note"],
            phase=extract_phase(row["note"]),
            child_session=(row["child_session"] or "").strip() if "child_session" in row.keys() else "",
            append_note=args.note,
        )
    error = validate_waiting_invariants(
        task_id=args.id,
        note=note,
        resume_due=resume_due,
        callback_state=row["callback_state"] if "callback_state" in row.keys() else "",
        callback_token=row["callback_token"] if "callback_token" in row.keys() else "",
    )
    if error:
        print(error, file=sys.stderr)
        return 1
    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET note=?, resume_due=?, heartbeat_at=?, last_activity_at=?, updated_at=?
            WHERE id=?
            """,
            (note, resume_due, now, now, now, args.id),
        )
    print(f"callback-heartbeat: {args.id}")
    return 0


def _callback_resume_update(conn: sqlite3.Connection, row: sqlite3.Row, args: argparse.Namespace) -> None:
    now = now_ts()
    proof = (args.proof or '').strip()
    child_session = (args.child_session or '').strip() or (row["child_session"] or '').strip()
    note = note_with_runtime_fields(
        row["note"],
        phase=(args.resume_phase or '').strip(),
        child_session=child_session,
        append_note=(args.resume_note or '').strip(),
    )
    error = validate_waiting_invariants(
        task_id=args.id,
        note=note,
        resume_due='',
        callback_state='completed',
        callback_token=row["callback_token"] if "callback_token" in row.keys() else '',
    )
    if error:
        raise RuntimeError(error)
    conn.execute(
        """
        UPDATE tasks
        SET status='IN_PROGRESS', bucket='active', blocked_reason='', closed_by='',
            note=?, child_session=?, resume_due='', callback_state='completed',
            proof_last=CASE WHEN ?!='' THEN ? ELSE proof_last END,
            heartbeat_at=?, last_activity_at=?, updated_at=?
        WHERE id=?
        """,
        (
            note,
            child_session,
            proof,
            proof,
            now,
            now,
            now,
            args.id,
        ),
    )


def cmd_callback_complete(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    ok, token_error = _assert_callback_token(row, (args.callback_token or "").strip(), args.id)
    if not ok:
        print(token_error, file=sys.stderr)
        return 1
    resume_phase = (args.resume_phase or '').strip()
    if resume_phase:
        try:
            with conn:
                _callback_resume_update(conn, row, args)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"callback-complete-resume: {args.id} -> {resume_phase}")
        return 0
    if (row["status"] or "").upper() == "DONE" and callback_state_of(row) == "completed":
        print(f"callback-complete: already completed {args.id}")
        return 0
    ok_close, error = close_status_with_context_guard(
        conn,
        args.id,
        status="DONE",
        bucket="done",
        proof=args.proof,
        closed_by=args.closed_by,
        allow_detached_terminal=True,
    )
    if not ok_close:
        print(error or f"callback-complete failed: {args.id}", file=sys.stderr)
        return 1
    now = now_ts()
    terminal_note = note_with_runtime_fields(
        row["note"],
        phase='callback_completed',
        child_session=(row["child_session"] or '').strip() if "child_session" in row.keys() else '',
        append_note='',
    )
    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET note=?, resume_due='', callback_state='completed', heartbeat_at=?, last_activity_at=?, updated_at=?
            WHERE id=?
            """,
            (terminal_note, now, now, now, args.id),
        )
    print(f"callback-complete: {args.id}")
    return 0


def cmd_callback_fail(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ticket not found: {args.id}", file=sys.stderr)
        return 1
    ok, token_error = _assert_callback_token(row, (args.callback_token or "").strip(), args.id)
    if not ok:
        print(token_error, file=sys.stderr)
        return 1
    if (row["status"] or "").upper() == "BLOCKED" and callback_state_of(row) == "failed":
        print(f"callback-fail: already failed {args.id}")
        return 0
    ok_close, error = close_status_with_context_guard(
        conn,
        args.id,
        status="BLOCKED",
        bucket="backlog",
        blocked_reason=args.reason,
        closed_by=args.closed_by or "callback",
        allow_detached_terminal=True,
    )
    if not ok_close:
        print(error or f"callback-fail failed: {args.id}", file=sys.stderr)
        return 1
    now = now_ts()
    terminal_note = note_with_runtime_fields(
        row["note"],
        phase='callback_failed',
        child_session=(row["child_session"] or '').strip() if "child_session" in row.keys() else '',
        append_note=args.reason,
    )
    with conn:
        conn.execute(
            """
            UPDATE tasks
            SET note=?, resume_due='', callback_state='failed', heartbeat_at=?, last_activity_at=?, updated_at=?
            WHERE id=?
            """,
            (terminal_note, now, now, now, args.id),
        )
    print(f"callback-fail: {args.id}")
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
    sql = "SELECT id, status, bucket, priority, title, note, assigned_by, owner, assignee, review_status, resume_due, closed_by, callback_state, callback_token, child_session, resource_keys, heartbeat_at FROM tasks"
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


def _safe_read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _match_text(value: str, query: str) -> bool:
    if not query:
        return True
    return query in (value or "").lower()


def cmd_evidence_search(args: argparse.Namespace) -> int:
    query = (args.query or "").strip().lower()
    ticket_filter = (args.ticket_id or "").strip()
    limit = max(1, int(args.limit))
    canonical_rows = _safe_read_jsonl(EVIDENCE_PROOF_INDEX)

    results: list[dict[str, Any]] = []
    for row in canonical_rows:
        if ticket_filter and (row.get("ticket_id") or "") != ticket_filter:
            continue
        if not args.include_raw and not bool(row.get("canonical_summary")):
            continue
        haystack = " ".join(
            [
                str(row.get("ticket_id") or ""),
                str(row.get("objective") or ""),
                str(row.get("final_summary") or ""),
                str(row.get("proof_excerpt") or ""),
                str(row.get("decisive_proof") or ""),
            ]
        ).lower()
        if not _match_text(haystack, query):
            continue
        results.append(
            {
                "ticket_id": row.get("ticket_id", ""),
                "status": row.get("status", ""),
                "closed_at": row.get("ts", ""),
                "canonical_summary": bool(row.get("canonical_summary")),
                "final_summary": row.get("final_summary", ""),
                "decisive_proof": row.get("decisive_proof", ""),
                "evidence_card": row.get("evidence_card", ""),
            }
        )
        if len(results) >= limit:
            break

    raw_hits: list[dict[str, Any]] = []
    if args.include_raw:
        conn = connect(Path(args.db).expanduser().resolve())
        init_schema(conn)
        rows = conn.execute(
            "SELECT id, status, updated_at, proof, proof_last, blocked_reason FROM tasks ORDER BY datetime(updated_at) DESC, id DESC"
        ).fetchall()
        for row in rows:
            if ticket_filter and row["id"] != ticket_filter:
                continue
            text = " ".join(
                [
                    row["proof"] or "",
                    row["proof_last"] or "",
                    row["blocked_reason"] or "",
                ]
            ).lower()
            if not _match_text(text, query):
                continue
            raw_hits.append(
                {
                    "ticket_id": row["id"],
                    "status": row["status"],
                    "updated_at": row["updated_at"],
                    "proof": compact_text(row["proof"], 200),
                    "proof_last": compact_text(row["proof_last"], 200),
                    "blocked_reason": compact_text(row["blocked_reason"], 200),
                }
            )
            if len(raw_hits) >= limit:
                break

    payload = {
        "ok": True,
        "query": args.query or "",
        "ticket_id": ticket_filter,
        "canonical_only": not args.include_raw,
        "proof_index": to_rel(EVIDENCE_PROOF_INDEX),
        "results": results,
        "raw_hits": raw_hits,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    if args.top < 0 or args.recent < 0:
        print("--top/--recent must be >= 0", file=sys.stderr)
        return 1
    conn = connect(Path(args.db).expanduser().resolve())
    init_schema(conn)
    counts = conn.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress, SUM(CASE WHEN status='TODO' THEN 1 ELSE 0 END) AS todo, SUM(CASE WHEN status='BLOCKED' THEN 1 ELSE 0 END) AS blocked, SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END) AS done FROM tasks").fetchone()
    assignment_counts = conn.execute("SELECT SUM(CASE WHEN status='IN_PROGRESS' AND assignee != '' AND review_status='PENDING' THEN 1 ELSE 0 END) AS assigned, SUM(CASE WHEN status='IN_PROGRESS' AND review_status='REWORK' THEN 1 ELSE 0 END) AS rework FROM tasks").fetchone()
    active_rows = conn.execute("SELECT id, priority, status, title, note, assigned_by, owner, assignee, assigned_run_id, review_status, resume_due, closed_by, callback_state, callback_token, child_session, resource_keys, heartbeat_at FROM tasks WHERE bucket='active' ORDER BY CASE UPPER(priority) WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, sort_order, id LIMIT ?", (args.top,)).fetchall()
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
    p_add.add_argument("--resource-keys", default="", help="Comma-separated resource lock keys (default: repo:global)")
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
    sub.add_parser("requeue-blocked", help="Requeue retryable or auto-cleared BLOCKED tickets")
    p_phase = sub.add_parser("mark-phase", help="Mark orchestration phase on a ticket")
    p_phase.add_argument("--id", required=True)
    p_phase.add_argument("--phase", required=True)
    p_phase.add_argument("--child-session", default="")
    p_phase.add_argument("--resume-due", default="")
    p_phase.add_argument("--note", default="")
    p_detach = sub.add_parser("detach", help="Detach running work and move task to awaiting callback state")
    p_detach.add_argument("--id", required=True)
    p_detach.add_argument("--callback-token", required=True)
    p_detach.add_argument("--resume-due", required=True)
    p_detach.add_argument("--job-ref", default="")
    p_detach.add_argument("--child-session", default="")
    p_detach.add_argument("--resource-keys", default="", help="Comma-separated resource lock keys")
    p_detach.add_argument("--note", default="")
    p_detach_watch = sub.add_parser("detach-watch", help="Create a formal watcher callback contract and release the worker slot")
    p_detach_watch.add_argument("--id", required=True)
    p_detach_watch.add_argument("--event-id", required=True)
    p_detach_watch.add_argument("--callback-token", required=True)
    p_detach_watch.add_argument("--resume-due", required=True)
    p_detach_watch.add_argument("--job-ref", default="")
    p_detach_watch.add_argument("--watch-kind", default="web-review")
    p_detach_watch.add_argument("--child-session", default="")
    p_detach_watch.add_argument("--resource-keys", default="", help="Comma-separated resource lock keys")
    p_detach_watch.add_argument("--note", default="")
    p_callback_heartbeat = sub.add_parser("callback-heartbeat", help="Refresh heartbeat for detached callback")
    p_callback_heartbeat.add_argument("--id", required=True)
    p_callback_heartbeat.add_argument("--callback-token", required=True)
    p_callback_heartbeat.add_argument("--resume-due", default="")
    p_callback_heartbeat.add_argument("--note", default="")
    p_callback_complete = sub.add_parser("callback-complete", help="Complete detached callback success and optionally resume the task")
    p_callback_complete.add_argument("--id", required=True)
    p_callback_complete.add_argument("--callback-token", required=True)
    p_callback_complete.add_argument("--proof", required=True)
    p_callback_complete.add_argument("--closed-by", default="callback")
    p_callback_complete.add_argument("--resume-phase", default="")
    p_callback_complete.add_argument("--resume-note", default="")
    p_callback_complete.add_argument("--child-session", default="")
    p_callback_fail = sub.add_parser("callback-fail", help="Terminal close for detached callback failure")
    p_callback_fail.add_argument("--id", required=True)
    p_callback_fail.add_argument("--callback-token", required=True)
    p_callback_fail.add_argument("--reason", required=True)
    p_callback_fail.add_argument("--closed-by", default="callback")
    p_release = sub.add_parser("release", help="Clear task assignee/run metadata")
    p_release.add_argument("--id", required=True)
    p_remove = sub.add_parser("remove", help="Delete task from ledger")
    p_remove.add_argument("--id", required=True)
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", nargs="*", help="Status filter(s)")
    p_list.add_argument("--bucket", nargs="*", help="Bucket filter(s)")
    p_evidence_search = sub.add_parser("evidence-search", help="Search canonical evidence index (raw opt-in)")
    p_evidence_search.add_argument("--query", default="", help="Substring match on canonical objective/summary/proof")
    p_evidence_search.add_argument("--ticket-id", default="", help="Optional exact ticket filter")
    p_evidence_search.add_argument("--include-raw", action="store_true", help="Include raw task proof fields")
    p_evidence_search.add_argument("--limit", type=int, default=10)
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
    if args.command == "requeue-blocked":
        return cmd_requeue_blocked(args)
    if args.command == "mark-phase":
        return cmd_mark_phase(args)
    if args.command == "detach":
        return cmd_detach(args)
    if args.command == "detach-watch":
        return cmd_detach_watch(args)
    if args.command == "callback-heartbeat":
        return cmd_callback_heartbeat(args)
    if args.command == "callback-complete":
        return cmd_callback_complete(args)
    if args.command == "callback-fail":
        return cmd_callback_fail(args)
    if args.command == "release":
        return cmd_release(args)
    if args.command == "remove":
        return cmd_remove(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "evidence-search":
        return cmd_evidence_search(args)
    if args.command == "summary":
        return cmd_summary(args)
    if args.command == "render-md":
        return cmd_render_md(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
