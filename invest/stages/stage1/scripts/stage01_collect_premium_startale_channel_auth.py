#!/usr/bin/env python3
import argparse
import hashlib
import json
import random
import re
import time
from collections import Counter
from datetime import datetime
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
DISCOVERY_PATH = ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/premium/startale_channel_direct/_discovery.json"
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/text/premium/startale"
BLOCKED_DIR = OUT_DIR / "BLOCKED_PAYWALL_OR_SESSION"
PROCESS_INDEX_PATH = OUT_DIR / "_index.json"
RUNTIME_STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/premium_channel_auth_collect_status.json"
REPORT_MD_PATH = ROOT / "invest/stages/stage1/outputs/reports/stage_updates/PREMIUM_CHANNEL_AUTH_COLLECT_20260305.md"
REPORT_JSON_PATH = ROOT / "invest/stages/stage1/outputs/reports/stage_updates/PREMIUM_CHANNEL_AUTH_COLLECT_20260305.json"

BASE_CHANNEL_URL = "https://contents.premium.naver.com/startale0517/startale/contents"
ARTICLE_URL_RE = re.compile(r"https://contents\.premium\.naver\.com/startale0517/startale/contents/[0-9A-Za-z]{8,30}")
CONTENT_ID_RE = re.compile(r"/contents/([0-9A-Za-z]{8,30})")
DATE_RE = re.compile(r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}[.]?(?:\s*(?:오전|오후)?\s*\d{1,2}:\d{2})?")

