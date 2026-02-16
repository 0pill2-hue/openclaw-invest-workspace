#!/usr/bin/env python3
import json
import subprocess
import time
from pathlib import Path

ROOT = Path('/Users/jobiseu/.openclaw/workspace')
MEM = ROOT / 'memory'
MEM.mkdir(parents=True, exist_ok=True)

HEALTH = MEM / 'health-state.json'
QUEUE = MEM / 'msg-queue.json'
PENDING = MEM / 'pending-replies.json'
RESTART_COUNTER = MEM / 'restart-counter.json'
RESTART_LOG = MEM / 'gateway-restart.log'

HEARTBEAT_STALE_SEC = 30 * 60
MAX_PENDING_WARN = 10


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _append_log(line: str):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    with RESTART_LOG.open('a', encoding='utf-8') as f:
        f.write(f'[{ts}] {line}\n')


def _gateway_ok() -> bool:
    try:
        p = subprocess.run(
            ['openclaw', 'gateway', 'status'],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
        )
        out = (p.stdout or '') + '\n' + (p.stderr or '')
        return p.returncode == 0 and ('RPC probe: ok' in out or 'Runtime: running' in out)
    except Exception:
        return False


def _restart_gateway() -> tuple[bool, str]:
    try:
        p = subprocess.run(
            ['openclaw', 'gateway', 'restart'],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=40,
        )
        out = ((p.stdout or '') + ' ' + (p.stderr or '')).strip()
        return p.returncode == 0, out[:300]
    except Exception as e:
        return False, str(e)


def _cooldown_sec(recent_restarts: int) -> int:
    if recent_restarts <= 0:
        return 0
    if recent_restarts == 1:
        return 5 * 60
    if recent_restarts == 2:
        return 15 * 60
    if recent_restarts == 3:
        return 30 * 60
    return 10**9  # manual intervention required


def _send_tg_notify(msg: str):
    """텔레그램 알림 전송 (openclaw message 사용, 실패 시 무시)."""
    try:
        subprocess.run(
            ['openclaw', 'message', 'send', '--channel', 'telegram', msg],
            cwd=str(ROOT),
            capture_output=True,
            timeout=15,
        )
    except Exception:
        pass


def _emit_status(status: str, consecutive_warn_count: int, pending: int, note: str):
    print(f'{status}|consecutive_warn_count={consecutive_warn_count}|pending={pending}|note={note}')
    # RECOVERED / FAILED 시 텔레그램 알림
    if status in ('RECOVERED', 'FAILED'):
        emoji = '✅' if status == 'RECOVERED' else '🚨'
        _send_tg_notify(f'{emoji} [watchdog] {status}: {note} (pending={pending})')


def main():
    now = int(time.time())

    health = _load_json(
        HEALTH,
        {
            'lastSuccessfulResponse': now,
            'pendingMessages': 0,
            'consecutiveFailures': 0,
            'consecutiveWarnCount': 0,
            'gatewayRestarts': 0,
            'lastHealthCheck': now,
        },
    )

    queue = _load_json(QUEUE, [])
    pending_replies = _load_json(PENDING, [])
    restarts = _load_json(RESTART_COUNTER, {'timestamps': []})

    if not isinstance(queue, list):
        queue = []
    if not isinstance(pending_replies, list):
        pending_replies = []
    if not isinstance(restarts, dict) or 'timestamps' not in restarts:
        restarts = {'timestamps': []}

    restart_ts = [t for t in restarts.get('timestamps', []) if isinstance(t, int) and now - t <= 3600]
    restarts['timestamps'] = restart_ts

    pending_count = sum(1 for x in queue if isinstance(x, dict) and not x.get('processed', False)) + len(pending_replies)
    health['pendingMessages'] = pending_count
    health['lastHealthCheck'] = now

    gw_ok = _gateway_ok()
    if gw_ok:
        health['lastSuccessfulResponse'] = now
        health['consecutiveFailures'] = 0
        if pending_count > MAX_PENDING_WARN:
            health['consecutiveWarnCount'] = int(health.get('consecutiveWarnCount', 0)) + 1
            _emit_status('WARN', int(health['consecutiveWarnCount']), pending_count, f'pending_queue_high>{MAX_PENDING_WARN}')
        else:
            health['consecutiveWarnCount'] = 0
            print('HEALTHY')

        _save_json(HEALTH, health)
        _save_json(QUEUE, queue)
        _save_json(PENDING, pending_replies)
        _save_json(RESTART_COUNTER, restarts)
        return

    health['consecutiveFailures'] = int(health.get('consecutiveFailures', 0)) + 1
    health['consecutiveWarnCount'] = int(health.get('consecutiveWarnCount', 0)) + 1
    stale = (now - int(health.get('lastSuccessfulResponse', now))) > HEARTBEAT_STALE_SEC
    reason = f'gateway_unhealthy; failures={health["consecutiveFailures"]}; stale={stale}; pending={pending_count}'

    should_restart = health['consecutiveFailures'] >= 2 or stale
    if not should_restart:
        _save_json(HEALTH, health)
        _save_json(RESTART_COUNTER, restarts)
        _emit_status('WARN', int(health['consecutiveWarnCount']), pending_count, reason)
        return

    recent = len(restart_ts)
    cooldown = _cooldown_sec(recent)
    last_restart = restart_ts[-1] if restart_ts else 0

    if cooldown >= 10**9:
        _append_log(f'MANUAL_REQUIRED {reason}; recent_restarts={recent}')
        _save_json(HEALTH, health)
        _save_json(RESTART_COUNTER, restarts)
        _emit_status('FAILED', int(health['consecutiveWarnCount']), pending_count, 'manual_required_too_many_restarts')
        return

    if now - last_restart < cooldown:
        wait = cooldown - (now - last_restart)
        _append_log(f'COOLDOWN {reason}; wait={wait}s')
        _save_json(HEALTH, health)
        _save_json(RESTART_COUNTER, restarts)
        _emit_status('WARN', int(health['consecutiveWarnCount']), pending_count, f'cooldown_active_{wait}s')
        return

    ok, out = _restart_gateway()
    if ok:
        restart_ts.append(now)
        restarts['timestamps'] = restart_ts
        health['gatewayRestarts'] = int(health.get('gatewayRestarts', 0)) + 1
        health['consecutiveFailures'] = 0
        health['consecutiveWarnCount'] = 0
        health['lastSuccessfulResponse'] = now
        _append_log(f'RECOVERED {reason}; detail={out}')
        _save_json(HEALTH, health)
        _save_json(RESTART_COUNTER, restarts)
        _emit_status('RECOVERED', 0, pending_count, 'gateway_restarted')
    else:
        _append_log(f'FAILED {reason}; detail={out}')
        _save_json(HEALTH, health)
        _save_json(RESTART_COUNTER, restarts)
        _emit_status('FAILED', int(health['consecutiveWarnCount']), pending_count, 'gateway_restart_failed')


if __name__ == '__main__':
    main()
