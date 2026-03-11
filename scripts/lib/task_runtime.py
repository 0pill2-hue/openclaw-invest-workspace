#!/usr/bin/env python3
from __future__ import annotations

EXPLICIT_NONTERMINAL_WAIT_PHASES = {
    'awaiting_callback',
    'awaiting_result',
    'delegated',
    'delegated_to_subagent',
    'long_running_active_execution',
    'long_running_execution',
    'subagent',
    'subagent_launched',
    'subagent_running',
    'waiting_child_completion',
    'waiting_subagent',
    'waiting_writer_and_subagent',
}


def normalize_phase_name(phase: str | None) -> str:
    text = str(phase or '').strip().lower()
    if not text:
        return ''
    return text.replace('-', '_').replace(' ', '_')


def is_nonterminal_wait_phase(phase: str | None) -> bool:
    normalized = normalize_phase_name(phase)
    if not normalized:
        return False
    if normalized in EXPLICIT_NONTERMINAL_WAIT_PHASES:
        return True
    if 'subagent' in normalized:
        return True
    if normalized.startswith('awaiting_'):
        return True
    if normalized.startswith('delegated_to_'):
        return True
    return False


def is_nonterminal_wait_state(status: str | None, phase: str | None) -> bool:
    normalized_status = str(status or '').strip().upper()
    return normalized_status in {'IN_PROGRESS', 'BLOCKED'} and is_nonterminal_wait_phase(phase)
