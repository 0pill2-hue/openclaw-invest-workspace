# JB-20260311-WEB-REVIEW-DOM-WATCHER

- status: READY_FOR_REVIEW
- started_at: 2026-03-11 19:10 KST
- close_recommendation: DONE

## accomplished
- `web-review` skill에 DOM watcher 운영 규약을 추가했다.
- 번들 스크립트 `scripts/watch_chatgpt_response.py`를 추가했다.
- 이 스크립트는 Chrome ChatGPT 쿠키를 읽고, 대상 대화 URL DOM을 polling하여 응답 완료/평결 token(APPLY/REJECT/NEED_MORE_CONTEXT)을 감지한다.
- 스킬 문서에 "질문 전송 후 대기하지 말고 watcher를 돌리면서 다른 일 진행" 규약을 추가했다.

## proof
- `/Users/jobiseu/.agents/skills/web-review/SKILL.md`
- `/Users/jobiseu/.agents/skills/web-review/scripts/watch_chatgpt_response.py`
- `runtime/tasks/JB-20260311-WEB-REVIEW-DOM-WATCHER.md`
