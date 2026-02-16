import subprocess
import json
import time
import os

# Load buddy list
with open('/Users/jobiseu/.openclaw/workspace/invest/data/master/naver_buddies_full.json', 'r', encoding='utf-8') as f:
    buddies = json.load(f)

base_dir = '/Users/jobiseu/.openclaw/workspace/invest/data/alternative/blog_posts'
os.makedirs(base_dir, exist_ok=True)

# Process first 5 buddies as a start to show progress
for buddy in buddies[:5]:
    bid = buddy['id']
    buddy_dir = os.path.join(base_dir, bid)
    os.makedirs(buddy_dir, exist_ok=True)
    
    print(f"Processing buddy: {bid}")
    url = f"https://blog.naver.com/PostList.naver?blogId={bid}&from=postList"
    subprocess.run(["openclaw", "browser", "open", "--browser-profile", "openclaw", url])
    time.sleep(3)
    
    # Extract post list from the frame
    # Note: Naver Blog uses an iframe with id='mainFrame' for content
    # We can try to extract all links that look like post views
    cmd = ["openclaw", "browser", "evaluate", "--browser-profile", "openclaw", "--fn", """
        () => {
            const frame = document.getElementById('mainFrame');
            if (!frame) return [];
            const doc = frame.contentWindow.document;
            const links = Array.from(doc.querySelectorAll('a[href*="/PostView.naver"]'));
            return links.map(a => ({
                title: a.innerText.trim(),
                url: a.href,
                id: a.href.split('logNo=')[1]?.split('&')[0]
            })).filter(p => p.id);
        }
    """]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        posts = json.loads(result.stdout.strip())
        print(f"Found {len(posts)} posts for {bid}")
        
        for post in posts[:3]: # Limit to 3 posts per buddy for now to stay fast
            post_id = post['id']
            post_path = os.path.join(buddy_dir, f"{post_id}.md")
            
            if os.path.exists(post_path):
                continue
                
            print(f"  Scraping post: {post['title']} ({post_id})")
            subprocess.run(["openclaw", "browser", "open", "--browser-profile", "openclaw", post['url']])
            time.sleep(3)
            
            content_cmd = ["openclaw", "browser", "evaluate", "--browser-profile", "openclaw", "--fn", """
                () => {
                    const frame = document.getElementById('mainFrame');
                    if (!frame) return 'Frame not found';
                    const doc = frame.contentWindow.document;
                    const container = doc.querySelector('.se-main-container') || doc.querySelector('#post-view') || doc.body;
                    return container.innerText;
                }
            """]
            content_result = subprocess.run(content_cmd, capture_output=True, text=True)
            
            with open(post_path, 'w', encoding='utf-8') as pf:
                pf.write(content_result.stdout.strip())
    except Exception as e:
        print(f"Failed to process {bid}: {e}")

print("Batch processing complete.")
