#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/jobiseu/.openclaw/workspace
/usr/bin/python3 /Users/jobiseu/.openclaw/workspace/scripts/task_dispatch_tick.py
