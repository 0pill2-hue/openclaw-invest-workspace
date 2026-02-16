import subprocess
import json
import time
import os
import re
import html
import fcntl
import urllib.request
import urllib.parse
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


def _fetch_html(url, timeout=20):
    req = urllib.request.Request(
        url,
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


def _extract_posts_from_html(list_url):
    """HTTP fallback parser for post list (no browser)."""
    posts = []
    first = _fetch_html(list_url, timeout=20)

    m = re.search(r'<iframe[^>]+id=["\']mainFrame["\'][^>]+src=["\']([^"\']+)["\']', first, re.I)
    page_html = _fetch_html(urllib.parse.urljoin(list_url, m.group(1)), timeout=20) if m else first

    # Extract href + title roughly from links
    link_pat = re.compile(r'<a[^>]+href=["\']([^"\']*PostView\.naver[^"\']*logNo=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>', re.I | re.S)
    date_pat = re.compile(r'(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)')

    for mm in link_pat.finditer(page_html):
        href = html.unescape(mm.group(1))
        log_no = mm.group(2)
        title = _strip_html_to_text(mm.group(3))[:200] or f"post_{log_no}"
        url = urllib.parse.urljoin(list_url, href)

        # best-effort nearby date extraction
        span = page_html[max(0, mm.start() - 300): mm.end() + 300]
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
    return list(uniq.values())


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
                    const link = row.querySelector('a[href*="/PostView.naver"]');
                    const dateStr = row.querySelector('.date')?.innerText || "";
                    return {
                        title: link?.innerText.trim(),
                        url: link?.href,
                        date: dateStr,
                        id: link?.href?.split('logNo=')[1]?.split('&')[0]
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
USE_BROWSER_FALLBACK = os.environ.get('BLOG_USE_BROWSER_FALLBACK', '1').strip().lower() not in ('0', 'false', 'no')
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
    i = start_idx + offset
    bid = buddy['id']
    buddy_dir = os.path.join(base_dir, bid)
    os.makedirs(buddy_dir, exist_ok=True)

    log_msg(f"[{i}/{len(buddies)}] Processing buddy: {bid} ({i/len(buddies)*100:.2f}%)")

    list_tab_id = None
    url = f"https://blog.naver.com/PostList.naver?blogId={bid}&from=postList"

    try:
        # HTTP first (browser is fallback only)
        posts = _extract_posts_from_html(url)

        if not posts and USE_BROWSER_FALLBACK:
            log_msg(f"  HTTP list empty for {bid}, trying browser fallback")
            list_open = subprocess.run(
                ["openclaw", "browser", "open", "--browser-profile", "background", "--json", url],
                capture_output=True,
                text=True,
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
            if date_raw:
                try:
                    p_date = datetime.strptime(date_raw.strip('.'), '%Y. %m. %d')
                    if p_date < target_date:
                        continue
                except Exception:
                    # Skip only if there is a malformed date string
                    log_msg(f"  Skipping post with unparseable date: {date_raw}")
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
