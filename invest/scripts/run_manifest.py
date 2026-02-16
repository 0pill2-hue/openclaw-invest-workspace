import os
import json
import hashlib
import subprocess
from datetime import datetime, timezone


def _sha256_file(path: str):
    if not path or not os.path.exists(path):
        return None
    if os.path.isdir(path):
        h = hashlib.sha256()
        for root, _, files in os.walk(path):
            for name in sorted(files):
                fp = os.path.join(root, name)
                h.update(fp.encode('utf-8', errors='ignore'))
                try:
                    with open(fp, 'rb') as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b''):
                            h.update(chunk)
                except Exception:
                    continue
        return h.hexdigest()

    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(workdir: str):
    try:
        out = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workdir, text=True).strip()
        return out
    except Exception:
        return None


def write_run_manifest(run_type: str, params: dict, inputs: list, outputs: list, out_path: str, workdir: str):
    run_id = f"{run_type}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    manifest = {
        'run_id': run_id,
        'run_type': run_type,
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'git_commit': _git_commit(workdir),
        'params': params or {},
        'inputs': [],
        'outputs': []
    }

    for p in inputs or []:
        manifest['inputs'].append({'path': p, 'sha256': _sha256_file(p)})
    for p in outputs or []:
        manifest['outputs'].append({'path': p, 'sha256': _sha256_file(p)})

    manifest['ended_at_utc'] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest
