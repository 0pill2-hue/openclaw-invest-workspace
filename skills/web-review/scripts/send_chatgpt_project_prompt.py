#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
VENV_PYTHON = WORKSPACE / '.venv' / 'bin' / 'python'
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

import browser_cookie3
from playwright.sync_api import sync_playwright

CHATGPT_DOMAINS = ("chatgpt.com", "openai.com", "auth.openai.com")
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROJECT_NAME = "시스템트레이딩 모델개발"
DEFAULT_PROJECT_URL = "https://chatgpt.com/g/g-p-69b3a95600208191aa7035d4da89a6c7-siseutemteureiding-modelgaebal/project"
DEFAULT_MAX_PROJECT_CHATS = 5
DEFAULT_MODEL_TARGET = "Thinking 5.4"
UPLOAD_PENDING_PATTERNS = (
    "업로드 중",
    "Uploading",
    "Analyzing",
    "분석 중",
    "processing",
)
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
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


def _project_chat_prefix(project_url: str) -> str:
    return project_url[:-len('/project')] if project_url.endswith('/project') else project_url.rstrip('/')


def _project_chat_path_prefix(project_url: str) -> str:
    return urlparse(_project_chat_prefix(project_url)).path.rstrip('/')


def _conversation_url_ok(url: str, project_chat_prefix: str) -> bool:
    return bool(re.match(rf"^{re.escape(project_chat_prefix)}/c/[0-9a-f\-]+$", url or ''))


def read_page_body(page, timeout: int = 5000) -> str:
    try:
        return page.locator("body").inner_text(timeout=timeout) or ""
    except Exception:
        return ""


def verify_project_context(page, project_name: str, project_url: str) -> dict:
    body = read_page_body(page)
    project_chat_prefix = _project_chat_prefix(project_url)
    loaded_url = page.url
    return {
        "ok": project_name in body and loaded_url.startswith(project_chat_prefix),
        "project_name_visible": project_name in body,
        "loaded_url_matches_prefix": loaded_url.startswith(project_chat_prefix),
        "project_name": project_name,
        "project_url": project_url,
        "project_chat_prefix": project_chat_prefix,
        "loaded_url": loaded_url,
        "title": page.title(),
        "body_sample": body[:1500],
    }


def collect_project_chats(page, project_url: str) -> list[dict]:
    project_chat_prefix = _project_chat_prefix(project_url)
    return page.evaluate(
        """
(conversationPrefix) => {
  const normalize = (href) => {
    try {
      return new URL(href, window.location.origin).toString();
    } catch {
      return '';
    }
  };
  const rows = [];
  const seen = new Set();
  for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
    const absoluteHref = normalize(anchor.getAttribute('href') || anchor.href || '');
    if (!absoluteHref.startsWith(conversationPrefix + '/c/')) continue;
    const row = anchor.closest('li');
    if (!row) continue;
    const menuButton = row.querySelector('button[data-conversation-options-trigger]');
    if (!menuButton) continue;
    const conversationId = (menuButton.getAttribute('data-conversation-options-trigger') || '').trim();
    if (!conversationId || seen.has(conversationId)) continue;
    seen.add(conversationId);
    const titleEl = row.querySelector('.text-sm.font-medium') || anchor.querySelector('.text-sm.font-medium');
    const previewEl = row.querySelector('.text-token-text-secondary') || anchor.querySelector('.text-token-text-secondary');
    const dateEl = row.querySelector('[data-testid="project-conversation-overflow-date"]');
    rows.push({
      position: rows.length,
      conversation_id: conversationId,
      href: absoluteHref,
      raw_href: anchor.getAttribute('href') || '',
      title: (titleEl?.textContent || anchor.getAttribute('aria-label') || anchor.textContent || '').trim(),
      preview: (previewEl?.textContent || '').trim().slice(0, 400),
      date_text: (dateEl?.textContent || '').trim(),
      row_text: (row.innerText || '').trim().slice(0, 600),
    });
  }
  return rows;
}
""",
        project_chat_prefix,
    )


def summarize_project_chats(rows: list[dict]) -> list[dict]:
    return [
        {
            "position": row.get("position"),
            "conversation_id": row.get("conversation_id"),
            "title": row.get("title"),
            "date_text": row.get("date_text"),
            "href": row.get("href"),
        }
        for row in rows
    ]


