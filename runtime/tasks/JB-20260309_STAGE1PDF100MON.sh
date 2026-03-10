#!/usr/bin/env bash
set -euo pipefail
cd /Users/jobiseu/.openclaw/workspace

mkdir -p runtime/tasks
report="runtime/tasks/JB-20260309-STAGE1PDF100MON_report.md"
runlog="runtime/tasks/JB-20260309_stage1_pdf_live_backfill.log"
stats_json="runtime/tasks/JB-20260309_stage1_pdf_live_backfill_stats.json"
base_path="invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/**/*.pdf"
fetch_limit="${TELEGRAM_ATTACH_LIVE_FETCH_LIMIT:-2000}"
batch_size="${TELEGRAM_ATTACH_LIVE_FETCH_BATCH:-100}"
pdf_threshold="${STAGE1_PDF_MIN_COUNT:-100}"
retry_interval_sec="${STAGE1_PDF_RETRY_INTERVAL_SEC:-120}"
poll_interval_sec="${STAGE1_PDF_POLL_INTERVAL_SEC:-60}"
last_attempt_epoch=0
last_note=""

count_pdf() {
  python3 <<'PY'
import json
import sqlite3
from pathlib import Path

root = Path('/Users/jobiseu/.openclaw/workspace')
db_path = root / 'invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3'
status_path = root / 'invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json'
attach_root = root / 'invest/stages/stage1/outputs/raw/qualitative/attachments/telegram'

if db_path.exists():
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("select count(*) from pdf_documents").fetchone()
        if row and int(row[0]) > 0:
            print(int(row[0]))
            raise SystemExit(0)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

if status_path.exists():
    try:
        data = json.loads(status_path.read_text(encoding='utf-8'))
        for key in ('pdf_meta_total', 'supported_candidates', 'legacy_pdf_candidates'):
            value = int(data.get(key) or 0)
            if value > 0:
                print(value)
                raise SystemExit(0)
    except Exception:
        pass

count = sum(1 for _ in attach_root.rglob('*.pdf')) if attach_root.exists() else 0
print(count)
PY
}

ts() {
  date '+%Y-%m-%d %H:%M:%S %Z'
}

log_report() {
  printf -- '- [%s] %s\n' "$(ts)" "$1" >> "$report"
}

note_if_changed() {
  if [ "$1" != "$last_note" ]; then
    log_report "$1"
    last_note="$1"
  fi
}

live_rows() {
  python3 <<'PY'
import subprocess
out = subprocess.check_output(['ps', '-axo', 'pid=,etime=,command='], text=True)
for line in out.splitlines():
    parts = line.split(None, 2)
    if len(parts) < 3:
        continue
    pid, etime, cmd = parts
    if 'JB-20260309_STAGE1PDF100MON.sh' in cmd:
        continue
    if 'JB-20260309_stage1_pdf_live_backfill.py' in cmd:
        print(pid, etime)
PY
}

live_pids() {
  live_rows | awk '{print $1}'
}

live_running() {
  live_rows | grep -q .
}

stats_field() {
  python3 - "$stats_json" "$1" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
field = sys.argv[2]
if not path.exists():
    print('')
    raise SystemExit(0)
try:
    data = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    print('')
    raise SystemExit(0)
value = data.get(field, '')
if value is None:
    value = ''
print(value)
PY
}

if [ ! -f "$report" ]; then
  printf '# JB-20260309-STAGE1PDF100MON report\n\n' > "$report"
fi

log_report "aggressive live backfill monitor active; current_pdf_count=$(count_pdf); pdf_threshold=${pdf_threshold}; base_path=${base_path}; fetch_limit=${fetch_limit}; batch_size=${batch_size}; retry_interval_sec=${retry_interval_sec}; poll_interval_sec=${poll_interval_sec}"

while true; do
  count=$(count_pdf)
  queued=$(stats_field queued_missing_original)
  status=$(stats_field status)
  downloads_ok=$(stats_field downloads_ok)
  extract_ok=$(stats_field extract_ok)

  if [ "${count:-0}" -ge "$pdf_threshold" ]; then
    log_report "stage1 pdf threshold satisfied; current_pdf_count=${count}; pdf_threshold=${pdf_threshold}; queued_missing_original=${queued:-unknown}; status=${status:-unknown}; downloads_ok=${downloads_ok}; extract_ok=${extract_ok}; stopping monitor"
    printf 'DONE COUNT=%s PATH=%s\n' "$count" "$base_path"
    exit 0
  fi

  if [ -f "$stats_json" ] && [ "${queued:-}" = "0" ] && [ "${status:-}" = "OK" ]; then
    log_report "backfill queue empty; current_pdf_count=${count}; downloads_ok=${downloads_ok}; extract_ok=${extract_ok}; stopping monitor"
    printf 'DONE COUNT=%s PATH=%s\n' "$count" "$base_path"
    exit 0
  fi

  if live_running; then
    pids=$(live_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')
    note_if_changed "live backfill running; current_pdf_count=${count}; queued_missing_original=${queued:-unknown}; pids=${pids}; waiting"
    sleep "$poll_interval_sec"
    continue
  fi

  now=$(date +%s)
  if [ "$last_attempt_epoch" -gt 0 ]; then
    remaining=$((retry_interval_sec - (now - last_attempt_epoch)))
    if [ "$remaining" -gt 0 ]; then
      note_if_changed "backfill cooldown; current_pdf_count=${count}; queued_missing_original=${queued:-unknown}; remaining=${remaining}s"
      if [ "$remaining" -gt "$poll_interval_sec" ]; then
        sleep "$poll_interval_sec"
      else
        sleep "$remaining"
      fi
      continue
    fi
  fi

  log_report "starting aggressive live backfill; current_pdf_count=${count}; queued_missing_original=${queued:-unknown}; fetch_limit=${fetch_limit}; batch_size=${batch_size}"
  TELEGRAM_ATTACH_LIVE_FETCH_LIMIT="$fetch_limit" TELEGRAM_ATTACH_LIVE_FETCH_BATCH="$batch_size" \
    python3 runtime/tasks/JB-20260309_stage1_pdf_live_backfill.py >> "$runlog" 2>&1 &
  started_pid=$!
  last_attempt_epoch=$now
  last_note=""
  log_report "live backfill started; pid=${started_pid}"
  sleep "$poll_interval_sec"
done
