# JB-20260312-CLEANUP-DEAD-WRAPPERS-OBSOLETE

## what
- landed:
  - `invest/stages/stage1/scripts/scrape_all_posts.py` 삭제
  - `invest/stages/stage1/scripts/update_dashboard.py` 삭제
  - `invest/stages/stage5/scripts/stage5_hardening_3items.py` 삭제
  - `scripts/**/__pycache__`, `invest/stages/**/__pycache__` 전부 제거
- related docs alignment:
  - 추가 문서 수정은 하지 않음. 삭제 대상 3개는 canonical docs/운영 경로 참조가 없거나, 이미 `runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md`에서 삭제 후보로 분류되어 있어 문서 side effect가 없도록 최소 범위만 정리함.

## why
- `scrape_all_posts.py`
  - 파일 자체가 `stage01_scrape_all_posts_v2.main()`만 호출하는 2-line thin wrapper였다.
  - prior audit(`runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md`)가 legacy compat wrapper로 분류했고, AGENTS hard rule도 새/잔존 compat wrapper를 줄이라고 요구한다.
- `update_dashboard.py`
  - repo 내 참조가 없었다.
  - 코드가 현재 repo에 없는 `invest/web/index.html`를 하드코딩하고, repo 밖 auth profile 경로까지 직접 참조해 현행 구조 기준 obsolete helper였다.
- `stage5_hardening_3items.py`
  - Stage5 canonical run 문서(`docs/invest/stage5/README.md`)는 `stage05_feature_engineer.py`만 실행 진입점으로 둔다.
  - repo 내 경로 참조가 없고, 출력도 `STAGE5_HARDENING_3ITEMS_20260218.*` 고정 파일명으로 쓰는 one-off audit 성격이라 현재 운영 경로에서 dead script로 판단했다.
- `__pycache__`
  - `.gitignore`가 이미 `__pycache__/`, `*.pyc`를 무시한다.
  - 특히 `scripts/__pycache__/taskdb.cpython-314.pyc`, `directivesdb.cpython-314.pyc`, `task_gate.cpython-314.pyc` 등은 현재 flat source tree와 맞지 않는 legacy residue라 탐색 noise만 만든다.

## next
- remaining:
  - repo 밖 수동 alias/cron/launchd가 삭제된 3개 파일을 직접 호출하는지는 미확인. 발견 시 wrapper를 되살리지 말고 canonical entrypoint로 외부 호출 경로를 교체해야 한다.
  - 문서-코드 충돌 정리는 아직 남음. 우선순위는 prior audit가 적어둔 Stage1 selected_articles 문서 canonicalize, Stage2 Telegram PDF path 문서 canonicalize 순서가 맞다.

## proof
- source evidence:
  - `runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md`
  - `docs/invest/stage5/README.md`
  - 삭제 전 파일 관찰:
    - `invest/stages/stage1/scripts/scrape_all_posts.py` → thin wrapper only
    - `invest/stages/stage1/scripts/update_dashboard.py` → missing `invest/web/index.html` + external auth path hardcode
    - `invest/stages/stage5/scripts/stage5_hardening_3items.py` → dated one-off hardening report writer
- minimal verification:
  - target existence check: 세 파일 모두 `gone`
  - pycache existence check: tracked cleanup target set 기준 `remaining_count 0`
  - git status shows:
    - `D invest/stages/stage1/scripts/scrape_all_posts.py`
    - `D invest/stages/stage1/scripts/update_dashboard.py`
    - `D invest/stages/stage5/scripts/stage5_hardening_3items.py`