def plan_overflow_cleanup(existing_rows: list[dict], max_keep: int) -> dict:
    limit = max(1, int(max_keep))
    overflow_if_send = max(0, len(existing_rows) + 1 - limit)
    delete_candidates = existing_rows[-overflow_if_send:] if overflow_if_send else []
    kept_existing = existing_rows[: max(0, limit - 1)]
    return {
        "max_keep": limit,
        "existing_count": len(existing_rows),
        "current_overflow_without_send": max(0, len(existing_rows) - limit),
        "overflow_if_send": overflow_if_send,
        "kept_existing_after_send": summarize_project_chats(kept_existing),
        "delete_candidates_after_send": summarize_project_chats(delete_candidates),
        "delete_candidate_ids_after_send": [row.get("conversation_id") for row in delete_candidates],
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
    body = read_page_body(page, timeout=3000)
    if not body:
        return False
    if any(pat.lower() in body.lower() for pat in UPLOAD_PENDING_PATTERNS):
        return False

    non_image_names = [name for name in names if Path(name).suffix.lower() not in IMAGE_SUFFIXES]
    if non_image_names and not all(name in body for name in non_image_names):
        return False

    if all(name in body for name in names):
        return True

    remove_selectors = [
        'button[aria-label="파일 제거"]',
        'button[aria-label="Remove file"]',
        'button[aria-label*="remove"]',
        'button[aria-label*="Remove"]',
    ]
    for sel in remove_selectors:
        try:
            remove_buttons = page.locator(sel).count()
            if remove_buttons >= len(names):
                return True
        except Exception:
            continue

    return bool(non_image_names)


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


def wait_for_project_internal_chat_url(page, project_chat_prefix: str, timeout_seconds: int) -> bool:
    deadline = time.time() + max(timeout_seconds, 0)
    while time.time() < deadline:
        if _conversation_url_ok(page.url, project_chat_prefix):
            return True
        page.wait_for_timeout(250)
    return _conversation_url_ok(page.url, project_chat_prefix)


def try_send(page, project_chat_prefix: str, wait_seconds: int):
    attempts = []

    def snapshot(label):
        attempts.append({
            'label': label,
            'url': page.url,
            'title': page.title(),
        })

    page.keyboard.press('Enter')
    page.wait_for_timeout(wait_seconds * 1000)
    snapshot('enter')
    if _conversation_url_ok(page.url, project_chat_prefix):
        return True, attempts

    page.keyboard.press('Meta+Enter')
    page.wait_for_timeout(wait_seconds * 1000)
    snapshot('meta_enter')
    if _conversation_url_ok(page.url, project_chat_prefix):
        return True, attempts

    send_selectors = [
        'button[data-testid="send-button"]',
        'button[aria-label="Send prompt"]',
        'button[aria-label="메시지 보내기"]',
        'button[type="submit"]',
    ]
    for sel in send_selectors:
        loc = page.locator(sel)
        if loc.count() <= 0:
            continue
        try:
            btn = loc.first
            if btn.is_visible() and btn.is_enabled():
                btn.click(timeout=3000)
                page.wait_for_timeout(wait_seconds * 1000)
                snapshot(f'click:{sel}')
                if _conversation_url_ok(page.url, project_chat_prefix):
                    return True, attempts
        except Exception:
            continue

    return False, attempts


def click_project_chat_menu(page, project_url: str, conversation_id: str) -> bool:
    project_chat_prefix = _project_chat_prefix(project_url)
    buttons = page.locator(f'button[data-conversation-options-trigger="{conversation_id}"]')
    count = buttons.count()
    for idx in range(count):
        btn = buttons.nth(idx)
        try:
            anchor_href = btn.evaluate(
                """
(el) => {
  const row = el.closest('li');
  const anchor = row ? row.querySelector('a[href]') : null;
  if (!anchor) return '';
  try {
    return new URL(anchor.getAttribute('href') || anchor.href || '', window.location.origin).toString();
  } catch {
    return '';
  }
}
"""
            )
        except Exception:
            continue
        if not anchor_href.startswith(project_chat_prefix + '/c/'):
            continue
        try:
            btn.click(force=True, timeout=5000)
            return True
        except Exception:
            continue
    return False


def delete_project_chat(page, project_url: str, conversation: dict) -> dict:
    result = {
        "conversation_id": conversation.get("conversation_id"),
        "title": conversation.get("title"),
        "href": conversation.get("href"),
        "ok": False,
    }
    if not click_project_chat_menu(page, project_url, conversation.get("conversation_id", "")):
        result["error"] = "project_chat_menu_not_found"
        return result

    page.wait_for_timeout(500)
    menu_delete = None
    for text in ['삭제', 'Delete']:
        loc = page.get_by_text(text, exact=True)
        if loc.count() > 0 and loc.first.is_visible():
            menu_delete = loc.first
            break
    if menu_delete is None:
        result["error"] = "project_chat_delete_menu_item_not_found"
        return result

    menu_delete.click(timeout=3000)
    page.wait_for_timeout(500)

    confirm = page.locator('[data-testid="delete-conversation-confirm-button"]')
    if confirm.count() <= 0 or not confirm.first.is_visible():
        result["error"] = "delete_confirm_button_not_found"
        return result
    confirm.first.click(timeout=3000)

    deadline = time.time() + 12
    while time.time() < deadline:
        page.wait_for_timeout(500)
        rows = collect_project_chats(page, project_url)
        if all(row.get("conversation_id") != conversation.get("conversation_id") for row in rows):
            result["ok"] = True
            result["remaining_count"] = len(rows)
            return result

    result["error"] = "delete_not_reflected_in_project_list"
    return result


def execute_project_chat_cleanup(page, project_name: str, project_url: str, planned_ids: list[str], dry_run: bool) -> dict:
    cleanup = {
        "attempted": False,
        "dry_run": bool(dry_run),
        "target_ids": planned_ids,
        "ok": True,
        "status": "not_needed",
        "deleted": [],
        "errors": [],
    }
    if not planned_ids:
        return cleanup

    cleanup["attempted"] = True
    page.goto(project_url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(6000)

    guard = verify_project_context(page, project_name, project_url)
    cleanup["guard"] = guard
    if not guard.get("ok"):
        cleanup["ok"] = False
        cleanup["status"] = "guard_failed"
        cleanup["errors"].append("project_guard_failed_before_cleanup")
        return cleanup

    current_rows = collect_project_chats(page, project_url)
    cleanup["current_project_chat_count"] = len(current_rows)
    cleanup["current_project_chats"] = summarize_project_chats(current_rows)

    target_set = set(planned_ids)
    targets = [row for row in current_rows if row.get("conversation_id") in target_set]
    cleanup["matched_targets"] = summarize_project_chats(targets)
    cleanup["missing_target_ids"] = [cid for cid in planned_ids if cid not in {row.get('conversation_id') for row in targets}]

    if dry_run:
        cleanup["status"] = "dry_run"
        cleanup["final_project_chat_count"] = len(current_rows)
        return cleanup

    for target in reversed(targets):
        delete_result = delete_project_chat(page, project_url, target)
        if delete_result.get("ok"):
            cleanup["deleted"].append(delete_result)
        else:
            cleanup["ok"] = False
            cleanup["errors"].append(delete_result)

    final_rows = collect_project_chats(page, project_url)
    cleanup["final_project_chat_count"] = len(final_rows)
    cleanup["final_project_chats"] = summarize_project_chats(final_rows)
    cleanup["status"] = "deleted" if cleanup["ok"] else "partial_failure"
    return cleanup


def maybe_capture_screenshot(page, screenshot_path: str):
    if not screenshot_path:
        return
    shot = Path(screenshot_path)
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=True)


def main():
    ap = argparse.ArgumentParser(description="Send a prompt inside the fixed system-trading ChatGPT project.")
    ap.add_argument("--prompt-file", default="")
    ap.add_argument("--attach-file", action="append", default=[])
    ap.add_argument("--attach-list-file", action="append", default=[])
    ap.add_argument("--project-url", default=os.environ.get("OPENCLAW_CHATGPT_PROJECT_URL", DEFAULT_PROJECT_URL))
    ap.add_argument("--project-name", default=os.environ.get("OPENCLAW_CHATGPT_PROJECT_NAME", DEFAULT_PROJECT_NAME))
    ap.add_argument("--chrome-path", default=DEFAULT_CHROME)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--screenshot", default="")
    ap.add_argument("--max-project-chats", type=int, default=DEFAULT_MAX_PROJECT_CHATS)
    ap.add_argument("--cleanup-dry-run", action="store_true", help="Plan project-internal overflow deletion but do not actually delete chats")
    ap.add_argument("--verify-only", action="store_true", help="Verify project page/chat discovery and cleanup plan without sending a prompt")
    ap.add_argument("--post-send-wait-seconds", type=int, default=5)
    ap.add_argument("--upload-timeout-seconds", type=int, default=180)
    ap.add_argument("--model-target", default=DEFAULT_MODEL_TARGET)
    ap.add_argument("--skip-model-selection", action="store_true")
    args = ap.parse_args()

    result = {
        "ok": False,
        "project_name": args.project_name,
        "project_url": args.project_url,
        "max_project_chats": max(1, int(args.max_project_chats)),
        "cleanup_dry_run": bool(args.cleanup_dry_run),
        "verify_only": bool(args.verify_only),
    }

    if not args.verify_only and not args.prompt_file:
        result["error"] = "prompt_file_required"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    prompt = Path(args.prompt_file).read_text() if args.prompt_file else ""
    attachment_paths = load_attachment_paths(args)
    cookies = load_cookies()
    result["cookie_count"] = len(cookies)
    result["files"] = len(attachment_paths)
    result["attachment_names"] = [p.name for p in attachment_paths]
    result["model_target"] = None if args.skip_model_selection else args.model_target
    if not cookies:
        result["error"] = "no_cookies"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    project_chat_prefix = _project_chat_prefix(args.project_url)
    project_chat_path_prefix = _project_chat_path_prefix(args.project_url)
    result["project_chat_prefix"] = project_chat_prefix
    result["project_chat_path_prefix"] = project_chat_path_prefix

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

        project_guard = verify_project_context(page, args.project_name, args.project_url)
        result["project_guard_before_send"] = project_guard
        if not project_guard.get("project_name_visible"):
            result["error"] = "project_not_visible"
            maybe_capture_screenshot(page, args.screenshot)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 2
        if not project_guard.get("loaded_url_matches_prefix"):
            result["error"] = "project_url_not_loaded"
            maybe_capture_screenshot(page, args.screenshot)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 3

        project_chats = collect_project_chats(page, args.project_url)
        result["project_chat_count_before_send"] = len(project_chats)
        result["project_chats_before_send"] = summarize_project_chats(project_chats)
        result["project_chat_cleanup_plan"] = plan_overflow_cleanup(project_chats, args.max_project_chats)

        if args.verify_only:
            result["ok"] = True
            result["status"] = "verified_project_chat_cleanup_plan"
            maybe_capture_screenshot(page, args.screenshot)
            browser.close()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        result["pre_send_model_text"] = current_model_text(page)
        if not args.skip_model_selection:
            result["model_selection"] = ensure_model(page, args.model_target)
            result["model_selected"] = current_model_text(page)
            if not result["model_selection"].get("ok"):
                result["error"] = "model_selection_failed"
                result["title"] = page.title()
                maybe_capture_screenshot(page, args.screenshot)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                browser.close()
                return 4

        composer = find_composer(page)
        if composer is None:
            result["error"] = "composer_not_found_on_project_page"
            result["title"] = page.title()
            result["loaded_url"] = page.url
            maybe_capture_screenshot(page, args.screenshot)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 5

        if attachment_paths:
            chooser = open_native_attach(page)
            if chooser is None:
                result["error"] = "native_attach_menu_not_found"
                result["title"] = page.title()
                maybe_capture_screenshot(page, args.screenshot)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                browser.close()
                return 6
            chooser.set_files([str(p) for p in attachment_paths])
            result["attachments_visible"] = wait_for_attachments(page, attachment_paths, args.upload_timeout_seconds)
            if not result["attachments_visible"]:
                result["error"] = "attachment_visibility_timeout"
                result["title"] = page.title()
                result["body_sample"] = read_page_body(page)[:2000]
                maybe_capture_screenshot(page, args.screenshot)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                browser.close()
                return 7

        try:
            composer.fill(prompt, timeout=8000)
        except Exception:
            page.keyboard.type(prompt)

        sent, attempts = try_send(page, project_chat_prefix, max(args.post_send_wait_seconds, 1))
        result["send_attempts"] = attempts

        if not sent and not wait_for_project_internal_chat_url(page, project_chat_prefix, max(args.post_send_wait_seconds, 1)):
            result["error"] = "send_not_confirmed"
            result["title"] = page.title()
            result["loaded_url"] = page.url
            result["expected_prefix"] = project_chat_prefix + "/c/..."
            maybe_capture_screenshot(page, args.screenshot)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 8

        final_body = read_page_body(page)
        final_url = page.url
        result["conversation_url"] = final_url
        result["title"] = page.title()
        result["project_confirmed_after_send"] = args.project_name in final_body
        result["project_internal_chat_confirmed"] = _conversation_url_ok(final_url, project_chat_prefix)
        result["body_sample"] = final_body[:1500]

        if not result["project_internal_chat_confirmed"]:
            result["error"] = "not_project_internal_chat_url"
            result["expected_prefix"] = project_chat_prefix + "/c/..."
            maybe_capture_screenshot(page, args.screenshot)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
            return 9

        cleanup_plan = result["project_chat_cleanup_plan"]
        cleanup_result = execute_project_chat_cleanup(
            page,
            project_name=args.project_name,
            project_url=args.project_url,
            planned_ids=cleanup_plan.get("delete_candidate_ids_after_send", []),
            dry_run=args.cleanup_dry_run,
        )
        result["project_chat_cleanup"] = cleanup_result

        result["ok"] = True
        result["status"] = "sent"
        maybe_capture_screenshot(page, args.screenshot)
        browser.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
