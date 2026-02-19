import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from pipeline_logger import append_pipeline_event

DATA_DIR = "invest/data/raw/market/news/rss"
CONFIG_PATH = "invest/config/news_sources.json"
RE_YMD = re.compile(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})")


def load_config():
    """
    Role: load_config 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-19
    """
    if not os.path.exists(CONFIG_PATH):
        return {"keywords": [], "feeds": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path):
    """
    Role: ensure_dir 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-19
    """
    os.makedirs(path, exist_ok=True)


def _to_iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_datetime(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None

    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            return dt
    except Exception:
        pass

    for cand in (s, s.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(cand)
        except Exception:
            pass

    m = RE_YMD.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except Exception:
            return None

    return None


def _normalize_published(entry: dict) -> tuple[str, str]:
    """return (published_iso, source)"""
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    if st:
        try:
            dt = datetime(*st[:6], tzinfo=timezone.utc)
            return _to_iso(dt), "feed_struct_time"
        except Exception:
            pass

    raw = str(entry.get("published") or entry.get("updated") or "")
    dt = _parse_datetime(raw)
    if dt:
        return _to_iso(dt), "published_or_updated"

    for field in ("link", "title", "summary"):
        dt = _parse_datetime(str(entry.get(field, "")))
        if dt:
            return _to_iso(dt), f"{field}_pattern"

    return "", "undated"


def fetch_feed(name, url):
    """
    Role: fetch_feed 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-19
    """
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries:
        published_raw = str(e.get("published") or e.get("updated") or "")
        published_iso, date_source = _normalize_published(e)
        items.append(
            {
                "title": e.get("title", ""),
                "link": e.get("link", ""),
                "published": published_iso,
                "published_raw": published_raw,
                "published_date": published_iso[:10] if published_iso else "",
                "published_year": int(published_iso[:4]) if published_iso else None,
                "date_source": date_source,
                "summary": e.get("summary", ""),
            }
        )
    return items


def filter_items(items, keywords):
    """
    Role: filter_items 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-19
    """
    if not keywords:
        return items
    filtered = []
    for it in items:
        text = f"{it.get('title','')} {it.get('summary','')}"
        if any(k.lower() in text.lower() for k in keywords):
            filtered.append(it)
    return filtered


def main():
    """
    Role: main 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-19
    """
    ensure_dir(DATA_DIR)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = {}
    cfg = load_config()
    feeds = cfg.get("feeds", {})
    keywords = cfg.get("keywords", [])
    errors = []
    total_items = 0

    for name, url in feeds.items():
        try:
            items = fetch_feed(name, url)
            filtered = filter_items(items, keywords)
            out[name] = filtered
            total_items += len(filtered)
            time.sleep(0.5)
        except Exception as e:
            out[name] = {"error": str(e)}
            errors.append(f"{name}: {e}")

    with open(os.path.join(DATA_DIR, f"rss_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    status = "OK" if not errors else "WARN"
    append_pipeline_event(
        source="fetch_news_rss",
        status=status,
        count=total_items,
        errors=errors,
        note=f"feeds={len(feeds)} saved={len(out)}",
    )
    print(f"Saved {len(out)} feeds -> {DATA_DIR}")


if __name__ == "__main__":
    main()
