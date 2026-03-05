#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/.venv/bin/python3"
[ -x "$PY" ] || PY="$ROOT/invest/venv/bin/python"
[ -x "$PY" ] || PY="python3"

export DART_BACKFILL_MONITOR_INTERVAL_HOURS="24"

exec "$ROOT/invest/stages/stage1/scripts/launchd/launchd_notify_on_failure.sh" \
  "dart_backfill_autopilot" \
  "$PY" "$ROOT/invest/stages/stage1/scripts/stage01_dart_backfill_autopilot.py"
