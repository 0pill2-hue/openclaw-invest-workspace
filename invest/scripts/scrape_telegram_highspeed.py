import asyncio
import os
import subprocess
import sys
import time
import json
import fcntl
from datetime import datetime, timedelta, timezone

try:
    from telethon import TelegramClient
except ModuleNotFoundError:
    # Cron may run with system python; re-exec with workspace venv if available.
    venv_py = '/Users/jobiseu/.openclaw/workspace/.venv/bin/python3'
    if os.path.exists(venv_py) and os.path.realpath(sys.executable) != os.path.realpath(venv_py):
        os.execv(venv_py, [venv_py] + sys.argv)
    raise

from pipeline_logger import append_pipeline_event

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)


# Load .env file if exists
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()

# API credentials from environment (security fix)
api_id = int(os.environ.get('TELEGRAM_API_ID', '0'))
api_hash = os.environ.get('TELEGRAM_API_HASH', '')

if not api_id or not api_hash:
    err = "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment."
    print(f"ERROR: {err}")
    append_pipeline_event("scrape_telegram_highspeed", "FAILED", count=0, errors=[err], note="missing telegram credentials")
    sys.exit(1)

# Save directory
save_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/alternative/telegram_logs'
os.makedirs(save_dir, exist_ok=True)

# Time windows
target_date = datetime.now(timezone.utc) - timedelta(days=365)
bootstrap_lookback_days = int(os.environ.get('TELEGRAM_BOOTSTRAP_LOOKBACK_DAYS', '3'))
bootstrap_date = datetime.now(timezone.utc) - timedelta(days=max(1, bootstrap_lookback_days))

LOCK_FILE = '/Users/jobiseu/.openclaw/workspace/invest/data/runtime/telegram_scrape.lock'
CHECKPOINT_FILE = '/Users/jobiseu/.openclaw/workspace/invest/data/runtime/telegram_scrape_checkpoint.json'
ALLOWLIST_FILE = '/Users/jobiseu/.openclaw/workspace/invest/config/telegram_channel_allowlist.txt'
INVEST_KEYWORDS = (
    '투자', '주식', '리서치', '뉴스', '증시', '마켓', 'stock', 'invest', 'research', 'market',
    'trading', 'finance', 'alpha', 'macro'
)

# Reliability guards (seconds)
GLOBAL_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_GLOBAL_TIMEOUT_SEC', '270'))
PER_CHANNEL_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_PER_CHANNEL_TIMEOUT_SEC', '90'))
DASHBOARD_TIMEOUT_SEC = int(os.environ.get('TELEGRAM_SCRAPE_DASHBOARD_TIMEOUT_SEC', '45'))
INCREMENTAL_ONLY = os.environ.get('TELEGRAM_INCREMENTAL_ONLY', '1').strip().lower() not in ('0', 'false', 'no')


def acquire_lock():
    os.makedirs('/Users/jobiseu/.openclaw/workspace/invest/data/runtime', exist_ok=True)
    fp = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        return fp
    except BlockingIOError:
        print('SKIP: telegram scraper already running (lock exists).')
        fp.close()
        return None


def load_allowlist():
    allowed = set()
    if os.path.exists(ALLOWLIST_FILE):
        with open(ALLOWLIST_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                v = line.strip()
                if not v or v.startswith('#'):
                    continue
                allowed.add(v.lstrip('@').lower())
    env_allowed = os.environ.get('TELEGRAM_CHANNEL_ALLOWLIST', '').strip()
    if env_allowed:
        for item in env_allowed.split(','):
            v = item.strip()
            if v:
                allowed.add(v.lstrip('@').lower())
    return allowed


def is_investment_channel(title, username, allowed):
    uname = (username or '').strip().lstrip('@').lower()
    title_l = (title or '').lower()

    if uname and uname in allowed:
        return True
    if title_l in allowed:
        return True

    # Safety default: skip channels not explicitly allowlisted unless they look investment-related
    return any(k in title_l for k in INVEST_KEYWORDS)


def _load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return {}
    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_checkpoint(checkpoint):
    try:
        payload = dict(checkpoint)
        payload['_saved_at'] = datetime.now(timezone.utc).isoformat()
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"WARNING: failed to save checkpoint: {e}", flush=True)


async def scrape_single_channel(client, entity, title, username, fname, checkpoint):
    """
    Incremental collection:
    - If checkpoint exists: fetch only messages with id > checkpoint[channel]
    - If no checkpoint and incremental mode: bootstrap only recent N days
    - Otherwise fallback to historical 1-year scan
    """
    key = str(username)
    last_id = int(checkpoint.get(key, 0) or 0)

    if last_id > 0:
        msg_iter = client.iter_messages(entity, min_id=last_id)
        mode = f"incremental(min_id={last_id})"
    else:
        msg_iter = client.iter_messages(entity)
        mode = f"bootstrap({bootstrap_lookback_days}d)" if INCREMENTAL_ONLY else "full(1y)"

    new_count = 0
    max_seen_id = last_id
    created = os.path.exists(fname)

    with open(fname, 'a', encoding='utf-8') as f:
        if not created:
            f.write(f"# Telegram Log: {title} ({username})\n\n")

        async for message in msg_iter:
            # For first run without checkpoint, avoid 1-year full drain by default
            if last_id <= 0 and INCREMENTAL_ONLY:
                if message.date < bootstrap_date:
                    break
            else:
                if message.date < target_date:
                    break

            date_str = message.date.strftime('%Y-%m-%d %H:%M:%S')
            text = message.text or ""
            f.write(f"--- \nDate: {date_str}\n")
            if message.forward:
                f.write(f"Forwarded from: {message.forward.chat_id if hasattr(message.forward, 'chat_id') else 'Unknown'}\n")
            f.write(f"\n{text}\n\n")
            new_count += 1

            if message.id > max_seen_id:
                max_seen_id = message.id

            # periodic checkpoint flush for crash/timeout resilience
            if new_count % 30 == 0:
                checkpoint[key] = max_seen_id
                _save_checkpoint(checkpoint)
                f.flush()

        f.flush()

    checkpoint[key] = max_seen_id
    _save_checkpoint(checkpoint)
    return new_count, mode


