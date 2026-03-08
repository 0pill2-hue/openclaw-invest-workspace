#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HIGH = ROOT / "invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py"
FALLBACK = ROOT / "invest/stages/stage1/scripts/stage01_scrape_telegram_public_fallback.py"
STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/telegram_collector_status.json"
HIGH_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/telegram_last_run_status.json"
FALLBACK_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/telegram_public_fallback_status.json"
ALLOWLIST_PATH = ROOT / "invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt"


def _has_secret_env() -> bool:
    return bool(os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH"))


def _save_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run(label: str, path: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(path)], cwd=str(ROOT))
    attempt = {
        "collector": label,
        "script": str(path.relative_to(ROOT)),
        "returncode": int(proc.returncode),
        "ok": proc.returncode == 0,
    }
    return int(proc.returncode), attempt


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _allowlist_total() -> int:
    if not ALLOWLIST_PATH.exists():
        return 0
    total = 0
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        total += 1
    return total


def _coverage_incomplete(high_status: dict) -> tuple[bool, str]:
    allowlist_total = _allowlist_total()
    channels_targeted = int(high_status.get("channels_targeted", 0) or 0)
    channels_collected = int(high_status.get("channels_collected", 0) or 0)
    failed_count = int(high_status.get("failed_count", 0) or 0)
    if allowlist_total <= 0:
        return False, "allowlist_empty"
    if channels_targeted != allowlist_total:
        return True, f"channels_targeted={channels_targeted} != allowlist_total={allowlist_total}"
    if channels_collected != allowlist_total:
        return True, f"channels_collected={channels_collected} != allowlist_total={allowlist_total}"
    if failed_count != 0:
        return True, f"failed_count={failed_count} != 0"
    return False, "complete"


def main() -> int:
    has_secret_env = _has_secret_env()
    selected = "highspeed" if has_secret_env else "public_fallback"
    attempts: list[dict] = []

    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "has_secret_env": has_secret_env,
        "selected_collector": selected,
        "successful_collector": None,
        "fallback_used": False,
        "fallback_reason": "",
        "ok": False,
        "final_returncode": 1,
        "attempts": attempts,
        "highspeed_status_path": str(HIGH_STATUS_PATH.relative_to(ROOT)),
        "public_fallback_status_path": str(FALLBACK_STATUS_PATH.relative_to(ROOT)),
    }

    if has_secret_env:
        rc, attempt = _run("highspeed", HIGH)
        attempts.append(attempt)
        high_status = _load_json(HIGH_STATUS_PATH)
        incomplete, reason = _coverage_incomplete(high_status)

        if rc == 0 and not incomplete:
            payload.update({
                "successful_collector": "highspeed",
                "ok": True,
                "final_returncode": 0,
            })
            _save_status(payload)
            return 0

        fb_rc, fb_attempt = _run("public_fallback", FALLBACK)
        attempts.append(fb_attempt)
        payload["fallback_used"] = True
        payload["fallback_reason"] = reason if rc == 0 else f"highspeed_returncode={rc}"
        if fb_rc == 0:
            payload.update({
                "successful_collector": "highspeed+public_fallback" if rc == 0 else "public_fallback",
                "ok": True,
                "final_returncode": 0,
            })
            _save_status(payload)
            return 0

        payload["final_returncode"] = rc if rc != 0 else fb_rc
        _save_status(payload)
        return payload["final_returncode"]

    rc, attempt = _run("public_fallback", FALLBACK)
    attempts.append(attempt)
    payload.update({
        "successful_collector": "public_fallback" if rc == 0 else None,
        "ok": rc == 0,
        "final_returncode": rc,
    })
    _save_status(payload)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
