#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUTO_STATE = ROOT / "invest/stages/stage2/outputs/runtime/stage02_auto_state.json"
RUNTIME_CONFIG = ROOT / "invest/stages/stage2/inputs/config/stage2_runtime_config.json"
PROCESSED_INDEX = ROOT / "invest/stages/stage2/outputs/clean/production/_processed_index.json"
REPORTS_DIR = ROOT / "invest/stages/stage2/outputs/reports"
QC_DIR = REPORTS_DIR / "qc"
STATUS_PATH = ROOT / "invest/stages/stage2/outputs/runtime/stage2_status.json"

_CACHE: dict[str, Any] = {"signature": None, "payload": None}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def latest_nonempty_refine_report() -> Path | None:
    files = sorted(QC_DIR.glob("FULL_REFINE_REPORT_*.json"))
    chosen: Path | None = None
    for path in reversed(files):
        payload = safe_load_json(path, {})
        totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
        if totals.get("total_input_files"):
            return path
        chosen = chosen or path
    return chosen


def summarize_processed_index(path: Path) -> dict[str, Any]:
    payload = safe_load_json(path, {})
    meta = payload.get("__meta__") if isinstance(payload.get("__meta__"), dict) else {}
    entries = payload.get("entries") if isinstance(payload.get("entries"), dict) else {}
    folders = meta.get("folders") if isinstance(meta.get("folders"), list) else []
    return {
        "entry_count": len(entries),
        "folder_count": len(folders),
        "meta": meta,
        "source": str(path.relative_to(ROOT)) if path.exists() else "",
    }


def file_signature(paths: list[Path]) -> tuple[Any, ...]:
    sig: list[Any] = []
    for path in paths:
        if path and path.exists():
            stat = path.stat()
            sig.extend([str(path), stat.st_mtime_ns, stat.st_size])
        else:
            sig.extend([str(path) if path else "", None, None])
    return tuple(sig)


