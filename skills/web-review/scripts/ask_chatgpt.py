#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path('/Users/jobiseu/.openclaw/workspace')
VENV_PYTHON = WORKSPACE / '.venv' / 'bin' / 'python'
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

SCRIPT_DIR = Path(__file__).resolve().parent
NEW_CHAT_SENDER = SCRIPT_DIR / 'send_chatgpt_new_chat_prompt.py'
PROJECT_SENDER = SCRIPT_DIR / 'send_chatgpt_project_prompt.py'
WATCHER = SCRIPT_DIR / 'watch_chatgpt_response.py'
DEFAULT_CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


def parse_json_block(text: str):
    text = (text or '').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != '{':
            continue
        try:
            obj, end = decoder.raw_decode(text[idx:])
            tail = text[idx + end :].strip()
            if not tail:
                return obj
        except Exception:
            continue
    return None


def write_json(path: str, payload):
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run_json_command(cmd):
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True)
    payload = parse_json_block(proc.stdout)
    if payload is None:
        payload = parse_json_block(proc.stderr)
    return proc, payload


def build_sender_command(args, sender_screenshot: str):
    prompt_file = str(Path(args.prompt_file).expanduser().resolve())
    cmd = [sys.executable]
    if args.sender_mode == 'project':
        cmd.extend([
            str(PROJECT_SENDER),
            '--prompt-file', prompt_file,
            '--chrome-path', args.chrome_path,
            '--post-send-wait-seconds', str(args.post_send_wait_seconds),
            '--project-url', args.project_url,
            '--project-name', args.project_name,
            '--max-project-chats', str(args.max_project_chats),
        ])
        if args.cleanup_dry_run:
            cmd.append('--cleanup-dry-run')
    else:
        cmd.extend([
            str(NEW_CHAT_SENDER),
            '--prompt-file', prompt_file,
            '--chrome-path', args.chrome_path,
            '--upload-timeout-seconds', str(args.upload_timeout_seconds),
            '--post-send-wait-seconds', str(args.post_send_wait_seconds),
        ])
        if args.model_target:
            cmd.extend(['--model-target', args.model_target])
        if args.skip_model_selection:
            cmd.append('--skip-model-selection')
    if args.headful:
        cmd.append('--headful')
    if sender_screenshot:
        cmd.extend(['--screenshot', sender_screenshot])
    for item in args.attach_file:
        cmd.extend(['--attach-file', str(Path(item).expanduser().resolve())])
    for item in args.attach_list_file:
        cmd.extend(['--attach-list-file', str(Path(item).expanduser().resolve())])
    return cmd


def build_watcher_command(args, conversation_url: str, watch_output_json: str, watch_screenshot: str):
    cmd = [
        sys.executable,
        str(WATCHER),
        '--url', conversation_url,
        '--timeout-seconds', str(args.watch_timeout_seconds),
        '--poll-seconds', str(args.poll_seconds),
        '--chrome-path', args.chrome_path,
    ]
    if args.headful:
        cmd.append('--headful')
    if args.require_json:
        cmd.append('--require-json')
    if args.delete_after:
        cmd.append('--delete-after')
    if args.record_unreported_queue:
        cmd.append('--record-unreported-queue')
    if args.skip_task_start_sync:
        cmd.append('--skip-task-start-sync')
    if args.queue_file:
        cmd.extend(['--queue-file', str(Path(args.queue_file).expanduser().resolve())])
    if args.event_id:
        cmd.extend(['--event-id', args.event_id])
    if args.task_id:
        cmd.extend(['--task-id', args.task_id])
    if args.callback_token:
        cmd.extend(['--callback-token', args.callback_token])
    if watch_output_json:
        cmd.extend(['--output-json', watch_output_json])
    if watch_screenshot:
        cmd.extend(['--screenshot', watch_screenshot])
    return cmd


