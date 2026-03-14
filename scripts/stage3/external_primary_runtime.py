#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Sequence

MIN_BATCH_ITEMS = 20
MAX_BATCH_ITEMS = 40
DEFAULT_TARGET_BATCH_ITEMS = 30
TARGET_BATCH_TOKEN_ESTIMATE = 12000
HARD_BATCH_TOKEN_ESTIMATE = 16000
TARGET_BATCH_BYTES = 65000
HARD_BATCH_BYTES = 90000
LONGFORM_TOKEN_THRESHOLD = 320
LONGFORM_CHAR_THRESHOLD = 1400
HIGH_CHATTER_RATIO = 0.35
HIGH_LONGFORM_RATIO = 0.35
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
    'canonical_audit.json',
    'normalized_score_table.jsonl',
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
FORENSIC_HOLD_FILENAMES = (
    'forensic_hold',
    '.forensic_hold',
    'forensic_hold.json',
)
CHATTERISH_ITEM_TYPES = {'chatter', 'opinion', 'mixed', 'unknown'}


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


def estimate_token_count(text: str) -> int:
    raw = str(text or '')
    if not raw.strip():
        return 0
    return max(1, math.ceil(len(raw) / 4))


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_jsonable_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for raw in value:
        item = str(raw or '').strip()
        if item:
            out.append(item)
    return out


def _normalized_partition_item(raw: Mapping[str, object] | str) -> dict[str, object]:
    if isinstance(raw, Mapping):
        item_id = str(raw.get('item_id') or raw.get('document_or_item_id') or '').strip()
        item_type = str(raw.get('item_type') or 'unknown').strip().lower() or 'unknown'
        text = str(raw.get('source_text') or raw.get('text') or raw.get('evidence_summary') or '').strip()
        token_estimate = _safe_int(raw.get('token_estimate'), estimate_token_count(text))
        attachment_bytes = _safe_int(raw.get('attachment_bytes'), len(text.encode('utf-8')))
    else:
        item_id = str(raw).strip()
        item_type = 'unknown'
        text = ''
        token_estimate = 0
        attachment_bytes = 0
    return {
        'item_id': item_id,
        'item_type': item_type,
        'token_estimate': max(0, token_estimate),
        'attachment_bytes': max(0, attachment_bytes),
        'longform': bool(token_estimate >= LONGFORM_TOKEN_THRESHOLD or len(text) >= LONGFORM_CHAR_THRESHOLD),
        'chatterish': item_type in CHATTERISH_ITEM_TYPES,
    }


def build_batch_split_observation(items: Sequence[Mapping[str, object] | str]) -> dict[str, object]:
    normalized = [_normalized_partition_item(item) for item in items]
    total = len(normalized)
    total_tokens = sum(int(item['token_estimate']) for item in normalized)
    total_bytes = sum(int(item['attachment_bytes']) for item in normalized)
    longform_count = sum(1 for item in normalized if item['longform'])
    chatter_count = sum(1 for item in normalized if item['chatterish'])
    item_type_counts = Counter(str(item['item_type']) for item in normalized)
    return {
        'item_count': total,
        'token_estimate_total': total_tokens,
        'attachment_bytes_total': total_bytes,
        'item_type_mix': dict(sorted(item_type_counts.items())),
        'longform_ratio': round((longform_count / total), 4) if total else 0.0,
        'chatter_ratio': round((chatter_count / total), 4) if total else 0.0,
    }


def _should_split_before_append(current: list[dict[str, object]], nxt: dict[str, object], target: int) -> bool:
    if not current:
        return False
    if len(current) >= MAX_BATCH_ITEMS:
        return True
    projected = current + [nxt]
    obs = build_batch_split_observation(projected)
    if obs['item_count'] > MAX_BATCH_ITEMS:
        return True
    if int(obs['token_estimate_total']) > HARD_BATCH_TOKEN_ESTIMATE:
        return True
    if int(obs['attachment_bytes_total']) > HARD_BATCH_BYTES:
        return True
    if len(current) < MIN_BATCH_ITEMS:
        return False
    if len(current) >= target and (
        int(obs['token_estimate_total']) >= TARGET_BATCH_TOKEN_ESTIMATE
        or int(obs['attachment_bytes_total']) >= TARGET_BATCH_BYTES
        or float(obs['longform_ratio']) > HIGH_LONGFORM_RATIO
        or float(obs['chatter_ratio']) > HIGH_CHATTER_RATIO
    ):
        return True
    return False


