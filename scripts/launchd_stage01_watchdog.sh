#!/bin/zsh
set -euo pipefail
cd /Users/jobiseu/.openclaw/workspace
if ! /usr/bin/python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py > /tmp/stage01_validate.out 2>&1; then
  openclaw system event --text "[ALERT] stage01 validation failed" --mode now >> invest/stages/stage1/outputs/logs/legacy_top_level/launchd_stage01_watchdog.log 2>&1 || true
fi
