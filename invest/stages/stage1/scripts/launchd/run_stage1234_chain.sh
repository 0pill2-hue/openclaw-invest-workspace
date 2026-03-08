#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${INVEST_PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi
export REPO_ROOT="$ROOT"

mkdir -p \
  invest/stages/stage1/outputs/logs/runtime \
  invest/stages/stage1/outputs/runtime \
  invest/stages/stage2/outputs/runtime \
  invest/stages/stage2/outputs/logs/runtime \
  invest/stages/stage3/outputs/logs/runtime \
  invest/stages/stage4/outputs/logs/runtime \
  invest/stages/stage5/outputs/logs/runtime
LOCKDIR="/tmp/stage1234_chain.lock"
LOCK_META="$LOCKDIR/owner.pid"
LOCK_TTL_SEC="${STAGE1234_LOCK_TTL_SEC:-21600}"
STATE="invest/stages/stage1/outputs/runtime/stage1234_chain_state.json"
LOGFILE="invest/stages/stage1/outputs/logs/runtime/launchd_stage1234_chain.log"

try_acquire_lock() {
  mkdir "$LOCKDIR" 2>/dev/null
}

cleanup_stale_lock_if_safe() {
  [[ -d "$LOCKDIR" ]] || return 1

  local now_epoch mtime age pid=""
  now_epoch=$(date +%s)
  mtime=$(stat -f %m "$LOCKDIR" 2>/dev/null || echo "$now_epoch")
  age=$((now_epoch - mtime))

  if [[ -f "$LOCK_META" ]]; then
    pid=$(head -n 1 "$LOCK_META" 2>/dev/null || true)
  fi

  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] stage1234 chain skipped (active lock pid=${pid}, age=${age}s)" >> "$LOGFILE"
    return 1
  fi

  if (( age < LOCK_TTL_SEC )); then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] stage1234 chain skipped (lock age=${age}s < ttl=${LOCK_TTL_SEC}s)" >> "$LOGFILE"
    return 1
  fi

  rm -rf "$LOCKDIR" >/dev/null 2>&1 || return 1
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] stage1234 stale lock cleaned (pid=${pid:-unknown}, age=${age}s, ttl=${LOCK_TTL_SEC}s)" >> "$LOGFILE"
  return 0
}

if ! try_acquire_lock; then
  cleanup_stale_lock_if_safe || exit 0
  if ! try_acquire_lock; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] stage1234 chain skipped (lock re-acquire failed)" >> "$LOGFILE"
    exit 0
  fi
fi
printf '%s\n%s\n' "$$" "$(date '+%Y-%m-%d %H:%M:%S')" > "$LOCK_META"
trap 'rm -rf "$LOCKDIR" >/dev/null 2>&1 || true' EXIT

RUN_KEY="$(TZ=Asia/Seoul date +%F)-DAILY"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOGFILE"
}

tg_notify() {
  local msg="$1"
  openclaw message send --channel telegram "$msg" >> "$LOGFILE" 2>&1 || \
  openclaw system event --text "$msg" --mode now >> "$LOGFILE" 2>&1 || true
}

fail_close_exit() {
  local exit_code="$1"
  local reason="$2"
  log "FAIL_CLOSE ${reason} (run_key=${RUN_KEY}, exit_code=${exit_code})"
  tg_notify "🚨 [invest] stage1234 fail-close: ${reason} (run_key=${RUN_KEY}, exit_code=${exit_code})"
  exit "$exit_code"
}

run_with_retry() {
  local stage="$1"
  local timeout_s="$2"
  local attempts="$3"
  local logfile="$4"
  shift 4

  local attempt rc=1
  for ((attempt=1; attempt<=attempts; attempt++)); do
    log "${stage} attempt ${attempt}/${attempts} start (timeout=${timeout_s}s)"

    if "$PYTHON_BIN" - "$timeout_s" "$@" >> "$logfile" 2>&1 <<'PY'
import subprocess, sys

timeout = int(sys.argv[1])
cmd = sys.argv[2:]
try:
    p = subprocess.run(cmd, timeout=timeout)
    raise SystemExit(p.returncode)
except subprocess.TimeoutExpired:
    print(f"TIMEOUT_EXPIRED|timeout={timeout}s|cmd={' '.join(cmd)}")
    raise SystemExit(124)
PY
    then
      rc=0
    else
      rc=$?
    fi

    if [[ $rc -eq 0 ]]; then
      log "${stage} attempt ${attempt}/${attempts} success"
      return 0
    fi

    log "${stage} attempt ${attempt}/${attempts} failed rc=${rc}"
    if [[ $attempt -lt $attempts ]]; then
      sleep 10
    fi
  done

  tg_notify "🚨 [invest] ${stage} failed after ${attempts} attempts (run_key=${RUN_KEY}, rc=${rc})"
  return $rc
}

