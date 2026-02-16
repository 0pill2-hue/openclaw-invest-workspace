import time
import os
import json

def scrape_buddy_list(browser_tool, target_id):
    all_buddies = []
    # Loop through roughly 64 pages (10 per page for 633 buddies)
    for page in range(1, 65):
        url = f"https://admin.blog.naver.com/BuddyListManage.naver?blogId=0pill2&currentPage={page}"
        print(f"Scraping page {page}...")
        
        # Navigate to page
        browser_tool(action='open', profile='openclaw', targetUrl=url)
        time.sleep(1.5) # Wait for load
        
        # Snapshot to get the buddy list
        snap = browser_tool(action='snapshot', profile='openclaw', targetId=target_id)
        
        # Extract blog IDs and names
        # Look for pattern: cell "이웃" [ref=...] followed by cell with name and link
        # Simplified: look for https://blog.naver.com/ID
        found_on_page = 0
        for line in snap.split('\n'):
            if 'https://blog.naver.com/' in line and 'url:' in line:
                try:
                    url_part = line.split('url: ')[1].strip().strip('"').strip("'")
                    if url_part.startswith('https://blog.naver.com/') and '?' not in url_part:
                        blog_id = url_part.split('/')[-1]
                        if blog_id and blog_id not in [b['id'] for b in all_buddies]:
                            all_buddies.append({'id': blog_id, 'url': url_part})
                            found_on_page += 1
                except:
                    continue
        print(f"Found {found_on_page} new buddies on page {page}.")
        
        # Periodic save
        if page % 5 == 0:
            with open('invest/data/master/naver_buddies.json', 'w', encoding='utf-8') as f:
                json.dump(all_buddies, f, ensure_ascii=False, indent=2)

    with open('invest/data/master/naver_buddies.json', 'w', encoding='utf-8') as f:
        json.dump(all_buddies, f, ensure_ascii=False, indent=2)
    return len(all_buddies)
