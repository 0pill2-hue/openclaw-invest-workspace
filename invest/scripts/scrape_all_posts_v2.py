import subprocess
import json
import time
import os
import re
import html
import fcntl
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta

from pipeline_logger import append_pipeline_event

# Target date: dynamically 1 year ago from now
target_date = datetime.now() - timedelta(days=365)

LOCK_FILE = '/Users/jobiseu/.openclaw/workspace/invest/data/runtime/blog_scrape.lock'
CKPT_FILE = '/Users/jobiseu/.openclaw/workspace/invest/data/runtime/blog_scrape_checkpoint.json'
os.makedirs('/Users/jobiseu/.openclaw/workspace/invest/data/runtime', exist_ok=True)
_lock_fp = open(LOCK_FILE, 'w')
try:
    fcntl.flock(_lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print('SKIP: blog scraper already running (lock exists).')
    raise SystemExit(0)

with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/naver_buddies_full.json', 'r', encoding='utf-8') as f:
    buddies = json.load(f)

base_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/alternative/blog_posts'
log_path = '/Users/jobiseu/.openclaw/workspace/invest/logs/blog_scrape.log'
os.makedirs(base_dir, exist_ok=True)
os.makedirs(os.path.dirname(log_path), exist_ok=True)


def log_msg(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted = f"[{ts}] {msg}"
    print(formatted)
    with open(log_path, 'a', encoding='utf-8') as lf:
        lf.write(formatted + "\n")


def _safe_url(url: str) -> str:
    """Normalize URL to ASCII-safe representation for urllib."""
    try:
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(parts.path, safe='/%:@-._~')
        query = urllib.parse.quote(parts.query, safe='=&%:@-._~')
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))
    except Exception:
        return url


