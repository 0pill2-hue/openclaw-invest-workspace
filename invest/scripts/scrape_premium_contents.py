import subprocess
import json
import time
import os
from datetime import datetime

base_url = "https://contents.premium.naver.com/startale0517/startale/contents"
save_dir = "/Users/jobiseu/.openclaw/workspace/invest/data/raw/text/premium/startale"
log_path = "/Users/jobiseu/.openclaw/workspace/invest/logs/premium_scrape.log"
os.makedirs(save_dir, exist_ok=True)

def log_msg(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted = f"[{ts}] {msg}"
    print(formatted)
    with open(log_path, 'a', encoding='utf-8') as lf:
        lf.write(formatted + "\n")

def scrape():
    profile = "openclaw" # Logged in profile
    
    log_msg(f"Opening full contents list: {base_url}")
    open_cmd = ["openclaw", "browser", "open", "--browser-profile", profile, "--json", base_url]
    res = subprocess.run(open_cmd, capture_output=True, text=True)
    try:
        main_tab = json.loads(res.stdout.strip())
        main_tab_id = main_tab.get("targetId")
    except:
        log_msg("Failed to open main page")
        return

    time.sleep(5)
    
    # Infinite scroll/More click to load all 415 posts
    log_msg("Loading all posts (scrolling to bottom)...")
    scroll_cmd = ["openclaw", "browser", "evaluate", "--browser-profile", profile, "--target-id", main_tab_id, "--timeout", "300000", "--fn", """
        async () => {
            const delay = ms => new Promise(res => setTimeout(res, ms));
            let lastHeight = document.body.scrollHeight;
            let count = 0;
            while (count < 150) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(2500);
                let newHeight = document.body.scrollHeight;
                
                // Naver Premium Contents uses .btn_more or sometimes just infinite scroll
                const moreBtn = document.querySelector('.btn_more');
                if (moreBtn && !moreBtn.hidden && moreBtn.style.display !== 'none') {
                    moreBtn.click();
                    await delay(3000);
                    newHeight = document.body.scrollHeight;
                }

                if (newHeight === lastHeight) {
                    // Try one more time after a longer delay
                    await delay(2000);
                    window.scrollTo(0, document.body.scrollHeight);
                    if (document.body.scrollHeight === lastHeight) break;
                }
                lastHeight = newHeight;
                count++;
            }
            const links = Array.from(document.querySelectorAll('a[href*="/contents/"]'));
            const data = links.map(l => {
                const href = l.href;
                const idMatch = href.match(/\\/contents\\/([a-zA-Z0-9]+)/);
                return {
                    url: href,
                    id: idMatch ? idMatch[1] : null,
                    title: l.innerText.trim().split('\\n')[0]
                };
            }).filter(item => item.id && item.id.length > 5);
            
            // Deduplicate by ID
            const seen = new Set();
            const uniq = [];
            for (const item of data) {
                if (!seen.has(item.id)) {
                    seen.add(item.id);
                    uniq.push(item);
                }
            }
            return JSON.stringify(uniq);
        }
    """]
    res = subprocess.run(scroll_cmd, capture_output=True, text=True, shell=False)
    try:
        raw = res.stdout.strip()
        # Log for debugging
        with open(log_path + ".debug", 'a') as df:
            df.write(f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}\n")
        # Some CLI versions might wrap output in quotes or adds extra lines
        if raw.startswith('"'):
            import json as j
            raw = j.loads(raw)
        
        # Strip potential non-json prefix/suffix
        if not raw.startswith('['):
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1:
                raw = raw[start:end+1]
        
        contents = json.loads(raw)
        if isinstance(contents, str):
            contents = json.loads(contents)
    except Exception as e:
        log_msg(f"Failed to parse content list: {e}")
        log_msg(f"Raw output snippet: {res.stdout[:200]}")
        contents = []

    log_msg(f"Total contents identified: {len(contents)}")
    
    for item in contents:
        fpath = os.path.join(save_dir, f"{item['id']}.md")
        if os.path.exists(fpath):
            continue
            
        log_msg(f"Fast-fetching premium content: {item['title']}")
        # We can't use web_fetch here because it's paid content (no cookies)
        # So we must use browser open but we can keep it lean
        open_res = subprocess.run(["openclaw", "browser", "open", "--browser-profile", profile, "--json", item['url']], capture_output=True, text=True)
        try:
            item_tab = json.loads(open_res.stdout.strip())
            item_tab_id = item_tab.get("targetId")
        except:
            log_msg(f"Failed to open item: {item['id']}")
            continue

        time.sleep(3)
        
        content_cmd = ["openclaw", "browser", "evaluate", "--browser-profile", profile, "--target-id", item_tab_id, "--fn", """
            () => {
                const title = document.querySelector('strong')?.innerText || "";
                const date = document.querySelector('span.date')?.innerText || "";
                const body = document.querySelector('.article_body') || document.body;
                return JSON.stringify({
                    title: title,
                    date: date,
                    text: body.innerText
                });
            }
        """]
        res = subprocess.run(content_cmd, capture_output=True, text=True)
        try:
            raw = res.stdout.strip()
            if raw.startswith('"'): import json as j; raw = j.loads(raw)
            data = json.loads(raw)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(f"Title: {data['title']}\nDate: {data['date']}\nSource: {item['url']}\n\n{data['text']}")
        except Exception as e:
            log_msg(f"Error scraping {item['id']}: {e}")
        finally:
            if item_tab_id:
                subprocess.run(["openclaw", "browser", "close", "--browser-profile", profile, item_tab_id])
            
    log_msg("Premium contents scrape finished")

if __name__ == "__main__":
    scrape()
