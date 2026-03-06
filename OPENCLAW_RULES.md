# OPENCLAW_RULES.md
- 2뇌 구조: Brain 1 = GPT-5.4 (메인), Brain 2 = Local (보조/폴백/요약/수집/배치)
- Context SSOT: `docs/openclaw/CONTEXT_MANIFEST.json`
- Tasks SSOT: `runtime/tasks/tasks.db` + `python3 scripts/taskdb.py`
- Directives SSOT: `runtime/directives/directives.db` + `python3 scripts/directivesdb.py`
- Hard rules: 추측 금지(`미확인`), 승인 게이트 준수, 시크릿 평문 금지, Git-only
- Memory 정책: `memory/YYYY-MM-DD.md`는 today only, `MEMORY.md`는 L2 + main 1:1 session only
