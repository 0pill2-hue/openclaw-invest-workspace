# JB-20260311-CHROME-SESSION-REUSE

- status: READY_FOR_REVIEW
- started_at: 2026-03-11 17:56 KST
- updated_at: 2026-03-11 18:02 KST
- close_recommendation: DONE

## goal
- Chrome에 로그인되어 있는 ChatGPT 웹 세션을 Playwright 자동화가 재사용할 수 있게 연결하고, 접근 테스트를 수행한다.

## result
- `Chrome 프로필 복제본 직접 재사용` 경로는 실패했다.
- 하지만 `실제 Chrome 쿠키를 읽어 새 브라우저 컨텍스트에 주입`하는 경로는 성공했다.
- 따라서 웹검토 자동화용 실사용 경로는 확보됐다.

## findings
1. Google Chrome app path 확인:
   - `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
2. Chrome user data root 확인:
   - `~/Library/Application Support/Google/Chrome`
3. profile 확인:
   - `Default`
   - `Profile 1`
4. ChatGPT/OpenAI session cookie는 `Default` 프로필에 존재했고 `Profile 1`에는 없었다.
5. 복제본 profile launch는 Cloudflare 대기/로그인 비활성 상태만 보여 세션 재사용에 실패했다.
6. `browser-cookie3`로 원본 Chrome 쿠키를 읽어 Playwright context에 주입한 뒤, headful Google Chrome으로 `https://chatgpt.com/` 접근 시 로그인된 ChatGPT 홈이 열렸다.

## working path
- read cookies from live Chrome profile (`Default`)
- inject cookies into Playwright browser context
- use real Google Chrome executable in headful mode
- then navigate to ChatGPT web and operate within authenticated session

## proof
- task report: `runtime/tasks/JB-20260311-CHROME-SESSION-REUSE.md`
- cookie-injected screenshot: `runtime/browser-profiles/cookie_injected_chatgpt.png`
- earlier failed probes:
  - `runtime/browser-profiles/default_chatgpt_probe.png`
  - `runtime/browser-profiles/profile1_chatgpt_probe.png`

## key observed success signal
- page title: `ChatGPT`
- body sample contained authenticated UI elements/history, including prior chats and `Pro` / model UI.

## notes
- 복제본 프로필 방식은 안전하지만 ChatGPT authenticated session을 보존하지 못했다.
- 실사용 경로는 `쿠키 읽기 -> context 주입`이므로 원본 프로필 자체를 직접 launch/lock 할 필요가 없다.
- ChatGPT 웹에서 자동조작이 필요한 경우에도 먼저 headful + cookie-injected session으로 진행하는 것이 안전하다.
