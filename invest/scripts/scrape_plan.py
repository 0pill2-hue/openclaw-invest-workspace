import json
import os
import time

def extract_buddies_from_snapshot(snapshot_text, buddies, existing_ids):
    new_count = 0
    for line in snapshot_text.split('\n'):
        if 'https://blog.naver.com/' in line and 'url:' in line:
            try:
                url = line.split('url: ')[1].strip().strip('"').strip("'")
                if url.startswith('https://blog.naver.com/') and '?' not in url:
                    blog_id = url.split('/')[-1]
                    if blog_id not in existing_ids:
                        buddies.append({'id': blog_id, 'url': url})
                        existing_ids.add(blog_id)
                        new_count += 1
            except: continue
    return new_count

def run():
    # Load current buddies
    buddy_file = 'invest/data/master/naver_buddies.json'
    buddies = []
    if os.path.exists(buddy_file):
        with open(buddy_file, 'r', encoding='utf-8') as f: buddies = json.load(f)
    existing_ids = {b['id'] for b in buddies}

    # Pages to scrape (skip 1 and 11 as done)
    pages = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13]
    
    # We'll use the browser tool manually via consecutive calls in the main flow 
    # instead of a script that calls the tool, to ensure reliability.
    pass

if __name__ == "__main__":
    run()
