# RULES_INDEX.md (Single Source Map)

목적: 규율 파일이 많아 보여도 어디를 기준으로 볼지 1장으로 고정.
충돌 시 컨텍스트/로드 정책 SSOT는 `docs/openclaw/CONTEXT_MANIFEST.json`을 우선한다.

## 1) 절대 기준 (항상)
1. `AGENTS.md` — 운영 게이트/우선순위/완료 게이트
2. DIRECTIVES SSOT — `runtime/directives/directives.db` + `scripts/directives/db.py` + `scripts/directives/gate.py` (`DIRECTIVES.md`는 usage index)
3. TASKS SSOT — `runtime/tasks/tasks.db` + `scripts/tasks/db.py` + `scripts/tasks/gate.py` (`TASKS.md`는 usage index)

## 2) L2 보조 규칙 (필요 시)
- `MEMORY.md` — MAIN 1:1 세션에서만 로드하는 핵심 원칙/보안/트레이딩 안전
- `docs/openclaw/BRAINS.md` — 2뇌 역할 분업
- `HEARTBEAT.md` — 헬스체크 루프
- `docs/CONTRIBUTING.md` — Git/PR 운영

## 3) 사용자/페르소나
- `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md`

## 4) 지금 읽는 최소 셋
- 빠른 운영: `AGENTS.md + DIRECTIVES.md + TASKS.md`
- 메모리 필요 시: `memory/YYYY-MM-DD.md` (오늘 only)
- 핵심 장기 원칙 필요 시: `MEMORY.md` (MAIN 세션 only)
- 모델/폴백 기준 확인 시: `BRAINS.md`

## 5) 정리 원칙
- 규칙은 새 파일 추가보다 기존 canonical 정리를 우선
- 중복 규칙 발견 시 원문 1곳만 남기고 나머지는 참조로 치환
- 대규모 삭제(백업/스냅샷)는 경로 단위 승인 후 실행
