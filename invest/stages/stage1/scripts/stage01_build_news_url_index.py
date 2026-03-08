#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import gzip
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[4]
WORKSPACE_VENV_PY = ROOT / '.venv/bin/python3'

try:
    import feedparser
except ModuleNotFoundError:
    venv_py = str(WORKSPACE_VENV_PY)
    if os.path.exists(venv_py) and os.path.realpath(sys.executable) != os.path.realpath(venv_py):
        os.execv(venv_py, [venv_py] + sys.argv)
    raise

from pipeline_logger import append_pipeline_event
CONFIG_PATH = ROOT / "invest/stages/stage1/inputs/config/news_sources.json"
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/url_index"
RUNTIME_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_url_index_status.json"

DATE_RE = re.compile(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})")
UA = "Mozilla/5.0 (compatible; stage01-news-index/1.0; +https://openclaw.local)"
TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid", "guccounter", "cmpid",
}
GUARDIAN_API_URL = "https://content.guardianapis.com/search"
DEFAULT_GUARDIAN_QUERY_GROUPS = [
    "Fed OR FOMC OR inflation OR rates OR CPI OR PCE OR recession",
    "ECB OR central bank OR stimulus OR liquidity OR currency",
    "oil OR OPEC OR gas OR commodity OR copper OR steel",
    "semiconductor OR chip OR AI OR battery OR EV OR supply chain",
    "regulation OR tariff OR sanction OR antitrust OR IPO OR M&A OR SEC",
]
DEFAULT_GUARDIAN_SECTION = "business"


@dataclass
class FeedSeed:
    name: str
    feed_url: str
    host: str
    base_domain: str


def _safe_int(raw: Optional[str], default: int, min_v: int = 1) -> int:
    try:
        return max(min_v, int((raw or "").strip()))
    except Exception:
        return default


