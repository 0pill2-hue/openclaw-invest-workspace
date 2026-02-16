import json
import os
import time
from datetime import datetime, timezone

import feedparser

from pipeline_logger import append_pipeline_event

DATA_DIR = "invest/data/news/rss"
CONFIG_PATH = "invest/config/news_sources.json"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"keywords": [], "feeds": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def fetch_feed(name, url):
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries:
        published = e.get("published") or e.get("updated") or ""
        items.append({
            "title": e.get("title", ""),
            "link": e.get("link", ""),
            "published": published,
            "summary": e.get("summary", "")
        })
    return items


def filter_items(items, keywords):
    if not keywords:
        return items
    filtered = []
    for it in items:
        text = f"{it.get('title','')} {it.get('summary','')}"
        if any(k.lower() in text.lower() for k in keywords):
            filtered.append(it)
    return filtered


def main():
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
