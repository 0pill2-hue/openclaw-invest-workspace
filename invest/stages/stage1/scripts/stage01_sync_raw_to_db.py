from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import fcntl

ROOT_PATH = Path(__file__).resolve().parents[4]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from invest.stages.common.stage_raw_db import (
    DEFAULT_DB_PATH,
    DEFAULT_RAW_ROOT,
    connect_raw_db,
    get_meta,
    index_pdf_artifacts_from_raw,
    sync_raw_tree_to_db,
)

DEFAULT_RUNTIME_DIR = ROOT_PATH / 'invest/stages/stage1/outputs/runtime'
RUNTIME_DIR = Path(os.environ.get('STAGE1_DB_RUNTIME_DIR', str(DEFAULT_RUNTIME_DIR)).strip() or str(DEFAULT_RUNTIME_DIR))
STATUS_PATH = Path(os.environ.get('STAGE1_DB_STATUS_PATH', str(RUNTIME_DIR / 'raw_db_sync_status.json')).strip() or str(RUNTIME_DIR / 'raw_db_sync_status.json'))
LOCK_PATH = Path(os.environ.get('STAGE1_DB_LOCK_PATH', str(RUNTIME_DIR / 'raw_db_sync.lock')).strip() or str(RUNTIME_DIR / 'raw_db_sync.lock'))
LOCK_TIMEOUT_SEC = float(os.environ.get('STAGE1_DB_LOCK_TIMEOUT_SEC', '1800').strip() or '1800')
LOCK_POLL_SEC = max(0.2, float(os.environ.get('STAGE1_DB_LOCK_POLL_SEC', '1.0').strip() or '1.0'))


@contextmanager
def _exclusive_lock(lock_path: Path, timeout_sec: float, *, lock_payload: dict | None = None):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+', encoding='utf-8') as fh:
        start = time.monotonic()
        acquired = False
        while not acquired:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                if timeout_sec >= 0 and (time.monotonic() - start) >= timeout_sec:
                    holder = _load_json_file(lock_path)
                    holder_pid = _pid_from_payload(holder)
                    holder_desc = f'pid={holder_pid}' if holder_pid > 0 else 'pid=unknown'
                    raise TimeoutError(f'raw_db_sync lock timeout after {timeout_sec:.1f}s: {lock_path} ({holder_desc})')
                time.sleep(LOCK_POLL_SEC)
        payload = {
            'pid': os.getpid(),
            'acquired_at': datetime.now().isoformat(),
            'lock_path': str(lock_path),
        }
        for key, value in (lock_payload or {}).items():
            if value not in (None, ''):
                payload[key] = value
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2))
        fh.flush()
        try:
            yield payload
        finally:
            fh.seek(0)
            fh.truncate()
            fh.flush()
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _load_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _pid_from_payload(payload: dict | None) -> int:
    if not isinstance(payload, dict):
        return 0
    try:
        return int(payload.get('pid') or 0)
    except Exception:
        return 0


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def _load_json_meta(db_path: str, key: str) -> dict:
    with connect_raw_db(db_path, readonly=True) as conn:
        raw = get_meta(conn, key, '{}')
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _write_status_file(payload: dict) -> dict:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def _write_running_status(*, db_path: str, raw_root: str, stage1_run_id: str, stage1_profile: str, scheduler_origin: str, lock_payload: dict) -> dict:
    payload = {
        'timestamp': datetime.now().isoformat(),
        'status': 'RUNNING',
        'status_mode': 'full_sync_running',
        'status_path': str(STATUS_PATH),
        'db_path': db_path,
        'raw_root': raw_root,
        'stage1_run_id': stage1_run_id,
        'stage1_profile': stage1_profile,
        'scheduler_origin': scheduler_origin,
        'lock': dict(lock_payload),
    }
    return _write_status_file(payload)


