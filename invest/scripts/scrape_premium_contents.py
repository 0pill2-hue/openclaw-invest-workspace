import subprocess
import json
import time
import os
from datetime import datetime

base_url = "https://contents.premium.naver.com/startale0517/startale/contents"
save_dir = "/Users/jobiseu/.openclaw/workspace/invest/data/alternative/premium_contents/startale"
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
    
    # Infinite scroll/More click to load all 410 posts
    log_msg("Loading all 410 posts (scrolling to bottom)...")
    scroll_cmd = ["openclaw", "browser", "evaluate", "--browser-profile", profile, "--fn", """
        async () => {
            const delay = ms => new Promise(res => setTimeout(res, ms));
            let lastHeight = document.body.scrollHeight;
            let count = 0;
            while (count < 100) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(3000);
                let newHeight = document.body.scrollHeight;
                if (newHeight === lastHeight) {
                    // Try clicking the more button if it exists
                    const moreBtn = document.querySelector('.btn_more');
                    if (moreBtn && !moreBtn.hidden && moreBtn.style.display !== 'none') {
                        moreBtn.click();
                        await delay(4000);
                    } else {
                        break;
                    }
                }
                lastHeight = newHeight;
                count++;
            }
            const links = Array.from(document.querySelectorAll('a[href*="/contents/"]'));
            return JSON.stringify(links.map(l => ({
                url: l.href,
                id: l.href.split('/').pop(),
                title: l.innerText.trim().split('\\n')[0]
            })));
        }
    """]
    res = subprocess.run(scroll_cmd, capture_output=True, text=True)
    try:
        raw = res.stdout.strip()
        if raw.startswith('"'): import json as j; raw = j.loads(raw)
        contents = json.loads(raw)
    except:
        log_msg("Failed to parse content list")
        contents = []

    log_msg(f"Total contents identified: {len(contents)}")
    
    for item in contents:
        fpath = os.path.join(save_dir, f"{item['id']}.md")
        if os.path.exists(fpath):
            continue
            
        log_msg(f"Fast-fetching premium content: {item['title']}")
        # We can't use web_fetch here because it's paid content (no cookies)
        # So we must use browser open but we can keep it lean
        subprocess.run(["openclaw", "browser", "open", "--browser-profile", profile, item['url']])
        time.sleep(3)
        
        content_cmd = ["openclaw", "browser", "evaluate", "--browser-profile", profile, "--fn", """
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
            
    log_msg("Premium contents scrape finished")

if __name__ == "__main__":
    scrape()
