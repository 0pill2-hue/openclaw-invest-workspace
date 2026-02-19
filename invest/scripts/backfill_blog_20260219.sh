#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/invest/venv/bin/python"
SCRIPT="$ROOT/invest/scripts/stage01_scrape_all_posts_v2.py"
LOG="$ROOT/invest/reports/stage_updates/logs/backfill_blog_20260219.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%F %T')] Blog backfill start" | tee -a "$LOG"

PASSES=${BLOG_BACKFILL_PASSES:-6}
for ((i=1; i<=PASSES; i++)); do
  ATTEMPT=1
  SUCCESS=0
  while [ $ATTEMPT -le 3 ]; do
    echo "[$(date '+%F %T')] pass=$i/$PASSES attempt=$ATTEMPT" | tee -a "$LOG"
    if BLOG_MAX_BUDDIES_PER_RUN=120 BLOG_REQUEST_DELAY_SEC=0.08 "$PY" "$SCRIPT" >> "$LOG" 2>&1; then
      SUCCESS=1
      break
    fi
    SLEEP_SEC=$((2**ATTEMPT))
    echo "[$(date '+%F %T')] retry_sleep=${SLEEP_SEC}s pass=$i" | tee -a "$LOG"
    sleep "$SLEEP_SEC"
    ATTEMPT=$((ATTEMPT+1))
  done
  if [ $SUCCESS -eq 0 ]; then
    echo "[$(date '+%F %T')] FAILED pass=$i after 3 attempts" | tee -a "$LOG"
  fi
  sleep 2
done

echo "[$(date '+%F %T')] Blog backfill end" | tee -a "$LOG"
