# OPENCLAW RULES

상위 인덱스: `docs/OPERATIONS_BOOK.md`

- 2뇌 구조: Brain 1 = GPT-5.4 (메인), Brain 2 = Local (보조/폴백/요약/수집/배치)
- Local Brain policy: 요약/압축/추출/폴백만 담당
- Local Brain I/O policy: 입력/출력은 English only 유지
- 금지: 최종 의사결정, 매매 추천, 전략 확정, 과도한 추론(thinking)
- Exception toggle: `OPENCLAW_LOCAL_SYSTEM_PROMPT=0`
- Optional display toggle: `OPENCLAW_LOCAL_TRANSLATE_KO=1`
- Context SSOT: `docs/openclaw/CONTEXT_MANIFEST.json`
- Tasks SSOT: `runtime/tasks/tasks.db` + `python3 scripts/tasks/db.py`
- Directives SSOT: `runtime/directives/directives.db` + `python3 scripts/directives/db.py`
