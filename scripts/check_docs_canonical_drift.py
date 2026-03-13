#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

required_paths = [
    'docs/operations/OPERATIONS_BOOK.md',
    'docs/invest/README.md',
    'docs/invest/RESULT_GOVERNANCE.md',
    'docs/invest/OPERATIONS_SOP.md',
    'docs/invest/KPI_MASTER.md',
    'docs/invest/stage1/README.md',
    'docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md',
    'docs/invest/stage1/RUNBOOK.md',
    'docs/invest/stage2/README.md',
    'docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md',
    'docs/invest/stage2/STAGE2_IMPLEMENTATION_CURRENT_SPEC.md',
    'docs/invest/stage6/README.md',
    'docs/invest/stage6/STAGE6_KPI_RUNTIME_SPEC.md',
]

deleted_paths = [
    'docs/operations/README.md',
    'docs/operations/context/README.md',
    'docs/operations/governance/README.md',
    'docs/operations/runtime/README.md',
    'docs/operations/orchestration/README.md',
    'docs/operations/skills/README.md',
]

stale_needles = deleted_paths[:]
required_refs = {
    'docs/invest/OPERATIONS_SOP.md': ['RESULT_GOVERNANCE.md'],
    'docs/invest/README.md': [
        'STAGE2_IMPLEMENTATION_CURRENT_SPEC.md',
        'STAGE6_KPI_RUNTIME_SPEC.md',
    ],
    'docs/invest/STAGE_EXECUTION_SPEC.md': [
        'STAGE2_IMPLEMENTATION_CURRENT_SPEC.md',
        'STAGE6_KPI_RUNTIME_SPEC.md',
    ],
    'docs/invest/stage2/README.md': ['STAGE2_IMPLEMENTATION_CURRENT_SPEC.md'],
    'docs/invest/stage6/README.md': ['STAGE6_KPI_RUNTIME_SPEC.md'],
    'docs/invest/RESULT_GOVERNANCE.md': ['validated_history', 'prod_history', 'test_history'],
}

for rel in required_paths:
    if not (ROOT / rel).is_file():
        print(f'MISSING: {rel}')
        sys.exit(1)

for rel in deleted_paths:
    if (ROOT / rel).exists():
        print(f'SHOULD_BE_DELETED: {rel}')
        sys.exit(1)

scan_files = []
for base in [ROOT / 'docs']:
    for path in base.rglob('*'):
        if path.is_file() and path.suffix in {'.md', '.html', '.json', '.txt'}:
            scan_files.append(path)

stale_hits = []
for path in scan_files:
    text = path.read_text(encoding='utf-8', errors='ignore')
    for needle in stale_needles:
        if needle in text:
            stale_hits.append((path.relative_to(ROOT), needle))

if stale_hits:
    for path, needle in stale_hits:
        print(f'STALE_REF: {path}: {needle}')
    sys.exit(1)

for rel, needles in required_refs.items():
    text = (ROOT / rel).read_text(encoding='utf-8', errors='ignore')
    for needle in needles:
        if needle not in text:
            print(f'MISSING_REF: {rel}: {needle}')
            sys.exit(1)

print('OK: docs canonical drift checks passed')
