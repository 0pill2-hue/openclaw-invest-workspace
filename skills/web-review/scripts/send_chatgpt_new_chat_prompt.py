#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from pathlib import Path

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
VENV_PYTHON = WORKSPACE / '.venv' / 'bin' / 'python'
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

import browser_cookie3
from playwright.sync_api import sync_playwright

CHATGPT_DOMAINS = ("chatgpt.com", "openai.com", "auth.openai.com")
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_HOME_URL = "https://chatgpt.com/"
DEFAULT_MODEL_TARGET = "Thinking 5.4"
UPLOAD_PENDING_PATTERNS = (
    "업로드 중",
    "Uploading",
    "Analyzing",
    "분석 중",
    "processing",
)
MODEL_SELECTOR_SELECTORS = (
    'button[aria-label^="모델 선택기"]',
    'button[aria-label^="Model selector"]',
    '[data-testid="model-switcher-dropdown-button"]',
)


def load_cookies():
    cookies = []
    for c in browser_cookie3.chrome():
        if any(k in c.domain for k in CHATGPT_DOMAINS):
            item = {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path or "/",
                "secure": bool(c.secure),
            }
            if c.expires and c.expires > 0:
                item["expires"] = int(c.expires)
            cookies.append(item)
    uniq = {}
    for c in cookies:
        uniq[(c["domain"], c["path"], c["name"])] = c
    return list(uniq.values())


def load_attachment_paths(args):
    paths = []
    for raw in args.attach_file or []:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"attachment_not_found:{p}")
        paths.append(p)
    for list_file in args.attach_list_file or []:
        for line in Path(list_file).expanduser().read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            p = Path(line).expanduser().resolve()
            if not p.exists():
                raise FileNotFoundError(f"attachment_not_found:{p}")
            paths.append(p)
    uniq = []
    seen = set()
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def normalize_model_text(text):
    return ' '.join((text or '').replace('-', ' ').replace('_', ' ').lower().split())



def model_matches(text, target):
    target_tokens = [tok for tok in normalize_model_text(target).split() if tok]
    hay = normalize_model_text(text)
    return bool(target_tokens) and all(tok in hay for tok in target_tokens)



def current_model_text(page):
    for sel in MODEL_SELECTOR_SELECTORS:
        loc = page.locator(sel)
        if loc.count() > 0:
            try:
                btn = loc.first
                if btn.is_visible():
                    txt = (btn.inner_text(timeout=1000) or '').strip()
                    if txt:
                        return txt
                    aria = (btn.get_attribute('aria-label') or '').strip()
                    if aria:
                        return aria
            except Exception:
                continue
    return ''



def ensure_model(page, target):
    before = current_model_text(page)
    if model_matches(before, target):
        return {
            'ok': True,
            'target': target,
            'current_before': before,
            'current_after': before,
            'selection_path': 'already_selected',
        }

    opened = False
    for sel in MODEL_SELECTOR_SELECTORS:
        loc = page.locator(sel)
        if loc.count() <= 0:
            continue
        try:
            if loc.first.is_visible():
                loc.first.click(timeout=3000)
                page.wait_for_timeout(1200)
                opened = True
                break
        except Exception:
            continue

    if not opened:
        after = current_model_text(page)
        return {
            'ok': False,
            'target': target,
            'current_before': before,
            'current_after': after,
            'selection_path': 'selector_not_found',
        }

    menu = page.locator('[role="menuitem"], [role="option"], button')
    count = min(menu.count(), 300)
    for i in range(count):
        item = menu.nth(i)
        try:
            if not item.is_visible():
                continue
            text = (item.inner_text(timeout=500) or '').strip()
            if model_matches(text, target):
                item.click(timeout=3000)
                page.wait_for_timeout(1500)
                after = current_model_text(page)
                return {
                    'ok': model_matches(after, target),
                    'target': target,
                    'current_before': before,
                    'current_after': after,
                    'selection_path': f'model_selector -> {target}',
                }
        except Exception:
            continue

    after = current_model_text(page)
    return {
        'ok': model_matches(after, target),
        'target': target,
        'current_before': before,
        'current_after': after,
        'selection_path': 'not_changed',
    }



def find_composer(page):
    for sel in ['#prompt-textarea', '[data-testid="prompt-textarea"]', 'textarea', '[contenteditable="true"]', '[role="textbox"]']:
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click(timeout=3000)
            return loc.first
    return None



