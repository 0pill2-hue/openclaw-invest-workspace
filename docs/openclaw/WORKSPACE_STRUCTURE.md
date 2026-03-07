# WORKSPACE_STRUCTURE.md

Last updated: 2026-03-05 KST
Purpose: invest 안/밖 포함 워크스페이스 구조와 문서 배치 기준의 단일 canonical

## 1) Top-level canonical
- `docs/openclaw/` : OpenClaw 시스템/구조/컨텍스트 재로딩 기준 문서
- `invest/` : 알고리즘/데이터/전략/스크립트 본체
- `invest/stages/stage*/outputs/reports/` : 투자 단계/검증 리포트
- `memory/` : 일자 메모리 + 상태파일 (`memory/README.md` 기준)
- `MEMORY.md` : 장기 메모리
- `runtime/directives/directives.db` : 지시사항 SSOT (`scripts/directives/db.py`, `scripts/directives/gate.py`)
- `runtime/tasks/tasks.db` : 작업 티켓 SSOT (`scripts/tasks/db.py`, `scripts/tasks/gate.py`)
- `DIRECTIVES.md` / `TASKS.md` : usage index

## 2) 루트 운영 코어 파일(고정)
- `AGENTS.md`
- `MEMORY.md`
- `DIRECTIVES.md`
- `TASKS.md`
- `HEARTBEAT.md`
- `SOUL.md`
- `USER.md`
- `TOOLS.md`
- `IDENTITY.md`

별도 docs canonical:
- `docs/openclaw/BRAINS.md`
- `docs/openclaw/OPENCLAW_RULES.md`
- `docs/CONTRIBUTING.md`

## 3) docs/openclaw 배치 기준
- OpenClaw 시스템 운영/복구/컨텍스트 정책 문서만 유지
- 투자 도메인(전략/게이트/코드규칙/산출물 규칙)은 `invest/docs/`로 배치
- 중복 문서 발생 시 최신 canonical 1개만 유지하고 나머지는 archive 격리

## 4) invest 문서/산출물 기준
- 투자 구조 정책 canonical: `invest/docs/INVEST_STRUCTURE_POLICY.md`
- 진입점: `invest/docs/INVEST_STRUCTURE_POLICY.md`
- 투자 전략 하드룰: `invest/docs/RULEBOOK_MASTER.md`
- 투자 운영 SOP: `invest/docs/OPERATIONS_SOP.md`

## 5) Top-level operational
- `.venv/` : 루트 Python 가상환경
- `.openclaw_tmp/` : 임시 작업 디렉터리
- `.trash/` : 삭제 대기 항목
- `.pi/` : 예약 폴더
- `skills/` : 스킬 폴더
- `scripts/` : 루트 운영 크론/감사 스크립트

## 6) 문서 우선순위
1. `AGENTS.md` → 운영 게이트/완료 게이트
2. `DIRECTIVES.md` / `TASKS.md` → usage index (상태/전이는 DB+CLI SSOT)
3. `invest/docs/RULEBOOK_MASTER.md` → 알고리즘 하드룰
