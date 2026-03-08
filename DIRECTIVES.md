# DIRECTIVES.md

## 역할
- DIRECTIVES usage index
- 실제 SSOT는 문서가 아니라 DB/CLI이다.

## SSOT
- DB: `runtime/directives/directives.db`
- 등록/상태전이/조회: `python3 scripts/directives/db.py`

## 기본 명령
- 요약 확인:
  - `python3 scripts/directives/db.py summary --top 5 --recent 5`
  - 리셋/신규 세션 복구 시에는 위 summary 후 `python3 scripts/context_policy.py resume-check --strict`까지 확인
- 실행 전 게이트:
  - `python3 scripts/directives/gate.py --id <directive_id>`

## 기록 원장
- 기존 장문 원장: `runtime/directives/directives_archive.md`