stage2_gate_once() {
  "$PYTHON_BIN" - >> "invest/stages/stage2/outputs/logs/runtime/launchd_stage02_auto.log" 2>&1 <<'PY'
#!/usr/bin/env python3
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ['REPO_ROOT']).resolve()
TZ = ZoneInfo('Asia/Seoul')
STATE_PATH = ROOT / 'invest/stages/stage2/outputs/runtime/stage02_auto_state.json'
STAGE2_QC_SCRIPT = ROOT / 'invest/stages/stage2/scripts/stage02_qc_cleaning_full.py'
STAGE2_REFINE_SCRIPT = ROOT / 'invest/stages/stage2/scripts/stage02_onepass_refine_full.py'
PYTHON_BIN = os.environ.get('INVEST_PYTHON_BIN', 'python3')

WINDOW_MODE = os.getenv('STAGE2_WINDOW_MODE', 'daily').lower()
COOLDOWN_HOURS = int(os.getenv('STAGE2_COOLDOWN_HOURS', '6'))
CUTOFF_HOUR = int(os.getenv('STAGE2_CUTOFF_HOUR', '23'))
CUTOFF_MINUTE = int(os.getenv('STAGE2_CUTOFF_MINUTE', '0'))

STAGE1_PATTERNS = [
    'invest/stages/stage1/outputs/raw/signal/us/ohlcv/*.csv',
    'invest/stages/stage1/outputs/raw/signal/kr/ohlcv/*.csv',
    'invest/stages/stage1/outputs/raw/signal/kr/supply/*_supply.csv',
    # stage1 실행 완료 시 항상 갱신되는 상태 파일(시장 휴장일에도 갱신됨)
    'invest/stages/stage1/outputs/runtime/daily_update_status.json',
]

def now_kst() -> datetime:
    return datetime.now(TZ)

def current_run_key(now: datetime) -> str:
    day = now.date().isoformat()
    if WINDOW_MODE == 'ampm':
        return f"{day}-AM" if now.hour < 12 else f"{day}-PM"
    return f"{day}-DAILY"

def parse_iso(value: str):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except Exception:
        return None

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}

def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

def latest_stage1_mtime():
    mtimes = []
    for pattern in STAGE1_PATTERNS:
        for fp in glob.glob(str(ROOT / pattern)):
            try:
                mtimes.append(os.path.getmtime(fp))
            except OSError:
                pass
    return max(mtimes) if mtimes else None

def main() -> int:
    now = now_kst()
    run_key = current_run_key(now)
    cutoff = now.replace(hour=CUTOFF_HOUR, minute=CUTOFF_MINUTE, second=0, microsecond=0)

    state = load_state()
    state['window_mode'] = WINDOW_MODE
    state['run_key'] = run_key
    state['last_attempt_kst'] = now.isoformat()

    if state.get('last_success_run_key') == run_key:
        msg = f'already_succeeded_run_key({run_key})'
        state['last_result'] = msg
        save_state(state)
        print(f"[{now.isoformat()}] stage02 auto: {msg}, skip")
        return 0

    last_success_dt = parse_iso(state.get('last_success_kst', ''))
    if last_success_dt is not None:
        elapsed = now - last_success_dt
        if elapsed < timedelta(hours=COOLDOWN_HOURS):
            msg = f'cooldown_active(elapsed={elapsed}, need={COOLDOWN_HOURS}h)'
            state['last_result'] = msg
            save_state(state)
            print(f"[{now.isoformat()}] stage02 auto: {msg}, skip")
            return 0

    mtime = latest_stage1_mtime()
    if mtime is None:
        msg = 'stage1_artifact_missing_before_cutoff' if now < cutoff else 'stage1_artifact_missing_after_cutoff'
        state['last_result'] = msg
        save_state(state)
        print(f"[{now.isoformat()}] stage02 auto: {msg}, skip")
        return 0

    try:
        latest_kst = datetime.fromtimestamp(mtime, TZ)
    except Exception as exc:
        msg = f'stage1_mtime_parse_error(error={exc})'
        state['last_result'] = msg
        save_state(state)
        print(f"[{now.isoformat()}] stage02 auto: {msg}, skip")
        return 0

    state['latest_stage1_kst'] = latest_kst.isoformat()
    age = now - latest_kst
    stage1_fresh = timedelta(0) <= age <= timedelta(hours=24)

    if not stage1_fresh:
        if age < timedelta(0):
            msg = f'stage1_timestamp_in_future(latest={latest_kst.isoformat()})'
        elif now < cutoff:
            msg = f'waiting_stage1_fresh_within_24h_before_cutoff(latest={latest_kst.isoformat()}, age={age})'
        else:
            msg = f'stale_stage1_over_24h_after_cutoff(latest={latest_kst.isoformat()}, age={age})'
        state['last_result'] = msg
        save_state(state)
        print(f"[{now.isoformat()}] stage02 auto: {msg}, skip")
        return 0

    print(f"[{now.isoformat()}] stage02 auto: start run_key={run_key} (latest_stage1={latest_kst.isoformat()})")

    qc = subprocess.run([PYTHON_BIN, str(STAGE2_QC_SCRIPT)], cwd=str(ROOT))
    if qc.returncode != 0:
        state['last_result'] = f'failed_qc_rc_{qc.returncode}'
        save_state(state)
        print(f"[{now.isoformat()}] stage02 auto: qc failed rc={qc.returncode}")
        return qc.returncode

    refine = subprocess.run([PYTHON_BIN, str(STAGE2_REFINE_SCRIPT)], cwd=str(ROOT))
    if refine.returncode != 0:
        state['last_result'] = f'failed_refine_rc_{refine.returncode}'
        save_state(state)
        print(f"[{now.isoformat()}] stage02 auto: refine failed rc={refine.returncode}")
        return refine.returncode

    state['last_success_kst'] = now.isoformat()
    state['last_success_run_key'] = run_key
    state['last_result'] = 'success'
    save_state(state)
    print(f"[{now.isoformat()}] stage02 auto: success run_key={run_key} (qc+refine)")
    return 0

