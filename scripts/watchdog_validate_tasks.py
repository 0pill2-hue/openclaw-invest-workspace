#!/usr/bin/env python3
from pathlib import Path
import re
import json
from datetime import datetime, timedelta

TASKS = Path('/Users/jobiseu/.openclaw/workspace/TASKS.md')
NOW = datetime.now()
STALE_MINUTES = 30  # heartbeat 기준: 30분 이상 무활동 감시


def parse_dt(v: str):
    v = (v or '').strip()
    if not v or v in {'-', 'none', 'None', 'N/A'}:
        return None
    # 허용: YYYY-MM-DD HH:MM:SS
    try:
        return datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def field(line: str, key: str):
    m = re.search(rf'\|\s*{re.escape(key)}\s*:\s*([^|]+)', line)
    return m.group(1).strip() if m else None


text = TASKS.read_text(encoding='utf-8') if TASKS.exists() else ''
issues = []

if 'HH:MM | task' in text:
    issues.append('TASKS.md에 템플릿 placeholder가 남아있음')

section = None
for raw in text.splitlines():
    line = raw.strip()

    if line.startswith('### '):
        section = line
        continue

    if '`JB-' not in raw or not raw.strip().startswith('- [ ]'):
        continue

    # ticket id format
    m_id = re.search(r'`(JB-\d{8}-\d{3}|JB-[^`]+)`', raw)
    if m_id:
        tid = m_id.group(1)
        if not re.match(r'^JB-\d{8}-\d{3}$', tid):
            issues.append(f'잘못된 ticket_id 형식: {tid}')

    # proof format check
    if '| proof:' not in raw:
        issues.append(f'proof 필드 누락: {raw.strip()}')

    if section == '### IN_PROGRESS':
        started = field(raw, 'started_at')
        last_act = field(raw, 'last_activity_at')
        if not started:
            issues.append(f'IN_PROGRESS started_at 누락: {raw.strip()}')
        if not last_act:
            issues.append(f'IN_PROGRESS last_activity_at 누락: {raw.strip()}')
        dt = parse_dt(last_act)
        if dt is None:
            issues.append(f'IN_PROGRESS last_activity_at 파싱 실패: {raw.strip()}')
        else:
            if NOW - dt > timedelta(minutes=STALE_MINUTES):
                issues.append(f'IN_PROGRESS 무활동 {STALE_MINUTES}분 초과: {raw.strip()}')

    if section == '### PAUSED':
        paused_at = field(raw, 'paused_at')
        resume_due = field(raw, 'resume_due')
        pause_reason = field(raw, 'pause_reason')
        if not paused_at:
            issues.append(f'PAUSED paused_at 누락: {raw.strip()}')
        if not pause_reason:
            issues.append(f'PAUSED pause_reason 누락: {raw.strip()}')
        if not resume_due:
            issues.append(f'PAUSED resume_due 누락: {raw.strip()}')
        else:
            rd = parse_dt(resume_due)
            if rd is None:
                issues.append(f'PAUSED resume_due 파싱 실패: {raw.strip()}')
            elif NOW > rd:
                issues.append(f'PAUSED resume_due 초과: {raw.strip()}')

result = {
    'ok': len(issues) == 0,
    'issues': issues,
    'checked_at': NOW.strftime('%Y-%m-%d %H:%M:%S'),
    'stale_minutes': STALE_MINUTES,
}
print(json.dumps(result, ensure_ascii=False))
