from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
NEWS_SELECTED_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles"
NEWS_SELECTED_SUMMARY_PATH = NEWS_SELECTED_DIR / "selected_articles_merged_summary.json"


def _rel(path: Path, *, root: Path = ROOT) -> str:
    return str(path.relative_to(root))


def _normalize_iso_date(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        digits = s[:10].replace("-", "")
        return digits if len(digits) == 8 and digits.isdigit() else None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return None


def _yyyymmdd_to_iso(raw: str | None) -> str | None:
    s = str(raw or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return None


def selected_articles_live_files(selected_dir: Path = NEWS_SELECTED_DIR) -> list[Path]:
    if not selected_dir.exists():
        return []
    files: list[Path] = []
    for path in sorted(selected_dir.glob("selected_articles_*.jsonl")):
        if not path.is_file() or path.name == "selected_articles_merged.jsonl":
            continue
        files.append(path)
    return files


def build_selected_articles_live_summary(
    files: list[Path] | None = None,
    *,
    selected_dir: Path = NEWS_SELECTED_DIR,
    root: Path = ROOT,
) -> dict[str, Any]:
    live_files = list(files) if files is not None else selected_articles_live_files(selected_dir)

    dates: list[str] = []
    rows_seen = 0
    unique_urls: set[str] = set()
    source_domains: Counter[str] = Counter()
    source_kinds: Counter[str] = Counter()
    row_counts_by_file: dict[str, int] = {}

    for path in live_files:
        local_rows = 0
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    rows_seen += 1
                    local_rows += 1
                    url = str(obj.get("url", "")).strip()
                    if url:
                        unique_urls.add(url)
                    source_domain = str(obj.get("source_domain", "")).strip()
                    if source_domain:
                        source_domains[source_domain] += 1
                    source_kind = str(obj.get("source_kind", "")).strip()
                    if source_kind:
                        source_kinds[source_kind] += 1
                    for field in ("published_date", "published_at", "collected_at"):
                        dt = _normalize_iso_date(obj.get(field, ""))
                        if dt is not None:
                            dates.append(dt)
                            break
        except Exception:
            continue
        row_counts_by_file[path.name] = local_rows

    recent_files = live_files[-2:]
    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None
    latest_file = live_files[-1] if live_files else None
    latest_mtime = latest_file.stat().st_mtime if latest_file and latest_file.exists() else None

    return {
        "summary_mode": "directory_jsonl_summary",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(selected_dir.relative_to(root)),
        "source_files": len(live_files),
        "source_files_list": [_rel(path, root=root) for path in live_files],
        "merged_count": rows_seen,
        "total_rows": rows_seen,
        "unique_url_count": len(unique_urls),
        "date_min": _yyyymmdd_to_iso(date_min),
        "date_max": _yyyymmdd_to_iso(date_max),
        "output_file": "",
        "latest_file": _rel(latest_file, root=root) if latest_file else None,
        "latest_file_mtime_utc": datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat() if latest_mtime else None,
        "recent_backfill_files": [_rel(path, root=root) for path in recent_files],
        "recent_backfill_added_rows": sum(row_counts_by_file.get(path.name, 0) for path in recent_files),
        "row_counts_by_file": {key: row_counts_by_file[key] for key in sorted(row_counts_by_file)},
        "source_domains": {key: source_domains[key] for key in sorted(source_domains)},
        "source_kinds": {key: source_kinds[key] for key in sorted(source_kinds)},
        "contract_note": "Canonical selected_articles corpus is the live selected_articles_*.jsonl set in this directory. This file is a directory summary only.",
    }


def validate_selected_articles_live_summary(
    summary: Any,
    files: list[Path] | None = None,
    *,
    selected_dir: Path = NEWS_SELECTED_DIR,
    root: Path = ROOT,
) -> list[str]:
    live_files = list(files) if files is not None else selected_articles_live_files(selected_dir)
    if not isinstance(summary, dict):
        return ["summary_missing_or_invalid"]
    expected = build_selected_articles_live_summary(files=live_files, selected_dir=selected_dir, root=root)
    issues: list[str] = []
    for key in (
        "summary_mode",
        "source_dir",
        "source_files",
        "source_files_list",
        "merged_count",
        "total_rows",
        "unique_url_count",
        "date_min",
        "date_max",
        "output_file",
        "latest_file",
        "latest_file_mtime_utc",
        "recent_backfill_files",
        "recent_backfill_added_rows",
        "row_counts_by_file",
        "source_domains",
        "source_kinds",
        "contract_note",
    ):
        if summary.get(key) != expected.get(key):
            issues.append(f"{key}_mismatch")
    return issues


def write_selected_articles_live_summary(
    path: Path = NEWS_SELECTED_SUMMARY_PATH,
    files: list[Path] | None = None,
    *,
    selected_dir: Path = NEWS_SELECTED_DIR,
    root: Path = ROOT,
) -> dict[str, Any]:
    summary = build_selected_articles_live_summary(files=files, selected_dir=selected_dir, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