if __name__ == '__main__':
    sys.exit(main())
PY
}

run_stage2_gate_with_retry() {
  local attempts=2
  local attempt rc=1

  for ((attempt=1; attempt<=attempts; attempt++)); do
    log "stage02_auto_gate attempt ${attempt}/${attempts} start"

    if stage2_gate_once; then
      rc=0
    else
      rc=$?
    fi

    if [[ $rc -eq 0 ]]; then
      log "stage02_auto_gate attempt ${attempt}/${attempts} success"
      return 0
    fi

    log "stage02_auto_gate attempt ${attempt}/${attempts} failed rc=${rc}"
    if [[ $attempt -lt $attempts ]]; then
      sleep 10
    fi
  done

  tg_notify "🚨 [invest] stage02_auto_gate failed after ${attempts} attempts (run_key=${RUN_KEY}, rc=${rc})"
  return $rc
}

log "stage1234 chain start run_key=${RUN_KEY}"

# Stage1
run_with_retry "stage01_daily_update" 5400 2 "invest/stages/stage1/outputs/logs/runtime/launchd_stage01_daily.log" \
  "$PYTHON_BIN" invest/stages/stage1/scripts/stage01_daily_update.py --profile daily_full

set +e
run_with_retry "stage01_checkpoint_gate" 900 1 "invest/stages/stage1/outputs/logs/runtime/launchd_stage01_daily.log" \
  "$PYTHON_BIN" invest/stages/stage1/scripts/stage01_checkpoint_gate.py
S1_CHECKPOINT_RC=$?
set -e
if [[ $S1_CHECKPOINT_RC -ne 0 ]]; then
  fail_close_exit 11 "stage01_checkpoint_gate failed rc=${S1_CHECKPOINT_RC}"
fi

set +e
run_with_retry "stage01_post_collection_validate" 900 1 "invest/stages/stage1/outputs/logs/runtime/launchd_stage01_daily.log" \
  "$PYTHON_BIN" invest/stages/stage1/scripts/stage01_post_collection_validate.py
S1_POST_COLLECTION_RC=$?
set -e
if [[ $S1_POST_COLLECTION_RC -ne 0 ]]; then
  fail_close_exit 12 "stage01_post_collection_validate failed rc=${S1_POST_COLLECTION_RC}"
fi
log "stage01 gates passed (checkpoint+post_collection, run_key=${RUN_KEY})"

# Stage1 OCR rolling (attach tmp/image_map 미처리 큐 점진 소진)
run_with_retry "stage01_images_ocr_rolling" 1200 1 "invest/stages/stage1/outputs/logs/runtime/launchd_stage01_daily.log" \
  "$PYTHON_BIN" invest/stages/stage1/scripts/stage01_run_images_ocr_rolling.py --batch-size "${STAGE01_OCR_ROLLING_BATCH:-80}" --max-scan "${STAGE01_OCR_ROLLING_SCAN:-5000}"

set +e
run_with_retry "stage01_ocr_postprocess_validate" 600 1 "invest/stages/stage1/outputs/logs/runtime/launchd_stage01_daily.log" \
  "$PYTHON_BIN" invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py
