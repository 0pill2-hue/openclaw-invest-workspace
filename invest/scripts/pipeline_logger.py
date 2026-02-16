import json
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "pipeline_events.jsonl"


def append_pipeline_event(source: str, status: str, count=None, errors=None, note: str = ""):
    """Append lightweight structured pipeline event JSONL."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if errors is None:
        normalized_errors = []
    elif isinstance(errors, (list, tuple)):
        normalized_errors = [str(e) for e in errors]
    else:
        normalized_errors = str(errors)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "status": status,
        "count": count,
        "errors": normalized_errors,
        "note": note,
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
