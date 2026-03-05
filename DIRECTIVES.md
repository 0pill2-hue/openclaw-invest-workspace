# DIRECTIVES.md
SSOT는 `runtime/directives/directives.db` 입니다.
등록/상태전이/조회는 `python3 scripts/directivesdb.py`로만 수행합니다.
요약 확인: `python3 scripts/directivesdb.py summary --top 5 --recent 5`
작업 실행 전 `python3 scripts/directives_gate.py --id <DIRECTIVE_ID>`를 반드시 통과합니다.
기존 장문 원장은 `runtime/directives/directives_archive.md`를 사용합니다.
