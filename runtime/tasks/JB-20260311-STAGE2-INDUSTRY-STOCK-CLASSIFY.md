# JB-20260311-STAGE2-INDUSTRY-STOCK-CLASSIFY

- directive_id: JB-20260311-STAGE2-INDUSTRY-STOCK-CLASSIFY
- status: IN_PROGRESS
- owner: main-orchestrator
- goal: Stage2에서 PDF/문서 내용을 산업과 종목 기준으로 분류하게 구현한다.
- rule: Stage1은 문서/페이지 분해만 담당, 의미 분류는 Stage2에서 수행.
- proof_log:
  - 2026-03-11 15:41 KST: 사용자 지시를 task/directive로 등록하고 구조 점검 착수.
  - 2026-03-11 15:43 KST: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`에 deterministic 산업/종목 분류를 추가. qualitative text clean 출력은 `*.classification.json` sidecar를 쓰고, selected_articles clean row에는 `stage2_classification` 필드를 넣도록 구현.
  - 2026-03-11 15:43 KST: `docs/invest/stage2/README.md`, `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`를 갱신해 Stage1=문서/페이지 split, Stage2=산업/종목 태깅 계약을 문서화.
  - 2026-03-11 15:44 KST: `python3 -m py_compile invest/stages/stage2/scripts/stage02_onepass_refine_full.py` 통과. 산업 분류는 master 업종표가 아니라 Stage2 keyword taxonomy 기반이며, 종목 분류는 `kr_stock_list.csv` name/code match 기반임을 명시.
