#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
VENV_PYTHON = WORKSPACE / '.venv' / 'bin' / 'python'
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

import browser_cookie3
from playwright.sync_api import sync_playwright

CHATGPT_DOMAINS = ("chatgpt.com", "openai.com", "auth.openai.com")
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROJECT_NAME = "시스템트래이딩 알고리즘"
DEFAULT_PROJECT_URL = "https://chatgpt.com/g/g-p-69b0acc3f4348191a6a5f8f10a7d77ad-siseutemteuraeiding-algorijeum"


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


def main():
    ap = argparse.ArgumentParser(description="Send a prompt inside the system-trading ChatGPT project.")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--project-url", default=DEFAULT_PROJECT_URL)
    ap.add_argument("--project-name", default=DEFAULT_PROJECT_NAME)
    ap.add_argument("--chrome-path", default=DEFAULT_CHROME)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--screenshot", default="")
    args = ap.parse_args()

    prompt = Path(args.prompt_file).read_text()
    cookies = load_cookies()
    result = {"ok": False, "project_name": args.project_name, "project_url": args.project_url, "cookie_count": len(cookies)}
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
        page.goto(args.project_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(6000)

        body = page.locator("body").inner_text(timeout=5000) or ""
        if args.project_name not in body:
            result["error"] = "project_not_visible"
            result["title"] = page.title()
            result["body_sample"] = body[:1500]
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 2

        # Count visible project chats; best-effort only
        try:
            items = page.locator("article")
            result["visible_articles_before"] = items.count()
        except Exception:
            pass

        # Create new chat from inside project page
        try:
            newchat = page.get_by_text(re.compile(r'^새 채팅$|^New chat$', re.I))
            if newchat.count() > 0:
                newchat.first.click(timeout=3000)
                page.wait_for_timeout(2500)
        except Exception:
            pass

        body2 = page.locator("body").inner_text(timeout=5000) or ""
        if args.project_name not in body2:
            result["error"] = "project_context_lost_after_new_chat"
            result["title"] = page.title()
            result["body_sample"] = body2[:1500]
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 3

        composer = None
        for sel in ['#prompt-textarea', 'textarea', '[contenteditable="true"]']:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                composer = loc.first
                composer.click(timeout=3000)
                break
        if composer is None:
            result["error"] = "composer_not_found"
            result["title"] = page.title()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 4

        try:
            composer.fill(prompt, timeout=8000)
        except Exception:
            page.keyboard.type(prompt)
        page.keyboard.press('Enter')
        page.wait_for_timeout(3000)

        result["ok"] = True
        result["conversation_url"] = page.url
        result["title"] = page.title()
        result["project_confirmed"] = args.project_name in (page.locator("body").inner_text(timeout=5000) or "")
        if args.screenshot:
            shot = Path(args.screenshot)
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot), full_page=True)
        browser.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
