#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/jobiseu/.openclaw/workspace

mkdir -p invest/stages/stage1/outputs/logs/runtime
mkdir -p runtime/tasks

echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] validate_tasks" >> invest/stages/stage1/outputs/logs/runtime/launchd_stage01_watchdog.log
/usr/bin/python3 /Users/jobiseu/.openclaw/workspace/scripts/tasks/watchdog_validate.py >> invest/stages/stage1/outputs/logs/runtime/launchd_stage01_watchdog.log 2>&1

echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] auto_recover" >> invest/stages/stage1/outputs/logs/runtime/launchd_stage01_watchdog.log
/usr/bin/python3 /Users/jobiseu/.openclaw/workspace/scripts/tasks/watchdog_recover.py >> invest/stages/stage1/outputs/logs/runtime/launchd_stage01_watchdog.log 2>&1