DISCLAIMER_PATTERNS = [
    "Disclaimer",
    "디스클레이머",
    "법적 책임소재",
    "매수/매도 추천",
    "투자 상담",
    "이 글만 믿고",
]
GATE_PATTERNS = [
    "로그인",
    "구독",
    "정기결제",
    "이용권",
    "멤버십",
    "유료",
    "삭제된 콘텐츠",
    "이 콘텐츠는 구독",
    "구독 후 이용",
    "콘텐츠 본문을 보시려면",
]
PREVIEW_PATTERNS = [
    "미리보기",
    "일부만 공개",
    "미리 보실 수 있습니다",
]


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _slug_from_url(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    tail = url.rstrip("/").split("/")[-1]
    tail = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", tail)[:60] or "item"
    return f"{tail}_{digest}"


def _normalize_text(raw: str) -> str:
    lines = []
    for line in raw.replace("\xa0", " ").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _extract_title(soup: BeautifulSoup) -> str:
    selectors = [
        ".se-title-text span",
        ".viewer_title .se-text-paragraph span",
        ".viewer_title h2",
        ".viewer_title",
        "h1",
        "h2",
        "meta[property='og:title']",
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
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _extract_date(soup: BeautifulSoup, html: str) -> str:
    selectors = [
        ".viewer_date",
        "time",
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "meta[property='og:article:published_time']",
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
            m = DATE_RE.search(cand)
            return m.group(0) if m else cand

    m = DATE_RE.search(html)
    return m.group(0) if m else ""


def _extract_body(soup: BeautifulSoup) -> Tuple[str, str]:
    selectors = [
        ".se-main-container",
        ".viewer_content",
        ".article_viewer",
        ".article_body",
        ".viewer_body",
        "article",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if not node:
            continue
        for bad in node.select(
            "script, style, noscript, .viewer_more_content_wrap, .ranking_content_card_wrap, "
            ".viewer_related_wrap, .ad_wrap, .promotion_wrap"
        ):
            bad.decompose()
        text = _normalize_text(node.get_text("\n"))
        if text:
            return text, sel
    return "", ""


def _analyze_body(body_text: str, html: str) -> Dict:
    lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
    disclaimer_lines = [ln for ln in lines if any(p in ln for p in DISCLAIMER_PATTERNS)]
    gate_lines = [ln for ln in lines if any(p in ln for p in GATE_PATTERNS)]

    filtered = []
    for line in lines:
        if line in disclaimer_lines:
            continue
        if line in gate_lines:
            continue
        filtered.append(line)

    filtered_text = "\n".join(filtered)
    meaningful_chars = len(re.findall(r"[0-9A-Za-z가-힣]", filtered_text))

    preview_hit = any(p in body_text or p in html for p in PREVIEW_PATTERNS)
    gate_hit = any(p in body_text or p in html for p in GATE_PATTERNS)

    reason = "ok"
    if not body_text:
        reason = "empty_body"
    elif preview_hit and meaningful_chars < 260:
        reason = "preview_only"
    elif gate_hit and meaningful_chars < 260:
        reason = "subscription_gate"
    elif len(disclaimer_lines) >= 3 and meaningful_chars < 260:
        reason = "disclaimer_only"
    elif meaningful_chars < 120:
        reason = "low_content"

    status = "blocked" if reason != "ok" else "success"
    return {
        "status": status,
        "reason": reason,
        "meaningful_chars": meaningful_chars,
        "filtered_text": filtered_text,
        "disclaimer_line_count": len(disclaimer_lines),
        "gate_line_count": len(gate_lines),
        "preview_hit": preview_hit,
    }


def _write_markdown(path: Path, title: str, url: str, published_at: str, body: str, status: str, reason: str, is_login) -> None:
    payload = (
        f"# {title or '제목 미확인'}\n\n"
        f"- URL: {url}\n"
        f"- PublishedAt: {published_at or '미확인'}\n"
        f"- CollectedAt: {datetime.now().isoformat(timespec='seconds')}\n"
        f"- Status: {status}\n"
        f"- Reason: {reason}\n"
        f"- isLogin: {is_login if is_login is not None else '미확인'}\n\n"
        f"## 본문\n\n{body.strip() if body.strip() else '본문 미추출'}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _cookie_worker(queue: Queue, domain: str) -> None:
    try:
        import browser_cookie3

        jar = browser_cookie3.chrome(domain_name=domain)
        cookies = []
        for c in jar:
            if not c.name:
                continue
            if domain not in (c.domain or "") and ".naver.com" not in (c.domain or ""):
                continue
            cookies.append(
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path or "/",
                    "secure": bool(c.secure),
                    "expires": c.expires,
                }
            )
        queue.put({"ok": True, "cookies": cookies})
    except Exception as e:
        queue.put({"ok": False, "error": f"{type(e).__name__}:{e}"})


def _load_chrome_cookies_with_timeout(session: requests.Session, domain: str, timeout_sec: int = 20) -> Dict:
    queue: Queue = Queue()
    proc = Process(target=_cookie_worker, args=(queue, domain), daemon=True)
    proc.start()
    proc.join(timeout=timeout_sec)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=2)
        return {
            "status": "timeout",
            "loaded_count": 0,
            "error": f"browser_cookie3_timeout_{timeout_sec}s",
        }

    if queue.empty():
        return {"status": "failed", "loaded_count": 0, "error": "cookie_worker_no_result"}

    result = queue.get()
    if not result.get("ok"):
        return {
            "status": "failed",
            "loaded_count": 0,
            "error": result.get("error", "cookie_worker_failed"),
        }

    loaded = 0
    for c in result.get("cookies", []):
        try:
            session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain") or domain,
                path=c.get("path") or "/",
            )
            loaded += 1
        except Exception:
            continue

    return {
        "status": "loaded" if loaded > 0 else "empty",
        "loaded_count": loaded,
        "error": "" if loaded > 0 else "no_cookie_for_domain",
    }


def _discover_urls_by_pagination(session: requests.Session, base_url: str, max_pages: int = 80) -> Tuple[List[str], List[Dict], str]:
    urls: List[str] = []
    url_set = set()
    page_infos: List[Dict] = []

    page = 1
    page_url = base_url
    seen_cursors = set()
    stop_reason = "max_pages_reached"

    while page <= max_pages:
        try:
            resp = session.get(page_url, timeout=25)
            html = resp.text
            status = resp.status_code
        except Exception as e:
            page_infos.append(
                {
                    "page": page,
                    "url": page_url,
                    "http_status": None,
                    "new_urls": 0,
                    "total_urls": len(url_set),
                    "has_next": False,
                    "cursor": "",
                    "error": f"request_error:{type(e).__name__}",
                }
            )
            stop_reason = f"request_error@page{page}"
            break

        soup = BeautifulSoup(html, "html.parser")
        found = set()
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            abs_url = urljoin(base_url, href)
            m = ARTICLE_URL_RE.search(abs_url)
            if m:
                found.add(m.group(0))

        found_sorted = sorted(found)
        new_count = 0
        for u in found_sorted:
            if u not in url_set:
                url_set.add(u)
                urls.append(u)
                new_count += 1

        cursor_node = soup.select_one("[data-cursor-name='lastContentId']")
        cursor = ""
        has_next = False
        if cursor_node:
            cursor = (cursor_node.get("data-cursor") or "").strip()
            has_next = (cursor_node.get("data-has-next") or "").strip().lower() == "true"

        page_infos.append(
            {
                "page": page,
                "url": page_url,
                "http_status": status,
                "new_urls": new_count,
                "total_urls": len(url_set),
                "has_next": has_next,
                "cursor": cursor,
            }
        )

        if not has_next:
            stop_reason = f"pagination_has_next_false@page{page}"
            break
        if not cursor:
            stop_reason = f"cursor_missing@page{page}"
            break
        if cursor in seen_cursors:
            stop_reason = f"cursor_repeated@page{page}"
            break

        seen_cursors.add(cursor)
        page_url = f"{base_url}?lastContentId={cursor}"
        page += 1

    return urls, page_infos, stop_reason


def _load_or_refresh_discovery_urls(session: requests.Session, discovery_path: Path) -> Tuple[List[str], Dict]:
    discovery = _load_json(discovery_path, {})

    direct_urls = []
    for key in ("urls", "unique_url_list", "article_urls"):
        vals = discovery.get(key, [])
        if isinstance(vals, list):
            for u in vals:
                if isinstance(u, str) and ARTICLE_URL_RE.fullmatch(u):
                    direct_urls.append(u)

    direct_urls = sorted(set(direct_urls))
    if direct_urls:
        discovery["unique_urls"] = len(direct_urls)
        discovery["url_source"] = "discovery_json"
        return direct_urls, discovery

    base_url = discovery.get("base") or BASE_CHANNEL_URL
    urls, pages, stop_reason = _discover_urls_by_pagination(session, base_url=base_url)

    merged = dict(discovery)
    merged["timestamp"] = datetime.now().isoformat(timespec="seconds")
    merged["base"] = base_url
    merged["pages"] = pages
    merged["stop_reason"] = stop_reason
    merged["unique_urls"] = len(urls)
    merged["urls"] = urls
    merged["url_source"] = "channel_pagination"

    _save_json(discovery_path, merged)
    return urls, merged


def _url_is_invalid(url: str) -> bool:
    if "…" in url:
        return True
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    if "contents.premium.naver.com" not in parsed.netloc:
        return True
    return False


def _content_id_from_url(url: str) -> str:
    m = CONTENT_ID_RE.search(url)
    return m.group(1) if m else ""


def _process_one(url: str, session: requests.Session) -> Dict:
    now = datetime.now().isoformat(timespec="seconds")
    cid = _content_id_from_url(url)

    if _url_is_invalid(url) or not cid:
        return {
            "status": "error",
            "reason": "invalid_url_or_content_id",
            "attempted_at": now,
            "http_status": None,
            "title": "",
            "published_at": "",
            "body_text": "",
            "selector": "",
            "is_login": None,
        }

    try:
        resp = session.get(url, timeout=25)
    except Exception as e:
        return {
            "status": "error",
            "reason": f"request_error:{type(e).__name__}",
            "attempted_at": now,
            "http_status": None,
            "title": "",
            "published_at": "",
            "body_text": "",
            "selector": "",
            "is_login": None,
        }

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    m_login = re.search(r"var\s+isLogin\s*=\s*(true|false)", html)
    is_login = None
    if m_login:
        is_login = m_login.group(1).lower() == "true"

    title = _extract_title(soup)
    published_at = _extract_date(soup, html)
    body_text, selector = _extract_body(soup)
    analyzed = _analyze_body(body_text, html)

    if resp.status_code >= 400:
        analyzed["status"] = "blocked"
        analyzed["reason"] = f"http_{resp.status_code}"

    return {
        "status": analyzed["status"],
        "reason": analyzed["reason"],
        "attempted_at": now,
        "http_status": resp.status_code,
        "title": title,
        "published_at": published_at,
        "body_text": body_text,
        "filtered_text": analyzed["filtered_text"],
        "selector": selector,
        "meaningful_chars": analyzed["meaningful_chars"],
        "disclaimer_line_count": analyzed["disclaimer_line_count"],
        "gate_line_count": analyzed["gate_line_count"],
        "preview_hit": analyzed["preview_hit"],
        "is_login": is_login,
    }


def run(max_attempts: int = 0, jitter_min: float = 0.1, jitter_max: float = 0.3, reprocess: bool = True) -> Dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)

    process_index = _load_json(PROCESS_INDEX_PATH, {}) if not reprocess else {}

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )

    cookie_info = _load_chrome_cookies_with_timeout(session, domain="naver.com", timeout_sec=20)

    urls, discovery_payload = _load_or_refresh_discovery_urls(session, DISCOVERY_PATH)
    urls = [u for u in urls if ARTICLE_URL_RE.fullmatch(u)]

    if max_attempts and max_attempts > 0:
        urls = urls[:max_attempts]

    sample_urls = urls[:3]
    login_true_sample = 0
    login_false_sample = 0
    login_none_sample = 0
    sample_checks = []
    for s_url in sample_urls:
        try:
            s_resp = session.get(s_url, timeout=25)
            html = s_resp.text
            m = re.search(r"var\s+isLogin\s*=\s*(true|false)", html)
            is_login = None if not m else m.group(1).lower() == "true"
            if is_login is True:
                login_true_sample += 1
            elif is_login is False:
                login_false_sample += 1
            else:
                login_none_sample += 1
            sample_checks.append(
                {
                    "url": s_url,
                    "http_status": s_resp.status_code,
                    "is_login": is_login,
                    "body_len": len(html),
                }
            )
        except Exception as e:
            login_none_sample += 1
            sample_checks.append(
                {
                    "url": s_url,
                    "http_status": None,
                    "is_login": None,
                    "error": f"{type(e).__name__}:{e}",
                }
            )

    attempted = 0
    success = 0
    blocked = 0
    error = 0
    skipped = 0
    blocked_reasons = Counter()

    login_true_total = 0
    login_false_total = 0
    login_none_total = 0

    success_files: List[Path] = []
    blocked_files: List[Path] = []

    for url in urls:
        if (not reprocess) and url in process_index:
            skipped += 1
            continue

        attempted += 1
        one = _process_one(url, session)

        is_login = one.get("is_login")
        if is_login is True:
            login_true_total += 1
        elif is_login is False:
            login_false_total += 1
        else:
            login_none_total += 1

        slug = _slug_from_url(url)
        if one["status"] == "success":
            out_path = OUT_DIR / f"{slug}.md"
            _write_markdown(
                out_path,
                title=one.get("title", ""),
                url=url,
                published_at=one.get("published_at", ""),
                body=one.get("body_text", ""),
                status="SUCCESS",
                reason=one.get("reason", "ok"),
                is_login=one.get("is_login"),
            )
            success += 1
            success_files.append(out_path)
        elif one["status"] == "blocked":
            out_path = BLOCKED_DIR / f"{slug}.md"
            _write_markdown(
                out_path,
                title=one.get("title", ""),
                url=url,
                published_at=one.get("published_at", ""),
                body=one.get("body_text", ""),
                status="BLOCKED_PAYWALL_OR_SESSION",
                reason=one.get("reason", "blocked"),
                is_login=one.get("is_login"),
            )
            blocked += 1
            blocked_reasons[one.get("reason", "blocked")] += 1
            blocked_files.append(out_path)
        else:
            out_path = BLOCKED_DIR / f"{slug}.md"
            _write_markdown(
                out_path,
                title=one.get("title", ""),
                url=url,
                published_at=one.get("published_at", ""),
                body=one.get("body_text", ""),
                status="ERROR",
                reason=one.get("reason", "error"),
                is_login=one.get("is_login"),
            )
            error += 1
            blocked_reasons[one.get("reason", "error")] += 1
            blocked_files.append(out_path)

        process_index[url] = {
            "status": one.get("status"),
            "reason": one.get("reason"),
            "file": str(out_path.relative_to(ROOT)),
            "title": one.get("title", ""),
            "published_at": one.get("published_at", ""),
            "http_status": one.get("http_status"),
            "body_length": len(one.get("body_text", "")),
            "meaningful_chars": one.get("meaningful_chars", 0),
            "selector": one.get("selector", ""),
            "is_login": one.get("is_login"),
            "attempted_at": one.get("attempted_at"),
        }

        if attempted % 20 == 0:
            _save_json(PROCESS_INDEX_PATH, process_index)

        if jitter_max > 0 and attempted < len(urls):
            time.sleep(random.uniform(jitter_min, jitter_max))

    _save_json(PROCESS_INDEX_PATH, process_index)

    if attempted == 0:
        result = "미확인"
    elif cookie_info.get("status") != "loaded":
        result = "FAIL"
    elif login_true_sample > 0 or login_true_total > 0:
        result = "PASS"
    else:
        result = "FAIL"

    evidence_files = [str(p.relative_to(ROOT)) for p in (success_files[:3] + blocked_files[:4])[:7]]

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "result": result,
        "worker_mode": "single_worker_serial",
        "attempted": attempted,
        "success": success,
        "blocked": blocked,
        "error": error,
        "skipped": skipped,
        "source_url_count": len(urls),
        "processed_index_size": len(process_index),
        "cookie_load": cookie_info,
        "login_signal": {
            "sample_check_count": len(sample_urls),
            "sample_isLogin_true": login_true_sample,
            "sample_isLogin_false": login_false_sample,
            "sample_isLogin_unknown": login_none_sample,
            "total_isLogin_true": login_true_total,
            "total_isLogin_false": login_false_total,
            "total_isLogin_unknown": login_none_total,
        },
        "sample_checks": sample_checks,
        "blocked_reason_distribution": dict(blocked_reasons),
        "discovery": {
            "path": str(DISCOVERY_PATH.relative_to(ROOT)),
            "base": discovery_payload.get("base", BASE_CHANNEL_URL),
            "unique_urls": discovery_payload.get("unique_urls", len(urls)),
            "url_source": discovery_payload.get("url_source", "unknown"),
            "stop_reason": discovery_payload.get("stop_reason", "미확인"),
            "pages": len(discovery_payload.get("pages", [])),
        },
        "output": {
            "text_dir": str(OUT_DIR.relative_to(ROOT)),
            "blocked_dir": str(BLOCKED_DIR.relative_to(ROOT)),
            "index": str(PROCESS_INDEX_PATH.relative_to(ROOT)),
        },
        "evidence_files": evidence_files,
    }

    _save_json(REPORT_JSON_PATH, summary)
    _save_json(RUNTIME_STATUS_PATH, summary)

    blocked_compact = ", ".join(f"{k}:{v}" for k, v in blocked_reasons.most_common()) or "none"
    md_lines = [
        "# PREMIUM CHANNEL AUTH COLLECT (2026-03-05)",
        f"- result: {result}",
        f"- attempted/success/blocked/error: {attempted}/{success}/{blocked}/{error}",
        (
            "- login_signal(sample true/false/unknown): "
            f"{login_true_sample}/{login_false_sample}/{login_none_sample}"
        ),
        (
            "- login_signal(total true/false/unknown): "
            f"{login_true_total}/{login_false_total}/{login_none_total}"
        ),
        (
            "- cookie_load: "
            f"status={cookie_info.get('status')} loaded_count={cookie_info.get('loaded_count', 0)} "
            f"error={cookie_info.get('error', '') or '-'}"
        ),
        f"- blocked_reasons: {blocked_compact}",
        f"- discovery: source={summary['discovery']['url_source']} unique_urls={summary['discovery']['unique_urls']} pages={summary['discovery']['pages']}",
        f"- runtime_status: {RUNTIME_STATUS_PATH.relative_to(ROOT)}",
        f"- report_json: {REPORT_JSON_PATH.relative_to(ROOT)}",
        f"- output_dir: {OUT_DIR.relative_to(ROOT)}",
        "- evidence_files:",
    ]
    md_lines.extend([f"  - {p}" for p in evidence_files])

    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    append_pipeline_event(
        source="collect_premium_startale_channel_auth",
        status=result,
        count=attempted,
        errors=[cookie_info.get("error", "")][:1] if cookie_info.get("error") else [],
        note=f"attempted={attempted} success={success} blocked={blocked} error={error}",
    )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Naver Premium Startale content with Chrome auth cookie")
    parser.add_argument("--max-attempts", type=int, default=0, help="0 means all URLs")
    parser.add_argument("--jitter-min", type=float, default=0.1)
    parser.add_argument("--jitter-max", type=float, default=0.3)
    parser.add_argument("--no-reprocess", action="store_true")
    args = parser.parse_args()

    if args.jitter_min < 0 or args.jitter_max < args.jitter_min:
        raise SystemExit("invalid jitter range")

    summary = run(
        max_attempts=args.max_attempts,
        jitter_min=args.jitter_min,
        jitter_max=args.jitter_max,
        reprocess=not args.no_reprocess,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
