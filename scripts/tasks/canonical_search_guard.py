#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import sys

FORBIDDEN_SUBSTRINGS = (
    'runtime/tasks/evidence/raw-hot.jsonl',
    'runtime/tasks/evidence/raw-warm.jsonl',
    'runtime/tasks/evidence/raw-cold.jsonl',
    'runtime/watch/raw',
    'runtime/tmp',
    'stdout',
    'stderr',
)


def main() -> int:
    ap = argparse.ArgumentParser(description='Reject recursive/raw runtime grep patterns and point callers to canonical evidence search.')
    ap.add_argument('command', nargs=argparse.REMAINDER, help='Command tokens to validate, e.g. -- grep -R foo runtime/tmp')
    args = ap.parse_args()
    tokens = [tok for tok in args.command if tok != '--']
    rendered = ' '.join(tokens).strip()
    lowered = rendered.lower()

    problems: list[str] = []
    if 'grep' in lowered and (' -r ' in f' {lowered} ' or ' -rin' in lowered or ' -rn' in lowered or lowered.startswith('grep -r')):
        problems.append('recursive_grep_forbidden')
    for item in FORBIDDEN_SUBSTRINGS:
        if item in lowered:
            problems.append(f'cold_raw_target_forbidden:{item}')

    ok = not problems
    payload = {
        'ok': ok,
        'command': rendered,
        'problems': problems,
        'recommended': 'python3 scripts/tasks/db.py evidence-search --limit 5 (add --include-raw only when explicitly justified)',
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
