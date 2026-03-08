#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
STAGE1_ROOT = WORKSPACE_ROOT / "invest/stages/stage1"
CHECKPOINT_PATH = STAGE1_ROOT / "outputs/runtime/stage01_images_ocr_rolling_checkpoint.json"
LATEST_STATS_PATH = STAGE1_ROOT / "outputs/runtime/stage01_images_ocr_rolling_latest.json"
OUT_PATH = STAGE1_ROOT / "outputs/runtime/stage01_ocr_postprocess_validate.json"
OCR_DIR = STAGE1_ROOT / "outputs/raw/qualitative/text/images_ocr"


def _safe_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _recent_items(processed: dict, recent_window_sec: int) -> list[dict]:
    now_ts = time.time()
    items: list[dict] = []
    for key, meta in processed.items():
        processed_at = meta.get("processed_at", "")
        try:
            dt = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
            age_sec = int(now_ts - dt.timestamp())
        except Exception:
            age_sec = None
        item = {
            "key": key,
            "status": meta.get("status", "unknown"),
            "reason": meta.get("reason", ""),
            "source": meta.get("source", ""),
            "output_txt": meta.get("output_txt", ""),
            "processed_at": processed_at,
            "age_sec": age_sec,
        }
        if age_sec is None or age_sec <= recent_window_sec:
            items.append(item)
    return sorted(items, key=lambda x: (x.get("processed_at", ""), x.get("key", "")), reverse=True)


def _txt_line_stats(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"exists": False, "char_count": 0, "line_count": 0}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "exists": True,
        "char_count": len(text.strip()),
        "line_count": len(lines),
    }


def main() -> int:
    checkpoint = _load_json(CHECKPOINT_PATH)
    latest_stats = _load_json(LATEST_STATS_PATH)
    processed = checkpoint.get("processed", {}) if isinstance(checkpoint, dict) else {}

    recent_window_sec = _safe_int_env("STAGE01_OCR_VALIDATE_RECENT_WINDOW_SEC", 72 * 3600)
    min_recent_success = _safe_int_env("STAGE01_OCR_VALIDATE_MIN_RECENT_SUCCESS", 1)
    max_recent_failure = _safe_int_env("STAGE01_OCR_VALIDATE_MAX_RECENT_FAILURE", 20)
    min_text_len = _safe_int_env("STAGE01_OCR_VALIDATE_MIN_TEXT_LEN", 5)
    max_txt_age_sec = _safe_int_env("STAGE01_OCR_VALIDATE_MAX_TXT_AGE_SEC", 14 * 24 * 3600)

    recent = _recent_items(processed, recent_window_sec)
    recent_success = [item for item in recent if item["status"] == "ok"]
    recent_failed = [item for item in recent if item["status"] != "ok"]

    txt_files = sorted([p for p in OCR_DIR.rglob("*.txt") if p.is_file()]) if OCR_DIR.exists() else []
    latest_txt_mtime = max((p.stat().st_mtime for p in txt_files), default=None)
    latest_txt_age_sec = int(time.time() - latest_txt_mtime) if latest_txt_mtime else None

    sample_outputs = []
    short_text_count = 0
    missing_output_count = 0
    for item in recent_success[:20]:
        out_rel = item.get("output_txt", "")
        out_path = WORKSPACE_ROOT / out_rel if out_rel else None
        stats = _txt_line_stats(out_path) if out_path else {"exists": False, "char_count": 0, "line_count": 0}
        if not stats["exists"]:
            missing_output_count += 1
        elif stats["char_count"] < min_text_len:
            short_text_count += 1
        sample_outputs.append({
            "source": item.get("source", ""),
            "output_txt": out_rel,
            **stats,
        })

    queued = int(latest_stats.get("queued", 0)) if isinstance(latest_stats, dict) else 0
    processed_now = int(latest_stats.get("processed_now", 0)) if isinstance(latest_stats, dict) else 0
    total_processed = int(checkpoint.get("total_processed", 0)) if isinstance(checkpoint, dict) else 0
    activity_required = (queued > 0) or (processed_now > 0) or (total_processed > 0)

    errors: list[str] = []
    if activity_required and len(recent_success) < min_recent_success:
        errors.append(f"recent_success={len(recent_success)} < min_recent_success={min_recent_success}")
    if len(recent_failed) > max_recent_failure:
        errors.append(f"recent_failed={len(recent_failed)} > max_recent_failure={max_recent_failure}")
    if missing_output_count > 0:
        errors.append(f"missing_output_count={missing_output_count} > 0")
    if short_text_count > 0:
        errors.append(f"short_text_count={short_text_count} > 0")
    if activity_required and latest_txt_age_sec is None:
        errors.append("latest_txt_age_sec=None")
    elif latest_txt_age_sec is not None and max_txt_age_sec >= 0 and latest_txt_age_sec > max_txt_age_sec:
        errors.append(f"latest_txt_age_sec={latest_txt_age_sec} > max_txt_age_sec={max_txt_age_sec}")

    payload = {
        "timestamp": datetime.now().isoformat(),
        "ok": len(errors) == 0,
        "message": "ocr postprocess validation ok" if not errors else f"ocr postprocess validation failed: {len(errors)} checks",
        "checkpoint_path": str(CHECKPOINT_PATH.relative_to(WORKSPACE_ROOT)),
        "ocr_dir": str(OCR_DIR.relative_to(WORKSPACE_ROOT)),
        "recent_window_sec": recent_window_sec,
        "activity_required": activity_required,
        "latest_stats_path": str(LATEST_STATS_PATH.relative_to(WORKSPACE_ROOT)),
        "queued": queued,
        "processed_now": processed_now,
        "recent_success_count": len(recent_success),
        "recent_failed_count": len(recent_failed),
        "total_processed": total_processed,
        "latest_txt_age_sec": latest_txt_age_sec,
        "txt_file_count": len(txt_files),
        "sample_outputs": sample_outputs,
        "recent_failures": recent_failed[:20],
        "errors": errors,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if errors:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