def _rebalance_small_tail(batches: list[list[dict[str, object]]]) -> list[list[dict[str, object]]]:
    if len(batches) < 2:
        return batches
    last = batches[-1]
    prev = batches[-2]
    while len(last) < MIN_BATCH_ITEMS and len(prev) > MIN_BATCH_ITEMS:
        last.insert(0, prev.pop())
    if len(last) == 0:
        batches.pop()
    return batches


def partition_stage3_items(
    items: Sequence[Mapping[str, object] | str],
    *,
    target_size: int | None = None,
) -> list[list[dict[str, object]]]:
    normalized = [_normalized_partition_item(item) for item in items if _normalized_partition_item(item)['item_id']]
    if not normalized:
        return []
    if len(normalized) <= MAX_BATCH_ITEMS:
        return [normalized]

    target = normalize_batch_target(target_size)
    batches: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    for item in normalized:
        if _should_split_before_append(current, item, target):
            batches.append(current)
            current = []
        current.append(item)
    if current:
        batches.append(current)
    return _rebalance_small_tail(batches)


def partition_item_ids(item_ids: Sequence[str], *, target_size: int | None = None) -> list[list[str]]:
    batches = partition_stage3_items(item_ids, target_size=target_size)
    return [[str(item['item_id']) for item in batch] for batch in batches]


def build_partition_metadata(
    *,
    package_id: str,
    batch_id: str,
    all_item_ids: Sequence[str],
    current_item_ids: Sequence[str],
    partition_index: int,
    partition_count: int,
    failed_item_ids: Sequence[str] | None = None,
    split_observation: Mapping[str, object] | None = None,
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
            'split_dimensions': [
                'item_count',
                'token_estimate_total',
                'attachment_bytes_total',
                'item_type_mix',
                'longform_ratio',
                'chatter_ratio',
            ],
        },
        'split_observation': dict(split_observation or {}),
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
    if 'audit' in tokens and 'canonical' in tokens:
        return True
    if 'normalized' in tokens and 'score' in tokens and 'table' in tokens:
        return True
    return False


def run_dir_has_forensic_hold(run_dir: Path) -> bool:
    for name in FORENSIC_HOLD_FILENAMES:
        if (run_dir / name).exists():
            return True
    for candidate in (run_dir / 'batch_manifest.json', run_dir / 'summary.json', run_dir / 'canonical_audit.json'):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding='utf-8'))
        except Exception:
            continue
        if payload.get('forensic_hold') is True:
            return True
        fh = payload.get('forensic_hold')
        if isinstance(fh, Mapping) and fh.get('active') is True:
            return True
    return False


def should_compact_runtime_path(path: Path, *, run_dir: Path) -> bool:
    if run_dir_has_forensic_hold(run_dir):
        return False
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
    if run_dir_has_forensic_hold(run_dir):
        return
    for path in sorted(run_dir.rglob('*')):
        if not path.is_file():
            continue
        if should_compact_runtime_path(path, run_dir=run_dir):
            yield path


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _find_duplicates(values: Sequence[str]) -> list[str]:
    counts = Counter(str(value or '').strip() for value in values if str(value or '').strip())
    return sorted(key for key, cnt in counts.items() if cnt > 1)


def _compare_count_map(expected: Mapping[str, object] | None, actual: Mapping[str, int]) -> bool:
    if not isinstance(expected, Mapping):
        return False
    cleaned_expected = {str(k): _safe_int(v) for k, v in expected.items()}
    cleaned_actual = {str(k): int(v) for k, v in actual.items()}
    keys = set(cleaned_expected) | set(cleaned_actual)
    for key in keys:
        if int(cleaned_expected.get(key, 0)) != int(cleaned_actual.get(key, 0)):
            return False
    return True


