#!/usr/bin/env python3
from pathlib import Path
import re
import json
from datetime import datetime

TASKS = Path('/Users/jobiseu/.openclaw/workspace/TASKS.md')


def main():
    if not TASKS.exists():
        print(json.dumps({"ok": False, "changed": False, "reason": "TASKS.md not found"}, ensure_ascii=False))
        return

    lines = TASKS.read_text(encoding='utf-8').splitlines()

    sec = None
    in_prog_idx = []
    blocked_insert_at = None

    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('### '):
            sec = s
            if s == '### BLOCKED':
                blocked_insert_at = i + 1
            continue
        if sec == '### IN_PROGRESS' and '`JB-' in line and line.strip().startswith('- [ ]'):
            in_prog_idx.append(i)

    changes = []
    moved = 0
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Move only tickets with missing proof to BLOCKED automatically.
    # This prevents infinite warning loops and forces explicit re-attach.
    for idx in in_prog_idx:
        line = lines[idx]
        m = re.search(r'\|\s*proof:\s*(.*)$', line)
        proof = m.group(1).strip() if m else ''
        if proof in ('', '-', 'none', 'None', 'N/A'):
            blocked_line = f"{line} | auto_blocked: watchdog_missing_proof ({ts})"
            changes.append((idx, blocked_line))

    if not changes:
        print(json.dumps({"ok": True, "changed": False, "moved": 0}, ensure_ascii=False))
        return

    # Remove from IN_PROGRESS (reverse order to keep indices stable)
    for idx, _ in sorted(changes, key=lambda x: x[0], reverse=True):
        lines.pop(idx)
        moved += 1

    # Ensure IN_PROGRESS is not empty
    sec = None
    in_progress_has_item = False
    in_progress_header_idx = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('### '):
            sec = s
            if s == '### IN_PROGRESS':
                in_progress_header_idx = i
            continue
        if sec == '### IN_PROGRESS' and line.strip().startswith('- [ ]') and '없음' not in line:
            in_progress_has_item = True
    if in_progress_header_idx is not None and not in_progress_has_item:
        # insert "없음" right after header if no tasks remain
        if in_progress_header_idx + 1 >= len(lines) or '없음' not in lines[in_progress_header_idx + 1]:
            lines.insert(in_progress_header_idx + 1, '- [ ] 없음')

    # Recompute BLOCKED insertion point
    blocked_insert_at = None
    for i, line in enumerate(lines):
        if line.strip() == '### BLOCKED':
            blocked_insert_at = i + 1
            break

    if blocked_insert_at is None:
        print(json.dumps({"ok": False, "changed": False, "reason": "BLOCKED section not found"}, ensure_ascii=False))
        return

    # Remove placeholder "없음" in BLOCKED when inserting items
    if blocked_insert_at < len(lines) and lines[blocked_insert_at].strip() == '- [ ] 없음':
        lines.pop(blocked_insert_at)

    for _, bline in changes:
        lines.insert(blocked_insert_at, bline)
        blocked_insert_at += 1

    TASKS.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({"ok": True, "changed": True, "moved": moved}, ensure_ascii=False))


if __name__ == '__main__':
    main()
