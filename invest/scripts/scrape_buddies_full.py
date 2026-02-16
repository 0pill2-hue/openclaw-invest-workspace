import json
import time
import os

def get_buddy_list(browser_tool):
    buddies = []
    base_url = "https://admin.blog.naver.com/BuddyListManage.naver?blogId=0pill2&currentPage="
    
    for page in range(1, 65):
        url = base_url + str(page)
        print(f"Scraping page {page}...")
        
        # Navigate to the page
        res = browser_tool(action='open', profile='openclaw', targetUrl=url)
        time.sleep(2) # Wait for page load
        
        # Take a snapshot to extract links
        snap = browser_tool(action='snapshot', profile='openclaw', targetId=res['targetId'])
        
        # Extraction logic
        for line in snap.split('\n'):
            if 'https://blog.naver.com/' in line:
                try:
                    parts = line.split('url: ')
                    if len(parts) > 1:
                        raw_url = parts[1].strip().strip('"').strip("'")
                        if raw_url.startswith('https://blog.naver.com/') and '?' not in raw_url:
                            blog_id = raw_url.split('/')[-1]
                            if blog_id and blog_id not in [b['id'] for b in buddies]:
                                buddies.append({'id': blog_id, 'url': raw_url})
                except:
                    continue
        
        if page % 10 == 0:
            print(f"Total buddies so far: {len(buddies)}")
            
    return buddies

# This will be used in an exec context with helper
