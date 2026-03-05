#!/usr/bin/env python3
import argparse
import json
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
BUDDIES_PATH = ROOT / "invest/stages/stage1/outputs/master/naver_buddies_full.json"
OUT_BASE = ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/blog"
BACKOFF_STATE = ROOT / "invest/stages/stage1/outputs/runtime/blog_scrape_backoff.json"
BUDDY_CURSOR_PATH = ROOT / "invest/stages/stage1/outputs/runtime/blog_buddy_cursor.json"
BLOG_LAST_RUN_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/blog_last_run_status.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"

POST_LINK_RE = re.compile(r"https?://blog\.naver\.com/PostView\.naver\?[^\"'\s<]+")
LOGNO_RE = re.compile(r"logNo=(\d+)")


def _resolve_target_date(raw_target_date: Optional[str], target_years: int) -> str:
    if raw_target_date and str(raw_target_date).strip():
        return str(raw_target_date).strip()
    years = max(1, int(target_years))
    return (datetime.now(timezone.utc) - timedelta(days=365 * years)).date().isoformat()


def _parse_target_date(raw_target_date: str) -> datetime.date:
    try:
        return datetime.fromisoformat(str(raw_target_date).strip()).date()
    except Exception:
        return datetime(2016, 1, 1).date()


def _safe_int(name: str, default: int, min_v: int = 0) -> int:
    try:
        return max(min_v, int(str(os.environ.get(name, str(default))).strip()))
    except Exception:
        return default


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_backoff_until() -> Optional[datetime]:
    if not BACKOFF_STATE.exists():
        return None
    try:
        data = json.loads(BACKOFF_STATE.read_text(encoding="utf-8"))
        raw = str(data.get("next_allowed_at", "")).strip()
        if not raw:
            return None
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _save_backoff_until(dt: Optional[datetime], reason: str = "") -> None:
    BACKOFF_STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_now().isoformat(),
        "next_allowed_at": dt.isoformat() if dt is not None else "",
        "reason": reason,
    }
    BACKOFF_STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sleep_with_jitter(base_sec: float) -> None:
    min_env = os.environ.get("BLOG_FETCH_SLEEP_MIN_SEC", "").strip()
    max_env = os.environ.get("BLOG_FETCH_SLEEP_MAX_SEC", "").strip()
    if min_env and max_env:
        try:
            lo = max(0.0, float(min_env))
            hi = max(lo, float(max_env))
            time.sleep(random.uniform(lo, hi))
            return
        except Exception:
            pass
    base = max(0.0, float(base_sec))
    if base <= 0:
        return
    lo = max(0.0, base * 0.7)
    hi = max(lo, base * 1.3)
    time.sleep(random.uniform(lo, hi))


