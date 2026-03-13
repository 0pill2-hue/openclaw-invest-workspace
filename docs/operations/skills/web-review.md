# web-review

역할: **ChatGPT Pro 웹 검토 스킬의 사람용 개요 문서**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

## 핵심
`web-review`는 ChatGPT Pro 웹을 외부 검토 비교군으로 사용할 때 쓰는 스킬이다.

이 문서는 개요만 담고,
**정본(source-of-truth)은 `workspace/skills/web-review/` 아래에 둔다.**
실제 런타임에서 읽히는 것은 `~/.agents/skills/web-review/SKILL.md` 배포본이며,
그 내용은 workspace 정본에서 동기화한다.
즉 여기 내용을 길게 복제해서 source-of-truth를 둘로 만들지 않는다.

## 언제 쓰는가
- 코드/문서/변경사항을 ChatGPT Pro 웹에서 한 번 더 검토하고 싶을 때
- 외부 비교군 의견을 짧은 JSON 형식으로 받고 싶을 때
- 직접 파일 첨부 또는 fresh chat 기반 ChatGPT Pro 검토가 필요할 때

## 현재 운영 핵심만 요약
- GitHub 최신 commit/hash 기준으로 baseline을 고정한다.
- 이전 대화/컨텍스트를 무시하도록 prompt에 명시한다.
- 답변은 짧은 JSON/코드블록 위주로 받는다.
- 웹 답변을 바로 적용하지 않고 먼저 조비스가 판단한다.
- direct attachment가 많으면 fresh chat 기준 20파일 이하로 나눈다.
- 전송이 막히면 `Enter -> Meta+Enter` 순으로 본다.
- watcher는 verdict token뿐 아니라 JSON-shaped 응답도 완료로 본다.
- watcher 완료는 바로 끝내지 말고 `runtime/watch/unreported_watch_events.json` 미보고 큐에 적재한다.
- watcher는 가능하면 기존 ticket(`--task-id` 또는 event/result 안의 ticket id)으로 즉시 note/proof를 동기화한다.
- 기존 ticket을 못 찾으면 fallback watcher task를 즉시 등록하고, stale queue backfill도 같은 규칙을 쓴다.

## 템플릿 문서
- `docs/operations/skills/web-review-templates.md`

## 설명 문서와 runtime의 관계
- 이 문서: 사람이 읽는 개요/설명
- `skills/web-review/`: Git 관리 정본 source
- `~/.agents/skills/web-review/`: OpenClaw가 읽는 runtime 배포본
- task 문서: historical proof

## sync
- source -> runtime 동기화: `bash scripts/skills/sync_web_review_skill.sh`

## watch completion queue
- queue 파일: `runtime/watch/unreported_watch_events.json`
- watcher 기록: `python3 scripts/watch_chatgpt_response.py --output-json <result.json> --record-unreported-queue --task-id <ticket-id-when-known> --event-id <stable-id>`
- 보고 후 ack: `python3 scripts/ack_watch_event.py --event-id <stable-id>`
- 미보고 승격: `python3 scripts/escalate_unreported_watch_events.py --older-than-seconds 90`

## historical proof
- `runtime/tasks/JB-20260311-WEB-REVIEW-SKILL.md`
- `runtime/tasks/JB-20260311-WEB-REVIEW-SKILL-TEMPLATE.md`
- `runtime/tasks/JB-20260311-CHROME-SESSION-REUSE.md`