def build_response_integrity_audit(
    response: Mapping[str, object] | None,
    *,
    expected_item_ids: Sequence[str],
    schema_validation_ok: bool,
) -> dict[str, object]:
    expected_ids = _dedupe_preserve_order(expected_item_ids)
    payload = dict(response or {})
    items = payload.get('items') if isinstance(payload.get('items'), list) else []
    package_audit = payload.get('package_audit') if isinstance(payload.get('package_audit'), Mapping) else {}
    summary = payload.get('summary') if isinstance(payload.get('summary'), Mapping) else {}

    returned_item_ids = [str(item.get('item_id') or '').strip() for item in items if isinstance(item, Mapping)]
    returned_item_ids = [item_id for item_id in returned_item_ids if item_id]
    duplicate_item_ids = _find_duplicates(returned_item_ids)
    missing_item_ids = sorted(set(expected_ids) - set(returned_item_ids))
    unexpected_item_ids = sorted(set(returned_item_ids) - set(expected_ids))

    actual_status_counts = Counter(
        str(item.get('status') or '').strip() for item in items if isinstance(item, Mapping) and str(item.get('status') or '').strip()
    )
    actual_preservation_counts = Counter(
        str(item.get('preservation_decision') or '').strip()
        for item in items
        if isinstance(item, Mapping) and str(item.get('preservation_decision') or '').strip()
    )
    actual_item_type_counts = Counter(
        str(item.get('item_type') or '').strip() for item in items if isinstance(item, Mapping) and str(item.get('item_type') or '').strip()
    )
    actual_source_family_counts = Counter(
        str(item.get('source_family') or '').strip() for item in items if isinstance(item, Mapping) and str(item.get('source_family') or '').strip()
    )

    status_preservation_conflicts: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get('item_id') or '').strip()
        status = str(item.get('status') or '').strip()
        preservation = str(item.get('preservation_decision') or '').strip()
        if status == 'skipped' and preservation != 'skipped':
            status_preservation_conflicts.append({
                'item_id': item_id,
                'status': status,
                'preservation_decision': preservation,
                'reason': 'skipped_status_requires_skipped_preservation_decision',
            })
        elif preservation == 'skipped' and status != 'skipped':
            status_preservation_conflicts.append({
                'item_id': item_id,
                'status': status,
                'preservation_decision': preservation,
                'reason': 'skipped_preservation_decision_requires_skipped_status',
            })

    audit_expected = package_audit.get('expected_item_count')
    audit_returned = package_audit.get('returned_item_count', package_audit.get('received_item_count'))
    counts_match = (
        _safe_int(audit_expected, -1) == len(expected_ids)
        and _safe_int(audit_returned, -1) == len(items)
        and len(items) == len(expected_ids)
    )
    summary_status_counts_match = _compare_count_map(summary.get('status_counts'), actual_status_counts)
    summary_preservation_counts_match = _compare_count_map(summary.get('preservation_counts'), actual_preservation_counts)
    summary_item_type_counts_match = _compare_count_map(summary.get('item_type_counts'), actual_item_type_counts)
    summary_source_family_counts_match = _compare_count_map(summary.get('source_family_counts'), actual_source_family_counts)
    package_item_type_counts_match = _compare_count_map(package_audit.get('item_type_counts'), actual_item_type_counts)
    package_source_family_counts_match = _compare_count_map(package_audit.get('source_family_counts'), actual_source_family_counts)
    separation_ok = not status_preservation_conflicts

    return {
        'schema_validation_ok': bool(schema_validation_ok),
        'expected_item_count': len(expected_ids),
        'returned_item_count': len(items),
        'package_audit_expected_item_count': _safe_int(audit_expected, -1),
        'package_audit_returned_item_count': _safe_int(audit_returned, -1),
        'counts_match': counts_match,
        'missing_item_ids': missing_item_ids,
        'unexpected_item_ids': unexpected_item_ids,
        'duplicate_item_ids': duplicate_item_ids,
        'summary_status_counts_match': summary_status_counts_match,
        'summary_preservation_counts_match': summary_preservation_counts_match,
        'summary_item_type_counts_match': summary_item_type_counts_match,
        'summary_source_family_counts_match': summary_source_family_counts_match,
        'package_item_type_counts_match': package_item_type_counts_match,
        'package_source_family_counts_match': package_source_family_counts_match,
        'status_preservation_separation_ok': separation_ok,
        'status_preservation_conflicts': status_preservation_conflicts,
        'actual_status_counts': dict(sorted(actual_status_counts.items())),
        'actual_preservation_counts': dict(sorted(actual_preservation_counts.items())),
        'actual_item_type_counts': dict(sorted(actual_item_type_counts.items())),
        'actual_source_family_counts': dict(sorted(actual_source_family_counts.items())),
        'success': bool(
            schema_validation_ok
            and counts_match
            and not missing_item_ids
            and not unexpected_item_ids
            and not duplicate_item_ids
            and separation_ok
            and summary_item_type_counts_match
            and summary_source_family_counts_match
            and package_item_type_counts_match
            and package_source_family_counts_match
        ),
    }


