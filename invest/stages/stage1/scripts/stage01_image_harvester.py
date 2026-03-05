import os
import re
import json
import time
import hashlib
import tempfile
import subprocess
import signal
from datetime import datetime, timezone

import requests

TEXT_DIRS = [
    "invest/stages/stage1/outputs/raw/qualitative/text/telegram",
    "invest/stages/stage1/outputs/raw/qualitative/text/blog",
]

MAP_DIR = "invest/stages/stage1/outputs/raw/qualitative/text/image_map"
OUT_DIR = "invest/stages/stage1/outputs/raw/qualitative/text/images_ocr"
CFG_PATH = "invest/stages/stage1/inputs/config/image_ocr_keywords.json"
SEEN_PATH = "invest/stages/stage1/outputs/raw/qualitative/text/images_ocr/seen_urls.json"

DOWNLOAD_TIMEOUT = int(os.environ.get("IMAGE_DL_TIMEOUT", "15"))
OCR_TIMEOUT = int(os.environ.get("OCR_TIMEOUT", "20"))
MAX_RUNTIME_SEC = int(os.environ.get("IMAGE_HARVEST_MAX_RUNTIME", "2400"))
MAX_FILES_SCAN = int(os.environ.get("IMAGE_HARVEST_MAX_FILES", "5000"))
MAX_MAP_ITEMS = int(os.environ.get("IMAGE_HARVEST_MAX_ITEMS", "500"))

IMG_MD_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
IMG_TAG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s\)\]\'\"]+", re.IGNORECASE)
IMG_EXT_RE = re.compile(r"\.(png|jpe?g|webp|gif|bmp)(\?.*)?$", re.IGNORECASE)
IMAGE_HINT_RE = re.compile(r"(image|img|photo|pic|cdn|media|telegram)", re.IGNORECASE)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
})


def ensure_dir(p):
    """
    Role: ensure_dir 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    os.makedirs(p, exist_ok=True)


def load_keywords():
    """
    Role: load_keywords 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    if not os.path.exists(CFG_PATH):
        return []
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("keywords", [])


def _is_image_url(url: str) -> bool:
    """
    Role: _is_image_url 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    if not url:
        return False
    u = url.strip()
    if u.startswith('//'):
        u = 'https:' + u
    if IMG_EXT_RE.search(u):
        return True
    return IMAGE_HINT_RE.search(u) is not None


def _normalize_url(url: str) -> str:
    """
    Role: _normalize_url 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    u = (url or '').strip()
    if u.startswith('//'):
        u = 'https:' + u
    return u


def build_map():
    """
    Role: build_map 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    ensure_dir(MAP_DIR)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = []
    seen = set()
    scanned_files = 0
    start_ts = time.time()

    for base in TEXT_DIRS:
        if not os.path.exists(base):
            continue
        if scanned_files >= MAX_FILES_SCAN or time.time() - start_ts > MAX_RUNTIME_SEC:
            break
        for root, _, files in os.walk(base):
            if scanned_files >= MAX_FILES_SCAN or time.time() - start_ts > MAX_RUNTIME_SEC:
                break
            for fn in files:
                if scanned_files >= MAX_FILES_SCAN or time.time() - start_ts > MAX_RUNTIME_SEC:
                    break
                if not fn.endswith(".md"):
                    continue
                scanned_files += 1
                if scanned_files >= MAX_FILES_SCAN:
                    print(f"[map] max files reached ({MAX_FILES_SCAN}). stopping scan.", flush=True)
                    break
                if time.time() - start_ts > MAX_RUNTIME_SEC:
                    print(f"[map] max runtime reached ({MAX_RUNTIME_SEC}s). stopping scan.", flush=True)
                    break
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8", errors='ignore') as f:
                        text = f.read()
                except Exception:
                    continue

                candidates = []
                candidates.extend(IMG_MD_RE.findall(text))
                candidates.extend(IMG_TAG_RE.findall(text))
                candidates.extend(URL_RE.findall(text))

                for raw in candidates:
                    u = _normalize_url(raw)
                    if not (u.startswith('http://') or u.startswith('https://')):
                        continue
                    if not _is_image_url(u):
                        continue
                    key = (u, path)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"url": u, "source": path})
                    if len(out) >= MAX_MAP_ITEMS:
                        print(f"[map] max items reached ({MAX_MAP_ITEMS}). stopping scan.", flush=True)
                        break
                if len(out) >= MAX_MAP_ITEMS:
                    break
            if scanned_files >= MAX_FILES_SCAN or len(out) >= MAX_MAP_ITEMS or time.time() - start_ts > MAX_RUNTIME_SEC:
                break

    map_path = os.path.join(MAP_DIR, f"image_map_{ts}.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    stats = {"scanned_files": scanned_files, "mapped_urls": len(out)}
    return map_path, out, stats


def keyword_match(text, keywords):
    """
    Role: keyword_match 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    if not keywords:
        return True
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def hash_url(url):
    """
    Role: hash_url 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def ocr_image(path):
    # Uses tesseract CLI (eng)
    """
    Role: ocr_image 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        out_base = tmp.name
    try:
        subprocess.run(["tesseract", path, out_base, "-l", "eng"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=OCR_TIMEOUT)
        txt_path = out_base + ".txt"
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    finally:
        for p in [out_base + ".txt"]:
            if os.path.exists(p):
                os.remove(p)
    return ""


def _timeout_handler(signum, frame):
    raise TimeoutError("max runtime reached")


def harvest(limit=50):
    """
    Role: harvest 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    ensure_dir(OUT_DIR)
    keywords = load_keywords()
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(MAX_RUNTIME_SEC)
    map_path, items, map_stats = build_map()

    seen = set()
    if os.path.exists(SEEN_PATH):
        try:
            with open(SEEN_PATH, "r", encoding="utf-8") as f:
                seen = set(json.load(f))
        except Exception:
            seen = set()

    processed = 0
    start_ts = time.time()
    for it in items:
        if processed >= limit:
            break
        if time.time() - start_ts > MAX_RUNTIME_SEC:
            print(f"[harvest] max runtime reached ({MAX_RUNTIME_SEC}s). stopping.")
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
            r = SESSION.get(url, timeout=(5, DOWNLOAD_TIMEOUT))
            if r.status_code != 200:
                continue
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
                "ts": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            out_path = os.path.join(OUT_DIR, f"{hash_url(url)}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            processed += 1
            seen.add(url)
            if processed % 5 == 0:
                print(f"[harvest] processed={processed}", flush=True)
            time.sleep(0.7)
        except subprocess.TimeoutExpired:
            print(f"[harvest] OCR timeout: {url}")
            continue
        except requests.exceptions.Timeout:
            print(f"[harvest] download timeout: {url}")
            continue
        except Exception as e:
            print(f"[harvest] error: {url} | {type(e).__name__}")
            continue

    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen)), f, ensure_ascii=False, indent=2)

    signal.alarm(0)
    return {
        "map": map_path,
        "processed": processed,
        "scanned_files": map_stats.get("scanned_files", 0),
        "mapped_urls": map_stats.get("mapped_urls", 0),
    }


if __name__ == "__main__":
    try:
        result = harvest(limit=50)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except TimeoutError:
        print("[harvest] HARD TIMEOUT reached. exiting.")
        raise SystemExit(2)
