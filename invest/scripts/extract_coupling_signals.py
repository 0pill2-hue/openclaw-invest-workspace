import os
import json
import re

# Paths
posts_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/alternative/blog_posts'
premium_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/alternative/premium_contents/startale'
tg_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/alternative/telegram_logs'
output_file = '/Users/jobiseu/.openclaw/workspace/invest/data/master/coupling_map_raw.json'

# Target Keywords for Supply Chain
keywords = ["납품", "공급", "수혜", "밸류체인", "공급망", "파트너", "채택", "독점", "벤더"]

def scan_files():
    found_relations = []
    
    # Collect all file paths
    all_files = []
    for root, dirs, files in os.walk(posts_dir):
        for f in files:
            if f.endswith('.md'): all_files.append(os.path.join(root, f))
    for root, dirs, files in os.walk(premium_dir):
        for f in files:
            if f.endswith('.md'): all_files.append(os.path.join(root, f))
    for root, dirs, files in os.walk(tg_dir):
        for f in files:
            if f.endswith('.md'): all_files.append(os.path.join(root, f))

    print(f"Scanning {len(all_files)} files for coupling signals...")

    for fpath in all_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Simple logic to find lines with keywords
                lines = content.split('\n')
                for line in lines:
                    if any(kw in line for kw in keywords):
                        found_relations.append({
                            "source": os.path.basename(fpath),
                            "text": line.strip()[:200] # Limit length
                        })
        except:
            continue

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(found_relations, f, ensure_ascii=False, indent=2)
    
    print(f"Extracted {len(found_relations)} raw coupling signals to {output_file}")

if __name__ == "__main__":
    scan_files()
