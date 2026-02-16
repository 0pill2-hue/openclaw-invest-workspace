import subprocess
import json
import time

all_buddies = []
for page in range(1, 14):
    url = f"https://admin.blog.naver.com/BuddyListManage.naver?blogId=0pill2&currentPage={page}"
    print(f"Scraping page {page}...")
    subprocess.run(["openclaw", "browser", "open", "--browser-profile", "openclaw", url])
    time.sleep(3)
    
    cmd = ["openclaw", "browser", "evaluate", "--browser-profile", "openclaw", "--fn", "() => Array.from(document.querySelectorAll('a[href*=\"blog.naver.com/\"]')).map(a => a.href).filter(h => h.split('/').length === 4 && !h.includes('?'))"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        urls = json.loads(result.stdout.strip())
        for u in urls:
            bid = u.split('/')[-1]
            if bid and bid not in [b['id'] for b in all_buddies] and bid != '0pill2':
                all_buddies.append({'id': bid, 'url': u})
    except:
        print(f"Failed to parse page {page}")

with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/naver_buddies_full.json', 'w', encoding='utf-8') as f:
    json.dump(all_buddies, f, ensure_ascii=False, indent=2)

print(f"Total buddies found: {len(all_buddies)}")