def _write_failure_status(*, db_path: str, raw_root: str, stage1_run_id: str, stage1_profile: str, scheduler_origin: str, error: str, lock_payload: dict | None = None, lock_released_at: str = '') -> dict:
    payload = {
        'timestamp': datetime.now().isoformat(),
        'status': 'FAIL',
        'status_mode': 'full_sync_failed',
        'status_path': str(STATUS_PATH),
        'db_path': db_path,
        'raw_root': raw_root,
        'stage1_run_id': stage1_run_id,
        'stage1_profile': stage1_profile,
        'scheduler_origin': scheduler_origin,
        'error': error,
    }
    if lock_payload is not None:
        payload['lock'] = {
            **dict(lock_payload),
            'released_at': lock_released_at or datetime.now().isoformat(),
        }
    return _write_status_file(payload)


def _write_status_payload(*, sync_payload: dict, pdf_payload: dict, stage1_run_id: str, stage1_profile: str, scheduler_origin: str, status_mode: str, status: str = 'PASS', lock_payload: dict | None = None, lock_released_at: str = '') -> dict:
    payload = {
        **sync_payload,
        'timestamp': datetime.now().isoformat(),
        'status': status,
        'status_path': str(STATUS_PATH),
        'stage1_run_id': stage1_run_id,
        'stage1_profile': stage1_profile,
        'scheduler_origin': scheduler_origin,
        'status_mode': status_mode,
        'pdf_index': pdf_payload,
    }
    if lock_payload is not None:
        payload['lock'] = {
            **dict(lock_payload),
            'released_at': lock_released_at or datetime.now().isoformat(),
        }
    return _write_status_file(payload)


