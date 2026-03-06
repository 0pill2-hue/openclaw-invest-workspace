#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
URL_INDEX_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/url_index"
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles"
RUNTIME_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_selected_articles_status.json"
NEWS_CONFIG_PATH = ROOT / "invest/stages/stage1/inputs/config/news_sources.json"
TEXT_FILTER_PATH = ROOT / "invest/stages/stage1/inputs/config/text_filter_keywords.json"

UA = "Mozilla/5.0 (compatible; stage01-news-select/1.0; +https://openclaw.local)"
DATE_RE = re.compile(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})")


def _safe_int(raw: Optional[str], default: int, min_v: int = 0) -> int:
    try:
        return max(min_v, int((raw or "").strip()))
    except Exception:
        return default


def _safe_float(raw: Optional[str], default: float, min_v: float = 0.0) -> float:
    try:
        return max(min_v, float((raw or "").strip()))
    except Exception:
        return default


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_keywords() -> list[str]:
    kws = []

    news_cfg = _load_json(NEWS_CONFIG_PATH, {})
    if isinstance(news_cfg, dict):
        for k in news_cfg.get("keywords", []):
            if isinstance(k, str) and k.strip():
                kws.append(k.strip())

    tf_cfg = _load_json(TEXT_FILTER_PATH, {})
    include = tf_cfg.get("keywords", {}).get("include", []) if isinstance(tf_cfg, dict) else []
    for k in include:
        if isinstance(k, str) and k.strip():
            kws.append(k.strip())

    extra = os.environ.get("NEWS_SELECTED_EXTRA_KEYWORDS", "").strip()
    if extra:
        for x in extra.split(","):
            x = x.strip()
            if x:
                kws.append(x)

    uniq = []
    seen = set()
    for kw in kws:
        key = kw.casefold()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(kw)
    return uniq


