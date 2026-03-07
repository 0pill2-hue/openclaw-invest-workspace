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
        "ok": False,
        "final_returncode": 1,
        "attempts": attempts,
    }

    if has_secret_env:
        rc, attempt = _run("highspeed", HIGH)
        attempts.append(attempt)
        if rc == 0:
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
        if fb_rc == 0:
            payload.update({
                "successful_collector": "public_fallback",
                "ok": True,
                "final_returncode": 0,
            })
            _save_status(payload)
            return 0

        payload["final_returncode"] = rc
        _save_status(payload)
        return rc

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
