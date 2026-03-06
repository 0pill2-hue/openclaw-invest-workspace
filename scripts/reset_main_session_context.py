#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from runtime_env import openclaw_home, sessions_store

SESSIONS_PATH = sessions_store()
SESSIONS_DIR = SESSIONS_PATH.parent
DEFAULT_SESSION_KEY = "agent:main:main"


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""


def safe_session_file(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    p = Path(path_str).expanduser().resolve()
    try:
        p.relative_to(SESSIONS_DIR.resolve())
    except Exception:
        return None
    if p.suffix != ".jsonl":
        return None
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="Hard reset OpenClaw main session context")
    parser.add_argument("--session-key", default=DEFAULT_SESSION_KEY)
    parser.add_argument("--no-restart", action="store_true", help="Do not restart gateway")
    args = parser.parse_args()

    if not SESSIONS_PATH.exists():
        print(json.dumps({"ok": False, "error": f"sessions file not found: {SESSIONS_PATH}"}, ensure_ascii=False))
        return 1

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = SESSIONS_PATH.with_name(f"sessions.backup.{ts}.json")

    try:
        shutil.copy2(SESSIONS_PATH, backup_path)
        data = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"backup_or_read_failed: {e}"}, ensure_ascii=False))
        return 1

    entry = data.pop(args.session_key, None)
    if entry is None:
        print(json.dumps({
            "ok": True,
            "changed": False,
            "message": f"session key not found: {args.session_key}",
            "backup": str(backup_path),
        }, ensure_ascii=False))
        return 0

    session_file = None
    if isinstance(entry, dict):
        session_file = safe_session_file(entry.get("sessionFile"))

    try:
        SESSIONS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"write_sessions_failed: {e}", "backup": str(backup_path)}, ensure_ascii=False))
        return 1

    session_file_deleted = False
    if session_file and session_file.exists():
        try:
            session_file.unlink()
            session_file_deleted = True
        except Exception:
            session_file_deleted = False

    restart_rc = None
    restart_out = ""
    restart_err = ""
    if not args.no_restart:
        restart_rc, restart_out, restart_err = run(["openclaw", "gateway", "restart"])

    status_rc, status_out, status_err = run(["openclaw", "status"])

    result = {
        "ok": True,
        "changed": True,
        "session_key": args.session_key,
        "backup": str(backup_path),
        "session_file_deleted": session_file_deleted,
        "gateway_restarted": (not args.no_restart),
        "gateway_restart_rc": restart_rc,
        "status_rc": status_rc,
        "next": "이후 session_status에서 context가 낮아졌는지 확인",
    }

    if restart_rc not in (None, 0):
        result["ok"] = False
        result["error"] = "gateway restart failed"
        result["restart_error"] = (restart_err or restart_out)[-500:]

    if status_rc != 0:
        result["ok"] = False
        result["error"] = "status check failed"
        result["status_error"] = (status_err or status_out)[-500:]

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