def _read_latest_url_index(path_override: str) -> tuple[Path, list[dict[str, Any]]]:
    if path_override:
        p = (ROOT / path_override).resolve() if not Path(path_override).is_absolute() else Path(path_override)
        rows = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return p, rows

    files = sorted(URL_INDEX_DIR.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        return URL_INDEX_DIR / "_missing_.jsonl", []

    p = files[0]
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return p, rows


def _parse_date(raw: str) -> Optional[datetime]:
    s = (raw or "").strip()
    if not s:
        return None
    for cand in (s, s.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(cand)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    m = DATE_RE.search(s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _normalize_text(raw: str) -> str:
    lines = []
    for line in raw.replace("\xa0", " ").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    if not text:
        return []
    t = text.casefold()
    found = []
    for kw in keywords:
        if kw.casefold() in t:
            found.append(kw)
    return found


def _recency_score(published_dt: Optional[datetime], now_dt: datetime) -> int:
    if not published_dt:
        return 0
    days = max(0, int((now_dt - published_dt).total_seconds() // 86400))
    if days <= 2:
        return 5
    if days <= 7:
        return 4
    if days <= 30:
        return 3
    if days <= 90:
        return 2
    if days <= 365:
        return 1
    return 0


def _priority(row: dict[str, Any], keywords: list[str], now_dt: datetime, recency_weight: float) -> dict[str, Any]:
    text = " ".join(
        [
            str(row.get("title") or ""),
            str(row.get("summary") or ""),
            str(row.get("url") or ""),
        ]
    )
    hits = _match_keywords(text, keywords)
    published_dt = _parse_date(str(row.get("published_at") or row.get("published_date") or ""))
    rscore = _recency_score(published_dt, now_dt)
    source_bonus = 2 if any((x.get("source_kind") in {"sitemap", "sitemap_feed", "sitemap_rss"}) for x in row.get("discovered_by", [])) else 0
    score = len(hits) * 10 + (rscore * recency_weight) + source_bonus

    one = dict(row)
    one["keyword_hits"] = len(hits)
    one["keywords_matched"] = hits[:20]
    one["priority_score"] = score
    one["published_dt"] = published_dt.isoformat() if published_dt else ""
    return one


def _extract_title(soup: BeautifulSoup) -> str:
    selectors = [
        "meta[property='og:title']",
        "meta[name='twitter:title']",
        "h1",
        "title",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if not node:
            continue
        if node.name == "meta":
            v = (node.get("content") or "").strip()
        else:
            v = node.get_text(" ", strip=True)
        if v:
            return v
    return ""


def _extract_published(soup: BeautifulSoup, html: str) -> str:
    selectors = [
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "meta[property='og:article:published_time']",
        "meta[name='pubdate']",
        "time",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if not node:
            continue
        if node.name == "meta":
            cand = (node.get("content") or "").strip()
        else:
            cand = node.get_text(" ", strip=True)
        if cand:
            return cand

    m = DATE_RE.search(html)
    return m.group(0) if m else ""


def _extract_body(soup: BeautifulSoup) -> tuple[str, str]:
    selectors = [
        "article",
        "[itemprop='articleBody']",
        ".article-body",
        ".story-body",
        ".article-content",
        ".entry-content",
        ".post-content",
        ".news_body",
        "main",
    ]

    for sel in selectors:
        node = soup.select_one(sel)
        if not node:
            continue
        for bad in node.select("script,style,noscript,aside,header,footer,nav,.ad,.ads,.advertisement"):
            bad.decompose()
        text = _normalize_text(node.get_text("\n"))
        if len(text) >= 280:
            return text, sel

    paras = []
    for p in soup.select("p"):
        t = p.get_text(" ", strip=True)
        t = re.sub(r"\s+", " ", t)
        if len(t) < 30:
            continue
        paras.append(t)
    fallback = _normalize_text("\n".join(paras[:120]))
    if len(fallback) >= 280:
        return fallback, "p_fallback"

    return "", ""


def _collect_article(session: requests.Session, row: dict[str, Any], timeout: int) -> dict[str, Any]:
    url = str(row.get("url") or "")
    now = datetime.now(timezone.utc).isoformat()

    try:
        resp = session.get(url, timeout=timeout)
    except Exception as e:
        return {"ok": False, "reason": f"request_error:{type(e).__name__}", "url": url, "collected_at": now}

    if resp.status_code >= 400:
        return {"ok": False, "reason": f"http_{resp.status_code}", "url": url, "collected_at": now, "http_status": resp.status_code}

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup) or str(row.get("title") or "")
    published_raw = _extract_published(soup, html)
    published_dt = _parse_date(published_raw) or _parse_date(str(row.get("published_at") or row.get("published_date") or ""))
    body, extractor = _extract_body(soup)

    if len(body) < 280:
        return {
            "ok": False,
            "reason": "short_or_empty_body",
            "url": url,
            "title": title,
            "http_status": resp.status_code,
            "collected_at": now,
        }

    host = urlparse(url).netloc.lower()

    return {
        "ok": True,
        "url": url,
        "source_domain": row.get("source_domain") or host,
        "title": title,
        "published_at": published_dt.isoformat() if published_dt else "",
        "published_date": published_dt.date().isoformat() if published_dt else "",
        "summary": row.get("summary", ""),
        "body": body,
        "body_chars": len(body),
        "priority_score": row.get("priority_score", 0),
        "keyword_hits": row.get("keyword_hits", 0),
        "keywords_matched": row.get("keywords_matched", []),
        "http_status": resp.status_code,
        "extractor": extractor,
        "collected_at": now,
        "worker_mode": "single_serial",
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _date_min_max(rows: list[dict[str, Any]]) -> tuple[str, str]:
    dates = [str(r.get("published_date") or "") for r in rows if r.get("published_date")]
    if not dates:
        return "", ""
    return min(dates), max(dates)


def run(args: argparse.Namespace) -> dict[str, Any]:
    index_file, rows = _read_latest_url_index(args.input_index)
    keywords = _load_keywords()

    if not rows:
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "reason": "url_index_empty_or_missing",
            "index_file": str(index_file),
            "selected_count": 0,
        }
        RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNTIME_STATUS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        append_pipeline_event("collect_selected_news_articles", "FAIL", count=0, errors=[summary["reason"]], note="")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary

    now_dt = datetime.now(timezone.utc)
    scored = [_priority(r, keywords, now_dt, args.recency_weight) for r in rows]

    scored = [s for s in scored if s.get("keyword_hits", 0) >= args.min_keyword_hits]
    scored.sort(key=lambda x: (float(x.get("priority_score", 0)), str(x.get("published_dt", ""))), reverse=True)

    if args.max_candidates > 0:
        scored = scored[: args.max_candidates]

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

    successes = []
    failures = []
    for idx, row in enumerate(scored, start=1):
        item = _collect_article(session, row, args.timeout)
        if item.get("ok"):
            successes.append(item)
        else:
            failures.append(
                {
                    "url": row.get("url"),
                    "reason": item.get("reason"),
                    "priority_score": row.get("priority_score", 0),
                    "keyword_hits": row.get("keyword_hits", 0),
                }
            )
        if args.sleep > 0 and idx < len(scored):
            import time
            time.sleep(args.sleep)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = OUT_DIR / f"selected_articles_{ts}.jsonl"
    _write_jsonl(out_file, successes)

    dmin, dmax = _date_min_max(successes)
    status = "PASS"
    errors = []
    if len(successes) < args.min_selected:
        status = "FAIL"
        errors.append(f"selected_count={len(successes)} < min_selected={args.min_selected}")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "worker_mode": "single_serial",
        "index_file": str(index_file.relative_to(ROOT)) if index_file.exists() else str(index_file),
        "output_file": str(out_file.relative_to(ROOT)),
        "url_index_count": len(rows),
        "keyword_pool_size": len(keywords),
        "candidate_count": len(scored),
        "selected_count": len(successes),
        "failed_count": len(failures),
        "date_min": dmin,
        "date_max": dmax,
        "min_keyword_hits": args.min_keyword_hits,
        "max_candidates": args.max_candidates,
        "recency_weight": args.recency_weight,
        "errors": errors,
        "failure_samples": failures[:30],
    }

    RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATUS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    append_pipeline_event(
        source="collect_selected_news_articles",
        status=status,
        count=len(successes),
        errors=errors,
        note=f"index={len(rows)} candidates={len(scored)} failed={len(failures)}",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Stage1 selected news body collector")
    ap.add_argument("--input-index", default=os.environ.get("NEWS_SELECTED_INPUT_INDEX", ""), help="url index jsonl path (default: latest)")
    ap.add_argument("--min-keyword-hits", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MIN_KEYWORD_HITS"), 1, min_v=0))
    ap.add_argument("--max-candidates", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MAX_ARTICLES"), 0, min_v=0))
    ap.add_argument("--recency-weight", type=float, default=_safe_float(os.environ.get("NEWS_SELECTED_RECENCY_WEIGHT"), 0.0, min_v=0.0))
    ap.add_argument("--min-selected", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MIN_SELECTED"), 1, min_v=0))
    ap.add_argument("--timeout", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_TIMEOUT_SEC"), 18, min_v=3))
    ap.add_argument("--sleep", type=float, default=float(os.environ.get("NEWS_SELECTED_SLEEP_SEC", "0.15")))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(args)
    return 0 if summary.get("status") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
