#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / "invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json"
CHAIN_STATE = ROOT / "invest/stages/stage1/outputs/runtime/stage1234_chain_state.json"
ATTACHMENT_RECOVERY_SUMMARY = ROOT / "invest/stages/stage1/outputs/runtime/stage1_attachment_recovery_summary.json"

_CACHE: dict[str, Any] = {"signature": None, "payload": None}

LABELS = {
    "kr_ohlcv": "KR OHLCV",
    "kr_supply": "KR Supply",
    "us_ohlcv": "US OHLCV",
    "market_macro": "Market Macro",
    "kr_dart": "KR DART",
    "market_rss": "Market RSS",
    "market_news_url_index": "News URL Index",
    "market_news_selected_articles": "Selected Articles",
    "text_blog": "Text Blog",
    "text_telegram": "Text Telegram",
    "text_premium": "Text Premium",
    "dart_continuity": "DART Continuity",
    "raw_tree_coverage": "Raw Tree Coverage",
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def file_signature(paths: list[Path]) -> tuple[Any, ...]:
    sig: list[Any] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            sig.extend([str(path), stat.st_mtime_ns, stat.st_size])
        else:
            sig.extend([str(path), None, None])
    return tuple(sig)


def dataset_summary(dataset_id: str, detail: dict[str, Any], failures: list[str]) -> tuple[str, str]:
    failure_text = " ".join(failures)
    failed = dataset_id in failure_text
    if "count" in detail:
        count = detail.get("count")
        minimum = detail.get("min_count")
        age = detail.get("latest_age_h")
        status = "fail" if failed else "ok"
        summary = f"count {count:,} / min {minimum:,} / latest {age}h" if isinstance(count, int) and isinstance(minimum, int) else f"count {count}"
        return status, summary
    if dataset_id == "dart_continuity":
        status = "fail" if failed else "ok"
        summary = f"{detail.get('min_date')} → {detail.get('max_date')} / gaps>{detail.get('gap_limit_days')}d = {len(detail.get('gaps_over_limit', []))}"
        return status, summary
    if dataset_id == "raw_tree_coverage":
        empty = detail.get("empty_leaf_dir_count", 0)
        status = "warn" if empty else "ok"
        summary = f"covered {detail.get('covered_leaf_dirs')} / leaf {detail.get('leaf_dir_count')} / empty {empty}"
        return status, summary
    return ("fail" if failed else "ok", "summary unavailable")


def build_summary() -> dict[str, Any]:
    signature = file_signature([CHECKPOINT, CHAIN_STATE, ATTACHMENT_RECOVERY_SUMMARY])
    if signature == _CACHE.get("signature") and _CACHE.get("payload") is not None:
        return _CACHE["payload"]

    checkpoint = safe_load_json(CHECKPOINT, {})
    chain_state = safe_load_json(CHAIN_STATE, {})
    attachment_recovery = safe_load_json(ATTACHMENT_RECOVERY_SUMMARY, {})
    failures = [str(item) for item in checkpoint.get("failures", [])] if isinstance(checkpoint.get("failures"), list) else []
    details = checkpoint.get("details") if isinstance(checkpoint.get("details"), dict) else {}

    cards = [
        {
            "id": "stage1_checkpoint",
            "label": "Stage1 Checkpoint",
            "status": "ok" if checkpoint.get("ok") else "warn",
            "summary": f"grade {checkpoint.get('grade', '미확인')} / failed {checkpoint.get('failed_count', '미확인')}",
            "detail": {
                "timestamp": checkpoint.get("timestamp"),
                "grade": checkpoint.get("grade"),
                "ok": checkpoint.get("ok"),
                "failed_count": checkpoint.get("failed_count"),
                "failures": failures,
                "source": str(CHECKPOINT.relative_to(ROOT)),
            },
        },
        {
            "id": "stage1_chain_state",
            "label": "Stage1 Chain State",
            "status": "ok" if chain_state else "warn",
            "summary": f"last success {chain_state.get('last_success_kst', '미확인')}",
            "detail": {
                **chain_state,
                "source": str(CHAIN_STATE.relative_to(ROOT)),
            },
        },
        {
            "id": "stage1_attachment_recovery",
            "label": "Stage1 Attachment Recovery",
            "status": "ok" if str(attachment_recovery.get('stage_status', '')).upper() == 'OK' else ("warn" if attachment_recovery else "warn"),
            "summary": (
                f"stage {attachment_recovery.get('stage_status', '미확인')} / "
                f"completeness {attachment_recovery.get('completeness_status', '미확인')} / "
                f"retry {((attachment_recovery.get('retry_visibility') or {}).get('retry_count', '미확인'))}"
            ),
            "detail": {
                **attachment_recovery,
                "source": str(ATTACHMENT_RECOVERY_SUMMARY.relative_to(ROOT)),
            },
        },
    ]

    for dataset_id, detail in details.items():
        if not isinstance(detail, dict):
            continue
        status, summary = dataset_summary(dataset_id, detail, failures)
        cards.append({
            "id": dataset_id,
            "label": LABELS.get(dataset_id, dataset_id),
            "status": status,
            "summary": summary,
            "detail": detail,
        })

    payload = {
        "available": bool(checkpoint),
        "summary": {
            "timestamp": _clean(checkpoint.get("timestamp")),
            "grade": _clean(checkpoint.get("grade")),
            "ok": bool(checkpoint.get("ok")) if checkpoint else None,
            "failed_count": checkpoint.get("failed_count", 0),
            "last_success_kst": _clean(chain_state.get("last_success_kst")),
            "last_success_run_key": _clean(chain_state.get("last_success_run_key")),
        },
        "cards": cards,
        "sources": {
            "checkpoint": str(CHECKPOINT.relative_to(ROOT)),
            "chain_state": str(CHAIN_STATE.relative_to(ROOT)),
            "attachment_recovery": str(ATTACHMENT_RECOVERY_SUMMARY.relative_to(ROOT)),
        },
        "degraded_fields": [name for name, value in {
            "checkpoint": checkpoint,
            "chain_state": chain_state,
            "attachment_recovery": attachment_recovery,
        }.items() if not value],
    }
    _CACHE["signature"] = signature
    _CACHE["payload"] = payload
    return payload


if __name__ == "__main__":
    print(json.dumps(build_summary(), ensure_ascii=False, indent=2))
