#!/usr/bin/env python3
"""
DART 백필 자동 전환 컨트롤러
- missing month 존재 시: incremental 백필 실행
- missing month 소진 시: monitor 모드 전환 + 내부 throttle(주기 완화)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/jobiseu/.openclaw/workspace")
DART_DIR = ROOT / "invest/data/raw/kr/dart"
INCREMENTAL_SCRIPT = ROOT / "invest/scripts/stage01_dart_backfill_incremental.py"
RUNTIME_DIR = ROOT / "invest/data/runtime"
STATE_PATH = RUNTIME_DIR / "dart_backfill_autopilot_state.json"
START_YM = "201601"


def ym_iter(start_ym: str, end_ym: str):
    sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    ey, em = int(end_ym[:4]), int(end_ym[4:6])
    y, m = sy, sm
    while (y < ey) or (y == ey and m <= em):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


def collected_months() -> set[str]:
    files = glob.glob(str(DART_DIR / "dart_list_*.csv"))
    months: set[str] = set()
    for fp in files:
        try:
            df = pd.read_csv(fp, usecols=["rcept_dt"])
            vals = df["rcept_dt"].astype(str).str[:6]
            months.update(v for v in vals if len(v) == 6 and v.isdigit())
        except Exception:
            continue
    return months


def detect_missing_months() -> list[str]:
    now = datetime.now()
    end_ym = now.strftime("%Y%m")
    have = collected_months()
    return [ym for ym in ym_iter(START_YM, end_ym) if ym not in have]


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: dict):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_incremental_once() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(INCREMENTAL_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    return proc.returncode, out[-1000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-monitor", action="store_true", help="테스트용: missing month를 0으로 간주")
    args = parser.parse_args()

    monitor_interval_hours = int(os.environ.get("DART_BACKFILL_MONITOR_INTERVAL_HOURS", "24"))
    monitor_interval_sec = max(3600, monitor_interval_hours * 3600)

    state = load_state()
    state.setdefault("mode", "backfill")

    missing_before = [] if args.force_monitor else detect_missing_months()
    now = int(time.time())

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "monitor_interval_hours": monitor_interval_hours,
        "force_monitor": bool(args.force_monitor),
        "missing_before_count": len(missing_before),
        "missing_before_sample": missing_before[:12],
    }

    if missing_before:
        rc, tail = run_incremental_once()
        missing_after = detect_missing_months()

        state["mode"] = "backfill"
        state["last_backfill_ts"] = now
        state["last_rc"] = rc
        state.pop("completed_at", None)
        if not missing_after:
            state["mode"] = "monitor"
            state["completed_at"] = datetime.now().isoformat(timespec="seconds")
            state["last_monitor_check_ts"] = now

        payload.update(
            {
                "action": "run_incremental",
                "incremental_rc": rc,
                "incremental_log_tail": tail,
                "missing_after_count": len(missing_after),
                "missing_after_sample": missing_after[:12],
                "mode_after": state["mode"],
            }
        )
        save_state(state)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if rc == 0 else rc

    # missing 없음: monitor 모드. 호출 주기는 hourly라도 내부 throttle로 완화.
    last_monitor_ts = int(state.get("last_monitor_check_ts", 0) or 0)
    elapsed = now - last_monitor_ts

    state["mode"] = "monitor"
    if not state.get("completed_at"):
        state["completed_at"] = datetime.now().isoformat(timespec="seconds")

    if elapsed < monitor_interval_sec:
        payload.update(
            {
                "action": "monitor_throttled",
                "elapsed_sec": elapsed,
                "remaining_sec": monitor_interval_sec - elapsed,
                "mode_after": "monitor",
            }
        )
        save_state(state)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # throttle window 경과 시 정기 모니터 체크 타임스탬프만 갱신
    state["last_monitor_check_ts"] = now
    payload.update({"action": "monitor_tick", "mode_after": "monitor", "elapsed_sec": elapsed})
    save_state(state)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