def open_native_attach(page):
    trigger_candidates = [
        'button[aria-label="파일 추가 및 기타"]',
        'button[aria-label="Add photos and files"]',
        'button:has-text("파일 추가 및 기타")',
        '[data-testid="composer-plus-btn"]',
    ]
    for sel in trigger_candidates:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=3000)
                page.wait_for_timeout(800)
                break
        except Exception:
            continue

    menu_targets = [
        ('text', '사진 및 파일 추가'),
        ('text', 'Add photos & files'),
        ('text', 'Add photos and files'),
    ]
    for kind, value in menu_targets:
        try:
            if kind == 'text':
                loc = page.get_by_text(value, exact=True)
                if loc.count() > 0:
                    with page.expect_file_chooser(timeout=5000) as fc:
                        loc.first.click(timeout=3000)
                    return fc.value
        except Exception:
            continue
    return None



def attachments_ready(page, names):
    try:
        body = page.locator('body').inner_text(timeout=3000) or ''
    except Exception:
        return False
    if any(pat.lower() in body.lower() for pat in UPLOAD_PENDING_PATTERNS):
        return False
    if not all(name in body for name in names):
        return False
    try:
        remove_buttons = page.locator('button[aria-label="파일 제거"]').count()
        if remove_buttons >= len(names):
            return True
    except Exception:
        pass
    return True



def wait_for_attachments(page, paths, timeout_seconds):
    if not paths:
        return True
    names = [p.name for p in paths]
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if attachments_ready(page, names):
            return True
        page.wait_for_timeout(1000)
    return False



def wait_for_conversation_url(page, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if '/c/' in page.url:
            return True
        page.wait_for_timeout(500)
    return '/c/' in page.url



def main():
    ap = argparse.ArgumentParser(description="Send a prompt in a fresh ChatGPT new chat.")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--attach-file", action="append", default=[])
    ap.add_argument("--attach-list-file", action="append", default=[])
    ap.add_argument("--chrome-path", default=DEFAULT_CHROME)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--screenshot", default="")
    ap.add_argument("--upload-timeout-seconds", type=int, default=180)
    ap.add_argument("--post-send-wait-seconds", type=int, default=5)
    ap.add_argument("--model-target", default=DEFAULT_MODEL_TARGET)
    ap.add_argument("--skip-model-selection", action="store_true")
    args = ap.parse_args()

    prompt = Path(args.prompt_file).read_text()
    attachment_paths = load_attachment_paths(args)
    cookies = load_cookies()
    result = {
        "ok": False,
        "home_url": DEFAULT_HOME_URL,
        "cookie_count": len(cookies),
        "files": len(attachment_paths),
        "attachment_names": [p.name for p in attachment_paths],
        "model_target": None if args.skip_model_selection else args.model_target,
    }
    if not cookies:
        result["error"] = "no_cookies"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=args.chrome_path,
            headless=not args.headful,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 960})
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        page.goto(DEFAULT_HOME_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(6000)

        for text in ["새 채팅", "New chat"]:
            try:
                loc = page.get_by_text(text, exact=True)
                if loc.count() > 0:
                    loc.first.click(timeout=3000)
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        result["pre_send_model_text"] = current_model_text(page)
        if not args.skip_model_selection:
            result["model_selection"] = ensure_model(page, args.model_target)
            result["model_selected"] = current_model_text(page)
            if not result["model_selection"].get("ok"):
                result["error"] = "model_selection_failed"
                result["title"] = page.title()
                if args.screenshot:
                    shot = Path(args.screenshot)
                    shot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shot), full_page=True)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                browser.close()
                return 2

        composer = find_composer(page)
        if composer is None:
            result["error"] = "composer_not_found"
            result["title"] = page.title()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 3

        if attachment_paths:
            chooser = open_native_attach(page)
            if chooser is None:
                result["error"] = "native_attach_menu_not_found"
                result["title"] = page.title()
                print(json.dumps(result, ensure_ascii=False, indent=2))
                browser.close()
                return 4
            chooser.set_files([str(p) for p in attachment_paths])
            result["attachments_visible"] = wait_for_attachments(page, attachment_paths, args.upload_timeout_seconds)
            if not result["attachments_visible"]:
                result["error"] = "attachment_visibility_timeout"
                result["title"] = page.title()
                if args.screenshot:
                    shot = Path(args.screenshot)
                    shot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shot), full_page=True)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                browser.close()
                return 5

        try:
            composer.fill(prompt, timeout=8000)
        except Exception:
            page.keyboard.type(prompt)
        page.keyboard.press('Enter')
        page.wait_for_timeout(max(args.post_send_wait_seconds, 1) * 1000)
        wait_for_conversation_url(page, 15)

        result["ok"] = True
        result["conversation_url"] = page.url
        result["title"] = page.title()
        if args.screenshot:
            shot = Path(args.screenshot)
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot), full_page=True)
        browser.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
