import json
import time
import os

def extract_buddies(snapshot):
    buddies = []
    # Find links that look like blog links in the buddy management table
    # Based on previous snapshot, buddy names are in links
    for line in snapshot.split('\n'):
        if 'https://blog.naver.com/' in line:
            # Simple extraction from the snapshot text format
            try:
                parts = line.split('url: ')
                if len(parts) > 1:
                    url = parts[1].strip().strip('"').strip("'")
                    # Naver blog URLs are typically https://blog.naver.com/ID
                    if url.startswith('https://blog.naver.com/') and '?' not in url:
                        blog_id = url.split('/')[-1]
                        if blog_id and blog_id not in [b['id'] for b in buddies]:
                            buddies.append({'id': blog_id, 'url': url})
            except:
                continue
    return buddies

# This script will be called with snapshots
