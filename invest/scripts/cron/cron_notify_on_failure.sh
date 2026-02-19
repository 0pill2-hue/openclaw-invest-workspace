#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
LOG_DIR="$ROOT/reports/stage_updates/logs/cron"
mkdir -p "$LOG_DIR"

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <job_name> <command...>" >&2
  exit 2
fi

JOB_NAME="$1"
shift

TS="$(date '+%Y%m%d_%H%M%S')"
LOG="$LOG_DIR/${JOB_NAME}_${TS}.log"

if "$@" >"$LOG" 2>&1; then
  # 성공시 무소음
  exit 0
fi

RC=$?
TAIL="$(tail -n 40 "$LOG" | sed 's/"/\\"/g')"
MSG="🚨 [cron:$JOB_NAME] failed rc=$RC\nlog=$LOG\n$TAIL"

if command -v openclaw >/dev/null 2>&1; then
  openclaw message send --channel telegram "$MSG" >/dev/null 2>&1 || true
fi

exit "$RC"