def _fetch_html(url, timeout=20):
    safe_url = _safe_url(url)
    req = urllib.request.Request(
        safe_url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        charset = resp.headers.get_content_charset() or 'utf-8'
        return body.decode(charset, errors='replace')


def _strip_html_to_text(raw_html):
    cleaned = re.sub(r'(?is)<script.*?>.*?</script>', ' ', raw_html)
    cleaned = re.sub(r'(?is)<style.*?>.*?</style>', ' ', cleaned)
    cleaned = re.sub(r'(?is)<br\s*/?>', '\n', cleaned)
    cleaned = re.sub(r'(?is)</p\s*>', '\n', cleaned)
    cleaned = re.sub(r'(?is)<[^>]+>', ' ', cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r'\r', '', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()


def fetch_post_text(url):
    first = _fetch_html(url)

    # Naver blog often serves content inside iframe(mainFrame)
    m = re.search(r'<iframe[^>]+id=["\']mainFrame["\'][^>]+src=["\']([^"\']+)["\']', first, re.I)
    if m:
        frame_src = urllib.parse.urljoin(url, m.group(1))
        second = _fetch_html(frame_src)
        text = _strip_html_to_text(second)
        if text:
            return text

    return _strip_html_to_text(first)


def _load_ckpt():
    if not os.path.exists(CKPT_FILE):
        return {"next_index": 0}
    try:
        with open(CKPT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"next_index": 0}
        return {"next_index": int(data.get("next_index", 0))}
    except Exception:
        return {"next_index": 0}


def _save_ckpt(next_index):
    try:
        with open(CKPT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"next_index": int(next_index), "saved_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_msg(f"  WARN: failed to save checkpoint: {e}")


def _extract_posts_from_rss(blog_id: str):
    """Prefer RSS for reliable latest ordering/date parsing."""
    rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
    try:
        xml_text = _fetch_html(rss_url, timeout=20)
    except Exception as e:
        log_msg(f"  WARN: RSS fetch failed for {blog_id}: {e}")
        return []

    posts = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    for item in root.findall('.//item'):
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        pub = (item.findtext('pubDate') or '').strip()

        m = re.search(r'logNo=(\d+)', link)
        if not m:
            # New Naver URL format: /blogId/logNo?fromRss=true&trackingCode=rss
            m = re.search(r'/(\d{8,})(?:[?&#]|$)', link)
        if not m:
            # Also try guid element as fallback
            guid = (item.findtext('guid') or '').strip()
            m = re.search(r'logNo=(\d+)', guid) or re.search(r'/(\d{8,})(?:[?&#]|$)', guid)
        if not m:
            continue
        log_no = m.group(1)

        d = None
        if pub:
            try:
                d = parsedate_to_datetime(pub)
                if d.tzinfo is not None:
                    d = d.astimezone().replace(tzinfo=None)
            except Exception:
                d = None

        date_str = f"{d.year}. {d.month}. {d.day}." if d else ''
        posts.append({
            'title': title or f'post_{log_no}',
            'url': link,
            'date': date_str,
            'id': log_no,
        })

    # RSS is newest-first in most cases, but enforce ordering by parsed date
    dated = []
    for p in posts:
        pd = _parse_post_date((p.get('date') or '').strip())
        if pd is None:
            continue
        p['_parsed_date'] = pd
        dated.append(p)
    dated.sort(key=lambda x: x.get('_parsed_date'), reverse=True)
    for p in dated:
        p.pop('_parsed_date', None)
    return dated


def _extract_posts_from_html(list_url):
    """HTTP fallback parser for post list (no browser)."""
    posts = []
    first = _fetch_html(list_url, timeout=20)

    m = re.search(r'<iframe[^>]+id=["\']mainFrame["\'][^>]+src=["\']([^"\']+)["\']', first, re.I)
    page_html = _fetch_html(urllib.parse.urljoin(list_url, m.group(1)), timeout=20) if m else first

    # Extract href + title roughly from links (support old PostView + new path-based URLs)
    link_pat = re.compile(r'<a[^>]+href=["\']([^"\']*(?:PostView\.naver|blog\.naver\.com/[^"\']+/\d{8,})[^"\']*)["\'][^>]*>(.*?)</a>', re.I | re.S)
    date_pat = re.compile(r'(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)')

    for mm in link_pat.finditer(page_html):
        href = html.unescape(mm.group(1))
        mid = re.search(r'logNo=(\d+)', href) or re.search(r'/(\d{8,})(?:[?&#]|$)', href)
        if not mid:
            continue
        log_no = mid.group(1)
        title = _strip_html_to_text(mm.group(2))[:200] or f"post_{log_no}"
        url = urllib.parse.urljoin(list_url, href)

        # Prefer local container-scoped date extraction to avoid cross-post date mix
        block = ""
        tr_start = page_html.rfind('<tr', 0, mm.start())
        tr_end = page_html.find('</tr>', mm.end())
        if tr_start != -1 and tr_end != -1 and tr_end > tr_start:
            block = page_html[tr_start:tr_end + 5]
        else:
            li_start = page_html.rfind('<li', 0, mm.start())
            li_end = page_html.find('</li>', mm.end())
            if li_start != -1 and li_end != -1 and li_end > li_start:
                block = page_html[li_start:li_end + 5]

        # fallback to small neighborhood only when container is unavailable
        span = block if block else page_html[max(0, mm.start() - 120): mm.end() + 120]
        dm = date_pat.search(span)
        date_str = dm.group(1) if dm else ""

        posts.append({
            "title": title,
            "url": url,
            "date": date_str,
            "id": log_no,
        })

    # Deduplicate by id
    uniq = {}
    for p in posts:
        if p["id"] not in uniq:
            uniq[p["id"]] = p

    # Keep only date-parseable rows and sort newest-first (prevents stale/sidebar links)
    filtered = []
    for p in uniq.values():
        pd = _parse_post_date((p.get('date') or '').strip())
        if pd is None:
            continue
        p['_parsed_date'] = pd
        filtered.append(p)

    filtered.sort(key=lambda x: x.get('_parsed_date'), reverse=True)
    for p in filtered:
        p.pop('_parsed_date', None)
    return filtered


def _parse_post_date(date_raw: str):
    """Parse naver blog date strings including relative expressions.
    Supports: YYYY. M. D. / YYYY.MM.DD / 방금 전 / N분 전 / N시간 전 / N일 전
    """
    if not date_raw:
        return None

    s = date_raw.strip()
    now = datetime.now()

    # absolute flexible forms: 2026. 2. 16. / 2026.2.16 / 2026-02-16
    m = re.search(r'(20\d{2})\s*[\.\-/]\s*(\d{1,2})\s*[\.\-/]\s*(\d{1,2})', s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass

    if s == '방금 전':
        return now

    m = re.match(r'^(\d+)\s*분\s*전$', s)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    m = re.match(r'^(\d+)\s*시간\s*전$', s)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    m = re.match(r'^(\d+)\s*일\s*전$', s)
    if m:
        return now - timedelta(days=int(m.group(1)))

    return None


def _extract_posts_with_browser(list_tab_id, bid):
    cmd = [
        "openclaw", "browser", "evaluate",
        "--browser-profile", "background",
        "--target-id", list_tab_id,
        "--fn",
        """
        () => {
            try {
                const frame = document.getElementById('mainFrame');
                const doc = frame ? frame.contentWindow.document : document;
                const rows = Array.from(doc.querySelectorAll('tr'));
                const posts = rows.map(row => {
                    const link = row.querySelector('a[href*="/PostView.naver"], a[href*="blog.naver.com/"]');
                    const href = link?.href || "";
                    const dateStr = row.querySelector('.date')?.innerText || "";
                    let id = null;
                    try {
                        const u = new URL(href);
                        id = u.searchParams.get('logNo') || (u.pathname.split('/').filter(Boolean).pop() || null);
                        if (!id || !/^[0-9]{8,}$/.test(id)) id = null;
                    } catch (_) {
                        id = null;
                    }
                    return {
                        title: link?.innerText.trim(),
                        url: href,
                        date: dateStr,
                        id
                    };
                }).filter(p => p.id);
                return JSON.stringify(posts);
            } catch (e) {
                return JSON.stringify({error: e.message});
            }
        }
        """,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)

    raw_out = result.stdout.strip()
    if raw_out.startswith('"'):
        import json as j
        raw_out = j.loads(raw_out)
    if not raw_out:
        raise RuntimeError(f"empty browser output for {bid}")

    data = json.loads(raw_out)
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"js_error: {data['error']}")
    if not isinstance(data, list):
        raise RuntimeError("unexpected browser output type")
    return data


MAX_BUDDIES_PER_RUN = int(os.environ.get('BLOG_MAX_BUDDIES_PER_RUN', '120'))
USE_BROWSER_FALLBACK = os.environ.get('BLOG_USE_BROWSER_FALLBACK', '0').strip().lower() not in ('0', 'false', 'no')
REQUEST_DELAY_SEC = float(os.environ.get('BLOG_REQUEST_DELAY_SEC', '0.15'))
saved_posts = 0
error_list = []

ckpt = _load_ckpt()
start_idx = max(0, min(len(buddies), ckpt.get("next_index", 0)))
end_idx = min(len(buddies), start_idx + MAX_BUDDIES_PER_RUN)
run_buddies = buddies[start_idx:end_idx]

log_msg(f"List mode: HTTP-first (browser fallback={'ON' if USE_BROWSER_FALLBACK else 'OFF'})")

if not run_buddies:
    log_msg("No pending buddies in checkpoint window. Resetting checkpoint to 0.")
    _save_ckpt(0)
    run_buddies = buddies[:MAX_BUDDIES_PER_RUN]
    start_idx = 0
    end_idx = min(len(buddies), MAX_BUDDIES_PER_RUN)

for offset, buddy in enumerate(run_buddies, 1):
    if REQUEST_DELAY_SEC > 0:
        time.sleep(REQUEST_DELAY_SEC)
    i = start_idx + offset
    bid = buddy['id']
    buddy_dir = os.path.join(base_dir, bid)
    os.makedirs(buddy_dir, exist_ok=True)

    log_msg(f"[{i}/{len(buddies)}] Processing buddy: {bid} ({i/len(buddies)*100:.2f}%)")

    list_tab_id = None
    url = f"https://blog.naver.com/PostList.naver?blogId={bid}&from=postList"

    try:
        # RSS first for latest ordering/date reliability, then HTTP fallback
        posts = _extract_posts_from_rss(bid)
        if not posts:
            posts = _extract_posts_from_html(url)

        if not posts and USE_BROWSER_FALLBACK:
            log_msg(f"  HTTP list empty for {bid}, trying browser fallback")
            list_open = subprocess.run(
                ["openclaw", "browser", "open", "--browser-profile", "background", "--json", url],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=20,
            )

            if list_open.returncode == 0:
                try:
                    list_tab = json.loads(list_open.stdout.strip())
                    list_tab_id = list_tab.get("targetId")
                except Exception:
                    list_tab_id = None

            if list_tab_id:
                time.sleep(2)
                try:
                    posts = _extract_posts_with_browser(list_tab_id, bid)
                except Exception as be:
                    error_list.append(f"{bid}: browser_list_error: {be}")
                    log_msg(f"  Browser list extraction failed: {be}")
            else:
                log_msg(f"  WARN: browser fallback tab open failed for {bid}")

        for post in posts:
            if not post.get('id'):
                continue

            date_raw = (post.get('date') or '').strip()
            if not date_raw:
                log_msg("  Skipping post with empty date")
                continue

            p_date = _parse_post_date(date_raw)
            if p_date is None:
                log_msg(f"  Skipping post with unparseable date: {date_raw}")
                continue
            if p_date < target_date:
                continue

            post_path = os.path.join(buddy_dir, f"{post['id']}.md")
            if os.path.exists(post_path):
                continue

            log_msg(f"  Fast-fetching: {post.get('title', 'no-title')} ({post.get('date', 'no-date')})")

            try:
                content = fetch_post_text(post['url'])
                if not content:
                    raise ValueError('empty content')
                with open(post_path, 'w', encoding='utf-8') as pf:
                    pf.write(
                        f"Title: {post.get('title', '')}\n"
                        f"Date: {post.get('date', '')}\n"
                        f"Source: {post.get('url', '')}\n\n{content}"
                    )
                saved_posts += 1
            except Exception as fe:
                error_list.append(f"{bid}:{post.get('id')}: {fe}")
                log_msg(f"  Fetch error for {post.get('id')}: {fe}")

        # Update dashboard every 5 buddies
        if i % 5 == 0:
            try:
                subprocess.run(
                    ["python3", "/Users/jobiseu/.openclaw/workspace/invest/scripts/update_dashboard.py"],
                    timeout=30,
                    check=False,
                )
            except Exception as e:
                log_msg(f"  WARN: dashboard update failed: {e}")

    except Exception as e:
        error_list.append(f"{bid}: outer_error: {e}")
        log_msg(f"  Outer error on {bid}: {e}")
    finally:
        # Critical: always close tab if opened (prevents tab leak / closed-tab loops)
        if list_tab_id:
            try:
                subprocess.run(
                    ["openclaw", "browser", "close", "--browser-profile", "background", list_tab_id],
                    timeout=15,
                    check=False,
                )
            except Exception as ce:
                log_msg(f"  WARN: tab close failed for {bid}: {ce}")

    _save_ckpt(i)

log_msg(f"Blog crawl finished (processed {len(run_buddies)} buddies this run; range={start_idx + 1}..{end_idx} / {len(buddies)}).")

result = "OK" if not error_list else "WARN"
print(f"STATUS: BLOG_SCRAPE_FINISHED RESULT={result} SAVED={saved_posts} ERRORS={len(error_list)}", flush=True)
append_pipeline_event(
    source="scrape_all_posts_v2",
    status=result,
    count=saved_posts,
    errors=error_list[:20],
    note=f"processed_buddies={len(run_buddies)} range={start_idx + 1}-{end_idx}",
)

try:
    fcntl.flock(_lock_fp.fileno(), fcntl.LOCK_UN)
    _lock_fp.close()
except Exception:
    pass
