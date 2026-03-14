# JB-20260313-WEB-REVIEW-CLOUDFLARE-FALLBACK

## landed
- `skills/web-review/SKILL.md` common orchestration rules에 Cloudflare 사람확인 대응 규칙을 추가했다.
  - headless 실행이 `잠시만 기다리십시오…` / `사람인지 확인하십시오` 같은 challenge page에 걸리면 selector/auth/project failure로 오진하지 말고 browser-mode gate로 처리
  - 이 경우 fail-closed 유지
  - screenshot/JSON 증빙을 남긴 뒤 `--headful` 로 재시도
- `docs/operations/skills/web-review.md` overview/operator memo에도 동일 운영 메모를 짧게 반영했다.
- `bash scripts/skills/sync_web_review_skill.sh` 로 runtime copy(`~/.agents/skills/web-review`)까지 동기화했다.

## why_here
- canonical 위치는 `skills/web-review/SKILL.md` 이다.
- 운영자가 나중에 overview에서 바로 찾을 수 있게 `docs/operations/skills/web-review.md` 에는 짧은 mirror 메모만 유지했다.

## proof
- `skills/web-review/SKILL.md`
- `docs/operations/skills/web-review.md`
- `runtime/tasks/JB-20260313-WEB-REVIEW-CLOUDFLARE-FALLBACK.md`
- sync command: `bash scripts/skills/sync_web_review_skill.sh`
