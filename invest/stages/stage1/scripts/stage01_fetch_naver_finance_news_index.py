#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pipeline_logger import append_pipeline_event

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = ROOT / "invest/stages/stage1/outputs/raw/qualitative/market/news/url_index"
STATUS_PATH = ROOT / "invest/stages/stage1/outputs/runtime/news_naver_finance_index_status.json"
BASE_URL = "https://finance.naver.com"
DEFAULT_SECTION_IDS = ["258", "259", "260", "261", "262"]
UA = "Mozilla/5.0 (compatible; stage01-naver-finance-index/1.0; +https://openclaw.local)"


def _safe_int(raw: str, default: int, min_v: int = 1) -> int:
    try:
        return max(min_v, int((raw or "").strip()))
    except Exception:
        return default


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _parse_sections(raw: str) -> list[str]:
    if not raw.strip():
        return list(DEFAULT_SECTION_IDS)
    out = []
    seen = set()
    for part in raw.split(","):
        sid = part.strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out or list(DEFAULT_SECTION_IDS)


def _to_iso(raw: str) -> str:
    text = _clean_text(raw)
    if not text:
        return ""
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone.utc).astimezone(timezone.utc).isoformat()
    except Exception:
        return ""


def _normalize_article_url(href: str) -> str:
    full_url = urljoin(BASE_URL, href)
    parsed = urlparse(full_url)
    if parsed.netloc.lower() == "finance.naver.com" and parsed.path.endswith("/news/news_read.naver"):
        q = parse_qs(parsed.query)
        article_id = str((q.get("article_id") or [""])[0]).strip()
        office_id = str((q.get("office_id") or [""])[0]).strip()
        if article_id and office_id:
            return f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}"
    return full_url


def _fetch_page(session: requests.Session, section_id2: str, page: int, timeout: int) -> list[dict]:
    url = f"{BASE_URL}/news/news_list.naver?mode=LSS2D&section_id=101&section_id2={section_id2}&page={page}"
    r = session.get(url, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    r.encoding = "euc-kr"
    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for dl in soup.select("ul.realtimeNewsList dl"):
        a = dl.select_one("dd.articleSubject a")
        if a is None:
            continue
        href = str(a.get("href") or "").strip()
        title = _clean_text(a.get_text(" ", strip=True))
        if not href or not title:
            continue
        summary_node = dl.select_one("dd.articleSummary")
        press = ""
        wdate = ""
        summary = ""
        if summary_node is not None:
            press = _clean_text((summary_node.select_one("span.press") or {}).get_text(" ", strip=True) if summary_node.select_one("span.press") else "")
            wdate = _clean_text((summary_node.select_one("span.wdate") or {}).get_text(" ", strip=True) if summary_node.select_one("span.wdate") else "")
            clone = BeautifulSoup(str(summary_node), "html.parser")
            body = clone.select_one("dd.articleSummary")
            if body is not None:
                for tag in body.select("span.press, span.bar, span.wdate"):
                    tag.decompose()
                summary = _clean_text(body.get_text(" ", strip=True))
        full_url = _normalize_article_url(href)
        rows.append(
            {
                "url": full_url,
                "published_at": _to_iso(wdate),
                "published_date": wdate[:10] if len(wdate) >= 10 else "",
                "title": title,
                "summary": summary,
                "press": press,
                "source_domain": urlparse(full_url).netloc.lower(),
                "source_kind": "naver_finance_list",
                "source_name": f"naver_finance_{section_id2}",
                "source_url": url,
                "discovered_by": [
                    {
                        "source_kind": "naver_finance_list",
                        "source_name": f"naver_finance_{section_id2}",
                        "source_url": url,
                    }
                ],
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", default=os.environ.get("NAVER_FINANCE_SECTION_IDS", "258,259,260,261,262"))
    ap.add_argument("--pages", type=int, default=_safe_int(os.environ.get("NAVER_FINANCE_MAX_PAGES", "3"), 3, min_v=1))
    ap.add_argument("--timeout", type=int, default=_safe_int(os.environ.get("NAVER_FINANCE_TIMEOUT_SEC", "15"), 15, min_v=3))
    args = ap.parse_args()

    sections = _parse_sections(args.sections)
    session = requests.Session()
    seen = set()
    rows = []
    errors = []

    for section_id2 in sections:
        for page in range(1, max(1, args.pages) + 1):
            try:
                fetched = _fetch_page(session, section_id2, page, args.timeout)
            except Exception as e:
                errors.append(f"section={section_id2}:page={page}:{type(e).__name__}")
                break
            if not fetched:
                break
            new_count = 0
            for row in fetched:
                url = row["url"]
                if url in seen:
                    continue
                seen.add(url)
                rows.append(row)
                new_count += 1
            if new_count == 0:
                break

    rows.sort(key=lambda r: (str(r.get("published_at") or ""), str(r.get("url") or "")), reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"url_index_naver_finance_{ts}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "pages": int(args.pages),
        "items_total": len(rows),
        "index_file": str(out_path.relative_to(ROOT)),
        "errors": errors,
        "status": "OK" if not errors else "WARN",
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_pipeline_event(
        source="news_naver_finance_index",
        status=payload["status"],
        count=len(rows),
        errors=errors[:20],
        note=f"sections={','.join(sections)} pages={args.pages} rows={len(rows)}",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
