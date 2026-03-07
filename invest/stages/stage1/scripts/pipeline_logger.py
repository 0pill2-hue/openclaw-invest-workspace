from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DIR = WORKSPACE_ROOT / "invest/stages/stage1/outputs/runtime"
EVENT_LOG_PATH = RUNTIME_DIR / "pipeline_events.jsonl"


def append_pipeline_event(source: str, status: str, count: int = 0, errors: Iterable[str] | None = None, note: str = "") -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "status": str(status),
        "count": int(count or 0),
        "errors": [str(x) for x in (errors or [])],
        "note": str(note or ""),
    }
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
