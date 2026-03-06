#!/usr/bin/env python3
"""Heartbeat guard for main local brain.

Checks gateway/session health and local llama-server responsiveness.
Adds session-overflow recovery for local-model sessions:
- if active main session token usage is near llama context size,
  rotate (reset) the main session storage so next turn starts fresh.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lib.runtime_env import llama_model_path, sessions_store

LLAMA_MODEL_PATH = str(llama_model_path())
SESSIONS_STORE = str(sessions_store())
MAIN_SESSION_KEY = "agent:main:main"

LLAMA_SERVER_CMD = [
    "llama-server",
    "-m",
    LLAMA_MODEL_PATH,
    "--host",
    os.environ.get("OPENCLAW_LOCAL_HOST", "127.0.0.1"),
    "--port",
    os.environ.get("OPENCLAW_LOCAL_PORT", "8090"),
    "-c",
    os.environ.get("OPENCLAW_LOCAL_CTX", "12288"),
    "-ngl",
    "99",
    "--flash-attn",
    "on",
    "--cache-type-k",
    "q8_0",
    "--cache-type-v",
    "q8_0",
    "--temp",
    "0.5",
    "--top-p",
    "0.9",
    "--top-k",
    "20",
    "--min-p",
    "0.02",
    "--repeat-penalty",
    "1.05",
    "--repeat-last-n",
    "128",
    "--chat-template-kwargs",
    '{"enable_thinking": false}',
]


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""


def parse_status_health(status_text: str) -> tuple[bool, list[str]]:
    issues: list[str] = []

    m_gateway = re.search(r"^│\s*Gateway service\s*│\s*(.+?)\s*│$", status_text, re.MULTILINE)
    if not m_gateway:
        issues.append("gateway_service_line_missing")
    else:
        v = m_gateway.group(1).lower()
        if not (("running" in v) or ("active" in v)):
            issues.append("gateway_service_not_running")

    m_sessions = re.search(r"^│\s*Sessions\s*│\s*(.+?)\s*│$", status_text, re.MULTILINE)
    if not m_sessions:
        issues.append("sessions_line_missing")
    else:
        v = m_sessions.group(1).lower()
        if "default" not in v:
            issues.append("sessions_default_model_missing")

    return len(issues) == 0, issues


def probe_local_llama(timeout_sec: int = 12) -> tuple[bool, str]:
    payload = {
        "model": "Qwen3.5-35B-A3B-Q4_K_M.gguf",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "temperature": 0.0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8090/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200:
                return False, f"http_{resp.status}"
            if "choices" not in body:
                return False, "invalid_response_no_choices"
            return True, ""
    except urllib.error.HTTPError as e:
        try:
            emsg = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            emsg = str(e)
        return False, f"http_error:{e.code}:{emsg}"
    except Exception as e:
        return False, str(e)[:300]


def restart_llama_server() -> tuple[bool, str]:
    run(["pkill", "-f", f"llama-server.*{LLAMA_MODEL_PATH}"])
    time.sleep(1)
    try:
        subprocess.Popen(
            LLAMA_SERVER_CMD,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, ""
    except Exception as e:  # pragma: no cover
        return False, f"spawn_failed:{e}"


def wait_for_llama(retries: int = 8, interval_sec: int = 2) -> tuple[bool, str]:
    last_err = ""
    for _ in range(retries):
        time.sleep(interval_sec)
        ok, err = probe_local_llama(timeout_sec=8)
        if ok:
            return True, ""
        last_err = err
    return False, last_err


def running_llama_ctx() -> int:
    rc, out, _ = run(["pgrep", "-af", f"llama-server.*{LLAMA_MODEL_PATH}"])
    if rc != 0 or not out.strip():
        return 16384
    m = re.search(r"\s-c\s+(\d+)\b", out)
    return int(m.group(1)) if m else 16384


def load_main_session() -> dict | None:
    try:
        with open(SESSIONS_STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
        v = data.get(MAIN_SESSION_KEY)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def is_local_session_model(sess: dict) -> bool:
    model = str(sess.get("model", "")).lower()
    provider = str(sess.get("modelProvider", "")).lower()
    if "local" in provider:
        return True
    return ("gguf" in model) or ("qwen" in model and "gpt" not in model)


def is_session_near_context_limit(sess: dict, ctx_limit: int) -> bool:
    tokens = int(sess.get("inputTokens", 0) or 0)
    if tokens <= 0:
        return False
    return tokens >= int(ctx_limit * 0.9)


def rotate_main_session_store() -> tuple[bool, str]:
    try:
        with open(SESSIONS_STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if MAIN_SESSION_KEY not in data:
            return True, "session_missing"

        entry = data.get(MAIN_SESSION_KEY) or {}
        session_file = entry.get("sessionFile")

        del data[MAIN_SESSION_KEY]
        with open(SESSIONS_STORE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if isinstance(session_file, str) and session_file and os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass

        return True, "rotated"
    except Exception as e:
        return False, str(e)[:200]


def add_stage_failure(stage_failures: list[dict], stage: str, reason: str, detail: str = "") -> None:
    stage_failures.append({
        "stage": stage,
        "reason": reason,
        "detail": detail[:300],
        "alert": f"[{stage}] {reason}" + (f" ({detail[:120]})" if detail else ""),
    })


def main() -> None:
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stage_failures: list[dict] = []

    status_rc, status_out, status_err = run(["openclaw", "status"])
    status_healthy = False
    status_issues: list[str] = []
    gateway_restarted = False
    gateway_recovered = False

    if status_rc == 0:
        status_healthy, status_issues = parse_status_health(status_out)
        if not status_healthy:
            add_stage_failure(stage_failures, "status.initial", "status_health_check_failed", ",".join(status_issues))
    else:
        status_issues = ["status_command_failed"]
        add_stage_failure(stage_failures, "status.initial", "status_command_failed", (status_err or status_out).strip())

    llama_ok, llama_err = probe_local_llama()
    if not llama_ok:
        add_stage_failure(stage_failures, "llama.probe.initial", "local_llama_unhealthy", llama_err)

    recovered = False
    llama_restarted = False
    llama_restart_error = ""

    # Recovery order (requested):
    # 1) pkill llama 2) start llama 3) sleep 2s 4) gateway restart
    if (not status_healthy) or (not llama_ok):
        llama_restarted = True
        recovered, llama_restart_error = restart_llama_server()
        if not recovered:
            add_stage_failure(stage_failures, "recovery.llama_restart", "llama_restart_failed", llama_restart_error)

        time.sleep(2)

        gateway_restarted = True
        gw_rc, gw_out, gw_err = run(["openclaw", "gateway", "restart"])
        if gw_rc != 0:
            add_stage_failure(stage_failures, "recovery.gateway_restart", "gateway_restart_command_failed", (gw_err or gw_out).strip())

        # Re-check gateway/session health.
        status_rc, status_out, status_err = run(["openclaw", "status"])
        if status_rc == 0:
            status_healthy, status_issues = parse_status_health(status_out)
            if not status_healthy:
                add_stage_failure(stage_failures, "status.recheck", "status_health_still_unhealthy", ",".join(status_issues))
        else:
            status_healthy = False
            status_issues = ["status_command_failed"]
            add_stage_failure(stage_failures, "status.recheck", "status_command_failed", (status_err or status_out).strip())
        gateway_recovered = status_healthy

        # Re-check llama health after recovery sequence.
        if recovered:
            llama_ok, llama_err = wait_for_llama()
            recovered = llama_ok
            if not llama_ok:
                add_stage_failure(stage_failures, "llama.probe.recheck", "local_llama_still_unhealthy", llama_err)
        else:
            llama_ok = False

    # NEW: if local session is near llama context limit, rotate session store.
    session_rotated = False
    session_rotate_reason = ""
    sess = load_main_session()
    if sess:
        # Rotate if main session token load is near current llama context limit.
        # (Do not rely only on model metadata; runtime model switches may lag in sessions.json.)
        ctx_limit = running_llama_ctx()
        if is_session_near_context_limit(sess, ctx_limit):
            ok, reason = rotate_main_session_store()
            session_rotated = ok
            session_rotate_reason = reason
            if not ok:
                add_stage_failure(stage_failures, "session.rotate", "session_rotate_failed", reason)

    all_ok = status_healthy and llama_ok

    if all_ok:
        print(json.dumps({
            "ok": True,
            "checked_at": checked_at,
            "gateway_restarted": gateway_restarted,
            "gateway_recovered": gateway_recovered,
            "restarted": llama_restarted,
            "recovered": recovered,
            "session_rotated": session_rotated,
            "session_rotate_reason": session_rotate_reason,
            "issues": [],
            "stage_failures": [],
            "alerts": [],
            "message": "HEARTBEAT_OK",
        }, ensure_ascii=False))
        return

    issues: list[str] = []
    if not status_healthy:
        issues.extend(status_issues)
    if not llama_ok:
        issues.append("local_llama_unhealthy")

    alerts = [x["alert"] for x in stage_failures]
    default_alert = "MAIN_LOCAL_BRAIN_DOWN / health_check_failed / 다음 1액션: openclaw status --deep"
    composed_alert = default_alert if not alerts else f"{default_alert} | " + " ; ".join(alerts)

    result = {
        "ok": False,
        "checked_at": checked_at,
        "gateway_restarted": gateway_restarted,
        "gateway_recovered": gateway_recovered,
        "restarted": llama_restarted,
        "recovered": recovered,
        "session_rotated": session_rotated,
        "session_rotate_reason": session_rotate_reason,
        "status_rc": status_rc,
        "status_error": (status_err or status_out).strip()[:300] if status_rc != 0 else "",
        "issues": issues,
        "stage_failures": stage_failures,
        "alerts": alerts,
        "llama_probe_error": llama_err,
        "llama_restart_error": llama_restart_error,
        "alert": composed_alert,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
