#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/.venv/bin/python3"
[ -x "$PY" ] || PY="$ROOT/invest/venv/bin/python"
[ -x "$PY" ] || PY="python3"

exec "$ROOT/invest/scripts/cron/cron_notify_on_failure.sh" \
  "rss_telegram_date_fix" \
  bash -lc "\
    '$PY' '$ROOT/invest/scripts/stage01_rss_date_repair.py' && \
    '$PY' '$ROOT/invest/scripts/stage01_telegram_undated_repair.py'\
  "
