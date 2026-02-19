#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    '# stage05_result_',
    '## 실행 요약',
    '## 게이트 요약',
    '## 정책 스냅샷',
    '## 성과 요약',
    '## MDD 구간 분리',
    '## 산출물 경로',
    '## 최종 판정',
]
REQUIRED_KEYS = ['gate1', 'gate2', 'gate3', 'gate4', 'final_decision', 'stop_reason']


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'ok': False, 'error': 'usage: stage05_validate_readable.py <readable.md>'}, ensure_ascii=False))
        sys.exit(2)
    p = Path(sys.argv[1])
    if not p.exists():
        print(json.dumps({'ok': False, 'error': 'file_not_found', 'path': str(p)}, ensure_ascii=False))
        sys.exit(2)

    txt = p.read_text(encoding='utf-8', errors='ignore')
    missing_sections = [s for s in REQUIRED_SECTIONS if s not in txt]
    missing_keys = [k for k in REQUIRED_KEYS if k not in txt]
    ok = (len(missing_sections) == 0 and len(missing_keys) == 0)
    out = {
        'ok': ok,
        'path': str(p),
        'missing_sections': missing_sections,
        'missing_keys': missing_keys,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
