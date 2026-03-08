#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/jobiseu/.openclaw/workspace

LEGACY_LOG="invest/stages/stage1/outputs/logs/runtime/launchd_stage01_watchdog.log"
RUNTIME_LOG="runtime/tasks/watchdog.launchd.log"

mkdir -p "${LEGACY_LOG:h}"
mkdir -p "${RUNTIME_LOG:h}"

log_step() {
  local message="[$(/bin/date '+%Y-%m-%d %H:%M:%S')] $1"
  print -- "$message" | tee -a "$LEGACY_LOG" >> "$RUNTIME_LOG"
}

run_step() {
  local label="$1"
  shift
  log_step "$label"
  "$@" 2>&1 | tee -a "$LEGACY_LOG" >> "$RUNTIME_LOG"
}

run_step "watchdog_cycle" /usr/bin/python3 /Users/jobiseu/.openclaw/workspace/scripts/watchdog/watchdog_cycle.py
