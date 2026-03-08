from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DIR = WORKSPACE_ROOT / "invest/stages/stage1/outputs/runtime"
EVENT_LOG_PATH = RUNTIME_DIR / "pipeline_events.jsonl"


@lru_cache(maxsize=1)
def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(WORKSPACE_ROOT),
            text=True,
        ).strip()
    except Exception:
        return ""


def _scheduler_origin() -> str:
    raw = os.environ.get("SCHEDULER_ORIGIN", "").strip()
    if raw:
        return raw
    if os.environ.get("LAUNCHD_JOB_LABEL"):
        return "launchd"
    return "manual"


def _failure_kind(errors: list[str]) -> str:
    text = "\n".join(errors).lower()
    if not text:
        return ""
    if "already running" in text or "lock exists" in text or "duplicate" in text:
        return "duplicate_run"
    if "authorization failed" in text or "auth" in text:
        return "auth_error"
    if "modulenotfounderror" in text or "no module named" in text or "command not found" in text:
        return "dependency_missing"
    if "timeout" in text:
        return "timeout"
    if "http error" in text or "connection failed" in text or "max retries exceeded" in text or "temporarily unavailable" in text:
        return "network_error"
    if "nameerror" in text or "filenotfounderror" in text or "path" in text:
        return "path_error"
    if "jsondecodeerror" in text or "keyerror" in text or "valueerror" in text or "typeerror" in text:
        return "invalid_state"
    if "permission denied" in text or "read-only" in text or "write" in text:
        return "output_write_failure"
    return "unknown_failure"


def append_pipeline_event(source: str, status: str, count: int = 0, errors: Iterable[str] | None = None, note: str = "") -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    error_list = [str(x) for x in (errors or [])]
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "status": str(status),
        "count": int(count or 0),
        "errors": error_list,
        "failure_kind": _failure_kind(error_list),
        "note": str(note or ""),
        "provenance": {
            "run_id": os.environ.get("STAGE1_RUN_ID", "").strip(),
            "profile": os.environ.get("STAGE1_PROFILE", "").strip(),
            "scheduler_origin": _scheduler_origin(),
            "launchd_job_label": os.environ.get("LAUNCHD_JOB_LABEL", "").strip(),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "python": sys.executable,
            "git_commit": _git_commit(),
        },
    }
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
