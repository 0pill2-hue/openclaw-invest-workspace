#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/.venv/bin/python3"
SCRIPT="$ROOT/invest/scripts/stage01_scrape_telegram_highspeed.py"
LOG="$ROOT/reports/stage_updates/logs/backfill_telegram_20260219.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%F %T')] Telegram backfill start" | tee -a "$LOG"

ATTEMPT=1
SUCCESS=0
while [ $ATTEMPT -le 2 ]; do
  echo "[$(date '+%F %T')] attempt=$ATTEMPT full_10y" | tee -a "$LOG"
  if TELEGRAM_INCREMENTAL_ONLY=0 TELEGRAM_SCRAPE_GLOBAL_TIMEOUT_SEC=5400 TELEGRAM_SCRAPE_PER_CHANNEL_TIMEOUT_SEC=900 "$PY" "$SCRIPT" >> "$LOG" 2>&1; then
    SUCCESS=1
    break
  fi
  SLEEP_SEC=$((5*ATTEMPT))
  echo "[$(date '+%F %T')] retry_sleep=${SLEEP_SEC}s" | tee -a "$LOG"
  sleep "$SLEEP_SEC"
  ATTEMPT=$((ATTEMPT+1))
done

if [ $SUCCESS -eq 0 ]; then
  echo "[$(date '+%F %T')] FAILED telegram full backfill" | tee -a "$LOG"
fi

echo "[$(date '+%F %T')] Telegram backfill end" | tee -a "$LOG"
