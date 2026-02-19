#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jobiseu/.openclaw/workspace"
PY="$ROOT/invest/venv/bin/python"
SCRIPT="$ROOT/invest/scripts/stage01_fetch_dart_disclosures.py"
PRE="$ROOT/reports/stage_updates/data_backfill_metrics_pre_20260219.json"
LOG="$ROOT/reports/stage_updates/logs/backfill_dart_20260219.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%F %T')] DART backfill start" | tee -a "$LOG"

python3 - <<'PY' > "$ROOT/invest/data/runtime/dart_missing_months_20260219.txt"
import json, datetime
p='reports/stage_updates/data_backfill_metrics_pre_20260219.json'
now=datetime.datetime.now()
with open(p,'r',encoding='utf-8') as f:
    d=json.load(f)
miss=d['dart']['missing_months_by_year']
out=[]
for y in sorted(int(k) for k in miss.keys()):
    for m in miss[str(y)]:
        out.append((y,m))
for y,m in out:
    start=f"{y:04d}{m:02d}01"
    if m==12:
        y2,m2=y+1,1
    else:
        y2,m2=y,m+1
    import datetime as dt
    end=(dt.date(y2,m2,1)-dt.timedelta(days=1)).strftime('%Y%m%d')
    print(start,end)
PY

TOTAL=$(wc -l < "$ROOT/invest/data/runtime/dart_missing_months_20260219.txt" | tr -d ' ')
IDX=0
while read -r BGN END; do
  IDX=$((IDX+1))
  ATTEMPT=1
  SUCCESS=0
  while [ $ATTEMPT -le 3 ]; do
    echo "[$(date '+%F %T')] [$IDX/$TOTAL] DART ${BGN}~${END} attempt=$ATTEMPT" | tee -a "$LOG"
    if DART_BGN_DE="$BGN" DART_END_DE="$END" "$PY" "$SCRIPT" >> "$LOG" 2>&1; then
      SUCCESS=1
      break
    fi
    SLEEP_SEC=$((2**ATTEMPT))
    echo "[$(date '+%F %T')] retry_sleep=${SLEEP_SEC}s for ${BGN}~${END}" | tee -a "$LOG"
    sleep "$SLEEP_SEC"
    ATTEMPT=$((ATTEMPT+1))
  done
  if [ $SUCCESS -eq 0 ]; then
    echo "[$(date '+%F %T')] FAILED window ${BGN}~${END} after 3 attempts" | tee -a "$LOG"
  fi
  sleep 1
done < "$ROOT/invest/data/runtime/dart_missing_months_20260219.txt"

echo "[$(date '+%F %T')] DART backfill end" | tee -a "$LOG"
