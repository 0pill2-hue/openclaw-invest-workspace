#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path('/Users/jobiseu/.openclaw/workspace')
CURRENT_TASK = ROOT / 'runtime' / 'current-task.md'
FILES = {
    'soul': ROOT / 'SOUL.md',
    'user': ROOT / 'USER.md',
    'agents': ROOT / 'AGENTS.md',
    'memory': ROOT / 'MEMORY.md',
    'current_task': CURRENT_TASK,
}


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_current_task(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r'^-\s+([a-zA-Z0-9_]+):\s*(.*)$', line.strip())
        if m:
            data[m.group(1)] = m.group(2)
    return data


def write_current_task(goal: str, last: str, next_action: str, paths: str, notes: str) -> None:
    ensure_parent(CURRENT_TASK)
    content = (
        '# current-task\n\n'
        f'- current_goal: {goal}\n'
        f'- last_completed_step: {last}\n'
        f'- next_action: {next_action}\n'
        f'- required_paths_or_params: {paths}\n'
        f'- notes: {notes}\n'
    )
    CURRENT_TASK.write_text(content, encoding='utf-8')


def compact(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + '...'


def build_reload_bundle(mode: str) -> dict:
    soul = read_text(FILES['soul'])
    user = read_text(FILES['user'])
    agents = read_text(FILES['agents'])
    current = read_text(FILES['current_task'])
    memory = read_text(FILES['memory']) if mode == 'main' else ''
    task = parse_current_task(current)

    bundle = {
        'mode': mode,
        'policy': {
            'main_soft_target': 100000,
            'main_hard_target': 120000,
            'main_action_at_hard': 'roll',
            'local_action_at_task_end': 'flush',
            'daily_memory_reload': 'forbidden',
        },
        'reload_order': ['SOUL.md', 'USER.md', 'AGENTS.md', 'runtime/current-task.md'] + ([ 'MEMORY.md' ] if mode == 'main' else []),
        'current_task': task,
        'snippets': {
            'soul': compact(soul, 1200),
            'user': compact(user, 1200),
            'agents': compact(agents, 3500),
            'current_task': compact(current, 1200),
        },
    }
    if mode == 'main':
        bundle['snippets']['memory'] = compact(memory, 1200)
    return bundle


def cmd_snapshot(args: argparse.Namespace) -> int:
    write_current_task(args.goal, args.last, args.next_action, args.paths, args.notes)
    print(json.dumps({'ok': True, 'file': str(CURRENT_TASK), 'action': 'snapshot_written'}, ensure_ascii=False))
    return 0


def cmd_show(_: argparse.Namespace) -> int:
    print(read_text(CURRENT_TASK))
    return 0


def cmd_reload(args: argparse.Namespace) -> int:
    print(json.dumps(build_reload_bundle(args.mode), ensure_ascii=False, indent=2))
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    tokens = args.tokens
    if args.mode == 'main':
        if tokens >= args.hard:
            action = 'roll'
        elif tokens >= args.soft:
            action = 'warn'
        else:
            action = 'keep'
    else:
        if tokens >= args.hard:
            action = 'flush'
        elif tokens >= args.soft:
            action = 'warn'
        else:
            action = 'keep'
    print(json.dumps({'mode': args.mode, 'tokens': tokens, 'soft': args.soft, 'hard': args.hard, 'action': action}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Context policy helper for main/local brain reload flow')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('snapshot', help='Write runtime/current-task.md')
    s.add_argument('--goal', required=True)
    s.add_argument('--last', required=True)
    s.add_argument('--next-action', required=True)
    s.add_argument('--paths', default='미정')
    s.add_argument('--notes', default='')
    s.set_defaults(func=cmd_snapshot)

    sh = sub.add_parser('show', help='Show runtime/current-task.md')
    sh.set_defaults(func=cmd_show)

    r = sub.add_parser('reload', help='Build minimal reload bundle')
    r.add_argument('--mode', choices=['main', 'local'], required=True)
    r.set_defaults(func=cmd_reload)

    d = sub.add_parser('decide', help='Decide keep/warn/roll/flush from token usage')
    d.add_argument('--mode', choices=['main', 'local'], required=True)
    d.add_argument('--tokens', type=int, required=True)
    d.add_argument('--soft', type=int, required=True)
    d.add_argument('--hard', type=int, required=True)
    d.set_defaults(func=cmd_decide)

    return p


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