def _http_get(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _http_get_with_retry(url: str, timeout: int = 20, retries: int = 2, retry_sleep: float = 0.8) -> str:
    last_err = None
    max_retries = max(0, int(retries))
    for attempt in range(max_retries + 1):
        try:
            return _http_get(url, timeout=timeout)
        except Exception as e:
            last_err = e
            if attempt >= max_retries:
                break
            _sleep_with_jitter(max(0.0, float(retry_sleep)) * (attempt + 1))
    if last_err is not None:
        raise last_err
    raise RuntimeError("http_get_with_retry_failed")


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _extract_post_links(html: str) -> list[str]:
    links = set(POST_LINK_RE.findall(html))
    for m in re.finditer(r"logNo=(\d+)", html):
        log_no = m.group(1)
        if log_no:
            links.add(f"https://blog.naver.com/PostView.naver?logNo={log_no}")
    return sorted(links)


def _extract_title(html: str) -> str:
    for pat in [
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r"<title>(.*?)</title>",
    ]:
        m = re.search(pat, html, flags=re.I | re.S)
        if m:
            return _strip_html(m.group(1))[:200]
    return ""


def _extract_body(html: str) -> str:
    candidates = [
        r'(?is)<div[^>]+class="[^"]*se-main-container[^"]*"[^>]*>(.*?)</div>',
        r'(?is)<div[^>]+id="postViewArea"[^>]*>(.*?)</div>',
        r'(?is)<div[^>]+class="[^"]*post_ct[^"]*"[^>]*>(.*?)</div>',
    ]
    for pat in candidates:
        m = re.search(pat, html)
        if m:
            body = _strip_html(m.group(1))
            if len(body) >= 80:
                return body
    return _strip_html(html)


def _normalize_date(raw: str) -> str:
    m = re.search(r"(20\d{2})[./-]\s*([01]?\d)[./-]\s*([0-3]?\d)", raw)
    if not m:
        return ""
    y = int(m.group(1)); mo = int(m.group(2)); d = int(m.group(3))
    if mo < 1 or mo > 12 or d < 1 or d > 31:
        return ""
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _extract_post_date(html: str) -> str:
    pats = [
        r'<meta\s+property="article:published_time"\s+content="([^"]+)"',
        r'<meta\s+property="og:article:published_time"\s+content="([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'<span[^>]+class="[^"]*se_publishDate[^"]*"[^>]*>(.*?)</span>',
        r'<p[^>]+class="[^"]*date[^"]*"[^>]*>(.*?)</p>',
    ]
    for pat in pats:
        m = re.search(pat, html, flags=re.I | re.S)
        if m:
            d = _normalize_date(_strip_html(m.group(1)))
            if d:
                return d

    # fallback: first plausible YYYY-MM-DD style found in page
    d = _normalize_date(html)
    return d


def _logno_from_url(url: str) -> str:
    q = parse_qs(urlparse(url).query)
    if "logNo" in q and q["logNo"]:
        return q["logNo"][0]
    m = LOGNO_RE.search(url)
    return m.group(1) if m else ""


def _iter_buddies(limit: int) -> list[dict]:
    if limit <= 0:
        return []
    if not BUDDIES_PATH.exists():
        return []
    try:
        data = json.loads(BUDDIES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    total = len(data)
    if total == 0:
        return []

    start_index = 0
    if BUDDY_CURSOR_PATH.exists():
        try:
            cursor = json.loads(BUDDY_CURSOR_PATH.read_text(encoding="utf-8"))
            if isinstance(cursor, dict):
                start_index = int(cursor.get("next_index", 0))
        except Exception:
            start_index = 0

    start_index = start_index % total
    pick_count = min(limit, total)
    picked = [data[(start_index + i) % total] for i in range(pick_count)]
    next_index = (start_index + pick_count) % total

    try:
        BUDDY_CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _utc_now().isoformat(),
            "total_buddies": total,
            "limit": int(limit),
            "start_index": start_index,
            "next_index": next_index,
        }
        BUDDY_CURSOR_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return picked


def _classify_buddy_error(raw: str) -> str:
    s = (raw or "").lower()
    if "429" in s:
        return "rate-limit"
    if "404" in s:
        return "404"
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "403" in s:
        return "access-denied"
    if "empty-posts" in s:
        return "empty-posts"
    if "parse-fail" in s or "short_body" in s:
        return "parse-fail"
    return "fetch-fail"


def run(
    limit_buddies: int,
    max_posts_per_buddy: int,
    max_pages_per_buddy: int,
    sleep_sec: float,
    target_date: str,
    backoff_hours: int,
    force_run: bool,
) -> dict:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    buddies = _iter_buddies(limit_buddies)
    target_dt = _parse_target_date(target_date)

    now = _utc_now()
    until = _load_backoff_until()
    if (not force_run) and until is not None and now < until:
        remain = int((until - now).total_seconds())
        msg = f"backoff_active_until={until.isoformat()} remain_sec={remain}"
        append_pipeline_event(
            source="scrape_all_posts_v2",
            status="WARN",
            count=0,
            errors=["backoff_active"],
            note=msg,
        )
        return {
            "status": "SKIP_BACKOFF",
            "buddies_target": len(buddies),
            "buddies_done": 0,
            "posts_saved": 0,
            "max_posts_per_buddy": max_posts_per_buddy,
            "max_pages_per_buddy": max_pages_per_buddy,
            "target_date": target_dt.isoformat(),
            "errors": ["backoff_active"],
            "next_allowed_at": until.isoformat(),
            "remain_sec": remain,
        }

    errors: list[str] = []
    post_saved = 0
    buddy_done = 0
    buddy_results: list[dict] = []

    for item in buddies:
        bid = str(item.get("id", "")).strip()
        if not bid:
            continue
        blog_url = str(item.get("url", "") or f"https://blog.naver.com/{bid}").strip()
        if not blog_url:
            continue

        buddy_dir = OUT_BASE / bid
        saved_for_buddy = 0
        short_body_count = 0
        picked: list[tuple[str, str]] = []
        page_error = ""

        try:
            seen_logno = set()
            for page in range(1, max(1, max_pages_per_buddy) + 1):
                post_list_url = (
                    f"https://blog.naver.com/PostList.naver?blogId={bid}&from=postList&currentPage={page}"
                )
                try:
                    html = _http_get_with_retry(post_list_url)
                except Exception as e:
                    page_error = str(e)
                    errors.append(f"{bid}:page_fetch:{e}")
                    break

                links = _extract_post_links(html)
                if not links:
                    m = re.search(r'(?is)<iframe[^>]+id="mainFrame"[^>]+src="([^"]+)"', html)
                    if m:
                        try:
                            iframe_html = _http_get_with_retry(urljoin("https://blog.naver.com/", m.group(1)))
                            links = _extract_post_links(iframe_html)
                        except Exception as e:
                            page_error = str(e)
                            errors.append(f"{bid}:iframe_fetch:{e}")
                            break

                page_added = 0
                for u in links:
                    log_no = _logno_from_url(u)
                    if not log_no or log_no in seen_logno:
                        continue
                    seen_logno.add(log_no)
                    picked.append((log_no, u))
                    page_added += 1
                    if len(picked) >= max_posts_per_buddy:
                        break

                if len(picked) >= max_posts_per_buddy:
                    break
                if page_added == 0:
                    break

            reached_target_for_buddy = False
            if picked:
                for log_no, post_url in picked:
                    buddy_dir.mkdir(parents=True, exist_ok=True)
                    out_path = buddy_dir / f"{log_no}.md"
                    if out_path.exists() and out_path.stat().st_size > 120:
                        prev = out_path.read_text(encoding="utf-8", errors="ignore")
                        if "PublishedDate:" in prev:
                            m_prev = re.search(r"(?m)^PublishedDate:\s*(\d{4}-\d{2}-\d{2})", prev)
                            if m_prev:
                                try:
                                    if datetime.fromisoformat(m_prev.group(1)).date() <= target_dt:
                                        reached_target_for_buddy = True
                                        break
                                except Exception:
                                    pass
                            continue

                    mobile_url = f"https://m.blog.naver.com/PostView.naver?blogId={bid}&logNo={log_no}"
                    try:
                        post_html = _http_get_with_retry(mobile_url)
                    except Exception as e:
                        errors.append(f"{bid}:post_fetch:{log_no}:{e}")
                        continue

                    title = _extract_title(post_html) or f"{bid}/{log_no}"
                    body = _extract_body(post_html)
                    post_date = _extract_post_date(post_html)

                    if len(body.strip()) < 40:
                        short_body_count += 1
                        errors.append(f"short_body:{bid}:{log_no}")
                        continue

                    now = datetime.now().isoformat(timespec="seconds")
                    date_line = f"PublishedDate: {post_date}" if post_date else "PublishedDate: 미확인"
                    out_path.write_text(
                        (
                            f"# {title}\n\n"
                            f"Date: {now}\n"
                            f"{date_line}\n"
                            f"Source: {mobile_url}\n\n"
                            f"{body}\n"
                        ),
                        encoding="utf-8",
                    )
                    post_saved += 1
                    saved_for_buddy += 1

                    if post_date:
                        try:
                            if datetime.fromisoformat(post_date).date() <= target_dt:
                                reached_target_for_buddy = True
                                break
                        except Exception:
                            pass

                    _sleep_with_jitter(sleep_sec)

            if saved_for_buddy > 0 or reached_target_for_buddy:
                status_for_buddy = "covered"
                cause_for_buddy = ""
            elif page_error:
                status_for_buddy = "uncovered"
                cause_for_buddy = _classify_buddy_error(page_error)
            elif not picked:
                status_for_buddy = "uncovered"
                cause_for_buddy = "empty-posts"
            elif short_body_count > 0:
                status_for_buddy = "uncovered"
                cause_for_buddy = "parse-fail"
            else:
                status_for_buddy = "uncovered"
                cause_for_buddy = "미확인"

            buddy_results.append(
                {
                    "id": bid,
                    "url": blog_url,
                    "status": status_for_buddy,
                    "cause": cause_for_buddy,
                    "picked_count": len(picked),
                    "saved_count": saved_for_buddy,
                    "short_body_count": short_body_count,
                }
            )
            buddy_done += 1
            _sleep_with_jitter(sleep_sec)
        except Exception as e:
            errors.append(f"{bid}:{e}")
            buddy_results.append(
                {
                    "id": bid,
                    "url": blog_url,
                    "status": "uncovered",
                    "cause": _classify_buddy_error(str(e)),
                    "picked_count": len(picked),
                    "saved_count": saved_for_buddy,
                    "short_body_count": short_body_count,
                    "error": str(e),
                }
            )
            buddy_done += 1

    had_429 = any("429" in e for e in errors)
    next_allowed_at = None
    if had_429:
        next_allowed_at = _utc_now() + timedelta(hours=max(1, int(backoff_hours)))
        _save_backoff_until(next_allowed_at, reason="http_429")
    else:
        _save_backoff_until(None, reason="clear")

    uncovered_causes: dict[str, int] = {}
    for one in buddy_results:
        if one.get("status") != "covered":
            cause = str(one.get("cause") or "미확인")
            uncovered_causes[cause] = int(uncovered_causes.get(cause, 0)) + 1

    run_payload = {
        "generated_at": _utc_now().isoformat(),
        "buddies_target": len(buddies),
        "buddies_done": buddy_done,
        "posts_saved": post_saved,
        "max_posts_per_buddy": max_posts_per_buddy,
        "max_pages_per_buddy": max_pages_per_buddy,
        "target_date": target_dt.isoformat(),
        "backoff_hours": backoff_hours,
        "next_allowed_at": next_allowed_at.isoformat() if next_allowed_at else "",
        "uncovered_causes": uncovered_causes,
        "buddy_results": buddy_results,
        "errors": errors[:2000],
    }
    try:
        BLOG_LAST_RUN_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        BLOG_LAST_RUN_STATUS_PATH.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    status = "OK" if not errors else "WARN"
    append_pipeline_event(
        source="scrape_all_posts_v2",
        status=status,
        count=post_saved,
        errors=errors[:20],
        note=(
            f"buddies={len(buddies)} done={buddy_done} posts={post_saved} "
            f"max_posts_per_buddy={max_posts_per_buddy} max_pages_per_buddy={max_pages_per_buddy} "
            f"target_date={target_dt.isoformat()} backoff_hours={backoff_hours} "
            f"next_allowed_at={(next_allowed_at.isoformat() if next_allowed_at else '')} "
            f"uncovered={sum(uncovered_causes.values())}"
        ),
    )

    return {
        "status": status,
        "buddies_target": len(buddies),
        "buddies_done": buddy_done,
        "posts_saved": post_saved,
        "max_posts_per_buddy": max_posts_per_buddy,
        "max_pages_per_buddy": max_pages_per_buddy,
        "target_date": target_dt.isoformat(),
        "backoff_hours": backoff_hours,
        "next_allowed_at": next_allowed_at.isoformat() if next_allowed_at else "",
        "uncovered_causes": uncovered_causes,
        "status_file": str(BLOG_LAST_RUN_STATUS_PATH.relative_to(ROOT)),
        "errors": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage1 blog collector v2")
    ap.add_argument("--limit-buddies", type=int, default=_safe_int("BLOG_LIMIT_BUDDIES", 120, min_v=0))
    ap.add_argument("--max-posts-per-buddy", type=int, default=_safe_int("BLOG_MAX_POSTS_PER_BUDDY", 80, min_v=1))
    ap.add_argument("--max-pages-per-buddy", type=int, default=_safe_int("BLOG_MAX_PAGES_PER_BUDDY", 40, min_v=1))
    ap.add_argument("--sleep", type=float, default=float(os.environ.get("BLOG_FETCH_SLEEP_SEC", "0.9")))
    ap.add_argument("--target-years", type=int, default=_safe_int("BLOG_TARGET_YEARS", 10, min_v=1))
    ap.add_argument("--target-date", type=str, default=os.environ.get("BLOG_TARGET_DATE", "").strip())
    ap.add_argument("--backoff-hours", type=int, default=_safe_int("BLOG_429_BACKOFF_HOURS", 3, min_v=1))
    ap.add_argument("--force", action="store_true", help="ignore active 429 backoff and run now")
    args = ap.parse_args()

    target_date = _resolve_target_date(args.target_date, args.target_years)
    result = run(
        args.limit_buddies,
        args.max_posts_per_buddy,
        args.max_pages_per_buddy,
        args.sleep,
        target_date,
        args.backoff_hours,
        args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
