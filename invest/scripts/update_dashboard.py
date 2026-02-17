import os
import json
import re
from datetime import datetime

# Paths
workspace_dir = '/Users/jobiseu/.openclaw/workspace/invest'
blog_posts_dir = os.path.join(workspace_dir, 'data/raw/text/blog')
tg_logs_dir = os.path.join(workspace_dir, 'data/raw/text/telegram')
blog_log_path = os.path.join(workspace_dir, 'logs/blog_scrape.log')
tg_log_path = os.path.join(workspace_dir, 'logs/tg_highspeed.log')
index_html_path = os.path.join(workspace_dir, 'web/index.html')
buddies_json_path = os.path.join(workspace_dir, 'data/master/naver_buddies_full.json')
auth_path = '/Users/jobiseu/.openclaw/agents/main/agent/auth-profiles.json'

def get_blog_progress():
    try:
        with open(buddies_json_path, 'r', encoding='utf-8') as f:
            total_buddies = len(json.load(f))
        completed = 0
        if os.path.exists(blog_posts_dir):
            for d in os.listdir(blog_posts_dir):
                dpath = os.path.join(blog_posts_dir, d)
                if os.path.isdir(dpath) and os.listdir(dpath):
                    completed += 1
        pct = (completed / total_buddies) * 100 if total_buddies > 0 else 0
        return completed, total_buddies, round(pct, 1)
    except:
        return 0, 633, 0.0

def get_tg_progress():
    try:
        files = [f for f in os.listdir(tg_logs_dir) if f.endswith('_full.md')]
        count = len(files)
        target = 50
        pct = min(100.0, round((count / target) * 100, 1))
        return count, target, pct
    except:
        return 0, 50, 0.0

def get_latest_intel():
    intel = []
    if os.path.exists(blog_log_path):
        try:
            with open(blog_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if "Processing buddy:" in line:
                        buddy = line.split("buddy:")[1].split("(")[0].strip()
                        intel.append({"source": "Blog Crawler", "msg": f"Node {buddy} scanning..."})
                        if len(intel) >= 2: break
        except: pass
    
    if os.path.exists(tg_log_path):
        try:
            with open(tg_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if "Finished:" in line:
                        chan = line.split("Finished:")[1].strip()
                        intel.append({"source": "Telegram Sync", "msg": f"Channel {chan} secured."})
                    if len(intel) >= 4: break
        except: pass
    return intel

def update_html():
    b_comp, b_total, b_pct = get_blog_progress()
    t_comp, t_total, t_pct = get_tg_progress()
    intel = get_latest_intel()
    
    # Global Progress: Weighted average
    # Blog 40%, TG 40%, Premium 10%, Quant 10%
    global_pct = round((b_pct * 0.4) + (t_pct * 0.4) + (4.8 * 0.1), 1)

    if not os.path.exists(index_html_path):
        return

    with open(index_html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Global Sync
    content = re.sub(r'id="global-progress-bar".*?style="width:.*?"', f'id="global-progress-bar" class="bg-gradient-to-r from-emerald-600 to-emerald-400 h-full shadow-[0_0_10px_#10b981]" style="width: {global_pct}%"', content)
    content = re.sub(r'id="global-progress-pct".*?>.*?<', f'id="global-progress-pct" class="text-xs font-mono font-bold text-emerald-400">{global_pct}%<', content)

    # 2. Detail Progress (Regex fix: allow attributes between id and >)
    content = re.sub(r'id="blog-pct-detail".*?>.*?<', f'id="blog-pct-detail" class="text-emerald-400 font-mono text-xs">{b_pct}% ({b_comp}/{b_total})<', content)
    content = re.sub(r'id="blog-bar".*?style="width:.*?"', f'id="blog-bar" class="bg-emerald-500 h-full shadow-[0_0_15px_#10b981]" style="width: {b_pct}%"', content)
    
    content = re.sub(r'id="tg-pct-detail".*?>.*?<', f'id="tg-pct-detail" class="text-blue-400 font-mono text-xs">{t_pct}% ({t_comp}/{t_total})<', content)
    content = re.sub(r'id="tg-bar".*?style="width:.*?"', f'id="tg-bar" class="bg-blue-500 h-full shadow-[0_0_10px_#3b82f6]" style="width: {t_pct}%"', content)

    # 3. Intel Feed
    feed_html = ""
    for item in intel:
        color = "emerald-500" if "Blog" in item['source'] else "blue-500"
        ts = datetime.now().strftime('%H:%M')
        feed_html += f"""
                        <div class="flex space-x-3">
                            <div class="w-1 h-10 bg-{color} rounded-full"></div>
                            <div>
                                <p class="text-[10px] text-slate-500 font-bold uppercase">{ts} KST · {item['source']}</p>
                                <p class="text-xs text-white font-semibold">{item['msg']}</p>
                            </div>
                        </div>"""
    
    start_marker = '<!-- Intel Feed Start -->'
    end_marker = '<!-- Intel Feed End -->'
    if start_marker in content and end_marker in content:
        parts = content.split(start_marker)
        rest = parts[1].split(end_marker)
        content = parts[0] + start_marker + feed_html + "\n                        " + end_marker + rest[1]

    with open(index_html_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    update_html()
