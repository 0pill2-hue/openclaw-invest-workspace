import json
import os
import time

def extract_buddies_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_buddies_to_file(buddies, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(buddies, f, ensure_ascii=False, indent=2)

def extract_from_snapshot(snapshot_text, buddies):
    existing_ids = {b['id'] for b in buddies}
    new_count = 0
    for line in snapshot_text.split('\n'):
        if 'https://blog.naver.com/' in line and 'url:' in line:
            try:
                url = line.split('url: ')[1].strip().strip('"').strip("'")
                if url.startswith('https://blog.naver.com/') and '?' not in url:
                    blog_id = url.split('/')[-1]
                    if blog_id and blog_id not in existing_ids:
                        buddies.append({'id': blog_id, 'url': url})
                        existing_ids.add(blog_id)
                        new_count += 1
            except:
                continue
    return new_count

def run_scrape_batch(browser_tool, start_page, end_page):
    buddy_file = 'invest/data/master/naver_buddies.json'
    buddies = extract_buddies_from_file(buddy_file)
    
    for page in range(start_page, end_page + 1):
        url = f"https://admin.blog.naver.com/BuddyListManage.naver?blogId=0pill2&currentPage={page}"
        print(f"Opening page {page}...")
        res = browser_tool(action='open', profile='openclaw', targetUrl=url)
        time.sleep(2)
        snap = browser_tool(action='snapshot', profile='openclaw', targetId=res['targetId'])
        new_found = extract_from_snapshot(snap, buddies)
        print(f"Page {page}: Found {new_found} new buddies.")
        save_buddies_to_file(buddies, buddy_file)
    
    return len(buddies)
