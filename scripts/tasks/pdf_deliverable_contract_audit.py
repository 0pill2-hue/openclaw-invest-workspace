#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json"
CATALOG_PATH = ROOT / "invest/stages/stage1/outputs/raw/source_coverage_index.json"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"expected object json: {path}")
    return data


def _get(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _yyyymmdd_to_iso(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return ""


def build_payload(status_path: Path, catalog_path: Path) -> dict[str, Any]:
    status = _load_json(status_path)
    catalog = _load_json(catalog_path)

    index_summary = _get(status, "pdf_db_index_summary") or {}
    attachment_scope = _get(catalog, "sources", "telegram", "scope", "attachment_artifacts") or {}
    telegram_source = _get(catalog, "sources", "telegram") or {}

    coverage_start_raw = (
        _get(index_summary, "earliest_message_date")
        or _get(attachment_scope, "earliest_message_date")
    )
    coverage_end_raw = (
        _get(index_summary, "latest_message_date")
        or _get(attachment_scope, "latest_message_date")
    )

    observed = {
        "status_runtime_state": str(status.get("status") or ""),
        "pdf_progress_basis": str(status.get("pdf_progress_basis") or ""),
        "pdf_meta_total": _as_int(status.get("pdf_meta_total") or status.get("pdf_db_documents_total")),
        "pdf_extract_ok_total": _as_int(status.get("pdf_extract_ok_total") or status.get("pdf_db_extract_ok_total")),
        "documents_with_text": _as_int(_get(index_summary, "documents_with_text") or status.get("pdf_db_text_ready_total")),
        "pdf_decompose_ok_total": _as_int(status.get("pdf_decompose_ok_total") or status.get("pdf_db_decomposed_total")),
        "pdf_pages_total": _as_int(status.get("pdf_pages_total") or status.get("pdf_db_pages_total")),
        "coverage_start": _yyyymmdd_to_iso(coverage_start_raw),
        "coverage_end": _yyyymmdd_to_iso(coverage_end_raw),
        "coverage_start_raw": str(coverage_start_raw or ""),
        "coverage_end_raw": str(coverage_end_raw or ""),
        "coverage_start_source": "status.pdf_db_index_summary.earliest_message_date"
        if _get(index_summary, "earliest_message_date")
        else "source_coverage_index.sources.telegram.scope.attachment_artifacts.earliest_message_date",
        "diagnostics": {
            "physical_pdf_files": _as_int(_get(attachment_scope, "pdf_files")),
            "generic_telegram_earliest_date": str(_get(telegram_source, "earliest_date") or ""),
            "attachment_pdf_earliest_message_date": str(_get(attachment_scope, "earliest_message_date") or ""),
            "status_pdf_db_missing_original_total": _as_int(status.get("pdf_db_missing_original_total")),
        },
    }

    checks: list[dict[str, Any]] = []

    def add_check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add_check(
        "required_counts_present",
        observed["pdf_meta_total"] > 0 and observed["pdf_extract_ok_total"] >= 0 and observed["documents_with_text"] > 0,
        (
            f"pdf_meta_total={observed['pdf_meta_total']}, "
            f"pdf_extract_ok_total={observed['pdf_extract_ok_total']}, "
            f"documents_with_text={observed['documents_with_text']}"
        ),
    )
    add_check(
        "coverage_start_present",
        bool(observed["coverage_start"]),
        f"coverage_start={observed['coverage_start'] or '<missing>'}",
    )
    add_check(
        "db_basis_locked",
        observed["pdf_progress_basis"] == "db.pdf_documents/pdf_pages",
        f"pdf_progress_basis={observed['pdf_progress_basis'] or '<missing>'}",
    )
    add_check(
        "pdf_specific_coverage_used",
        observed["diagnostics"]["attachment_pdf_earliest_message_date"] == observed["coverage_start_raw"],
        (
            "generic telegram earliest_date="
            f"{observed['diagnostics']['generic_telegram_earliest_date'] or '<missing>'}; "
            "pdf earliest_message_date="
            f"{observed['diagnostics']['attachment_pdf_earliest_message_date'] or '<missing>'}"
        ),
    )
    add_check(
        "original_file_count_not_success_gate",
        observed["diagnostics"]["physical_pdf_files"] != observed["pdf_meta_total"],
        (
            f"physical_pdf_files={observed['diagnostics']['physical_pdf_files']} vs "
            f"pdf_meta_total={observed['pdf_meta_total']}"
        ),
    )

    return {
        "contract_version": "2026-03-11",
        "success_basis": "db_reflected_decompose_extract",
        "original_retention_required": False,
        "artifacts": {
            "status_json": str(status_path.relative_to(ROOT)),
            "catalog_json": str(catalog_path.relative_to(ROOT)),
        },
        "required_deliverable_fields": {
            "pdf_meta_total": "status.pdf_meta_total (fallback: status.pdf_db_documents_total)",
            "pdf_extract_ok_total": "status.pdf_extract_ok_total (fallback: status.pdf_db_extract_ok_total)",
            "documents_with_text": "status.pdf_db_index_summary.documents_with_text (fallback: status.pdf_db_text_ready_total)",
            "coverage_start": "ISO date derived from PDF-specific earliest_message_date, not generic sources.telegram.earliest_date",
        },
        "observed": observed,
        "checks": checks,
        "contract_ok": all(item["ok"] for item in checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit for Stage1 PDF deliverable contract")
    parser.add_argument("--status-path", default=str(STATUS_PATH))
    parser.add_argument("--catalog-path", default=str(CATALOG_PATH))
    parser.add_argument("--write", default="")
    args = parser.parse_args()

    payload = build_payload(Path(args.status_path), Path(args.catalog_path))
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.write:
        out_path = Path(args.write)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload.get("contract_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
