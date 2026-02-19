#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

EXPECTED_TRACK_COUNTS_12_BASELINE: dict[str, int] = {
    "numeric": 3,
    "qualitative": 3,
    "hybrid": 3,
    "external-pretrained": 3,
}


def track_counts_assertion(track_counts: dict[str, int]) -> str:
    normalized = {k: int(v) for k, v in track_counts.items()}
    return "pass" if normalized == EXPECTED_TRACK_COUNTS_12_BASELINE else "fail"


def enforce_track_counts_or_fail_stop(
    track_counts: dict[str, int],
    *,
    out_json: Path | None = None,
    version: str,
    scope: str = "KRX_ONLY",
) -> dict[str, Any]:
    assertion = track_counts_assertion(track_counts)
    meta = {
        "protocol_enforced": True,
        "track_counts_assertion": assertion,
        "expected_track_counts": EXPECTED_TRACK_COUNTS_12_BASELINE,
    }
    if assertion == "pass":
        return meta

    fail_payload = {
        "result_grade": "DRAFT",
        "status": "FAIL_STOP",
        "watermark": "TEST ONLY",
        "scope": scope,
        "version": version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **meta,
        "track_counts": {k: int(v) for k, v in track_counts.items()},
        "fail_reason": "12-baseline protocol violation: track_counts must be numeric3/qualitative3/hybrid3/external-pretrained3",
    }

    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(fail_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    raise RuntimeError(
        "FAIL_STOP: 12-baseline protocol violation "
        f"(expected={EXPECTED_TRACK_COUNTS_12_BASELINE}, actual={track_counts})"
    )
