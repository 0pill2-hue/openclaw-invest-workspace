# JB-20260313-CHATGPT-PROJECT-SENDER-HARDEN

- ticket: JB-20260313-CHATGPT-PROJECT-SENDER-HARDEN
- status: DONE
- checked_at: 2026-03-13 19:57 KST

## Goal
ChatGPT 웹 자동 전송이 앞으로도 `시스템트레이딩 모델개발` 프로젝트 내부에서만 실행되도록 sender를 고정/강화한다.

## Landed
- `skills/web-review/scripts/send_chatgpt_project_prompt.py` 기본 프로젝트를 `시스템트레이딩 모델개발`로 교체했다.
- 기본 프로젝트 URL을 실제 프로젝트 경로(`/project`)로 고정했다.
- `새 채팅` 버튼 의존 로직을 제거했다.
- 프로젝트 페이지 자체 입력창에서만 전송하도록 수정했다.
- 전송 후 URL이 반드시 프로젝트 내부 채팅(`/g/.../c/...`)인지 검증하고, 아니면 성공 처리하지 않도록 강화했다.
- `OPENCLAW_CHATGPT_PROJECT_URL`, `OPENCLAW_CHATGPT_PROJECT_NAME` env override도 지원하게 했다.

## Verification
- `python3 -m py_compile skills/web-review/scripts/send_chatgpt_project_prompt.py`
- 실제 sender 실행 성공
  - project confirmed: true
  - project_internal_chat_confirmed: true
  - conversation_url: `https://chatgpt.com/g/g-p-69b3a95600208191aa7035d4da89a6c7-siseutemteureiding-modelgaebal/c/69b3ee28-70c0-83a3-808a-643d38e14c44`

## Proof
- `skills/web-review/scripts/send_chatgpt_project_prompt.py`
- `runtime/tmp/chatgpt-project-hi-hardened.png`
