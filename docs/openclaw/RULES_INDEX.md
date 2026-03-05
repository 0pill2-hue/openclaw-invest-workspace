# RULES_INDEX.md (Single Source Map)

목적: 규율 파일이 많아 보여도 **어디를 기준으로 볼지** 1장으로 고정.

## 1) 절대 기준 (항상)
1. `AGENTS.md` — 운영 게이트/우선순위/완료 게이트
2. `MEMORY.md` — 절대 원칙/보안/트레이딩 안전
3. DIRECTIVES SSOT — `runtime/directives/directives.db` + `scripts/directivesdb.py` + `scripts/directives_gate.py` (`DIRECTIVES.md`는 usage index)
4. TASKS SSOT — `runtime/tasks/tasks.db` + `scripts/taskdb.py` + `scripts/task_gate.py` (`TASKS.md`는 usage index)

## 2) 보조 규칙 (필요 시)
- `BRAINS.md` — 뇌 역할 분업
- `HEARTBEAT.md` — 헬스체크 루프

## 3) 사용자/페르소나
- `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md`

## 4) 지금 읽는 최소 셋
- 빠른 운영: `AGENTS.md + DIRECTIVES.md + TASKS.md` (상태 판정/전이는 각 DB+CLI SSOT 기준)
- 정책 확인 필요 시: `MEMORY.md`
- 모델/스킬 이슈 시: `AGENTS.md`의 Workflow/Skill Rules 확인

## 5) 정리 원칙
- 규칙은 **새 파일 추가 금지**, 위 파일에만 보강
- 중복 규칙 발견 시: 원문 1곳만 남기고 나머지는 링크/참조로 치환
- 대규모 삭제(백업/스냅샷)는 경로 단위 승인 후 실행