async def main():
    lock_fp = acquire_lock()
    if lock_fp is None:
        append_pipeline_event("scrape_telegram_highspeed", "WARN", count=0, errors=[], note="already running lock exists")
        return

    scraped_count = 0
    message_saved_count = 0
    error_list = []
    final_state = "FAILED"
    allowed = set()
    client = None
    checkpoint = _load_checkpoint()

    global_deadline = time.monotonic() + max(30, GLOBAL_TIMEOUT_SEC)

    try:
        client = TelegramClient('jobis_mtproto_session', api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            err = 'Authorization failed.'
            print(f"ERROR: {err}")
            append_pipeline_event("scrape_telegram_highspeed", "FAILED", count=0, errors=[err], note="telegram authorization")
            final_state = "FAILED_AUTH"
            return
    except Exception as e:
        err = f"Connection failed: {e}"
        print(f"ERROR: {err}")
        append_pipeline_event("scrape_telegram_highspeed", "FAILED", count=0, errors=[str(e)], note="telegram connect")
        final_state = "FAILED_CONNECT"
        return

    print("STATUS: FETCHING_ALL_CHANNELS")
    print(f"MODE: {'INCREMENTAL' if INCREMENTAL_ONLY else 'FULL_1Y'}", flush=True)
    allowed = load_allowlist()
    if allowed:
        print(f"Allowlist loaded: {len(allowed)} entries", flush=True)
    else:
        print("WARNING: telegram allowlist is empty; keyword-based fallback filter will be used.", flush=True)

    try:
        async for dialog in client.iter_dialogs():
            if time.monotonic() >= global_deadline:
                error_list.append(f"global timeout reached ({GLOBAL_TIMEOUT_SEC}s)")
                print(f"WARNING: Global timeout reached ({GLOBAL_TIMEOUT_SEC}s). Stopping further channel scans.", flush=True)
                final_state = "TIMEOUT_GLOBAL"
                break

            if not dialog.is_channel:
                continue

            entity = dialog.entity
            title = dialog.name
            username = entity.username or entity.id

            if not is_investment_channel(title, getattr(entity, 'username', None), allowed):
                print(f"Skipping non-target channel: {title} ({username})", flush=True)
                continue

            print(f"Scraping channel: {title} ({username})", flush=True)

            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
            fname = os.path.join(save_dir, f"{safe_title}_{username}_full.md")

            try:
                timeout_for_this_channel = max(1, min(PER_CHANNEL_TIMEOUT_SEC, int(global_deadline - time.monotonic())))
                new_msgs, mode = await asyncio.wait_for(
                    scrape_single_channel(client, entity, title, username, fname, checkpoint),
                    timeout=timeout_for_this_channel,
                )
                scraped_count += 1
                message_saved_count += new_msgs
                print(f"  Finished: {title} [{mode}] new_messages={new_msgs}", flush=True)

                try:
                    subprocess.run(
                        ["python3", "/Users/jobiseu/.openclaw/workspace/invest/scripts/update_dashboard.py"],
                        timeout=max(1, DASHBOARD_TIMEOUT_SEC),
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    msg = f"update_dashboard timeout after {DASHBOARD_TIMEOUT_SEC}s"
                    error_list.append(msg)
                    print(f"  Warning: {msg}", flush=True)
            except asyncio.TimeoutError:
                msg = f"{title}: channel timeout after {PER_CHANNEL_TIMEOUT_SEC}s"
                error_list.append(msg)
                print(f"  Error on {title}: {msg}", flush=True)
            except Exception as e:
                error_list.append(f"{title}: {e}")
                print(f"  Error on {title}: {e}", flush=True)

        if final_state == "FAILED":
            final_state = "OK" if not error_list else "WARN"
    finally:
        # Keep backward-compatible marker + machine-parseable result in all paths
        print(
            f"STATUS: ALL_CHANNELS_FINISHED RESULT={final_state} SCRAPED={scraped_count} "
            f"MSGS={message_saved_count} ERRORS={len(error_list)}",
            flush=True,
        )

        try:
            if client is not None:
                await client.disconnect()
        except Exception:
            pass

        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            lock_fp.close()
        except Exception:
            pass

    status = "OK" if not error_list else "WARN"
    if final_state.startswith("FAILED"):
        status = "FAILED"
    append_pipeline_event(
        source="scrape_telegram_highspeed",
        status=status,
        count=message_saved_count,
        errors=error_list[:20],
        note=f"allowlist={len(allowed)} result={final_state} channels={scraped_count} incremental={int(INCREMENTAL_ONLY)}",
    )


if __name__ == '__main__':
    asyncio.run(main())
