#!/usr/bin/env python3
"""
RSS 날짜 파싱 예외 자동 보정
- 기존 rss_*.json 파일의 item별 published 값을 정규화
- 파싱 실패 시 링크/제목/파일mtime fallback 적용
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGE1_DIR = ROOT / "invest/stages/stage1"
RSS_DIR = STAGE1_DIR / "outputs/raw/qualitative/market/rss"
RUNTIME_PATH = STAGE1_DIR / "outputs/runtime/rss_date_repair_status.json"

RE_YMD = re.compile(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})")


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _try_parse(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None

    # RFC2822 등
    try:
        dt = parsedate_to_datetime(s)
        if dt:
            return dt
    except Exception:
        pass

    # ISO 유사
    iso_candidates = [s, s.replace("Z", "+00:00")]
    for cand in iso_candidates:
        try:
            return datetime.fromisoformat(cand)
        except Exception:
            pass

    # yyyy-mm-dd / yyyymmdd
    m = RE_YMD.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except Exception:
            return None

    return None


def _parse_from_text_candidates(item: dict, file_dt: datetime) -> tuple[datetime, str]:
    raw = str(item.get("published_raw") or item.get("published") or item.get("updated") or "")
    dt = _try_parse(raw)
    if dt:
        return dt, "published_or_updated"

    for field in ("link", "title", "summary"):
        dt = _try_parse(str(item.get(field, "")))
        if dt:
            return dt, f"{field}_pattern"

    return file_dt, "file_mtime_fallback"


def _normalize_item(item: dict, file_dt: datetime) -> tuple[dict, bool, str]:
    if not isinstance(item, dict):
        return item, False, "invalid_item"

    dt, source = _parse_from_text_candidates(item, file_dt)
    iso = _to_iso(dt)
    date_only = iso[:10]

    changed = False
    out = dict(item)

    if out.get("published") != iso:
        out["published"] = iso
        changed = True

    raw_keep = str(item.get("published_raw") or item.get("published") or "")
    if out.get("published_raw") != raw_keep:
        out["published_raw"] = raw_keep
        changed = True

    if out.get("published_date") != date_only:
        out["published_date"] = date_only
        changed = True

    if out.get("published_year") != int(date_only[:4]):
        out["published_year"] = int(date_only[:4])
        changed = True

    if out.get("date_source") != source:
        out["date_source"] = source
        changed = True

    return out, changed, source


def main() -> int:
    RSS_DIR.mkdir(parents=True, exist_ok=True)
    rss_dir = RSS_DIR
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(rss_dir.glob("rss_*.json"))
    repaired_files = 0
    repaired_items = 0
    fallback_items = 0
    parse_sources: dict[str, int] = {}

    for fp in files:
        try:
            payload = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(payload, dict):
            continue

        file_dt = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
        file_changed = False

        for feed_name, feed_items in list(payload.items()):
            if not isinstance(feed_items, list):
                continue

            new_items = []
            for item in feed_items:
                out_item, changed, source = _normalize_item(item, file_dt)
                new_items.append(out_item)

                parse_sources[source] = parse_sources.get(source, 0) + 1
                if source == "file_mtime_fallback":
                    fallback_items += 1
                if changed:
                    repaired_items += 1
                    file_changed = True

            payload[feed_name] = new_items

        if file_changed:
            fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            repaired_files += 1

    status = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "rss_files_scanned": len(files),
        "rss_files_repaired": repaired_files,
        "items_repaired": repaired_items,
        "fallback_items": fallback_items,
        "parse_source_counts": parse_sources,
        "ok": True,
    }
    RUNTIME_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
