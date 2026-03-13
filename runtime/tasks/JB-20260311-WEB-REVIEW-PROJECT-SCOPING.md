# JB-20260311-WEB-REVIEW-PROJECT-SCOPING

- status: READY_FOR_REVIEW
- started_at: 2026-03-11 20:24 KST
- updated_at: 2026-03-11 20:41 KST
- close_recommendation: DONE

## accomplished
1. `web-review` skill에 대상 프로젝트를 **시스템트레이딩 알고리즘**으로 고정했다.
2. 프로젝트 밖으로 보내지 않도록 hard rule을 추가했다.
3. 전송용 스크립트 `send_chatgpt_project_prompt.py`를 추가해:
   - 고정 프로젝트 URL로 진입
   - 프로젝트 이름이 화면에서 확인될 때만 전송
   - 프로젝트 컨텍스트가 확인되지 않으면 실패하도록 만들었다.
4. 실제 전송 테스트에서 아래가 확인됐다:
   - `ok: true`
   - `project_name: 시스템트레이딩 알고리즘`
   - `project_confirmed: true`
   - conversation URL 생성 성공

## proof
- `/Users/jobiseu/.agents/skills/web-review/SKILL.md`
- `/Users/jobiseu/.agents/skills/web-review/scripts/send_chatgpt_project_prompt.py`
- `runtime/browser-profiles/web_review_stage12_send.png`
- `runtime/tasks/JB-20260311-WEB-REVIEW-PROJECT-SCOPING.md`
