#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from stage3.external_primary_runtime import iter_compaction_candidates, run_dir_has_forensic_hold


def remove_empty_dirs(path: Path, *, stop_at: Path) -> None:
    current = path.parent
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def compact_run_dir(run_dir: Path, *, mode: str, archive_root: Path | None, dry_run: bool) -> dict[str, object]:
    run_dir = run_dir.resolve()
    forensic_hold = run_dir_has_forensic_hold(run_dir)
    candidates = [] if forensic_hold else list(iter_compaction_candidates(run_dir))
    archived: list[str] = []
    deleted: list[str] = []
    kept = sorted(str(p.relative_to(run_dir)) for p in run_dir.rglob('*') if p.is_file() and p not in candidates)

    archive_dir = None
    if mode == 'archive' and not forensic_hold:
        base = archive_root.resolve() if archive_root else (run_dir.parent / '_archive').resolve()
        archive_dir = base / run_dir.name
        if not dry_run:
            archive_dir.mkdir(parents=True, exist_ok=True)

    for path in candidates:
        rel = path.relative_to(run_dir)
        if mode == 'archive':
            target = archive_dir / rel
            archived.append(str(rel))
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))
                remove_empty_dirs(path, stop_at=run_dir)
        else:
            deleted.append(str(rel))
            if not dry_run:
                path.unlink(missing_ok=True)
                remove_empty_dirs(path, stop_at=run_dir)

    payload = {
        'run_dir': str(run_dir),
        'mode': mode,
        'dry_run': dry_run,
        'forensic_hold': forensic_hold,
        'candidate_count': len(candidates),
        'kept_files': kept,
        'archived_files': archived,
        'deleted_files': deleted,
        'archive_dir': str(archive_dir) if archive_dir else '',
        'compaction_skipped_reason': 'forensic_hold' if forensic_hold else '',
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description='Compact Stage3 runtime outputs after completion.')
    ap.add_argument('run_dirs', nargs='+', help='Run directories to compact')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--archive', action='store_true', help='Move intermediates into a cold archive (default)')
    mode.add_argument('--delete', action='store_true', help='Delete intermediates instead of archiving them')
    ap.add_argument('--archive-root', default='', help='Optional cold archive root (default: sibling _archive/<run>)')
    ap.add_argument('--dry-run', action='store_true', help='Report without moving/deleting files')
    ap.add_argument('--write-json', default='', help='Optional path to write the compaction summary JSON')
    args = ap.parse_args()

    mode_name = 'delete' if args.delete else 'archive'
    archive_root = Path(args.archive_root).expanduser().resolve() if args.archive_root else None
    results = []
    for raw in args.run_dirs:
        run_dir = Path(raw).expanduser()
        if not run_dir.is_dir():
            raise SystemExit(f'run_dir_not_found:{run_dir}')
        results.append(compact_run_dir(run_dir, mode=mode_name, archive_root=archive_root, dry_run=args.dry_run))

    payload = {'ok': True, 'runs': results}
    if args.write_json:
        out = Path(args.write_json).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
