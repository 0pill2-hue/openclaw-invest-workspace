#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/invest/venv/bin/python"
LOG="$ROOT/reports/stage_updates/logs/backfill_stage01_missing_20260219.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%F %T')] Stage01 missing-source recollection start" | tee -a "$LOG"

run_retry() {
  local name="$1"
  shift
  local attempt=1
  local ok=0
  while [ $attempt -le 2 ]; do
    echo "[$(date '+%F %T')] RUN $name attempt=$attempt" | tee -a "$LOG"
    if "$@" >> "$LOG" 2>&1; then
      ok=1
      break
    fi
    sleep $((2**attempt))
    attempt=$((attempt+1))
  done
  if [ $ok -eq 0 ]; then
    echo "[$(date '+%F %T')] FAILED $name after retries" | tee -a "$LOG"
  fi
}

run_retry stage01_fetch_stock_list "$PY" "$ROOT/invest/scripts/stage01_fetch_stock_list.py"
run_retry stage01_fetch_ohlcv "$PY" "$ROOT/invest/scripts/stage01_fetch_ohlcv.py"
run_retry stage01_fetch_supply "$PY" "$ROOT/invest/scripts/stage01_fetch_supply.py"
run_retry stage01_fetch_us_ohlcv env US_OHLCV_MAX_TICKERS_PER_RUN=503 "$PY" "$ROOT/invest/scripts/stage01_fetch_us_ohlcv.py"
run_retry stage01_fetch_news_rss "$PY" "$ROOT/invest/scripts/stage01_fetch_news_rss.py"
run_retry stage01_fetch_macro_fred "$PY" "$ROOT/invest/scripts/stage01_fetch_macro_fred.py"
run_retry stage01_fetch_global_macro "$PY" "$ROOT/invest/scripts/stage01_fetch_global_macro.py"
run_retry stage01_fetch_trends "$PY" "$ROOT/invest/scripts/stage01_fetch_trends.py"
run_retry stage01_image_harvester "$PY" "$ROOT/invest/scripts/stage01_image_harvester.py"

echo "[$(date '+%F %T')] Stage01 missing-source recollection end" | tee -a "$LOG"
