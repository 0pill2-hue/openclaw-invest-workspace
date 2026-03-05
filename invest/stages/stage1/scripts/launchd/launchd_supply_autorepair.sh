#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/.venv/bin/python3"
[ -x "$PY" ] || PY="$ROOT/invest/venv/bin/python"
[ -x "$PY" ] || PY="python3"

exec "$ROOT/invest/stages/stage1/scripts/launchd/launchd_notify_on_failure.sh" \
  "kr_supply_autorepair" \
  "$PY" "$ROOT/invest/stages/stage1/scripts/stage01_supply_autorepair.py" --max-repair 3
