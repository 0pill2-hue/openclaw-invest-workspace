#!/usr/bin/env python3
"""Upper-level main brain guard aggregation.

Runs the local brain guard, then aggregates higher-level operating-path health for:
- Telegram response channel state from `openclaw status`
- tasks watchdog launchd/log health
- auto-dispatch launchd/status health
- current-task resume readiness via `context_policy.py resume-check --strict`

The script always emits machine-readable JSON. On failure it also provides a concise
`alert` string suitable for heartbeat forwarding.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import re

ROOT = Path(__file__).resolve().parents[2]
LOCAL_BRAIN_GUARD = ROOT / "scripts/heartbeat/local_brain_guard.py"
CONTEXT_POLICY = ROOT / "scripts/context_policy.py"
WATCHDOG_LOG = ROOT / "runtime/tasks/watchdog.launchd.log"
AUTO_DISPATCH_STATUS = ROOT / "runtime/tasks/auto_dispatch_status.json"

WATCHDOG_LABEL_KEY = "watchdog"
AUTO_DISPATCH_LABEL_KEY = "auto-dispatch"
LOCAL_BRAIN_LABEL_KEY = "local-brain-guard"
WATCHDOG_MAX_AGE = timedelta(minutes=25)
AUTO_DISPATCH_MAX_AGE = timedelta(minutes=15)

AUTO_DISPATCH_FAIL_ORCHESTRATORS = {
    "spawn_failed",
    "spawned_not_closed",
}
AUTO_DISPATCH_ALLOWED_ORCHESTRATORS = {
    "",
    "event_failed_continue",
    "recent_transition",
    "spawned_closed",
    "spawned_waiting_close",
}


@dataclass
class CommandResult:
    rc: int
    stdout: str
    stderr: str


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(cmd: list[str]) -> CommandResult:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "")


def parse_json_payload(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        return payload

    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_iso_dt(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_seconds(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    return max(0.0, (datetime.now(ts.tzinfo) - ts).total_seconds())


def format_age(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h{minutes % 60:02d}m"


def load_tail_json_objects(path: Path, count: int = 2, tail_bytes: int = 65536) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > tail_bytes:
            fh.seek(size - tail_bytes)
        text = fh.read().decode("utf-8", errors="replace")

    found: list[dict[str, Any]] = []
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            found.append(payload)
            if len(found) >= count:
                break
    found.reverse()
    return found


def flatten_str_list(values: Any) -> list[str]:
    if isinstance(values, list):
        return [str(x) for x in values]
    return []


def run_local_brain_guard() -> dict[str, Any]:
    result = run([sys.executable, str(LOCAL_BRAIN_GUARD)])
    payload = parse_json_payload(result.stdout)
    if result.rc != 0 or payload is None:
        detail = (result.stderr or result.stdout).strip()[:400]
        return {
            "ok": False,
            "issues": ["local_brain_guard_command_failed"],
            "alert": "local_brain_guard command failed",
            "rc": result.rc,
            "stdout": result.stdout.strip()[:400],
            "stderr": result.stderr.strip()[:400],
            "detail": detail,
        }

    issues = flatten_str_list(payload.get("issues"))
    alerts = flatten_str_list(payload.get("alerts"))
    return {
        "ok": bool(payload.get("ok")),
        "issues": issues,
        "alerts": alerts,
        "alert": str(payload.get("alert", "")),
        "result": payload,
    }


def run_openclaw_status() -> dict[str, Any]:
    result = run(["openclaw", "status"])
    if result.rc != 0:
        return {
            "ok": False,
            "issues": ["openclaw_status_failed"],
            "error": (result.stderr or result.stdout).strip()[:400],
            "text": result.stdout,
        }

    text = result.stdout
    issues: list[str] = []

    gateway_line = re.search(r"^│\s*Gateway\s*│\s*(.+?)\s*│$", text, re.MULTILINE)
    gateway_service_line = re.search(r"^│\s*Gateway service\s*│\s*(.+?)\s*│$", text, re.MULTILINE)
    telegram_line = re.search(r"^│\s*Telegram\s*│\s*(\S+)\s*│\s*(\S+)\s*│\s*(.*?)\s*│$", text, re.MULTILINE)

    if not telegram_line:
        issues.append("telegram_status_missing")
        telegram = {
            "enabled": "",
            "state": "",
            "detail": "",
            "ok": False,
        }
    else:
        enabled = telegram_line.group(1).strip()
        state = telegram_line.group(2).strip()
        detail = telegram_line.group(3).strip()
        if enabled != "ON":
            issues.append(f"telegram_enabled_{enabled.lower() or 'unknown'}")
        if state != "OK":
            issues.append(f"telegram_state_{state.lower() or 'unknown'}")
        telegram = {
            "enabled": enabled,
            "state": state,
            "detail": detail,
            "ok": enabled == "ON" and state == "OK",
        }

    if not gateway_line:
        issues.append("gateway_line_missing")
    if not gateway_service_line:
        issues.append("gateway_service_line_missing")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "gateway": gateway_line.group(1).strip() if gateway_line else "",
        "gateway_service": gateway_service_line.group(1).strip() if gateway_service_line else "",
        "telegram": telegram,
    }


def load_launchctl_entries() -> tuple[dict[str, dict[str, str]], list[str]]:
    result = run(["launchctl", "list"])
    if result.rc != 0:
        return {}, ["launchctl_list_failed"]

    entries: dict[str, dict[str, str]] = {}
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("PID"):
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid, status, label = parts
        entries[label] = {
            "pid": pid,
            "status": status,
            "label": label,
        }
    return entries, []


def find_launchctl_entry(entries: dict[str, dict[str, str]], keyword: str) -> dict[str, str] | None:
    candidates = [entry for label, entry in entries.items() if keyword in label]
    if not candidates:
        return None
    candidates.sort(key=lambda entry: entry["label"])
    return candidates[0]


def inspect_launchd_job(label: str) -> dict[str, Any] | None:
    domain_label = f"gui/{os.getuid()}/{label}"
    result = run(["launchctl", "print", domain_label])
    if result.rc != 0:
        return None

    text = result.stdout
    state_match = re.search(r"^\s*state = (.+?)\s*$", text, re.MULTILINE)
    exit_match = re.search(r"^\s*last exit code = (\S+)\s*$", text, re.MULTILINE)
    interval_match = re.search(r"^\s*run interval = (\d+) seconds\s*$", text, re.MULTILINE)
    return {
        "domain_label": domain_label,
        "state": state_match.group(1).strip() if state_match else "",
        "last_exit_code": int(exit_match.group(1)) if exit_match and exit_match.group(1).isdigit() else None,
        "run_interval_seconds": int(interval_match.group(1)) if interval_match and interval_match.group(1).isdigit() else None,
    }


def launchd_component(name: str, entry: dict[str, str] | None) -> dict[str, Any]:
    issues: list[str] = []
    if entry is None:
        issues.append(f"{name}_launchd_missing")
        return {"ok": False, "issues": issues, "launchd": None, "inspection": None}

    status_text = entry.get("status", "")
    inspection = inspect_launchd_job(entry.get("label", ""))
    interval_idle_ok = bool(
        inspection
        and inspection.get("state") == "not running"
        and inspection.get("last_exit_code") == 0
        and inspection.get("run_interval_seconds")
    )
    if status_text not in {"0", "-"} and not interval_idle_ok:
        issues.append(f"{name}_launchd_status_{status_text}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "launchd": entry,
        "inspection": inspection,
    }


def _watchdog_recent_result_ok(payload: dict[str, Any]) -> bool:
    if payload.get("ok") is True:
        return True

    recover_ok = bool((payload.get("recover") or {}).get("ok"))
    context_ok = bool((payload.get("context_hygiene") or {}).get("ok", True))
    issues = flatten_str_list(payload.get("issues"))
    allowed_issue_prefixes = (
        "IN_PROGRESS 무활동 30분 초과:",
        "BLOCKED:",
        "context_reset_required:",
    )
    if recover_ok and context_ok and issues and all(issue.startswith(allowed_issue_prefixes) for issue in issues):
        return True
    return False


def watchdog_component(entries: dict[str, dict[str, str]], launchctl_issues: list[str]) -> dict[str, Any]:
    issues = list(launchctl_issues)
    launchd = launchd_component("watchdog", find_launchctl_entry(entries, WATCHDOG_LABEL_KEY))
    issues.extend(launchd["issues"])

    recent_results = load_tail_json_objects(WATCHDOG_LOG, count=2)
    if not WATCHDOG_LOG.exists():
        issues.append("watchdog_log_missing")
        age = None
    else:
        age = age_seconds(datetime.fromtimestamp(WATCHDOG_LOG.stat().st_mtime))
        if age is not None and age > WATCHDOG_MAX_AGE.total_seconds():
            issues.append("watchdog_log_stale")

    if len(recent_results) < 1:
        issues.append("watchdog_recent_json_missing")
    else:
        latest_payload = recent_results[-1]
        if not _watchdog_recent_result_ok(latest_payload):
            issues.append("watchdog_recent_result_latest_failed")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "launchd": launchd.get("launchd"),
        "launchd_inspection": launchd.get("inspection"),
        "log_path": str(WATCHDOG_LOG),
        "log_age": format_age(age),
        "recent_results": recent_results,
    }


def auto_dispatch_component(entries: dict[str, dict[str, str]], launchctl_issues: list[str]) -> dict[str, Any]:
    issues = list(launchctl_issues)
    launchd = launchd_component("auto_dispatch", find_launchctl_entry(entries, AUTO_DISPATCH_LABEL_KEY))
    issues.extend(launchd["issues"])

    payload: dict[str, Any] | None = None
    age = None
    if not AUTO_DISPATCH_STATUS.exists():
        issues.append("auto_dispatch_status_missing")
    else:
        try:
            payload = json.loads(AUTO_DISPATCH_STATUS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append("auto_dispatch_status_invalid_json")
        except OSError:
            issues.append("auto_dispatch_status_read_failed")
        else:
            ts = parse_iso_dt(str(payload.get("ts", "")))
            age = age_seconds(ts)
            if age is None:
                issues.append("auto_dispatch_ts_missing")
            elif age > AUTO_DISPATCH_MAX_AGE.total_seconds():
                issues.append("auto_dispatch_status_stale")

            status = str(payload.get("status", "")).strip()
            orchestrator = str(payload.get("orchestrator", "")).strip()
            if status == "error":
                issues.append("auto_dispatch_status_error")
            elif status not in {"idle", "assigned"}:
                issues.append(f"auto_dispatch_status_{status or 'unknown'}")

            if orchestrator in AUTO_DISPATCH_FAIL_ORCHESTRATORS:
                issues.append(f"auto_dispatch_orchestrator_{orchestrator}")
            elif orchestrator not in AUTO_DISPATCH_ALLOWED_ORCHESTRATORS:
                issues.append(f"auto_dispatch_orchestrator_{orchestrator or 'unknown'}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "launchd": launchd.get("launchd"),
        "launchd_inspection": launchd.get("inspection"),
        "status_path": str(AUTO_DISPATCH_STATUS),
        "status_age": format_age(age),
        "status_payload": payload,
    }


def current_task_component() -> dict[str, Any]:
    result = run([sys.executable, str(CONTEXT_POLICY), "resume-check", "--strict"])
    payload = parse_json_payload(result.stdout)
    issues: list[str] = []

    if payload is None:
        issues.append("resume_check_json_missing")
        return {
            "ok": False,
            "issues": issues,
            "rc": result.rc,
            "stdout": result.stdout.strip()[:400],
            "stderr": result.stderr.strip()[:400],
        }

    status = payload.get("current_task_status") if isinstance(payload, dict) else None
    if not isinstance(status, dict):
        issues.append("current_task_status_missing")
    else:
        if status.get("placeholder"):
            issues.append("current_task_placeholder")
        missing_keys = status.get("missing_keys")
        if isinstance(missing_keys, list) and missing_keys:
            issues.extend([f"current_task_missing_{key}" for key in missing_keys])

    if result.rc != 0:
        issues.append(f"resume_check_rc_{result.rc}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "rc": result.rc,
        "resume_check": payload,
    }


def summarize_component_flags(checks: dict[str, dict[str, Any]]) -> str:
    order = ["local_brain", "telegram", "watchdog", "auto_dispatch", "current_task"]
    parts = []
    for name in order:
        payload = checks.get(name, {})
        parts.append(f"{name}={'OK' if payload.get('ok') else 'FAIL'}")
    return " ".join(parts)


def build_alert(failed_components: list[str], issues: list[str]) -> str:
    if not failed_components:
        return ""
    detail = ",".join(failed_components)
    issue_text = "; ".join(issues[:4])
    if issue_text:
        return f"MAIN_BRAIN_GUARD_FAIL / failed={detail} / issues={issue_text} / 다음 1액션: openclaw status --deep"
    return f"MAIN_BRAIN_GUARD_FAIL / failed={detail} / 다음 1액션: openclaw status --deep"


def main() -> None:
    local_brain = run_local_brain_guard()
    status_info = run_openclaw_status()
    launchctl_entries, launchctl_issues = load_launchctl_entries()
    watchdog = watchdog_component(launchctl_entries, launchctl_issues)
    auto_dispatch = auto_dispatch_component(launchctl_entries, launchctl_issues)
    current_task = current_task_component()

    telegram = {
        "ok": bool(status_info.get("telegram", {}).get("ok")) and bool(status_info.get("ok")),
        "issues": [x for x in status_info.get("issues", []) if x.startswith("telegram_") or x.startswith("openclaw_status_")],
        "status": status_info.get("telegram", {}),
        "gateway": status_info.get("gateway", ""),
        "gateway_service": status_info.get("gateway_service", ""),
    }
    if not status_info.get("ok") and "openclaw_status_failed" in status_info.get("issues", []):
        telegram["issues"] = list(dict.fromkeys(telegram["issues"] + ["openclaw_status_failed"]))

    checks = {
        "local_brain": local_brain,
        "telegram": telegram,
        "watchdog": watchdog,
        "auto_dispatch": auto_dispatch,
        "current_task": current_task,
    }

    failed_components = [name for name, payload in checks.items() if not payload.get("ok")]
    issues: list[str] = []
    alerts: list[str] = []

    for name, payload in checks.items():
        for issue in flatten_str_list(payload.get("issues")):
            issues.append(f"{name}:{issue}")
        direct_alert = str(payload.get("alert", "")).strip()
        if direct_alert:
            alerts.append(f"{name}:{direct_alert}")
        for item in flatten_str_list(payload.get("alerts")):
            alerts.append(f"{name}:{item}")

    ok = len(failed_components) == 0
    alert = build_alert(failed_components, issues)
    payload = {
        "ok": ok,
        "checked_at": now_str(),
        "message": "MAIN_BRAIN_GUARD_OK" if ok else "MAIN_BRAIN_GUARD_FAIL",
        "summary": summarize_component_flags(checks),
        "failed_components": failed_components,
        "issues": issues,
        "alerts": alerts,
        "alert": alert,
        "checks": checks,
        "sources": {
            "local_brain_guard": str(LOCAL_BRAIN_GUARD),
            "watchdog_log": str(WATCHDOG_LOG),
            "auto_dispatch_status": str(AUTO_DISPATCH_STATUS),
            "context_policy": str(CONTEXT_POLICY),
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
