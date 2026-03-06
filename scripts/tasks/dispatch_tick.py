#!/usr/bin/env python3
"""Periodic auto-dispatch tick for main orchestrator."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from typing import Any
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKDB_SCRIPT = ROOT / "scripts/tasks/db.py"
STATUS_PATH = ROOT / "runtime/tasks/auto_dispatch_status.json"
DEBUG_LOG_PATH = ROOT / "runtime/tasks/auto_dispatch_debug.log"
TASK_DB_PATH = ROOT / "runtime/tasks/tasks.db"
OPENCLAW_BIN = Path("/opt/homebrew/bin/openclaw")
NODE_BIN = Path("/opt/homebrew/bin/node")
ASSIGNEE = "main-orchestrator"
ORCH_AGENT_ID = os.environ.get("OPENCLAW_ORCH_AGENT_ID", "main").strip() or "main"
ORCH_TIMEOUT_SEC = 180
CLOSE_WAIT_SEC = 20

SUBPROCESS_ENV = dict(os.environ)
SUBPROCESS_ENV["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def now_ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_debug_log(
    *,
    run_id: str,
    ticket_id: str,
    phase: str,
    db_status: str,
    db_review_status: str,
    status_write: Any,
) -> None:
    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": now_ts(),
        "run_id": run_id,
        "ticket_id": ticket_id,
        "phase": phase,
        "db_status": db_status,
        "db_review_status": db_review_status,
        "status_write": status_write,
    }
    with DEBUG_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_ticket_db_state(ticket_id: str) -> tuple[str, str]:
    if not ticket_id or not TASK_DB_PATH.exists():
        return "", ""

    conn = sqlite3.connect(TASK_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT status, review_status FROM tasks WHERE id=?",
            (ticket_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return "", ""
    return (row["status"] or "").upper(), (row["review_status"] or "").upper()


def write_status(
    *,
    assigned_ticket: str,
    status: str,
    error: str,
    orchestrator: str = "",
    run_id: str = "",
    ticket_id: str = "",
    phase: str = "status_write",
    db_status: str = "",
    db_review_status: str = "",
) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "assigned_ticket": assigned_ticket,
        "status": status,
        "error": error,
        "orchestrator": orchestrator,
        "ts": now_ts(),
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_debug_log(
        run_id=run_id,
        ticket_id=ticket_id or assigned_ticket,
        phase=phase,
        db_status=db_status,
        db_review_status=db_review_status,
        status_write=payload,
    )


def run_task_assignment() -> tuple[int, str, str, str]:
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    cmd = [
        sys.executable,
        str(TASKDB_SCRIPT),
        "assign-next",
        "--assignee",
        ASSIGNEE,
        "--run-id",
        run_id,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, run_id, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def trigger_event(ticket_id: str, run_id: str) -> tuple[bool, str]:
    text = f"[AUTO_DISPATCH] assigned {ticket_id} assignee={ASSIGNEE} run_id={run_id}"

    openclaw_candidates: list[str] = []
    if OPENCLAW_BIN.exists():
        openclaw_candidates.append(str(OPENCLAW_BIN))
    which_openclaw = shutil.which("openclaw", path=SUBPROCESS_ENV.get("PATH"))
    if which_openclaw and which_openclaw not in openclaw_candidates:
        openclaw_candidates.append(which_openclaw)
    if not openclaw_candidates:
        openclaw_candidates.append("openclaw")

    details: list[str] = []

    for openclaw_cmd in openclaw_candidates:
        primary_cmd = [
            openclaw_cmd,
            "system",
            "event",
            "--mode",
            "now",
            "--text",
            text,
        ]
        try:
            proc = subprocess.run(primary_cmd, capture_output=True, text=True, env=SUBPROCESS_ENV)
        except FileNotFoundError as exc:
            details.append(f"{openclaw_cmd}: {exc}")
            proc = None

        if proc and proc.returncode == 0:
            return True, ""
        if proc:
            details.append((proc.stderr or proc.stdout or f"{openclaw_cmd}: event failed").strip())

        # launchd 환경에서 /usr/bin/env node 미탐지 대응
        if NODE_BIN.exists():
            fallback_cmd = [
                str(NODE_BIN),
                openclaw_cmd,
                "system",
                "event",
                "--mode",
                "now",
                "--text",
                text,
            ]
            try:
                proc2 = subprocess.run(fallback_cmd, capture_output=True, text=True, env=SUBPROCESS_ENV)
            except FileNotFoundError as exc:
                details.append(f"node fallback ({openclaw_cmd}): {exc}")
                proc2 = None

            if proc2 and proc2.returncode == 0:
                return True, ""
            if proc2:
                details.append((proc2.stderr or proc2.stdout or f"node fallback ({openclaw_cmd}) failed").strip())

    detail = " | ".join(x for x in details if x) or "openclaw system event failed"
    return False, detail


def transition_source(status: str, review_status: str) -> str:
    if status == "DONE":
        return "status:DONE"
    if status == "BLOCKED":
        return "status:BLOCKED"
    if review_status == "PASS":
        return "review:PASS"
    if review_status == "REWORK":
        return "review:REWORK"
    if review_status == "PENDING":
        return "review:PENDING"
    return "unclosed"


def ticket_closure_state(ticket_id: str) -> tuple[bool, str, str, str]:
    if not TASK_DB_PATH.exists():
        return False, "tasks.db missing", "", ""

    conn = sqlite3.connect(TASK_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT status, review_status FROM tasks WHERE id=?",
            (ticket_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return False, "ticket missing", "", ""

    status = (row["status"] or "").upper()
    review = (row["review_status"] or "").upper()
    closed = status in {"DONE", "BLOCKED"} or review in {"PASS", "REWORK"}
    source = transition_source(status, review)
    return closed, f"status={status} review_status={review} source={source}", status, review


def wait_for_close(ticket_id: str, seconds: int = CLOSE_WAIT_SEC) -> tuple[bool, str, str, str]:
    for _ in range(max(1, seconds)):
        closed, detail, db_status, db_review_status = ticket_closure_state(ticket_id)
        if closed:
            return True, detail, db_status, db_review_status
        time.sleep(1)
    closed, detail, db_status, db_review_status = ticket_closure_state(ticket_id)
    return closed, detail, db_status, db_review_status


def recent_run_transition(run_id: str) -> tuple[bool, str, str, str]:
    if not TASK_DB_PATH.exists():
        return False, "", "", ""

    conn = sqlite3.connect(TASK_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        recent_runs = [run_id] if run_id else []
        rows = conn.execute(
            """
            SELECT DISTINCT assigned_run_id
            FROM tasks
            WHERE assignee=? AND COALESCE(assigned_run_id, '')!=''
            ORDER BY datetime(assigned_at) DESC, assigned_run_id DESC
            LIMIT 8
            """,
            (ASSIGNEE,),
        ).fetchall()
        for row in rows:
            rid = (row["assigned_run_id"] or "").strip()
            if rid and rid not in recent_runs:
                recent_runs.append(rid)

        if not recent_runs:
            return False, "", "", ""

        placeholders = ",".join("?" for _ in recent_runs)
        related = conn.execute(
            f"""
            SELECT id, status, review_status, assigned_run_id
            FROM tasks
            WHERE assignee=? AND assigned_run_id IN ({placeholders})
            ORDER BY datetime(updated_at) DESC, id DESC
            """,
            (ASSIGNEE, *recent_runs),
        ).fetchall()
    finally:
        conn.close()

    for row in related:
        db_status = (row["status"] or "").upper()
        db_review_status = (row["review_status"] or "").upper()
        if db_status in {"DONE", "BLOCKED"} or db_review_status in {"PASS", "REWORK"}:
            source = transition_source(db_status, db_review_status)
            return True, row["id"], db_status, f"{db_review_status} source={source}"

    return False, "", "", ""


def run_orchestrator(ticket_id: str, run_id: str) -> tuple[bool, str]:
    message = (
        f"[AUTO_ORCHESTRATE] ticket={ticket_id} run_id={run_id}\n"
        "You are the main orchestrator.\n"
        "1) Read taskdb ticket details for the assigned ticket only.\n"
        "2) Spawn the required subagent(s) to execute it.\n"
        "3) Update task status/proof in taskdb and CLOSE the ticket with one of: DONE/BLOCKED/REWORK.\n"
        "4) If close is not possible now, set BLOCKED with explicit reason.\n"
        "5) Reply concise progress to the user."
    )

    cmd = [
        str(OPENCLAW_BIN),
        "agent",
        "--agent",
        ORCH_AGENT_ID,
        "--session-id",
        f"auto-orchestrator-{ticket_id}-{run_id}",
        "--message",
        message,
        "--json",
    ]
    if os.getenv("OPENCLAW_ORCH_LOCAL") == "1":
        cmd.insert(2, "--local")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=SUBPROCESS_ENV, timeout=ORCH_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return False, f"orchestrator timeout ({ORCH_TIMEOUT_SEC}s)"

    if proc.returncode == 0:
        return True, ""

    detail = (proc.stderr or proc.stdout or "openclaw agent orchestration failed").strip()
    return False, detail


def main() -> int:
    rc, run_id, stdout, stderr = run_task_assignment()
    append_debug_log(
        run_id=run_id,
        ticket_id="",
        phase="assign_next_result",
        db_status="",
        db_review_status="",
        status_write={"rc": rc, "stdout": stdout, "stderr": stderr},
    )

    if rc == 0:
        m = re.search(r"assigned\s+(JB-\d{8}-\d{3})", stdout)
        ticket_id = m.group(1) if m else ""
        if not ticket_id:
            error = f"assign-next succeeded but ticket parse failed: stdout={stdout!r}"
            write_status(
                assigned_ticket="",
                status="error",
                error=error,
                run_id=run_id,
                phase="status_assign_parse_error",
            )
            print(error, file=sys.stderr)
            return 1

        db_status, db_review_status = read_ticket_db_state(ticket_id)
        append_debug_log(
            run_id=run_id,
            ticket_id=ticket_id,
            phase="assigned_ticket",
            db_status=db_status,
            db_review_status=db_review_status,
            status_write="assigned_by_taskdb",
        )

        ok, event_error = trigger_event(ticket_id, run_id)
        event_warn = ""
        if not ok:
            event_warn = f"event delivery failed; continue orchestrator: {event_error}"
            db_status, db_review_status = read_ticket_db_state(ticket_id)
            write_status(
                assigned_ticket=ticket_id,
                status="assigned",
                error=event_warn,
                orchestrator="event_failed_continue",
                run_id=run_id,
                ticket_id=ticket_id,
                phase="status_event_failed_continue",
                db_status=db_status,
                db_review_status=db_review_status,
            )
            append_debug_log(
                run_id=run_id,
                ticket_id=ticket_id,
                phase="event_failed_continue",
                db_status=db_status,
                db_review_status=db_review_status,
                status_write={"event_error": event_error, "policy": "continue_orchestrator"},
            )

        orch_ok, orch_error = run_orchestrator(ticket_id, run_id)
        if not orch_ok:
            db_status, db_review_status = read_ticket_db_state(ticket_id)
            err_msg = f"{event_warn} | {orch_error}" if event_warn else orch_error
            write_status(
                assigned_ticket=ticket_id,
                status="assigned",
                error=err_msg,
                orchestrator="spawn_failed",
                run_id=run_id,
                ticket_id=ticket_id,
                phase="status_orchestrator_spawn_failed",
                db_status=db_status,
                db_review_status=db_review_status,
            )
            print(err_msg, file=sys.stderr)
            return 1

        closed, close_detail, db_status, db_review_status = wait_for_close(ticket_id)
        append_debug_log(
            run_id=run_id,
            ticket_id=ticket_id,
            phase="wait_for_close_result",
            db_status=db_status,
            db_review_status=db_review_status,
            status_write={"closed": closed, "detail": close_detail},
        )
        if not closed:
            msg = f"orchestrator spawned but ticket not closed within {CLOSE_WAIT_SEC}s ({close_detail})"
            if event_warn:
                msg = f"{event_warn} | {msg}"
            write_status(
                assigned_ticket=ticket_id,
                status="assigned",
                error=msg,
                orchestrator="spawned_not_closed",
                run_id=run_id,
                ticket_id=ticket_id,
                phase="status_not_closed",
                db_status=db_status,
                db_review_status=db_review_status,
            )
            print(msg, file=sys.stderr)
            return 1

        close_msg = f"closed {ticket_id} ({close_detail})"
        if event_warn:
            close_msg = f"{close_msg} | {event_warn}"
        write_status(
            assigned_ticket=ticket_id,
            status="assigned",
            error=close_msg,
            orchestrator="spawned_closed",
            run_id=run_id,
            ticket_id=ticket_id,
            phase="status_closed",
            db_status=db_status,
            db_review_status=db_review_status,
        )
        print(close_msg)
        return 0

    combined = f"{stdout}\n{stderr}".lower()
    if "no assignable ticket" in combined:
        transitioned, ticket_id, db_status, db_review_status = recent_run_transition(run_id)
        if transitioned:
            info = f"recent transition detected ticket={ticket_id} status={db_status} review_status={db_review_status}"
            write_status(
                assigned_ticket=ticket_id,
                status="assigned",
                error=info,
                orchestrator="recent_transition",
                run_id=run_id,
                ticket_id=ticket_id,
                phase="status_recent_transition",
                db_status=db_status,
                db_review_status=db_review_status,
            )
            print(info)
            return 0

        write_status(
            assigned_ticket="",
            status="idle",
            error="",
            run_id=run_id,
            phase="status_idle",
        )
        return 0

    error = stderr or stdout or f"assign-next failed (code={rc})"
    write_status(
        assigned_ticket="",
        status="error",
        error=error,
        run_id=run_id,
        phase="status_assign_failed",
    )
    print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
