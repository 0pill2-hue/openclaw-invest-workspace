#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PYTHON_FALLBACK = sys.executable
NAVER_INDEX_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_naver_finance_index_status.json"
COLLECTOR_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_selected_articles_status.json"
NAVER_SELECTED_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_selected_articles_naver_status.json"
SELECTED_ARTICLES_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles"
DEFAULT_ARCHIVE_ROOT = ROOT / "invest/stages/stage1/outputs/archive/news/selected_articles_disabled"
NAVER_INDEX_SCRIPT = ROOT / "invest/stages/stage1/scripts/stage01_fetch_naver_finance_news_index.py"
COLLECTOR_SCRIPT = ROOT / "invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py"


def _truthy(raw: str | None, default: bool = False) -> bool:
    text = (raw or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def _select_python_bin() -> str:
    env_python = os.environ.get("INVEST_PYTHON_BIN", "").strip()
    workspace_python = ROOT / ".venv/bin/python3"
    if env_python and Path(env_python).is_file() and os.access(env_python, os.X_OK):
        return env_python
    if workspace_python.is_file() and os.access(workspace_python, os.X_OK):
        return str(workspace_python)
    return PYTHON_FALLBACK


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (ROOT / path)


def _run(cmd: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _resolve_index_path_from_status() -> Path | None:
    payload = _load_json(NAVER_INDEX_STATUS_PATH, {})
    index_file = str(payload.get("index_file") or "").strip() if isinstance(payload, dict) else ""
    if not index_file:
        return None
    path = _resolve_path(index_file)
    return path if path.exists() else None


def _archive_existing_selected_articles(archive_root: Path) -> tuple[Path | None, list[str]]:
    if not SELECTED_ARTICLES_DIR.exists():
        return None, []
    targets = sorted(SELECTED_ARTICLES_DIR.glob("*.jsonl"))
    if not targets:
        return None, []

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_dir = archive_root / ts
    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []

    for src in targets:
        dst = archive_dir / src.name
        if dst.exists():
            dst = archive_dir / f"{src.stem}_{int(src.stat().st_mtime)}{src.suffix}"
        shutil.move(str(src), str(dst))
        moved.append(str(dst.relative_to(ROOT)))

    return archive_dir, moved


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run selected_articles collector from verified Naver finance index only")
    ap.add_argument("--sections", default="", help="comma-separated Naver section_id2 override")
    ap.add_argument("--pages", type=int, default=0, help="max pages per section (0=use script default/env)")
    ap.add_argument("--timeout", type=int, default=0, help="HTTP timeout seconds for Naver index fetch (0=default/env)")
    ap.add_argument(
        "--archive-existing-selected",
        action="store_true",
        default=_truthy(os.environ.get("NEWS_SELECTED_NAVER_ARCHIVE_EXISTING", "0")),
        help="move existing selected_articles *.jsonl to archive path before collection",
    )
    ap.add_argument(
        "--archive-dir",
        default=os.environ.get("NEWS_SELECTED_NAVER_ARCHIVE_DIR", str(DEFAULT_ARCHIVE_ROOT.relative_to(ROOT))),
        help="archive root path for one-time selected_articles replacement",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    python_bin = _select_python_bin()
    env = os.environ.copy()
    env["NEWS_SELECTED_MERGE_ALL_INDEXES"] = "0"

    archive_dir = None
    archived_paths: list[str] = []
    if args.archive_existing_selected:
        archive_root = _resolve_path(args.archive_dir)
        archive_dir, archived_paths = _archive_existing_selected_articles(archive_root)

    naver_cmd = [python_bin, str(NAVER_INDEX_SCRIPT)]
    if args.sections.strip():
        naver_cmd.extend(["--sections", args.sections.strip()])
    if args.pages > 0:
        naver_cmd.extend(["--pages", str(args.pages)])
    if args.timeout > 0:
        naver_cmd.extend(["--timeout", str(args.timeout)])

    naver_rc, naver_out, naver_err = _run(naver_cmd, env)
    index_path = _resolve_index_path_from_status()

    collector_rc = 1
    collector_out = ""
    collector_err = "index_path_missing"
    if naver_rc == 0 and index_path is not None:
        collector_cmd = [python_bin, str(COLLECTOR_SCRIPT), "--input-index", str(index_path)]
        collector_rc, collector_out, collector_err = _run(collector_cmd, env)

    naver_status = _load_json(NAVER_INDEX_STATUS_PATH, {})
    collector_status = _load_json(COLLECTOR_STATUS_PATH, {})
    status = "PASS" if naver_rc == 0 and collector_rc == 0 else "FAIL"

    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "input_index_path": str(index_path.relative_to(ROOT)) if index_path and ROOT in index_path.parents else (str(index_path) if index_path else ""),
        "archived_existing_selected_articles": {
            "requested": bool(args.archive_existing_selected),
            "archive_dir": str(archive_dir.relative_to(ROOT)) if archive_dir and ROOT in archive_dir.parents else (str(archive_dir) if archive_dir else ""),
            "archived_count": len(archived_paths),
            "archived_paths": archived_paths,
        },
        "naver_index": {
            "script": str(NAVER_INDEX_SCRIPT.relative_to(ROOT)),
            "returncode": naver_rc,
            "stdout_tail": naver_out[-1000:],
            "stderr_tail": naver_err[-1000:],
            "summary": naver_status,
        },
        "collector": {
            "script": str(COLLECTOR_SCRIPT.relative_to(ROOT)),
            "returncode": collector_rc,
            "stdout_tail": collector_out[-1000:],
            "stderr_tail": collector_err[-1000:],
            "summary": collector_status,
        },
    }

    NAVER_SELECTED_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    NAVER_SELECTED_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
