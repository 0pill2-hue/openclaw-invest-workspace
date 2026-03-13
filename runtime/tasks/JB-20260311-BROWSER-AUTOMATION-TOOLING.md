# JB-20260311-BROWSER-AUTOMATION-TOOLING

- status: READY_FOR_REVIEW
- started_at: 2026-03-11 17:45 KST
- updated_at: 2026-03-11 17:47 KST
- close_recommendation: DONE

## accomplished
1. workspace `.venv`에 Playwright Python 패키지를 설치했다.
   - version: `1.58.0`
2. Playwright managed browser를 설치했다.
   - Chromium
   - FFmpeg
   - Chrome Headless Shell
3. 최소 브라우저 자동화 실행 검증을 통과했다.
   - headless browser launch OK
   - page load OK
   - DOM read OK

## baseline findings
- 기존 `/opt/homebrew/bin/chromium` wrapper는 `/Applications/Chromium.app/...`를 가리키지만 실제 app이 없어 실행 불가였다.
- 따라서 Homebrew wrapper 경로 대신 Playwright managed browser를 설치하는 쪽으로 정리했다.

## verification
### install
- `.venv/bin/python -m pip install playwright`
- `.venv/bin/playwright install chromium`

### run proof
```bash
.venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('data:text/html,<title>ok</title><h1>browser-ok</h1>')
    print({'title': page.title(), 'h1': page.locator('h1').text_content()})
    browser.close()
PY
```
- result: `{'title': 'ok', 'h1': 'browser-ok'}`

## notes
- 지금부터는 브라우저 자동화 자체는 가능하다.
- 다만 ChatGPT Pro 웹 로그인 세션을 실제로 자동 재사용하려면, 주인님이 로그인해 둔 프로필을 어떤 방식으로 연결할지(전용 프로필/기존 프로필)만 정하면 된다.
- 현재 설치 작업 범위는 도구 설치 + 실행 검증까지다.
