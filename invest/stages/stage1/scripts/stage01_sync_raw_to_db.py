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

RUNTIME_DIR = ROOT_PATH / 'invest/stages/stage1/outputs/runtime'
STATUS_PATH = RUNTIME_DIR / 'raw_db_sync_status.json'
LOCK_PATH = RUNTIME_DIR / 'raw_db_sync.lock'
LOCK_TIMEOUT_SEC = float(os.environ.get('STAGE1_DB_LOCK_TIMEOUT_SEC', '1800').strip() or '1800')
LOCK_POLL_SEC = max(0.2, float(os.environ.get('STAGE1_DB_LOCK_POLL_SEC', '1.0').strip() or '1.0'))


@contextmanager
def _exclusive_lock(lock_path: Path, timeout_sec: float):
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
                    raise TimeoutError(f'raw_db_sync lock timeout after {timeout_sec:.1f}s: {lock_path}')
                time.sleep(LOCK_POLL_SEC)
        fh.seek(0)
        fh.truncate()
        fh.write(
            json.dumps(
                {
                    'pid': os.getpid(),
                    'acquired_at': datetime.now().isoformat(),
                    'lock_path': str(lock_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        fh.flush()
        try:
            yield
        finally:
            fh.seek(0)
            fh.truncate()
            fh.flush()
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _load_json_meta(db_path: str, key: str) -> dict:
    with connect_raw_db(db_path, readonly=True) as conn:
        raw = get_meta(conn, key, '{}')
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _write_status_payload(*, sync_payload: dict, pdf_payload: dict, stage1_run_id: str, stage1_profile: str, scheduler_origin: str, status_mode: str) -> dict:
    payload = {
        **sync_payload,
        'timestamp': datetime.now().isoformat(),
        'status_path': str(STATUS_PATH),
        'stage1_run_id': stage1_run_id,
        'stage1_profile': stage1_profile,
        'scheduler_origin': scheduler_origin,
        'status_mode': status_mode,
        'pdf_index': pdf_payload,
    }
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--status-only', action='store_true', help='DB 재스캔 없이 sync_meta 기반으로 raw_db_sync_status.json만 재생성')
    args = parser.parse_args()

    raw_root = os.environ.get('STAGE1_RAW_ROOT', str(DEFAULT_RAW_ROOT)).strip() or str(DEFAULT_RAW_ROOT)
    db_path = os.environ.get('STAGE1_RAW_DB_PATH', str(DEFAULT_DB_PATH)).strip() or str(DEFAULT_DB_PATH)
    stage1_run_id = os.environ.get('STAGE1_RUN_ID', '').strip()
    stage1_profile = os.environ.get('STAGE1_PROFILE', '').strip()
    scheduler_origin = os.environ.get('SCHEDULER_ORIGIN', '').strip()

    if args.status_only:
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

    with _exclusive_lock(LOCK_PATH, LOCK_TIMEOUT_SEC):
        sync_summary = sync_raw_tree_to_db(
            raw_root=raw_root,
            db_path=db_path,
            stage1_run_id=stage1_run_id,
            stage1_profile=stage1_profile,
            scheduler_origin=scheduler_origin,
        )
        pdf_summary = index_pdf_artifacts_from_raw(raw_root=raw_root, db_path=db_path)

    payload = _write_status_payload(
        sync_payload=sync_summary.as_dict(),
        pdf_payload=pdf_summary.as_dict(),
        stage1_run_id=stage1_run_id,
        stage1_profile=stage1_profile,
        scheduler_origin=scheduler_origin,
        status_mode='full_sync',
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
