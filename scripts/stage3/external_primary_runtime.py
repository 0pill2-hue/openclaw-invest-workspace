#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

MIN_BATCH_ITEMS = 20
MAX_BATCH_ITEMS = 40
DEFAULT_TARGET_BATCH_ITEMS = 30
ALLOWED_RUN_METRIC_KEYS = (
    'wall_seconds',
    'item_count',
    'parse_integrity',
    'completeness',
    'cost_estimate',
)
CANONICAL_RESULT_BASENAMES = {
    'batch_manifest.json',
    'manifest.json',
    'result.json',
    'summary.json',
    'card.json',
    'proof-index.jsonl',
}
INTERMEDIATE_DIR_MARKERS = {
    'actual',
    'tmp',
    'prompt',
    'prompts',
    'result',
    'results',
    'comparison',
    'comparisons',
    'per-run-metrics',
    'metrics',
    'logs',
    'stdout',
    'stderr',
}
HOT_EVIDENCE_ALLOWED = (
    'runtime/current-task.md',
    'runtime/context-handoff.md',
    'runtime/tasks/evidence/cards/*',
    'runtime/tasks/evidence/proof-index.jsonl',
)


def bool_from_env(value: str | None) -> bool:
    raw = str(value or '').strip().lower()
    return raw in {'1', 'true', 'yes', 'y', 'on', 'debug'}


def should_save_raw(*, debug: bool = False, env_value: str | None = None) -> bool:
    if debug:
        return True
    return bool_from_env(env_value)


def compact_run_metrics(metrics: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(metrics, Mapping):
        return {}
    compact: dict[str, object] = {}
    for key in ALLOWED_RUN_METRIC_KEYS:
        value = metrics.get(key)
        if value in (None, '', [], {}):
            continue
        compact[key] = value
    return compact


def normalize_batch_target(requested: int | None = None) -> int:
    value = DEFAULT_TARGET_BATCH_ITEMS if requested in (None, 0) else int(requested)
    if value < MIN_BATCH_ITEMS:
        return MIN_BATCH_ITEMS
    if value > MAX_BATCH_ITEMS:
        return MAX_BATCH_ITEMS
    return value


def partition_item_ids(item_ids: Sequence[str], *, target_size: int | None = None) -> list[list[str]]:
    ids = [str(item).strip() for item in item_ids if str(item).strip()]
    if not ids:
        return []
    total = len(ids)
    target = normalize_batch_target(target_size)
    if total <= MAX_BATCH_ITEMS:
        return [ids]

    min_parts = max(1, math.ceil(total / MAX_BATCH_ITEMS))
    max_parts = max(1, math.ceil(total / MIN_BATCH_ITEMS))
    best_parts = None
    best_distance = None
    for parts in range(min_parts, max_parts + 1):
        min_size = total // parts
        max_size = math.ceil(total / parts)
        if min_size < MIN_BATCH_ITEMS or max_size > MAX_BATCH_ITEMS:
            continue
        distance = abs((total / parts) - target)
        if best_distance is None or distance < best_distance:
            best_parts = parts
            best_distance = distance
    if best_parts is None:
        best_parts = min_parts

    base = total // best_parts
    remainder = total % best_parts
    sizes = [base + (1 if idx < remainder else 0) for idx in range(best_parts)]
    batches: list[list[str]] = []
    cursor = 0
    for size in sizes:
        batches.append(ids[cursor: cursor + size])
        cursor += size
    return batches


def build_partition_metadata(
    *,
    package_id: str,
    batch_id: str,
    all_item_ids: Sequence[str],
    current_item_ids: Sequence[str],
    partition_index: int,
    partition_count: int,
    failed_item_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    failures = [str(item).strip() for item in (failed_item_ids or []) if str(item).strip()]
    current = [str(item).strip() for item in current_item_ids if str(item).strip()]
    all_ids = [str(item).strip() for item in all_item_ids if str(item).strip()]
    return {
        'package_id': package_id,
        'batch_id': batch_id,
        'partition_index': partition_index,
        'partition_count': partition_count,
        'item_count': len(current),
        'item_ids': current,
        'all_item_ids': all_ids,
        'batch_item_policy': {
            'min_items': MIN_BATCH_ITEMS,
            'max_items': MAX_BATCH_ITEMS,
            'default_target': DEFAULT_TARGET_BATCH_ITEMS,
        },
        'partial_failure': {
            'failed_item_ids': failures,
            'repartition_recommended': bool(failures),
            'next_action': 'repartition_failed_item_ids_only' if failures else 'none',
        },
    }


def _basename_tokens(path: Path) -> set[str]:
    stem = path.name.lower().replace('.', '-').replace('_', '-').split('-')
    return {token for token in stem if token}


def is_canonical_runtime_artifact(path: Path) -> bool:
    name = path.name.lower()
    if name in CANONICAL_RESULT_BASENAMES:
        return True
    tokens = _basename_tokens(path)
    if 'proof' in tokens and 'index' in tokens:
        return True
    if 'manifest' in tokens:
        return True
    if 'summary' in tokens and 'prompt' not in tokens and 'metrics' not in tokens:
        return True
    if 'card' in tokens and 'scorecard' not in tokens:
        return True
    if 'result' in tokens and 'results' not in tokens and 'template' not in tokens and 'metrics' not in tokens:
        return True
    return False


def should_compact_runtime_path(path: Path, *, run_dir: Path) -> bool:
    if is_canonical_runtime_artifact(path):
        return False
    rel_parts = path.relative_to(run_dir).parts
    lowered = {part.lower() for part in rel_parts[:-1]}
    if lowered & INTERMEDIATE_DIR_MARKERS:
        return True
    name = path.name.lower()
    if 'results_template' in name:
        return True
    if 'prompt' in name:
        return True
    if 'metric' in name:
        return True
    if 'comparison' in name:
        return True
    return True


def iter_compaction_candidates(run_dir: Path) -> Iterable[Path]:
    for path in sorted(run_dir.rglob('*')):
        if not path.is_file():
            continue
        if should_compact_runtime_path(path, run_dir=run_dir):
            yield path
