# JB-20260311-WEB-REVIEW-WATCHER-FALSE-POSITIVE report

## 결론
- close_status: PENDING_MAIN
- close_recommendation: DONE
- summary: `watch_chatgpt_response.py`의 verdict 판정을 전체 body/마지막 article 기준이 아니라 마지막 assistant-side 메시지 기준으로 제한해, 사용자 프롬프트에 포함된 `APPLY`/`REJECT`/`NEED_MORE_CONTEXT` echo로 인한 false positive를 막았습니다.

## 변경 사항
- 파일: `/Users/jobiseu/.agents/skills/web-review/scripts/watch_chatgpt_response.py`
- 추가: assistant 힌트 패턴(`ChatGPT의 말`, `ChatGPT says`) 및 `get_last_assistant_text()`
- 변경: verdict 추출 대상을 `last_assistant`로 제한
- 유지: pending 판정은 assistant 메시지가 있으면 그것을 우선 사용하고, 없으면 기존처럼 body fallback을 사용

## 검증 노트
- fake page 검증에서 user article에 `Please answer with one of APPLY / REJECT / NEED_MORE_CONTEXT only.`를 넣고,
  assistant article을 `ChatGPT says\nThinking about the repo diff…`로 둔 경우:
  - `extract_verdict(last_assistant) == None`
  - `has_pending(last_assistant) == True`
- 같은 조건에서 assistant article을 `ChatGPT says\nREJECT\nReason: insufficient evidence.`로 바꾼 경우:
  - `extract_verdict(last_assistant) == 'REJECT'`
- 즉, user prompt echo의 verdict 토큰은 더 이상 최종 판정으로 오인되지 않고, 마지막 assistant 메시지에 있는 verdict만 채택됩니다.

## 비고
- taskdb 상태 전이는 수행하지 않았습니다.

## Proof paths
- `/Users/jobiseu/.agents/skills/web-review/scripts/watch_chatgpt_response.py`
- `/Users/jobiseu/.openclaw/workspace/runtime/tasks/JB-20260311-WEB-REVIEW-WATCHER-FALSE-POSITIVE.md`
