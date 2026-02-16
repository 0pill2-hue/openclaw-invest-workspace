import os
import re
import json
import time
import hashlib
import tempfile
import subprocess
from datetime import datetime

import requests

TEXT_DIRS = [
    "invest/data/alternative/telegram_logs",
]

MAP_DIR = "invest/data/image_map"
OUT_DIR = "invest/data/images_ocr"
CFG_PATH = "invest/config/image_ocr_keywords.json"
SEEN_PATH = "invest/data/images_ocr/seen_urls.json"

IMG_MD_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
})


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def load_keywords():
    if not os.path.exists(CFG_PATH):
        return []
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("keywords", [])


def build_map():
    ensure_dir(MAP_DIR)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out = []
    for base in TEXT_DIRS:
        if not os.path.exists(base):
            continue
        for root, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception:
                    continue
                for m in IMG_MD_RE.findall(text):
                    out.append({"url": m.strip(), "source": path})
    map_path = os.path.join(MAP_DIR, f"image_map_{ts}.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return map_path, out


def keyword_match(text, keywords):
    if not keywords:
        return True
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def hash_url(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def ocr_image(path):
    # Uses tesseract CLI (eng)
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        out_base = tmp.name
    try:
        subprocess.run(["tesseract", path, out_base, "-l", "eng"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        txt_path = out_base + ".txt"
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    finally:
        for p in [out_base + ".txt"]:
            if os.path.exists(p):
                os.remove(p)
    return ""


def harvest(limit=50):
    ensure_dir(OUT_DIR)
    keywords = load_keywords()
    map_path, items = build_map()

    seen = set()
    if os.path.exists(SEEN_PATH):
        try:
            with open(SEEN_PATH, "r", encoding="utf-8") as f:
                seen = set(json.load(f))
        except Exception:
            seen = set()

    processed = 0
    for it in items:
        if processed >= limit:
            break
        url = it["url"]
        if url in seen:
            continue
        src = it["source"]
        # keyword filter by source text snippet
        try:
            with open(src, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        if not keyword_match(content, keywords):
            continue
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code != 200:
                continue
            # save temp image
            suffix = ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as imgf:
                imgf.write(r.content)
                img_path = imgf.name
            text = ocr_image(img_path)
            os.remove(img_path)
            out = {
                "url": url,
                "source": src,
                "ocr": text,
                "ts": datetime.utcnow().isoformat() + "Z"
            }
            out_path = os.path.join(OUT_DIR, f"{hash_url(url)}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            processed += 1
            seen.add(url)
            time.sleep(0.7)
        except Exception:
            continue

    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen)), f, ensure_ascii=False, indent=2)

    return {"map": map_path, "processed": processed}


if __name__ == "__main__":
    result = harvest(limit=50)
    print(json.dumps(result, ensure_ascii=False, indent=2))