def _recover_stale_runtime_state(*, db_path: str, raw_root: str, stage1_run_id: str, stage1_profile: str, scheduler_origin: str) -> dict | None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open('a+', encoding='utf-8') as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None

        fh.seek(0)
        raw = fh.read().strip()
        lock_payload = {}
        if raw:
            try:
                parsed = json.loads(raw)
                lock_payload = parsed if isinstance(parsed, dict) else {}
            except Exception:
                lock_payload = {'raw': raw[:500]}

        status_payload = _load_json_file(STATUS_PATH)
        stale_reasons: list[str] = []
        lock_pid = _pid_from_payload(lock_payload)
        status_lock_payload = status_payload.get('lock') if isinstance(status_payload.get('lock'), dict) else {}
        status_pid = _pid_from_payload(status_lock_payload)

        if lock_payload:
            stale_reasons.append('lock_payload_without_active_flock')
            if lock_pid and not _pid_is_alive(lock_pid):
                stale_reasons.append('lock_pid_missing')
        if str(status_payload.get('status') or '').strip().upper() == 'RUNNING':
            stale_reasons.append('running_status_without_active_flock')
            if status_pid and not _pid_is_alive(status_pid):
                stale_reasons.append('status_pid_missing')

        if not stale_reasons:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return None

        fh.seek(0)
        fh.truncate()
        fh.flush()
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    cleanup = {
        'detected_at': datetime.now().isoformat(),
        'reasons': stale_reasons,
        'previous_lock': lock_payload,
        'previous_status': {
            'timestamp': status_payload.get('timestamp'),
            'status': status_payload.get('status'),
            'status_mode': status_payload.get('status_mode'),
            'stage1_run_id': status_payload.get('stage1_run_id'),
            'stage1_profile': status_payload.get('stage1_profile'),
        },
    }

    sync_payload = _load_json_meta(db_path, 'last_sync_summary')
    pdf_payload = _load_json_meta(db_path, 'last_pdf_index_summary')
    if sync_payload:
        sync_payload.setdefault('db_path', db_path)
        sync_payload.setdefault('raw_root', raw_root)
        pdf_payload.setdefault('db_path', db_path)
        pdf_payload.setdefault('raw_root', raw_root)
        payload = {
            **sync_payload,
            'timestamp': datetime.now().isoformat(),
            'status': 'PASS',
            'status_path': str(STATUS_PATH),
            'stage1_run_id': stage1_run_id,
            'stage1_profile': stage1_profile,
            'scheduler_origin': scheduler_origin,
            'status_mode': 'status_only_from_sync_meta_after_stale_cleanup',
            'pdf_index': pdf_payload,
            'stale_cleanup': cleanup,
        }
        return _write_status_file(payload)

    payload = {
        'timestamp': datetime.now().isoformat(),
        'status': 'FAIL',
        'status_mode': 'stale_lock_cleanup_no_sync_meta',
        'status_path': str(STATUS_PATH),
        'db_path': db_path,
        'raw_root': raw_root,
        'stage1_run_id': stage1_run_id,
        'stage1_profile': stage1_profile,
        'scheduler_origin': scheduler_origin,
        'error': 'stale_lock_cleanup_without_sync_meta',
        'stale_cleanup': cleanup,
    }
    return _write_status_file(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--status-only', action='store_true', help='DB 재스캔 없이 sync_meta 기반으로 raw_db_sync_status.json만 재생성')
    args = parser.parse_args()

    raw_root = os.environ.get('STAGE1_RAW_ROOT', str(DEFAULT_RAW_ROOT)).strip() or str(DEFAULT_RAW_ROOT)
    db_path = os.environ.get('STAGE1_RAW_DB_PATH', str(DEFAULT_DB_PATH)).strip() or str(DEFAULT_DB_PATH)
    stage1_run_id = os.environ.get('STAGE1_RUN_ID', '').strip()
    stage1_profile = os.environ.get('STAGE1_PROFILE', '').strip()
    scheduler_origin = os.environ.get('SCHEDULER_ORIGIN', '').strip()

    recovered_payload = _recover_stale_runtime_state(
        db_path=db_path,
        raw_root=raw_root,
        stage1_run_id=stage1_run_id,
        stage1_profile=stage1_profile,
        scheduler_origin=scheduler_origin,
    )

    if args.status_only:
        if recovered_payload is not None:
            print(json.dumps(recovered_payload, ensure_ascii=False))
            return
        sync_payload = _load_json_meta(db_path, 'last_sync_summary')
        pdf_payload = _load_json_meta(db_path, 'last_pdf_index_summary')
        if not sync_payload:
            raise SystemExit('sync_meta.last_sync_summary missing; full sync first')
        sync_payload.setdefault('db_path', db_path)
        sync_payload.setdefault('raw_root', raw_root)
        pdf_payload.setdefault('db_path', db_path)
        pdf_payload.setdefault('raw_root', raw_root)
        payload = _write_status_payload(
            sync_payload=sync_payload,
            pdf_payload=pdf_payload,
            stage1_run_id=stage1_run_id,
            stage1_profile=stage1_profile,
            scheduler_origin=scheduler_origin,
            status_mode='status_only_from_sync_meta',
        )
        print(json.dumps(payload, ensure_ascii=False))
        return

    lock_payload: dict | None = None
    try:
        with _exclusive_lock(
            LOCK_PATH,
            LOCK_TIMEOUT_SEC,
            lock_payload={
                'db_path': db_path,
                'raw_root': raw_root,
                'status_path': str(STATUS_PATH),
                'stage1_run_id': stage1_run_id,
                'stage1_profile': stage1_profile,
                'scheduler_origin': scheduler_origin,
            },
        ) as lock_payload:
            _write_running_status(
                db_path=db_path,
                raw_root=raw_root,
                stage1_run_id=stage1_run_id,
                stage1_profile=stage1_profile,
                scheduler_origin=scheduler_origin,
                lock_payload=lock_payload,
            )
            sync_summary = sync_raw_tree_to_db(
                raw_root=raw_root,
                db_path=db_path,
                stage1_run_id=stage1_run_id,
                stage1_profile=stage1_profile,
                scheduler_origin=scheduler_origin,
            )
            pdf_summary = index_pdf_artifacts_from_raw(raw_root=raw_root, db_path=db_path)
    except Exception as exc:
        _write_failure_status(
            db_path=db_path,
            raw_root=raw_root,
            stage1_run_id=stage1_run_id,
            stage1_profile=stage1_profile,
            scheduler_origin=scheduler_origin,
            error=f'{type(exc).__name__}: {exc}',
            lock_payload=lock_payload,
            lock_released_at=datetime.now().isoformat(),
        )
        raise

    payload = _write_status_payload(
        sync_payload=sync_summary.as_dict(),
        pdf_payload=pdf_summary.as_dict(),
        stage1_run_id=stage1_run_id,
        stage1_profile=stage1_profile,
        scheduler_origin=scheduler_origin,
        status_mode='full_sync',
        status='PASS',
        lock_payload=lock_payload,
        lock_released_at=datetime.now().isoformat(),
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
