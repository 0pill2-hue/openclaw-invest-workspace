# CONTEXT_LOAD_POLICY.md

Last updated: 2026-03-06 KST  
Purpose: 컨텍스트 절감 + 안전성 유지 로딩 정책

## Tier 정의
- L1 (Always): 짧고 안정적인 핵심
- L2 (On-demand): 작업 유형별 상세 문서

## 기본 원칙
- 문서 삭제보다 계층 로딩을 우선
- L1은 짧고 안정적으로 유지
- L2는 트리거 발생 시에만 로드
- 일자 메모리는 `memory/YYYY-MM-DD.md` **오늘 only**
- `MEMORY.md`는 **L2 + MAIN 1:1 세션에서만** 로드
- TASKS SSOT: `runtime/tasks/tasks.db` (`python3 scripts/taskdb.py`, 게이트: `python3 scripts/task_gate.py`)
- DIRECTIVES SSOT: `runtime/directives/directives.db` (`python3 scripts/directivesdb.py`, 게이트: `python3 scripts/directives_gate.py`)
- 고위험 작업(삭제/외부전송/전략변경) 직전 관련 원문 재확인

## On-demand 트리거
- 전략 변경/게이트 판단: RULEBOOK + stage 상세
- 코드 수정/리팩토링: AGENTS.md + `TASKS.md`/`DIRECTIVES.md`(usage index) + DB/CLI 기준으로 수행
- 보고/운영 이슈: OPERATING_GOVERNANCE + `scripts/directivesdb.py list` 기준 확인
- 시스템/구조 변경: OPENCLAW_SYSTEM_BASELINE + WORKSPACE_STRUCTURE
- 뇌 역할/폴백 기준 확인: BRAINS.md

## 운영 KPI (권장)
- 리셋 후 작업시작시간(TTR)
- 필수 규칙 누락률(MRR)
- 작업당 참조 문서수(DDR)
- 문서 충돌/중복 건수(CRR)
