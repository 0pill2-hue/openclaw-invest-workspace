# SKILLS

역할: **스킬 설명 인덱스**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

이 문서는 사람이 읽는 스킬 설명의 진입점만 담당한다.
세부 실행 규칙을 이 문서에 길게 복제하지 않는다.

## 원칙
- `docs/operations/` 문서는 **사람용 설명/탐색 문서**다.
- Git 관리되는 **정본(source-of-truth)** 은 `workspace/skills/<skill-name>/` 아래에 둔다.
- 실제 runtime 동작의 최신 내용은 **`~/.agents/skills/<skill-name>/SKILL.md` 배포본**을 기준으로 보되, 그 내용은 workspace 정본에서 동기화한다.
- 따라서 docs 문서는 얇게 유지하고, 긴 절차/세부 규칙 복제는 피한다.
- 템플릿처럼 사람이 따로 보고 관리할 가치가 있는 내용만 별도 문서로 둔다.
- `runtime/tasks/*.md`는 작업 기록/증빙이며, 스킬 설명 canonical 문서로 쓰지 않는다.

## 스킬 목록
- `docs/operations/skills/web-review.md` — ChatGPT Pro 웹 검토 스킬 개요
- `docs/operations/skills/web-review-templates.md` — web-review 질문/응답 템플릿

## 구조 메모
- `skills/<skill-name>/`: Git 관리 정본 source
- `~/.agents/skills/<skill-name>/`: OpenClaw가 읽는 runtime 배포본
- docs 쪽: 사람이 읽는 설명/인덱스

## historical proof
- `runtime/tasks/JB-20260311-WEB-REVIEW-SKILL.md`
- `runtime/tasks/JB-20260311-WEB-REVIEW-SKILL-TEMPLATE.md`
- `runtime/tasks/JB-20260311-CHROME-SESSION-REUSE.md`