def _base_domain(host: str) -> str:
    h = (host or "").lower().strip(".")
    parts = [p for p in h.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return h


def _normalize_url(url: str) -> str:
    try:
        p = urlparse((url or "").strip())
    except Exception:
        return ""
    if p.scheme not in {"http", "https"} or not p.netloc:
        return ""

    clean_q = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        if k.lower() in TRACKING_QUERY_KEYS or k.lower().startswith("utm_"):
            continue
        clean_q.append((k, v))
    clean_q.sort(key=lambda x: (x[0], x[1]))
    query = urlencode(clean_q, doseq=True)

    path = p.path or "/"
    if path != "/":
        path = path.rstrip("/")

    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", query, ""))


def _parse_datetime(raw: str) -> Optional[datetime]:
    s = (raw or "").strip()
    if not s:
        return None

    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    for cand in (s, s.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(cand)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    m = DATE_RE.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except Exception:
            return None

    return None


def _to_iso(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _date_str(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.date().isoformat()


def _extract_dt_from_struct(struct_time: Any) -> Optional[datetime]:
    if not struct_time:
        return None
    try:
        return datetime(*struct_time[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _guardian_enabled(args: argparse.Namespace, config: dict[str, Any], target_dt: Optional[datetime]) -> bool:
    if getattr(args, "guardian_enable", False):
        return True
    if target_dt is None:
        return False
    return any(str(k).lower().startswith("guardian") for k in (config.get("feeds", {}) or {}).keys())


def _guardian_query_groups() -> list[str]:
    raw = os.environ.get("GUARDIAN_QUERY_GROUPS", "").strip()
    if not raw:
        return list(DEFAULT_GUARDIAN_QUERY_GROUPS)
    out = [part.strip() for part in raw.split("||") if part.strip()]
    return out or list(DEFAULT_GUARDIAN_QUERY_GROUPS)


def _month_start(dt: date) -> date:
    return date(dt.year, dt.month, 1)


def _month_end(dt: date) -> date:
    if dt.month == 12:
        return date(dt.year, 12, 31)
    return date(dt.year, dt.month + 1, 1) - timedelta(days=1)


def _next_month(dt: date) -> date:
    if dt.month == 12:
        return date(dt.year + 1, 1, 1)
    return date(dt.year, dt.month + 1, 1)


def _guardian_month_slices(target_dt: Optional[datetime], end_dt: Optional[datetime], max_months: int) -> list[tuple[str, str]]:
    start = _month_start((target_dt or datetime.now(timezone.utc)).date())
    finish = _month_end((end_dt or datetime.now(timezone.utc)).date())
    if finish < start:
        return []

    slices: list[tuple[str, str]] = []
    cursor = start
    while cursor <= finish:
        end_cursor = _month_end(cursor)
        if end_cursor > finish:
            end_cursor = finish
        slices.append((cursor.isoformat(), end_cursor.isoformat()))
        cursor = _next_month(cursor)
        if max_months > 0 and len(slices) >= max_months:
            break
    return slices


def _resolve_seeds(config: dict[str, Any]) -> list[FeedSeed]:
    feeds = config.get("feeds", {}) if isinstance(config, dict) else {}
    out: list[FeedSeed] = []
    for name, feed_url in feeds.items():
        p = urlparse(str(feed_url))
        host = (p.netloc or "").lower()
        if not host:
            continue
        out.append(FeedSeed(name=name, feed_url=str(feed_url), host=host, base_domain=_base_domain(host)))
    return out


def _robots_sitemaps(session: requests.Session, host: str, timeout: int) -> list[str]:
    url = f"https://{host}/robots.txt"
    try:
        r = session.get(url, timeout=timeout)
        if r.status_code >= 400:
            return []
    except Exception:
        return []

    found = []
    for line in r.text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k.strip().lower() == "sitemap":
            cand = _normalize_url(v.strip())
            if cand:
                found.append(cand)
    return found


def _guess_sitemaps_for_host(host: str) -> list[str]:
    paths = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/news-sitemap.xml",
        "/news_sitemap.xml",
        "/sitemap_news.xml",
        "/sitemap-news.xml",
        "/sitemaps/sitemap.xml",
        "/sitemaps/news.xml",
    ]
    return [f"https://{host}{p}" for p in paths]


def _safe_xml_root(content: bytes, url: str) -> Optional[ET.Element]:
    payload = content
    if url.endswith(".gz"):
        try:
            payload = gzip.decompress(content)
        except Exception:
            pass
    try:
        return ET.fromstring(payload)
    except Exception:
        return None


def _find_text(node: ET.Element, local_name: str) -> str:
    for child in node.iter():
        tag = child.tag.rsplit("}", 1)[-1] if isinstance(child.tag, str) else ""
        if tag == local_name:
            txt = (child.text or "").strip()
            if txt:
                return txt
    return ""


def _rss_page_url(base_url: str, page_no: int) -> str:
    if page_no <= 1:
        return base_url
    p = urlparse(base_url)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    q["paged"] = str(page_no)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment))


def _record_from_parts(url: str, published_raw: str, title: str, summary: str, source_domain: str, source_kind: str, source_name: str, source_url: str, extra: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    nurl = _normalize_url(url)
    if not nurl:
        return None
    dt = _parse_datetime(published_raw)
    parsed_host = (urlparse(nurl).netloc or "").lower().strip()
    canonical_domain = parsed_host or (source_domain or "").lower().strip()
    payload = {
        "url": nurl,
        "published_at": _to_iso(dt),
        "published_date": _date_str(dt),
        "title": (title or "").strip(),
        "summary": (summary or "").strip(),
        "source_domain": canonical_domain,
        "source_kind": source_kind,
        "source_name": source_name,
        "source_url": source_url,
    }
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value not in (None, ""):
                payload[key] = value
    return payload


def _merge_record(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if (not existing.get("published_at")) and incoming.get("published_at"):
        existing["published_at"] = incoming["published_at"]
        existing["published_date"] = incoming.get("published_date", "")
    if len(incoming.get("title", "")) > len(existing.get("title", "")):
        existing["title"] = incoming.get("title", "")
    if len(incoming.get("summary", "")) > len(existing.get("summary", "")):
        existing["summary"] = incoming.get("summary", "")

    for key in ("api_url", "section_name", "query_group", "query_slice"):
        if (not existing.get(key)) and incoming.get(key):
            existing[key] = incoming.get(key)

    seen = {(x.get("source_kind"), x.get("source_name"), x.get("source_url")) for x in existing.get("discovered_by", [])}
    key = (incoming.get("source_kind"), incoming.get("source_name"), incoming.get("source_url"))
    if key not in seen:
        existing.setdefault("discovered_by", []).append(
            {
                "source_kind": incoming.get("source_kind"),
                "source_name": incoming.get("source_name"),
                "source_url": incoming.get("source_url"),
            }
        )
    return existing


def _collect_from_rss(session: requests.Session, seed: FeedSeed, records: dict[str, dict[str, Any]], max_pages: int, timeout: int, sleep_sec: float, target_dt: Optional[datetime]) -> dict[str, Any]:
    total_raw = 0
    added = 0
    oldest: Optional[datetime] = None
    empty_pages = 0

    for page in range(1, max_pages + 1):
        feed_url = _rss_page_url(seed.feed_url, page)
        try:
            fp = feedparser.parse(feed_url)
        except Exception:
            break
        entries = getattr(fp, "entries", None) or []
        if not entries:
            empty_pages += 1
            if empty_pages >= 2:
                break
            continue

        new_on_page = 0
        for e in entries:
            total_raw += 1
            published_dt = _extract_dt_from_struct(e.get("published_parsed") or e.get("updated_parsed"))
            published_raw = _to_iso(published_dt) if published_dt else str(e.get("published") or e.get("updated") or "")
            rec = _record_from_parts(
                url=str(e.get("link") or ""),
                published_raw=published_raw,
                title=str(e.get("title") or ""),
                summary=str(e.get("summary") or ""),
                source_domain=seed.host,
                source_kind="rss",
                source_name=seed.name,
                source_url=feed_url,
            )
            if not rec:
                continue

            dt = _parse_datetime(rec.get("published_at") or rec.get("published_date") or "")
            if dt:
                oldest = dt if oldest is None else min(oldest, dt)

            key = rec["url"]
            if key in records:
                _merge_record(records[key], rec)
            else:
                rec["discovered_by"] = [{"source_kind": rec["source_kind"], "source_name": rec["source_name"], "source_url": rec["source_url"]}]
                records[key] = rec
                added += 1
                new_on_page += 1

        if new_on_page == 0:
            empty_pages += 1
            if empty_pages >= 2:
                break
        else:
            empty_pages = 0

        if target_dt and oldest and oldest <= target_dt:
            break
        time.sleep(sleep_sec)

    return {
        "source": seed.name,
        "kind": "rss",
        "raw_items": total_raw,
        "unique_added": added,
        "oldest": _date_str(oldest),
    }


def _collect_from_sitemaps(
    session: requests.Session,
    seed: FeedSeed,
    records: dict[str, dict[str, Any]],
    max_sitemaps: int,
    timeout: int,
    sleep_sec: float,
    target_dt: Optional[datetime],
) -> dict[str, Any]:
    queue: deque[str] = deque()
    visited: set[str] = set()

    for cand in _robots_sitemaps(session, seed.host, timeout):
        queue.append(cand)

    for host in {seed.host, seed.base_domain, f"www.{seed.base_domain}"}:
        for cand in _guess_sitemaps_for_host(host):
            queue.append(cand)

    total_urls_raw = 0
    added = 0
    checked = 0
    oldest: Optional[datetime] = None

    while queue and checked < max_sitemaps:
        sm_url = _normalize_url(queue.popleft())
        if not sm_url or sm_url in visited:
            continue
        visited.add(sm_url)
        checked += 1

        try:
            r = session.get(sm_url, timeout=timeout)
        except Exception:
            continue
        if r.status_code >= 400:
            continue

        root = _safe_xml_root(r.content, sm_url)
        if root is None:
            # some sources expose RSS in sitemap candidates
            try:
                fp = feedparser.parse(r.content)
                entries = getattr(fp, "entries", None) or []
            except Exception:
                entries = []
            if entries:
                for e in entries:
                    total_urls_raw += 1
                    published_dt = _extract_dt_from_struct(e.get("published_parsed") or e.get("updated_parsed"))
                    published_raw = _to_iso(published_dt) if published_dt else str(e.get("published") or e.get("updated") or "")
                    rec = _record_from_parts(
                        url=str(e.get("link") or ""),
                        published_raw=published_raw,
                        title=str(e.get("title") or ""),
                        summary=str(e.get("summary") or ""),
                        source_domain=seed.host,
                        source_kind="sitemap_rss",
                        source_name=seed.name,
                        source_url=sm_url,
                    )
                    if not rec:
                        continue
                    dt = _parse_datetime(rec.get("published_at") or rec.get("published_date") or "")
                    if dt:
                        oldest = dt if oldest is None else min(oldest, dt)
                    key = rec["url"]
                    if key in records:
                        _merge_record(records[key], rec)
                    else:
                        rec["discovered_by"] = [{"source_kind": rec["source_kind"], "source_name": rec["source_name"], "source_url": rec["source_url"]}]
                        records[key] = rec
                        added += 1
                time.sleep(sleep_sec)
            continue

        root_tag = root.tag.rsplit("}", 1)[-1].lower() if isinstance(root.tag, str) else ""

        if root_tag == "sitemapindex":
            for sm in root.findall(".//{*}sitemap"):
                loc = _find_text(sm, "loc")
                if not loc:
                    continue
                queue.append(loc)

        elif root_tag == "urlset":
            for url_node in root.findall(".//{*}url"):
                total_urls_raw += 1
                loc = _find_text(url_node, "loc")
                lastmod = _find_text(url_node, "lastmod")
                pub = _find_text(url_node, "publication_date") or _find_text(url_node, "pubDate") or lastmod
                title = _find_text(url_node, "title")

                rec = _record_from_parts(
                    url=loc,
                    published_raw=pub,
                    title=title,
                    summary="",
                    source_domain=seed.host,
                    source_kind="sitemap",
                    source_name=seed.name,
                    source_url=sm_url,
                )
                if not rec:
                    continue

                dt = _parse_datetime(rec.get("published_at") or rec.get("published_date") or "")
                if dt:
                    oldest = dt if oldest is None else min(oldest, dt)

                key = rec["url"]
                if key in records:
                    _merge_record(records[key], rec)
                else:
                    rec["discovered_by"] = [{"source_kind": rec["source_kind"], "source_name": rec["source_name"], "source_url": rec["source_url"]}]
                    records[key] = rec
                    added += 1

        elif root_tag in {"rss", "feed"}:
            try:
                fp = feedparser.parse(r.content)
                entries = getattr(fp, "entries", None) or []
            except Exception:
                entries = []
            for e in entries:
                total_urls_raw += 1
                published_dt = _extract_dt_from_struct(e.get("published_parsed") or e.get("updated_parsed"))
                published_raw = _to_iso(published_dt) if published_dt else str(e.get("published") or e.get("updated") or "")
                rec = _record_from_parts(
                    url=str(e.get("link") or ""),
                    published_raw=published_raw,
                    title=str(e.get("title") or ""),
                    summary=str(e.get("summary") or ""),
                    source_domain=seed.host,
                    source_kind="sitemap_feed",
                    source_name=seed.name,
                    source_url=sm_url,
                )
                if not rec:
                    continue
                dt = _parse_datetime(rec.get("published_at") or rec.get("published_date") or "")
                if dt:
                    oldest = dt if oldest is None else min(oldest, dt)
                key = rec["url"]
                if key in records:
                    _merge_record(records[key], rec)
                else:
                    rec["discovered_by"] = [{"source_kind": rec["source_kind"], "source_name": rec["source_name"], "source_url": rec["source_url"]}]
                    records[key] = rec
                    added += 1

        if target_dt and oldest and oldest <= target_dt:
            break

        time.sleep(sleep_sec)

    return {
        "source": seed.name,
        "kind": "sitemap",
        "sitemaps_checked": checked,
        "raw_items": total_urls_raw,
        "unique_added": added,
        "oldest": _date_str(oldest),
    }


def _collect_from_guardian_open_platform(
    session: requests.Session,
    records: dict[str, dict[str, Any]],
    target_dt: Optional[datetime],
    end_dt: Optional[datetime],
    max_months: int,
    max_pages_per_slice: int,
    page_size: int,
    timeout: int,
    sleep_sec: float,
) -> dict[str, Any]:
    slices = _guardian_month_slices(target_dt, end_dt, max_months)
    if not slices:
        return {
            "source": "guardian_open_platform",
            "kind": "guardian_open_platform",
            "query_groups": 0,
            "slices": 0,
            "raw_items": 0,
            "unique_added": 0,
            "oldest": "",
        }

    total_raw = 0
    added = 0
    oldest: Optional[datetime] = None
    queries = _guardian_query_groups()
    api_key = os.environ.get("GUARDIAN_API_KEY", "test").strip() or "test"

    for query in queries:
        for from_date, to_date in slices:
            for page in range(1, max_pages_per_slice + 1):
                params = {
                    "api-key": api_key,
                    "q": query,
                    "section": DEFAULT_GUARDIAN_SECTION,
                    "from-date": from_date,
                    "to-date": to_date,
                    "page-size": str(page_size),
                    "page": str(page),
                    "show-fields": "headline,trailText",
                    "order-by": "newest",
                }
                try:
                    r = session.get(GUARDIAN_API_URL, params=params, timeout=timeout)
                except Exception:
                    break
                if r.status_code >= 400:
                    break
                try:
                    payload = r.json()
                except Exception:
                    break
                response = payload.get("response", {}) if isinstance(payload, dict) else {}
                results = response.get("results", []) if isinstance(response, dict) else []
                if not isinstance(results, list) or not results:
                    break

                new_on_page = 0
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    total_raw += 1
                    rec = _record_from_parts(
                        url=str(item.get("webUrl") or ""),
                        published_raw=str(item.get("webPublicationDate") or ""),
                        title=str((item.get("fields") or {}).get("headline") or item.get("webTitle") or ""),
                        summary=str((item.get("fields") or {}).get("trailText") or ""),
                        source_domain="theguardian.com",
                        source_kind="guardian_open_platform",
                        source_name="guardian_open_platform",
                        source_url=r.url,
                        extra={
                            "api_url": str(item.get("apiUrl") or ""),
                            "section_name": str(item.get("sectionName") or ""),
                            "query_group": query,
                            "query_slice": f"{from_date}:{to_date}",
                        },
                    )
                    if not rec:
                        continue
                    dt = _parse_datetime(rec.get("published_at") or rec.get("published_date") or "")
                    if dt:
                        oldest = dt if oldest is None else min(oldest, dt)
                    key = rec["url"]
                    if key in records:
                        _merge_record(records[key], rec)
                    else:
                        rec["discovered_by"] = [{"source_kind": rec["source_kind"], "source_name": rec["source_name"], "source_url": rec["source_url"]}]
                        records[key] = rec
                        added += 1
                        new_on_page += 1

                if new_on_page == 0:
                    break
                time.sleep(sleep_sec)

    return {
        "source": "guardian_open_platform",
        "kind": "guardian_open_platform",
        "query_groups": len(queries),
        "slices": len(slices),
        "raw_items": total_raw,
        "unique_added": added,
        "oldest": _date_str(oldest),
        "target_date": _date_str(target_dt),
        "end_date": _date_str(end_dt),
    }


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"feeds": {}}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"feeds": {}}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _date_min_max(rows: list[dict[str, Any]]) -> tuple[str, str]:
    dates = [r.get("published_date", "") for r in rows if r.get("published_date")]
    if not dates:
        return "", ""
    return min(dates), max(dates)


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = _load_config()
    seeds = _resolve_seeds(config)
    target_dt = _parse_datetime(args.target_date) if args.target_date else None
    guardian_enabled = _guardian_enabled(args, config, target_dt)
    if not seeds and not guardian_enabled:
        summary = {
            "status": "FAIL",
            "reason": "no_feeds_or_guardian_backfill_sources",
            "url_count": 0,
            "index_file": "",
        }
        RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNTIME_STATUS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        append_pipeline_event(source="build_news_url_index", status="FAIL", count=0, errors=["no_feeds_or_guardian_backfill_sources"], note="feeds=0 guardian=0")
        return summary

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/xml,text/xml,text/html;q=0.9,application/json;q=0.9,*/*;q=0.8"})

    records: dict[str, dict[str, Any]] = {}
    per_source = []

    for seed in seeds:
        per_source.append(
            _collect_from_rss(
                session=session,
                seed=seed,
                records=records,
                max_pages=args.rss_max_pages,
                timeout=args.timeout,
                sleep_sec=args.sleep,
                target_dt=target_dt,
            )
        )
        per_source.append(
            _collect_from_sitemaps(
                session=session,
                seed=seed,
                records=records,
                max_sitemaps=args.max_sitemaps,
                timeout=args.timeout,
                sleep_sec=args.sleep,
                target_dt=target_dt,
            )
        )

    guardian_end_dt = _parse_datetime(args.guardian_end_date) if args.guardian_end_date else None
    if guardian_enabled:
        per_source.append(
            _collect_from_guardian_open_platform(
                session=session,
                records=records,
                target_dt=target_dt,
                end_dt=guardian_end_dt,
                max_months=args.guardian_max_months,
                max_pages_per_slice=args.guardian_max_pages_per_slice,
                page_size=args.guardian_page_size,
                timeout=args.timeout,
                sleep_sec=args.sleep,
            )
        )

    rows = sorted(records.values(), key=lambda x: (x.get("published_date", ""), x.get("url", "")), reverse=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = OUT_DIR / f"url_index_{ts}.jsonl"
    _write_jsonl(out_file, rows)

    dmin, dmax = _date_min_max(rows)
    errors = []
    status = "PASS"
    if len(rows) < args.min_urls:
        status = "FAIL"
        errors.append(f"url_count={len(rows)} < min_urls={args.min_urls}")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "worker_mode": "single_serial",
        "feeds": len(seeds),
        "guardian_enabled": guardian_enabled,
        "sources": per_source,
        "url_count": len(rows),
        "date_min": dmin,
        "date_max": dmax,
        "index_file": str(out_file.relative_to(ROOT)),
        "target_date": args.target_date or "",
        "errors": errors,
    }

    RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATUS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    append_pipeline_event(
        source="build_news_url_index",
        status=status,
        count=len(rows),
        errors=errors,
        note=f"feeds={len(seeds)} rss_max_pages={args.rss_max_pages} max_sitemaps={args.max_sitemaps}",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Stage1 news URL index builder (RSS archive + sitemap + Guardian Open Platform backfill)")
    ap.add_argument("--rss-max-pages", type=int, default=_safe_int(os.environ.get("NEWS_INDEX_RSS_MAX_PAGES"), 40, min_v=1))
    ap.add_argument("--max-sitemaps", type=int, default=_safe_int(os.environ.get("NEWS_INDEX_MAX_SITEMAPS"), 140, min_v=1))
    ap.add_argument("--timeout", type=int, default=_safe_int(os.environ.get("NEWS_INDEX_TIMEOUT_SEC"), 18, min_v=3))
    ap.add_argument("--sleep", type=float, default=float(os.environ.get("NEWS_INDEX_SLEEP_SEC", "0.12")))
    ap.add_argument("--min-urls", type=int, default=_safe_int(os.environ.get("NEWS_INDEX_MIN_URLS"), 1, min_v=0))
    ap.add_argument("--target-date", default=os.environ.get("NEWS_INDEX_TARGET_DATE", ""))
    ap.add_argument("--guardian-enable", action="store_true", default=os.environ.get("GUARDIAN_ENABLE", "0").strip().lower() in {"1", "true", "yes", "on"})
    ap.add_argument("--guardian-end-date", default=os.environ.get("GUARDIAN_END_DATE", ""))
    ap.add_argument("--guardian-max-months", type=int, default=_safe_int(os.environ.get("GUARDIAN_MAX_MONTHS"), 60, min_v=0))
    ap.add_argument("--guardian-max-pages-per-slice", type=int, default=_safe_int(os.environ.get("GUARDIAN_MAX_PAGES_PER_SLICE"), 1, min_v=1))
    ap.add_argument("--guardian-page-size", type=int, default=_safe_int(os.environ.get("GUARDIAN_PAGE_SIZE"), 50, min_v=1))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(args)
    return 0 if summary.get("status") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
