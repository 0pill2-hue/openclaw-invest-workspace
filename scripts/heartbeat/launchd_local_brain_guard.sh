#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/jobiseu/.openclaw/workspace

mkdir -p runtime/heartbeat

echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] local_brain_guard" >> runtime/heartbeat/local_brain_guard.launchd.log
/usr/bin/python3 /Users/jobiseu/.openclaw/workspace/scripts/heartbeat/local_brain_guard.py >> runtime/heartbeat/local_brain_guard.launchd.log 2>&1
