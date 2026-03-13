#!/usr/bin/env bash
set -euo pipefail

SRC="/Users/jobiseu/.openclaw/workspace/skills/web-review/"
DST="/Users/jobiseu/.agents/skills/web-review/"

mkdir -p "$DST"
rsync -a --delete --exclude '__pycache__/' --exclude '*.pyc' "$SRC" "$DST"
echo "synced: $SRC -> $DST"
