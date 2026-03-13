# JB-20260312-WEB-REVIEW-SOURCE-OF-TRUTH

## Goal
web-review skill의 정본(source-of-truth)을 workspace 안으로 옮기고, `~/.agents/skills/web-review`는 runtime 배포본으로 고정한다.

## Applied
- `skills/web-review/` 경로를 정본으로 생성하고 기존 runtime skill 내용을 복제했다.
- `scripts/skills/sync_web_review_skill.sh`를 추가해 source -> runtime 동기화 경로를 고정했다.
- `skills/web-review/SKILL.md`를 수정해 source/deploy 관계를 명시하고, 스크립트 참조를 상대경로(`scripts/...`)로 바꿨다.
- `docs/operations/skills/README.md`와 `docs/operations/skills/web-review.md`에 workspace 정본 / runtime 배포본 구조를 반영했다.
- 동기화 스크립트를 실제 실행해 `~/.agents/skills/web-review`까지 반영했다.

## Verification
- `bash scripts/skills/sync_web_review_skill.sh`

## Proof
- `skills/web-review/SKILL.md`
- `skills/web-review/scripts/watch_chatgpt_response.py`
- `skills/web-review/scripts/ack_watch_event.py`
- `skills/web-review/scripts/escalate_unreported_watch_events.py`
- `scripts/skills/sync_web_review_skill.sh`
- `docs/operations/skills/README.md`
- `docs/operations/skills/web-review.md`
- `~/.agents/skills/web-review/SKILL.md`
