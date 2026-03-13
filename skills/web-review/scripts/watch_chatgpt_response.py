#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
VENV_PYTHON = WORKSPACE / '.venv' / 'bin' / 'python'
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

import browser_cookie3
from playwright.sync_api import sync_playwright

from sync_watch_event_to_task import sync_event_to_task

PENDING_PATTERNS = [
    re.compile(r"응답을 생성 중입니다"),
    re.compile(r"생각 중"),
    re.compile(r"thinking", re.I),
    re.compile(r"just a moment", re.I),
    re.compile(r"analyzing", re.I),
    re.compile(r"processing", re.I),
]
VERDICT_PATTERNS = [
    re.compile(r"\bAPPLY\b"),
    re.compile(r"\bREJECT\b"),
    re.compile(r"\bNEED_MORE_CONTEXT\b"),
]
ASSISTANT_HINT_PATTERNS = [
    re.compile(r"chatgpt의 말[:：]?", re.I),
    re.compile(r"chatgpt says[:：]?", re.I),
]
INTRO_PATTERNS = [
    re.compile(r"먼저 .*확인한 뒤", re.I),
    re.compile(r"읽어서 .*반환하겠습니다", re.I),
    re.compile(r"json만 반환하겠습니다", re.I),
    re.compile(r"i(?:'|’)ll .*return", re.I),
    re.compile(r"i will .*return", re.I),
]
CHATGPT_DOMAINS = ("chatgpt.com", "openai.com", "auth.openai.com")
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_QUEUE_FILE = WORKSPACE / 'runtime' / 'watch' / 'unreported_watch_events.json'
TASK_EVENT_CLI = WORKSPACE / 'scripts' / 'tasks' / 'record_task_event.py'


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


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


def has_pending(text: str) -> bool:
    lower = text.lower()
    return any(p.search(text) for p in PENDING_PATTERNS) or "chatgpt의 말:" in text and "응답을 생성 중입니다" in text or "chatgpt says" in lower and "thinking" in lower


def extract_verdict(text: str):
    for p in VERDICT_PATTERNS:
        m = p.search(text)
        if m:
            return m.group(0)
    return None


def is_assistant_text(text: str) -> bool:
    return any(p.search(text) for p in ASSISTANT_HINT_PATTERNS)


def looks_like_intro_only(text: str) -> bool:
    if not text or looks_like_json_payload(text):
        return False
    return any(p.search(text) for p in INTRO_PATTERNS)


def extract_json_candidate(text: str):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.S | re.I)
        if m:
            candidate = m.group(1).strip()
            try:
                return json.dumps(json.loads(candidate), ensure_ascii=False)
            except Exception:
                pass
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.dumps(json.loads(stripped), ensure_ascii=False)
        except Exception:
            pass

    decoder = json.JSONDecoder()
    start_positions = [m.start() for m in re.finditer(r"\{", text)]
    for start in start_positions:
        try:
            obj, end = decoder.raw_decode(text[start:])
            tail = text[start + end :].strip()
            if not tail or tail in {"```", "```json"}:
                return json.dumps(obj, ensure_ascii=False)
        except Exception:
            continue
    return None


def looks_like_json_payload(text: str) -> bool:
    return extract_json_candidate(text) is not None


