#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    import feedparser
except ModuleNotFoundError:
    ROOT = Path(__file__).resolve().parents[4]
    env_python = os.environ.get("INVEST_PYTHON_BIN", "").strip()
    candidate = Path(env_python) if env_python else ROOT / ".venv/bin/python3"
    if candidate.exists() and os.access(candidate, os.X_OK) and Path(sys.executable).resolve() != candidate.resolve():
        os.execv(str(candidate), [str(candidate)] + sys.argv)
    print("[error] feedparser is not installed. Install with: pip install feedparser", file=sys.stderr)
    raise

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/rss"
CONFIG_PATH = ROOT / "invest/stages/stage1/inputs/config/news_sources.json"
RE_YMD = re.compile(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})")


def _truthy(raw: str, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")


def _safe_int(name: str, default: int, min_v: int = 0) -> int:
    try:
        return max(min_v, int(os.environ.get(name, str(default)).strip()))
    except Exception:
        return default


def _parse_iso_or_ymd(raw: str, fallback: str) -> datetime:
    for cand in (str(raw or "").strip(), str(fallback or "").strip()):
        if not cand:
            continue
        try:
            dt = datetime.fromisoformat(cand)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
        try:
            dt = datetime.strptime(cand, "%Y%m%d")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime(2016, 1, 1, tzinfo=timezone.utc)


def _resolve_target_date() -> tuple[datetime, int]:
    raw_date = os.environ.get("RSS_BACKFILL_TARGET_DATE", "").strip()
    if raw_date:
        dt = _parse_iso_or_ymd(raw_date, fallback="2016-01-01")
        return dt, max(1, _safe_int("RSS_BACKFILL_TARGET_YEARS", 10, min_v=1))

    years = max(1, _safe_int("RSS_BACKFILL_TARGET_YEARS", 10, min_v=1))
    dt = datetime.now(timezone.utc) - timedelta(days=365 * years)
    return dt, years


def _paged_url(base_url: str, page_no: int) -> str:
    if page_no <= 1:
        return base_url
    parsed = urlparse(base_url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q["paged"] = str(page_no)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(q), parsed.fragment))


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"keywords": [], "feeds": {}}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _to_iso(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_datetime(raw: str) -> Optional[datetime]:
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


def fetch_feed(name: str, url: str) -> tuple[list[dict], dict]:
    enable_paged_backfill = _truthy(os.environ.get("RSS_ENABLE_PAGED_BACKFILL", "1"), default=True)
    max_pages = _safe_int("RSS_BACKFILL_MAX_PAGES", 120, min_v=1)
    max_empty_pages = _safe_int("RSS_BACKFILL_MAX_EMPTY_PAGES", 2, min_v=1)
    target_dt, target_years = _resolve_target_date()

    items: list[dict] = []
    seen_keys = set()
    page = 1
    no_new_pages = 0
    oldest_dt: Optional[datetime] = None

    while page <= max_pages:
        page_url = _paged_url(url, page)
        feed = feedparser.parse(page_url)
        entries = getattr(feed, "entries", None) or []
        if not entries:
            break

        new_on_page = 0
        for e in entries:
            published_raw = str(e.get("published") or e.get("updated") or "")
            published_iso, date_source = _normalize_published(e)
            key = (e.get("link") or "", e.get("title") or "", published_iso)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            if published_iso:
                dt = _parse_datetime(published_iso)
                if dt:
                    oldest_dt = dt if oldest_dt is None else min(oldest_dt, dt)

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
            new_on_page += 1

        if not enable_paged_backfill:
            break
        if new_on_page == 0:
            no_new_pages += 1
        else:
            no_new_pages = 0
        if no_new_pages >= max_empty_pages:
            break
        if oldest_dt is not None and oldest_dt <= target_dt:
            break

        page += 1
        time.sleep(0.25)

    meta = {
        "feed": name,
        "base_url": url,
        "pages_attempted": page,
        "items_total": len(items),
        "oldest_published": oldest_dt.date().isoformat() if oldest_dt else "",
        "target_date": target_dt.date().isoformat(),
        "target_years": target_years,
        "paged_backfill_enabled": enable_paged_backfill,
    }
    return items, meta


def filter_items(items: list[dict], keywords: list[str]) -> list[dict]:
    if _truthy(os.environ.get("RSS_DISABLE_KEYWORD_FILTER", "0"), default=False):
        return items
    if not keywords:
        return items
    filtered = []
    for it in items:
        text = f"{it.get('title', '')} {it.get('summary', '')}"
        if any(k.lower() in text.lower() for k in keywords):
            filtered.append(it)
    return filtered


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    out: dict = {}
    cfg = load_config()
    feeds = cfg.get("feeds", {})
    keywords = cfg.get("keywords", [])

    errors: list[str] = []
    total_items = 0
    feeds_with_items = 0
    per_feed_meta: list[dict] = []

    for name, url in feeds.items():
        try:
            items, meta = fetch_feed(name, url)
            filtered = filter_items(items, keywords)
            out[name] = filtered
            total_items += len(filtered)
            if filtered:
                feeds_with_items += 1
            meta["items_after_filter"] = len(filtered)
            per_feed_meta.append(meta)
            time.sleep(0.5)
        except Exception as exc:
            out[name] = {"error": str(exc)}
            errors.append(f"{name}: {exc}")

    out["_meta"] = {
        "timestamp": ts,
        "feeds": per_feed_meta,
        "keyword_filter_disabled": _truthy(os.environ.get("RSS_DISABLE_KEYWORD_FILTER", "0"), default=False),
    }

    out_name = f"rss_{ts}.json"
    (DATA_DIR / out_name).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    min_total_items = int(os.environ.get("RSS_MIN_TOTAL_ITEMS", "1"))
    min_feeds_with_items = int(os.environ.get("RSS_MIN_FEEDS_WITH_ITEMS", "1"))

    hard_fail_reasons: list[str] = []
    if total_items < max(0, min_total_items):
        hard_fail_reasons.append(f"total_items={total_items} < min_total_items={min_total_items}")
    if feeds_with_items < max(0, min_feeds_with_items):
        hard_fail_reasons.append(
            f"feeds_with_items={feeds_with_items} < min_feeds_with_items={min_feeds_with_items}"
        )

    status = "FAIL" if hard_fail_reasons else ("OK" if not errors else "WARN")
    pipeline_errors = errors + hard_fail_reasons
    append_pipeline_event(
        source="fetch_news_rss",
        status=status,
        count=total_items,
        errors=pipeline_errors,
        note=(
            f"feeds={len(feeds)} saved={len(out)-1} feeds_with_items={feeds_with_items} "
            f"min_total_items={min_total_items} paged_backfill={os.environ.get('RSS_ENABLE_PAGED_BACKFILL','1')} "
            f"target_years={os.environ.get('RSS_BACKFILL_TARGET_YEARS','10')}"
        ),
    )

    print(
        f"Saved {len(out)-1} feeds -> {DATA_DIR} "
        f"(status={status}, total_items={total_items}, feeds_with_items={feeds_with_items})"
    )
    if status == "FAIL":
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