def flatten_response_item_for_score_table(item: Mapping[str, object], baseline: Mapping[str, object] | None = None) -> dict[str, object]:
    common_scores = item.get('common_scores') if isinstance(item.get('common_scores'), Mapping) else {}
    normalized = item.get('normalized_judgement') if isinstance(item.get('normalized_judgement'), Mapping) else {}
    timing = item.get('timing') if isinstance(item.get('timing'), Mapping) else {}
    baseline = baseline if isinstance(baseline, Mapping) else {}
    return {
        'package_id': baseline.get('package_id', ''),
        'batch_id': baseline.get('batch_id', ''),
        'item_id': item.get('item_id', ''),
        'document_or_item_id': item.get('document_or_item_id', ''),
        'item_type': item.get('item_type', ''),
        'source_family': item.get('source_family', ''),
        'focus_entities': item.get('focus_entities', []),
        'status': item.get('status', ''),
        'preservation_decision': item.get('preservation_decision', ''),
        'primary_claim': item.get('primary_claim', ''),
        'evidence_summary': item.get('evidence_summary', ''),
        'evidence_refs': _safe_jsonable_list(item.get('evidence_refs')),
        'risk_summary': _safe_jsonable_list(item.get('risk_summary')),
        'counterpoint_summary': _safe_jsonable_list(item.get('counterpoint_summary')),
        'transmission_path': _safe_jsonable_list(item.get('transmission_path')),
        'evidence_quality_score': common_scores.get('evidence_quality_score'),
        'novelty_score': common_scores.get('novelty_score'),
        'materiality_score': common_scores.get('materiality_score'),
        'transmission_clarity_score': common_scores.get('transmission_clarity_score'),
        'source_reliability_score': common_scores.get('source_reliability_score'),
        'counterbalance_score': common_scores.get('counterbalance_score'),
        'timing_clarity_score': common_scores.get('timing_clarity_score'),
        'stance': normalized.get('stance'),
        'time_horizon': normalized.get('time_horizon'),
        'market_scope': normalized.get('market_scope'),
        'actionability': normalized.get('actionability'),
        'duplicate_or_near_duplicate': normalized.get('duplicate_or_near_duplicate'),
        'final_result_label': item.get('final_result_label'),
        'analysis_confidence': item.get('analysis_confidence'),
        'timing_source': timing.get('timing_source'),
        'batch_wall_seconds_observed': timing.get('batch_wall_seconds_observed'),
        'normalized_item_wall_seconds': timing.get('normalized_item_wall_seconds'),
        'operator_active_seconds_share': timing.get('operator_active_seconds_share'),
        'timing_comparability_note': timing.get('timing_comparability_note'),
    }


def build_canonical_output_bundle(
    response: Mapping[str, object] | None,
    *,
    integrity_audit: Mapping[str, object],
    forensic_hold: bool = False,
) -> dict[str, object]:
    payload = dict(response or {})
    baseline = payload.get('baseline') if isinstance(payload.get('baseline'), Mapping) else {}
    audit = {
        'contract_version': payload.get('contract_version', ''),
        'review_mode': payload.get('review_mode', ''),
        'baseline': baseline,
        'package_audit': payload.get('package_audit', {}),
        'review_batch': payload.get('review_batch', {}),
        'summary': payload.get('summary', {}),
        'integrity_audit': dict(integrity_audit),
        'forensic_hold': bool(forensic_hold),
    }
    items = payload.get('items') if isinstance(payload.get('items'), list) else []
    score_rows = [
        flatten_response_item_for_score_table(item, baseline=baseline)
        for item in items
        if isinstance(item, Mapping)
    ]
    return {
        'canonical_audit': audit,
        'normalized_score_table': score_rows,
    }


def write_canonical_output_bundle(
    run_dir: Path,
    response: Mapping[str, object] | None,
    *,
    integrity_audit: Mapping[str, object],
    forensic_hold: bool = False,
) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    bundle = build_canonical_output_bundle(
        response,
        integrity_audit=integrity_audit,
        forensic_hold=forensic_hold,
    )
    audit_path = run_dir / 'canonical_audit.json'
    score_table_path = run_dir / 'normalized_score_table.jsonl'
    audit_path.write_text(json.dumps(bundle['canonical_audit'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with score_table_path.open('w', encoding='utf-8') as fp:
        for row in bundle['normalized_score_table']:
            fp.write(json.dumps(row, ensure_ascii=False) + '\n')
    return {
        'canonical_audit_file': str(audit_path),
        'normalized_score_table_file': str(score_table_path),
    }