def write_status_json(status_payload: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_summary() -> dict[str, Any]:
    latest_qc = latest_file(REPORTS_DIR, "QC_REPORT_*.json")
    latest_refine = latest_nonempty_refine_report()
    signature = file_signature([AUTO_STATE, RUNTIME_CONFIG, PROCESSED_INDEX, latest_qc or Path(""), latest_refine or Path("")])
    if signature == _CACHE.get("signature") and _CACHE.get("payload") is not None:
        return _CACHE["payload"]

    auto_state = safe_load_json(AUTO_STATE, {})
    runtime_config = safe_load_json(RUNTIME_CONFIG, {})
    processed_index = summarize_processed_index(PROCESSED_INDEX) if PROCESSED_INDEX.exists() else {}
    qc_report = safe_load_json(latest_qc, {}) if latest_qc else {}
    refine_report = safe_load_json(latest_refine, {}) if latest_refine else {}

    qc_totals = qc_report.get("totals") if isinstance(qc_report.get("totals"), dict) else {}
    refine_totals = refine_report.get("totals") if isinstance(refine_report.get("totals"), dict) else {}
    classification = refine_report.get("classification") if isinstance(refine_report.get("classification"), dict) else {}
    link_enrichment = refine_report.get("link_enrichment") if isinstance(refine_report.get("link_enrichment"), dict) else {}
    telegram_pdf = refine_report.get("telegram_pdf") if isinstance(refine_report.get("telegram_pdf"), dict) else {}
    corpus_dedup = refine_report.get("corpus_dedup") if isinstance(refine_report.get("corpus_dedup"), dict) else {}

    status_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": _clean(auto_state.get("last_result")) or "unknown",
        "run_key": _clean(auto_state.get("run_key")),
        "last_attempt_kst": _clean(auto_state.get("last_attempt_kst")),
        "last_success_kst": _clean(auto_state.get("last_success_kst")),
        "latest_stage1_kst": _clean(auto_state.get("latest_stage1_kst")),
        "processed_index": {
            "entry_count": processed_index.get("entry_count", 0),
            "folder_count": processed_index.get("folder_count", 0),
            "stage2_rule_version": _clean((processed_index.get("meta") or {}).get("stage2_rule_version")),
            "classification_version": _clean((processed_index.get("meta") or {}).get("classification_version")),
            "semantic_version": _clean((processed_index.get("meta") or {}).get("semantic_version")),
            "input_source": _clean((processed_index.get("meta") or {}).get("input_source")),
        },
        "config_provenance": {
            "runtime_config_version": _clean(runtime_config.get("version")),
            "refine_provenance": (refine_report.get("config_provenance") or {}) if isinstance(refine_report.get("config_provenance"), dict) else {},
            "qc_provenance": (qc_report.get("config_provenance") or {}) if isinstance(qc_report.get("config_provenance"), dict) else {},
        },
        "latest_reports": {
            "refine": {
                "path": str(latest_refine.relative_to(ROOT)) if latest_refine else "",
                "generated_at": _clean(refine_report.get("generated_at")),
                "totals": refine_totals,
            },
            "qc": {
                "path": str(latest_qc.relative_to(ROOT)) if latest_qc else "",
                "executed_at": _clean(qc_report.get("executed_at")),
                "totals": qc_totals,
                "validation": qc_report.get("validation", {}),
            },
        },
    }
    write_status_json(status_payload)

    cards = [
        {
            "id": "stage2_runtime",
            "label": "Stage2 Runtime",
            "status": "ok" if _clean(auto_state.get("last_result")) == "success" else "warn",
            "summary": f"run {auto_state.get('run_key', '미확인')} / last success {auto_state.get('last_success_kst', '미확인')}",
            "detail": {
                **auto_state,
                "source": str(AUTO_STATE.relative_to(ROOT)),
            },
        },
        {
            "id": "stage2_processed_index",
            "label": "Processed Index",
            "status": "ok" if processed_index else "warn",
            "summary": f"entries {processed_index.get('entry_count', 0):,} / folders {processed_index.get('folder_count', 0):,}",
            "detail": processed_index,
        },
        {
            "id": "stage2_refine",
            "label": "Latest Full Refine",
            "status": "ok" if refine_report else "warn",
            "summary": f"input {refine_totals.get('total_input_files', 0):,} / clean {refine_totals.get('total_clean_files', 0):,} / quarantine {refine_totals.get('total_quarantine_files', 0):,}",
            "detail": {
                "path": str(latest_refine.relative_to(ROOT)) if latest_refine else "",
                "generated_at": _clean(refine_report.get("generated_at")),
                "run_mode": _clean(refine_report.get("run_mode")),
                "totals": refine_totals,
                "classification": classification,
                "link_enrichment": link_enrichment,
                "telegram_pdf": telegram_pdf,
                "corpus_dedup": corpus_dedup,
                "config_provenance": refine_report.get("config_provenance", {}),
            },
        },
        {
            "id": "stage2_qc",
            "label": "Latest QC",
            "status": "ok" if bool((qc_report.get("validation") or {}).get("pass")) else "warn",
            "summary": f"processed {qc_totals.get('processed_files', 0):,} / anomalies {qc_totals.get('anomalies', 0):,} / hard failures {qc_totals.get('hard_failures', 0):,}",
            "detail": {
                "path": str(latest_qc.relative_to(ROOT)) if latest_qc else "",
                "executed_at": _clean(qc_report.get("executed_at")),
                "totals": qc_totals,
                "validation": qc_report.get("validation", {}),
                "config_provenance": qc_report.get("config_provenance", {}),
                "input_source": qc_report.get("input_source", {}),
            },
        },
        {
            "id": "stage2_status",
            "label": "Stage2 Status Cache",
            "status": "ok",
            "summary": f"cached to {STATUS_PATH.relative_to(ROOT)}",
            "detail": status_payload,
        },
    ]

    payload = {
        "available": bool(auto_state or processed_index or qc_report or refine_report),
        "summary": {
            "status": _clean(auto_state.get("last_result")) or "unknown",
            "run_key": _clean(auto_state.get("run_key")),
            "last_success_kst": _clean(auto_state.get("last_success_kst")),
            "processed_entries": processed_index.get("entry_count", 0),
            "processed_folders": processed_index.get("folder_count", 0),
            "runtime_config_version": _clean(runtime_config.get("version")),
        },
        "cards": cards,
        "sources": {
            "auto_state": str(AUTO_STATE.relative_to(ROOT)),
            "runtime_config": str(RUNTIME_CONFIG.relative_to(ROOT)),
            "processed_index": str(PROCESSED_INDEX.relative_to(ROOT)),
            "latest_qc": str(latest_qc.relative_to(ROOT)) if latest_qc else "",
            "latest_refine": str(latest_refine.relative_to(ROOT)) if latest_refine else "",
            "status_cache": str(STATUS_PATH.relative_to(ROOT)),
        },
        "degraded_fields": [name for name, value in {
            "auto_state": auto_state,
            "runtime_config": runtime_config,
            "processed_index": processed_index,
            "latest_qc": qc_report,
            "latest_refine": refine_report,
        }.items() if not value],
    }
    _CACHE["signature"] = signature
    _CACHE["payload"] = payload
    return payload


if __name__ == "__main__":
    print(json.dumps(build_summary(), ensure_ascii=False, indent=2))
