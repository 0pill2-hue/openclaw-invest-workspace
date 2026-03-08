#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from fnmatch import fnmatch

import requests
from bs4 import BeautifulSoup

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
URL_INDEX_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/url_index"
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles"
RUNTIME_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_selected_articles_status.json"
URL_INDEX_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_url_index_status.json"
NEWS_CONFIG_PATH = ROOT / "invest/stages/stage1/inputs/config/news_sources.json"
TEXT_FILTER_PATH = ROOT / "invest/stages/stage1/inputs/config/text_filter_keywords.json"

UA = "Mozilla/5.0 (compatible; stage01-news-select/1.0; +https://openclaw.local)"
DATE_RE = re.compile(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})")
PAYWALL_DOMAIN_PENALTIES = {
    "bloomberg.com": 18.0,
    "wsj.com": 16.0,
    "barrons.com": 14.0,
    "ft.com": 14.0,
    "theinformation.com": 20.0,
}
PAYWALL_DOMAIN_CANDIDATE_CAP = {
    "bloomberg.com": 2,
    "wsj.com": 2,
    "barrons.com": 1,
    "ft.com": 1,
    "theinformation.com": 1,
}


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


def _truthy(raw: Optional[str], default: bool = False) -> bool:
    text = (raw or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


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


def _resolve_index_path(path_override: str) -> Path:
    return (ROOT / path_override).resolve() if path_override and not Path(path_override).is_absolute() else Path(path_override)



def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows



def _preferred_url_index_path() -> Path:
    status = _load_json(URL_INDEX_STATUS_PATH, {})
    status_path = str(status.get("index_file") or "").strip() if isinstance(status, dict) else ""
    if status_path:
        p = _resolve_index_path(status_path)
        if p.exists():
            return p

    files = sorted(URL_INDEX_DIR.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        return URL_INDEX_DIR / "_missing_.jsonl"
    return files[0]



def _dedupe_url_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        prev = by_url.get(url)
        if prev is None:
            by_url[url] = row
            continue

        prev_dt = _row_published_dt(prev)
        curr_dt = _row_published_dt(row)
        prev_key = (
            1 if prev_dt else 0,
            prev_dt.isoformat() if prev_dt else "",
            len(str(prev.get("summary") or "")),
            len(str(prev.get("title") or "")),
        )
        curr_key = (
            1 if curr_dt else 0,
            curr_dt.isoformat() if curr_dt else "",
            len(str(row.get("summary") or "")),
            len(str(row.get("title") or "")),
        )
        if curr_key >= prev_key:
            by_url[url] = row

    merged = list(by_url.values())
    merged.sort(key=lambda x: (str(x.get("published_date") or ""), str(x.get("published_at") or ""), str(x.get("url") or "")), reverse=True)
    return merged


def _load_existing_selected_urls() -> set[str]:
    urls: set[str] = set()
    if not OUT_DIR.exists():
        return urls
    for path in sorted(OUT_DIR.glob('*.jsonl')):
        try:
            with path.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    url = str(row.get('url') or '').strip()
                    if url:
                        urls.add(url)
        except Exception:
            continue
    return urls



def _read_url_index_rows(path_override: str, merge_all: bool) -> tuple[list[Path], list[dict[str, Any]]]:
    if path_override:
        p = _resolve_index_path(path_override)
        return [p], _load_jsonl_rows(p)

    files = sorted(URL_INDEX_DIR.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        missing = _preferred_url_index_path()
        return [missing], []

    if not merge_all:
        p = _preferred_url_index_path()
        if not p.exists():
            return [p], []
        return [p], _load_jsonl_rows(p)

    rows: list[dict[str, Any]] = []
    for p in files:
        rows.extend(_load_jsonl_rows(p))
    return files, _dedupe_url_rows(rows)


def _parse_date(raw: str) -> Optional[datetime]:
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
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _row_published_dt(row: dict[str, Any]) -> Optional[datetime]:
    for key in ("published_dt", "published_at", "published_date", "published", "published_raw", "date", "created_at"):
        dt = _parse_date(str(row.get(key) or ""))
        if dt is not None:
            return dt
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


def _canonical_domain(raw: str) -> str:
    host = (raw or "").strip().lower()
    if not host:
        return ""
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host



def _domain_penalty(host: str) -> float:
    host = _canonical_domain(host)
    for domain, penalty in PAYWALL_DOMAIN_PENALTIES.items():
        if host == domain or host.endswith(f".{domain}"):
            return penalty
    return 0.0



def _domain_candidate_cap(host: str) -> int:
    host = _canonical_domain(host)
    for domain, cap in PAYWALL_DOMAIN_CANDIDATE_CAP.items():
        if host == domain or host.endswith(f".{domain}"):
            return cap
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
    published_dt = _row_published_dt(row)
    rscore = _recency_score(published_dt, now_dt)
    source_bonus = 2 if any((x.get("source_kind") in {"sitemap", "sitemap_feed", "sitemap_rss"}) for x in row.get("discovered_by", [])) else 0
    host = _canonical_domain(str(row.get("source_domain") or urlparse(str(row.get("url") or "")).netloc))
    domain_penalty = _domain_penalty(host)
    score = len(hits) * 10 + (rscore * recency_weight) + source_bonus - domain_penalty

    one = dict(row)
    one["source_domain"] = host or row.get("source_domain") or ""
    one["keyword_hits"] = len(hits)
    one["keywords_matched"] = hits[:20]
    one["priority_score"] = score
    one["domain_penalty"] = domain_penalty
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


def _limit_paywall_domain_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    limited_counts: dict[str, int] = {}
    for row in rows:
        host = _canonical_domain(str(row.get("source_domain") or urlparse(str(row.get("url") or "")).netloc))
        cap = _domain_candidate_cap(host)
        if cap <= 0:
            kept.append(row)
            continue
        used = limited_counts.get(host, 0)
        if used >= cap:
            continue
        limited_counts[host] = used + 1
        kept.append(row)
    return kept


def _parse_csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [part.strip().lower() for part in raw.split(',') if part.strip()]


def _should_exclude_candidate(row: dict[str, Any], excluded_domains: list[str], excluded_url_patterns: list[str]) -> bool:
    url = str(row.get("url") or "").strip()
    host = _canonical_domain(str(row.get("source_domain") or urlparse(url).netloc))
    if host and any(host == dom or host.endswith(f'.{dom}') for dom in excluded_domains):
        return True
    lower_url = url.lower()
    for pattern in excluded_url_patterns:
        if fnmatch(lower_url, pattern) or pattern in lower_url:
            return True
    return False



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


def _select_year_spread_candidates(rows: list[dict[str, Any]], target_dt: Optional[datetime], yearly_quota: int, max_candidates: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if target_dt is None or yearly_quota <= 0:
        selected = rows[:max_candidates] if max_candidates > 0 else list(rows)
        return selected, {}

    eligible = []
    overflow = []
    for row in rows:
        published_dt = _row_published_dt(row)
        if published_dt is not None and published_dt >= target_dt:
            eligible.append(row)
        else:
            overflow.append(row)

    by_year: dict[int, list[dict[str, Any]]] = {}
    for row in eligible:
        published_dt = _row_published_dt(row)
        if published_dt is None:
            overflow.append(row)
            continue
        by_year.setdefault(published_dt.year, []).append(row)

    picked: list[dict[str, Any]] = []
    picked_urls: set[str] = set()
    yearly_counts: dict[str, int] = {}

    for year in sorted(by_year):
        year_rows = sorted(by_year[year], key=lambda x: (float(x.get("priority_score", 0)), str(x.get("published_dt", ""))), reverse=True)
        take = year_rows[:yearly_quota]
        yearly_counts[str(year)] = len(take)
        for row in take:
            url = str(row.get("url") or "")
            if url in picked_urls:
                continue
            picked.append(row)
            picked_urls.add(url)

    for row in rows:
        if max_candidates > 0 and len(picked) >= max_candidates:
            break
        url = str(row.get("url") or "")
        if url in picked_urls:
            continue
        picked.append(row)
        picked_urls.add(url)

    if max_candidates > 0:
        picked = picked[:max_candidates]
    return picked, yearly_counts


def run(args: argparse.Namespace) -> dict[str, Any]:
    index_files, rows = _read_url_index_rows(args.input_index, args.merge_all_indexes)
    keywords = _load_keywords()
    existing_urls = _load_existing_selected_urls() if args.skip_existing else set()

    if existing_urls:
        rows = [row for row in rows if str(row.get('url') or '').strip() not in existing_urls]

    if not rows:
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "reason": "url_index_empty_or_missing",
            "index_file": str(index_files[0]) if index_files else "",
            "index_files": [str(p) for p in index_files],
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
    scored = _limit_paywall_domain_candidates(scored)

    excluded_domains = _parse_csv_env('NEWS_SELECTED_EXCLUDED_DOMAINS')
    excluded_url_patterns = _parse_csv_env('NEWS_SELECTED_EXCLUDED_URL_PATTERNS')
    if excluded_domains or excluded_url_patterns:
        scored = [row for row in scored if not _should_exclude_candidate(row, excluded_domains, excluded_url_patterns)]

    target_dt = _parse_date(args.target_date) if args.target_date else None
    attempt_limit = args.max_attempts if args.max_attempts > 0 else args.max_candidates
    scored, yearly_counts = _select_year_spread_candidates(
        scored,
        target_dt=target_dt,
        yearly_quota=args.yearly_quota,
        max_candidates=attempt_limit,
    )

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

    successes = []
    failures = []
    for idx, row in enumerate(scored, start=1):
        item = _collect_article(session, row, args.timeout)
        if item.get("ok"):
            successes.append(item)
            if args.max_candidates > 0 and len(successes) >= args.max_candidates:
                break
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
        "index_file": str(index_files[0].relative_to(ROOT)) if index_files and index_files[0].exists() else (str(index_files[0]) if index_files else ""),
        "index_files": [str(p.relative_to(ROOT)) if p.exists() and ROOT in p.parents else str(p) for p in index_files],
        "index_file_count": len(index_files),
        "merge_all_indexes": bool(args.merge_all_indexes and not args.input_index),
        "output_file": str(out_file.relative_to(ROOT)),
        "url_index_count": len(rows),
        "existing_url_count": len(existing_urls),
        "skip_existing": bool(args.skip_existing),
        "keyword_pool_size": len(keywords),
        "candidate_count": len(scored),
        "max_attempts": args.max_attempts,
        "selected_count": len(successes),
        "failed_count": len(failures),
        "date_min": dmin,
        "date_max": dmax,
        "min_keyword_hits": args.min_keyword_hits,
        "max_candidates": args.max_candidates,
        "recency_weight": args.recency_weight,
        "target_date": args.target_date,
        "yearly_quota": args.yearly_quota,
        "yearly_candidate_counts": yearly_counts,
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
    ap.add_argument("--input-index", default=os.environ.get("NEWS_SELECTED_INPUT_INDEX", ""), help="url index jsonl path (default: auto-discover)")
    ap.add_argument("--merge-all-indexes", action="store_true", default=os.environ.get("NEWS_SELECTED_MERGE_ALL_INDEXES", "1").strip().lower() in {"1", "true", "yes", "on"}, help="merge all url_index jsonl files in news folder before selection")
    ap.add_argument("--min-keyword-hits", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MIN_KEYWORD_HITS"), 1, min_v=0))
    ap.add_argument("--max-candidates", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MAX_ARTICLES"), 0, min_v=0))
    ap.add_argument("--max-attempts", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MAX_ATTEMPTS"), 0, min_v=0))
    ap.add_argument("--recency-weight", type=float, default=_safe_float(os.environ.get("NEWS_SELECTED_RECENCY_WEIGHT"), 0.0, min_v=0.0))
    ap.add_argument("--target-date", default=os.environ.get("NEWS_SELECTED_TARGET_DATE", ""))
    ap.add_argument("--yearly-quota", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_YEARLY_QUOTA"), 3, min_v=0))
    ap.add_argument("--min-selected", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_MIN_SELECTED"), 1, min_v=0))
    ap.add_argument("--timeout", type=int, default=_safe_int(os.environ.get("NEWS_SELECTED_TIMEOUT_SEC"), 18, min_v=3))
    ap.add_argument("--sleep", type=float, default=float(os.environ.get("NEWS_SELECTED_SLEEP_SEC", "0.15")))
    ap.add_argument("--skip-existing", action="store_true", default=_truthy(os.environ.get("NEWS_SELECTED_SKIP_EXISTING", "1"), default=True), help="skip URLs already collected in prior selected_articles jsonl outputs")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(args)
    return 0 if summary.get("status") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