def looks_like_jsonish_text(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    required_markers = [
        '"contract_version"',
        '"baseline"',
        '"items"',
    ]
    return all(marker in stripped for marker in required_markers)


def get_last_assistant_text(page):
    try:
        items = page.locator('[data-message-author-role="assistant"]')
        count = items.count()
        for idx in range(count - 1, -1, -1):
            text = items.nth(idx).inner_text(timeout=5000) or ""
            if text.strip():
                return text
    except Exception:
        pass

    try:
        articles = page.locator("article")
        count = articles.count()
        for idx in range(count - 1, -1, -1):
            text = articles.nth(idx).inner_text(timeout=5000) or ""
            if is_assistant_text(text):
                return text
    except Exception:
        pass

    return ""


def delete_current_chat(page):
    menu_selectors = [
        'button[aria-label*="More"]',
        'button[aria-label*="더보기"]',
        'button:has-text("More")',
        'button:has-text("더보기")',
        '[data-testid="conversation-actions-button"]',
    ]
    for sel in menu_selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=2000)
                page.wait_for_timeout(800)
                break
        except Exception:
            pass
    for txt in ['Delete', '삭제']:
        try:
            loc = page.get_by_text(txt, exact=True)
            if loc.count() > 0:
                loc.first.click(timeout=2000)
                page.wait_for_timeout(800)
                break
        except Exception:
            pass
    for txt in ['Delete', '삭제', '확인', 'Confirm']:
        try:
            loc = page.get_by_text(txt, exact=True)
            if loc.count() > 0:
                loc.first.click(timeout=2000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass
    return False


def load_queue(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "events": []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {"version": 1, "events": []}
    if not isinstance(data, dict):
        return {"version": 1, "events": []}
    events = data.get('events')
    if not isinstance(events, list):
        data['events'] = []
    data.setdefault('version', 1)
    return data


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')


def derive_event_id(result: dict, explicit_event_id: str = '', output_json: str = '') -> str:
    explicit = (explicit_event_id or '').strip()
    if explicit:
        return explicit
    output_path = (output_json or '').strip()
    if output_path:
        return Path(output_path).stem
    basis = '|'.join([
        str(result.get('url') or ''),
        str(result.get('status') or ''),
        str(result.get('title') or ''),
        str(result.get('last_assistant_length') or ''),
    ])
    return 'watch-' + hashlib.sha1(basis.encode('utf-8')).hexdigest()[:12]


def record_unreported_event(*, result: dict, queue_file: Path, event_id: str, output_json: str = '', follow_up_required: bool = False, explicit_task_id: str = '') -> dict:
    queue = load_queue(queue_file)
    events = queue.setdefault('events', [])
    now = utc_now_iso()
    existing = None
    for item in events:
        if str(item.get('id') or '') == event_id:
            existing = item
            break

    event_payload = {
        'id': event_id,
        'kind': 'chatgpt_watch_completion',
        'source': 'web-review',
        'observed_at': existing.get('observed_at') if existing else now,
        'updated_at': now,
        'acked_at': existing.get('acked_at') if existing else None,
        'escalated_at': existing.get('escalated_at') if existing else None,
        'task_id': existing.get('task_id') if existing else None,
        'status': result.get('status'),
        'verdict': result.get('verdict'),
        'url': result.get('url'),
        'title': result.get('title'),
        'result_json_path': output_json or (existing.get('result_json_path') if existing else ''),
        'last_assistant_length': result.get('last_assistant_length'),
        'json_hint': bool(result.get('json_hint')),
        'follow_up_required': bool(follow_up_required or (existing.get('follow_up_required') if existing else False)),
    }

    try:
        task_sync = sync_event_to_task(
            event_payload,
            result=result,
            explicit_task_id=explicit_task_id,
            allow_create=True,
            dry_run=False,
        )
        event_payload['task_sync_status'] = task_sync.get('action', '')
        event_payload['task_sync_at'] = task_sync.get('synced_at', '')
        event_payload['task_sync_match'] = task_sync.get('matched_by', '')
        if task_sync.get('task_id'):
            event_payload['task_id'] = task_sync['task_id']
        if task_sync.get('proof_path'):
            event_payload['proof_path'] = task_sync['proof_path']
    except Exception as exc:
        event_payload['task_sync_status'] = 'error'
        event_payload['task_sync_at'] = utc_now_iso()
        event_payload['task_sync_match'] = 'error'
        event_payload['task_sync_error'] = repr(exc)

    if existing is None:
        events.append(event_payload)
    else:
        existing.update(event_payload)

    events.sort(key=lambda item: str(item.get('observed_at') or ''), reverse=True)
    queue['updated_at'] = now
    write_json(queue_file, queue)
    return event_payload


def record_task_start(task_id: str, *, url: str, timeout_seconds: int, poll_seconds: int, output_json: str = '') -> dict:
    cmd = [
        sys.executable,
        str(TASK_EVENT_CLI),
        '--task-id', task_id,
        '--source', 'web-review watcher',
        '--summary', 'ChatGPT DOM watcher started; main should continue other non-conflicting backlog while waiting.',
        '--phase', 'awaiting_callback',
        '--detail', f'url={url}',
        '--detail', f'timeout_seconds={timeout_seconds} poll_seconds={poll_seconds}',
        '--release-assignee',
    ]
    if output_json:
        cmd.extend(['--proof-path', output_json])
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True)
    return {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'stdout': (proc.stdout or '').strip(),
        'stderr': (proc.stderr or '').strip(),
    }


def main():
    ap = argparse.ArgumentParser(description="Watch a ChatGPT web conversation until response completes.")
    ap.add_argument("--url", required=True, help="ChatGPT conversation/project URL to watch")
    ap.add_argument("--timeout-seconds", type=int, default=900)
    ap.add_argument("--poll-seconds", type=int, default=15)
    ap.add_argument("--headful", action="store_true", help="Use visible Chrome instead of headless")
    ap.add_argument("--chrome-path", default=DEFAULT_CHROME)
    ap.add_argument("--screenshot", default="")
    ap.add_argument("--delete-after", action="store_true", help="Delete the conversation after response is captured")
    ap.add_argument("--require-json", action="store_true", help="Only mark complete when the final assistant turn parses as JSON")
    ap.add_argument("--output-json", default="", help="Write the final watcher result JSON to this file")
    ap.add_argument("--record-unreported-queue", action="store_true", help="Append successful completion into the unreported watch-event queue")
    ap.add_argument("--queue-file", default=str(DEFAULT_QUEUE_FILE), help="Queue JSON path for unreported watch events")
    ap.add_argument("--event-id", default="", help="Stable event id for queue upsert; defaults to output-json stem or a URL hash")
    ap.add_argument("--follow-up-required", action="store_true", help="Mark this queue event as requiring follow-up/task escalation")
    ap.add_argument("--task-id", default="", help="Known task/ticket id to sync this watcher completion back into")
    ap.add_argument("--skip-task-start-sync", action="store_true", help="Do not mark awaiting_callback/release assignee at watcher start")
    args = ap.parse_args()

    task_start_sync = {
        'ok': True,
        'skipped': True,
    }
    if args.task_id and not args.skip_task_start_sync:
        task_start_sync = record_task_start(
            args.task_id,
            url=args.url,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            output_json=(args.output_json or '').strip(),
        )

    cookies = load_cookies()
    result = {
        "ok": False,
        "status": "unknown",
        "url": args.url,
        "cookie_count": len(cookies),
        "verdict": None,
        "body_sample": "",
        "title": "",
    }
    if args.task_id:
        result['task_id'] = args.task_id
    if not task_start_sync.get('ok'):
        result['task_start_sync'] = task_start_sync

    if not cookies:
        result["status"] = "no_cookies"
        if args.output_json:
            write_json(Path(args.output_json), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    deadline = time.time() + args.timeout_seconds
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=args.chrome_path,
            headless=not args.headful,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 960})
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=45000)

        stable_without_pending = 0
        while time.time() < deadline:
            page.wait_for_timeout(int(args.poll_seconds * 1000))
            try:
                body = page.locator("body").inner_text(timeout=5000) or ""
            except Exception:
                body = ""
            last_assistant = get_last_assistant_text(page)
            sample_source = last_assistant or body
            result["body_sample"] = sample_source[:3000]
            result["last_assistant_length"] = len(last_assistant or "")
            try:
                result["title"] = page.title()
            except Exception:
                pass

            verdict = extract_verdict(last_assistant)
            if verdict:
                result["ok"] = True
                result["status"] = "complete"
                result["verdict"] = verdict
                json_candidate = extract_json_candidate(last_assistant)
                if json_candidate:
                    result["json_text"] = json_candidate
                break

            json_candidate = extract_json_candidate(last_assistant)
            if json_candidate:
                result["ok"] = True
                result["status"] = "complete_json"
                result["json_text"] = json_candidate
                break

            if looks_like_jsonish_text(last_assistant):
                result["ok"] = True
                result["status"] = "complete_jsonish"
                result["json_hint"] = True
                break

            pending_source = last_assistant or body
            if has_pending(pending_source) or looks_like_intro_only(last_assistant):
                stable_without_pending = 0
                result["status"] = "pending"
                continue

            stable_without_pending += 1
            if not args.require_json and stable_without_pending >= 2:
                result["ok"] = True
                result["status"] = "complete_no_verdict"
                break

        if not result["ok"]:
            result["status"] = "timeout"

        if args.screenshot:
            shot = Path(args.screenshot)
            shot.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(shot), full_page=True)
            except Exception:
                pass
        if args.delete_after and result["ok"]:
            result["deleted"] = delete_current_chat(page)
        browser.close()

    output_json = (args.output_json or '').strip()
    event_id = ''
    if result['ok'] and args.record_unreported_queue:
        event_id = derive_event_id(result, explicit_event_id=args.event_id, output_json=output_json)
        queue_event = record_unreported_event(
            result=result,
            queue_file=Path(args.queue_file),
            event_id=event_id,
            output_json=output_json,
            follow_up_required=args.follow_up_required,
            explicit_task_id=args.task_id,
        )
        result['queue_recorded'] = True
        result['queue_file'] = str(Path(args.queue_file))
        result['event_id'] = queue_event['id']
        if queue_event.get('task_id'):
            result['task_id'] = queue_event['task_id']
        if queue_event.get('proof_path'):
            result['proof_path'] = queue_event['proof_path']
        if queue_event.get('task_sync_status'):
            result['task_sync_status'] = queue_event['task_sync_status']
            result['task_sync_match'] = queue_event.get('task_sync_match', '')
    elif args.event_id:
        result['event_id'] = args.event_id

    if output_json:
        write_json(Path(output_json), result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
