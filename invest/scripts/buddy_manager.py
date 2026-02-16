import json
import os

buddy_file = 'invest/data/master/naver_buddies.json'

def load_buddies():
    if os.path.exists(buddy_file):
        with open(buddy_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_buddies(buddies):
    with open(buddy_file, 'w', encoding='utf-8') as f:
        json.dump(buddies, f, ensure_ascii=False, indent=2)

def extract_from_snapshot(snapshot_text):
    buddies = load_buddies()
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
    
    save_buddies(buddies)
    return len(buddies), new_count
