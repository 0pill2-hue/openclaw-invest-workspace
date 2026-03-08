from __future__ import annotations

import hashlib
import json
from pathlib import Path

STAGE2_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = STAGE2_ROOT / 'inputs' / 'config'
RUNTIME_CONFIG_PATH = CONFIG_DIR / 'stage2_runtime_config.json'
REASON_CONFIG_PATH = CONFIG_DIR / 'stage2_reason_config.json'


def _read_json(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f'config root must be object: {path}')
    return payload


def _stable_dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def load_stage2_config_bundle() -> dict:
    runtime = _read_json(RUNTIME_CONFIG_PATH)
    reason = _read_json(REASON_CONFIG_PATH)
    runtime_sha1 = _sha1_text(_stable_dump(runtime))
    reason_sha1 = _sha1_text(_stable_dump(reason))
    bundle_payload = {
        'runtime': runtime,
        'reason': reason,
    }
    bundle_sha1 = _sha1_text(_stable_dump(bundle_payload))
    return {
        'runtime': runtime,
        'reason': reason,
        'provenance': {
            'runtime_config_path': str(RUNTIME_CONFIG_PATH),
            'reason_config_path': str(REASON_CONFIG_PATH),
            'runtime_config_version': runtime.get('version', ''),
            'reason_config_version': reason.get('version', ''),
            'runtime_config_sha1': runtime_sha1,
            'reason_config_sha1': reason_sha1,
            'bundle_sha1': bundle_sha1,
        },
    }