def main():
    ap = argparse.ArgumentParser(description='Thin wrapper over the existing ChatGPT web-review send/watch scripts.')
    ap.add_argument('--prompt-file', required=True)
    ap.add_argument('--attach-file', action='append', default=[])
    ap.add_argument('--attach-list-file', action='append', default=[])
    ap.add_argument('--sender-mode', choices=['new_chat', 'project'], default='project')
    ap.add_argument('--watch', action='store_true')
    ap.add_argument('--watch-timeout-seconds', type=int, default=900)
    ap.add_argument('--poll-seconds', type=int, default=15)
    ap.add_argument('--upload-timeout-seconds', type=int, default=180)
    ap.add_argument('--post-send-wait-seconds', type=int, default=5)
    ap.add_argument('--headful', action='store_true')
    ap.add_argument('--chrome-path', default=DEFAULT_CHROME)
    ap.add_argument('--model-target', default='Thinking 5.4')
    ap.add_argument('--skip-model-selection', action='store_true')
    ap.add_argument('--require-json', action='store_true')
    ap.add_argument('--delete-after', action='store_true')
    ap.add_argument('--record-unreported-queue', action='store_true')
    ap.add_argument('--queue-file', default='')
    ap.add_argument('--task-id', default='')
    ap.add_argument('--event-id', default='')
    ap.add_argument('--callback-token', default='')
    ap.add_argument('--skip-task-start-sync', action='store_true')
    ap.add_argument('--send-output-json', default='')
    ap.add_argument('--watch-output-json', default='')
    ap.add_argument('--output-json', default='')
    ap.add_argument('--screenshot-base', default='')
    ap.add_argument('--project-url', default=os.environ.get('OPENCLAW_CHATGPT_PROJECT_URL', 'https://chatgpt.com/g/g-p-69b3a95600208191aa7035d4da89a6c7-siseutemteureiding-modelgaebal/project'))
    ap.add_argument('--project-name', default=os.environ.get('OPENCLAW_CHATGPT_PROJECT_NAME', '시스템트레이딩 모델개발'))
    ap.add_argument('--max-project-chats', type=int, default=5)
    ap.add_argument('--cleanup-dry-run', action='store_true')
    args = ap.parse_args()

    screenshot_base = str(Path(args.screenshot_base).expanduser().resolve()) if args.screenshot_base else ''
    sender_screenshot = f'{screenshot_base}_send.png' if screenshot_base else ''
    watcher_screenshot = f'{screenshot_base}_watch.png' if screenshot_base else ''
    send_output_json = str(Path(args.send_output_json).expanduser().resolve()) if args.send_output_json else ''
    watch_output_json = str(Path(args.watch_output_json).expanduser().resolve()) if args.watch_output_json else ''
    output_json = str(Path(args.output_json).expanduser().resolve()) if args.output_json else ''

    result = {
        'ok': False,
        'sender_mode': args.sender_mode,
        'watch_requested': bool(args.watch),
        'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'prompt_file': str(Path(args.prompt_file).expanduser().resolve()),
        'attach_files': [str(Path(p).expanduser().resolve()) for p in args.attach_file],
        'attach_list_files': [str(Path(p).expanduser().resolve()) for p in args.attach_list_file],
    }

    sender_cmd = build_sender_command(args, sender_screenshot)
    result['sender_command'] = sender_cmd
    sender_proc, sender_payload = run_json_command(sender_cmd)
    result['sender_returncode'] = sender_proc.returncode
    result['sender_stdout'] = (sender_proc.stdout or '').strip()[:2000]
    result['sender_stderr'] = (sender_proc.stderr or '').strip()[:2000]
    result['sender_result'] = sender_payload
    if sender_payload is not None and send_output_json:
        write_json(send_output_json, sender_payload)

    if sender_proc.returncode != 0 or not isinstance(sender_payload, dict) or not sender_payload.get('ok'):
        result['error'] = 'sender_failed'
        result['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        write_json(output_json, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    conversation_url = str(sender_payload.get('conversation_url') or '').strip()
    result['conversation_url'] = conversation_url
    if not args.watch:
        result['ok'] = True
        result['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        write_json(output_json, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not conversation_url:
        result['error'] = 'conversation_url_missing'
        result['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        write_json(output_json, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3

    watcher_cmd = build_watcher_command(args, conversation_url, watch_output_json, watcher_screenshot)
    result['watch_command'] = watcher_cmd
    watcher_proc, watcher_payload = run_json_command(watcher_cmd)
    result['watch_returncode'] = watcher_proc.returncode
    result['watch_stdout'] = (watcher_proc.stdout or '').strip()[:2000]
    result['watch_stderr'] = (watcher_proc.stderr or '').strip()[:2000]
    result['watch_result'] = watcher_payload

    if watcher_payload is None and watch_output_json and Path(watch_output_json).exists():
        try:
            watcher_payload = json.loads(Path(watch_output_json).read_text(encoding='utf-8'))
            result['watch_result'] = watcher_payload
        except Exception:
            pass

    if isinstance(watcher_payload, dict):
        recovered_json = parse_json_block(watcher_payload.get('json_text') or watcher_payload.get('body_sample') or '')
        if recovered_json is not None and not watcher_payload.get('json_text'):
            watcher_payload['json_text'] = json.dumps(recovered_json, ensure_ascii=False)
        if recovered_json is not None and not watcher_payload.get('ok'):
            watcher_payload['ok'] = True
            watcher_payload['status'] = 'complete_json_recovered'
            watcher_payload['recovered_via_wrapper'] = 'body_sample_json'
        if watch_output_json:
            write_json(watch_output_json, watcher_payload)
        result['conversation_url'] = str(watcher_payload.get('url') or watcher_payload.get('conversation_url') or conversation_url)
        result['response_text'] = watcher_payload.get('json_text') or ''

    result['ok'] = isinstance(watcher_payload, dict) and watcher_payload.get('ok')
    if not result['ok']:
        result['error'] = 'watcher_failed'
    result['finished_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    write_json(output_json, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 4


if __name__ == '__main__':
    raise SystemExit(main())