S1_OCR_VALIDATE_RC=$?
set -e
if [[ $S1_OCR_VALIDATE_RC -ne 0 ]]; then
  fail_close_exit 13 "stage01_ocr_postprocess_validate failed rc=${S1_OCR_VALIDATE_RC}"
fi
log "stage01 OCR postprocess validate passed (run_key=${RUN_KEY})"

# Stage2 (run_key/cooldown/cutoff 게이트 포함)
set +e
run_stage2_gate_with_retry
S2_GATE_RC=$?
set -e
if [[ $S2_GATE_RC -ne 0 ]]; then
  fail_close_exit 21 "stage02_auto_gate execution failed rc=${S2_GATE_RC}"
fi

# Stage2 상태 판독 (fail-close: success가 아니면 stage4/4 금지)
S2_STATUS=$("$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

p = Path(os.environ['REPO_ROOT']).resolve() / 'invest/stages/stage2/outputs/runtime/stage02_auto_state.json'
if not p.exists():
    print('missing_state')
    raise SystemExit

s = json.loads(p.read_text(encoding='utf-8'))
rk = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat() + '-DAILY'
last_result = str(s.get('last_result', ''))
same_day_success_equivalent = last_result == 'success' or last_result.startswith('already_succeeded_run_key(')
if same_day_success_equivalent and s.get('last_success_run_key') == rk:
    print('success')
else:
    print(last_result or 'unknown')
PY
)

if [[ "$S2_STATUS" != "success" ]]; then
  fail_close_exit 22 "stage02 gate not passed (stage2_status=${S2_STATUS})"
fi
log "stage02 gate passed (run_key=${RUN_KEY})"

# Stage3 입력 빌드 (Stage1 raw -> Stage3 JSONL)
run_with_retry "stage03_input_build" 900 2 "invest/stages/stage3/outputs/logs/runtime/launchd_stage03_local_brain.log" \
  "$PYTHON_BIN" invest/stages/stage3/scripts/stage03_build_input_jsonl.py

# Stage3 (local brain attention gate)
STAGE3_CMD=(
  "$PYTHON_BIN"
  invest/stages/stage3/scripts/stage03_attention_gate_local_brain.py
  --input-jsonl invest/stages/stage3/inputs/stage2_text_meta_records.jsonl
  --output-csv invest/stages/stage3/outputs/features/attention_sentiment_features.csv
  --summary-json invest/stages/stage3/outputs/STAGE3_LOCAL_BRAIN_RUN_latest.json
)
if [[ "${STAGE3_BOOTSTRAP_EMPTY_OK:-1}" == "1" ]]; then
  STAGE3_CMD+=(--bootstrap-empty-ok)
fi
run_with_retry "stage03_local_brain_attention" 1800 2 "invest/stages/stage3/outputs/logs/runtime/launchd_stage03_local_brain.log" "${STAGE3_CMD[@]}"

# Stage4+4 run_key idempotency
LAST_KEY=$("$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
p = Path(os.environ['REPO_ROOT']).resolve() / 'invest/stages/stage1/outputs/runtime/stage1234_chain_state.json'
if not p.exists():
    print('')
    raise SystemExit
try:
    s = json.loads(p.read_text(encoding='utf-8'))
    print(s.get('last_success_run_key', ''))
except Exception:
    print('')
PY
)

if [[ "$LAST_KEY" == "$RUN_KEY" ]]; then
  log "stage1234 chain skip stage4/4 (already done run_key=${RUN_KEY})"
  exit 0
fi

# Stage4
run_with_retry "stage04_value_calc" 3600 2 "invest/stages/stage4/outputs/logs/runtime/launchd_stage04_auto.log" \
  "$PYTHON_BIN" invest/stages/stage4/scripts/calculate_stage4_values.py

# Stage5
run_with_retry "stage05_feature_engineer" 3600 2 "invest/stages/stage5/outputs/logs/runtime/launchd_stage05_auto.log" \
  "$PYTHON_BIN" invest/stages/stage5/scripts/stage05_feature_engineer.py

"$PYTHON_BIN" - <<PY
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
p = Path(os.environ['REPO_ROOT']).resolve() / 'invest/stages/stage1/outputs/runtime/stage1234_chain_state.json'
state = {}
if p.exists():
    try:
        state = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        state = {}
state['last_success_run_key'] = '${RUN_KEY}'
state['last_success_kst'] = datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
PY

log "stage1234 chain done run_key=${RUN_KEY}"
tg_notify "✅ [invest] stage1234 chain success (run_key=${RUN_KEY})"
