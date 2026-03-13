# JB-20260313-TOKEN-STRUCTURE-SLIMMING-runtime

- ticket: JB-20260313-TOKEN-STRUCTURE-SLIMMING
- scope: runtime / ops slimming
- checked_at: 2026-03-13 KST

## landed
1. `.gitignore`를 hot/cold 분리 기준으로 재정렬했다.
   - `runtime/tmp/**`, `runtime/watch/**`, `runtime/watch/raw/**`, `runtime/tasks/proofs/**`, `runtime/tasks/evidence/raw-*.jsonl`를 generated/untracked로 고정했다.
   - 반대로 canonical hot evidence인 `runtime/tasks/evidence/cards/**`, `runtime/tasks/evidence/proof-index.jsonl`는 tracked 허용으로 되돌렸다.
   - `invest/stages/stage3/outputs` 아래 `actual/tmp/prompt/result/results/comparison/per-run-metrics` 계열 generated 패턴을 tracked 금지 방향으로 추가했다.
2. tracked Stage3 runtime policy helper를 새로 추가했다: `scripts/stage3/external_primary_runtime.py`.
   - mixed-item batch 기본 범위를 `20-40`, default target을 `30`으로 고정했다.
   - partition metadata(`partition_index`, `partition_count`, `partial_failure.failed_item_ids`, repartition flag) 생성 helper를 넣었다.
   - run metrics는 `wall_seconds`, `item_count`, `parse_integrity`, `completeness`, `cost_estimate(optional)`만 남기는 compact helper를 넣었다.
   - raw watcher save는 explicit debug opt-in일 때만 허용하는 helper를 넣었다.
3. `scripts/stage3/compact_runtime_outputs.py`를 추가했다.
   - run 종료 후 keep set을 `manifest/result/summary/card/proof-index`로 제한한다.
   - 나머지 intermediate(`prompt`, `results_template`, `comparison`, `metrics`, `stdout/stderr/log`, 기타 non-canonical files)는 archive 또는 delete 대상으로 분류한다.
   - dry-run / archive / delete / write-json CLI를 지원한다.
4. 실제 watcher 코드(`skills/web-review/scripts/watch_chatgpt_response.py`)에 raw capture 기본 OFF 정책을 반영했다.
   - 기본 동작은 기존과 동일하게 watcher JSON만 남긴다.
   - `--debug-save-raw`를 명시했을 때만 `runtime/watch/raw/`에 final assistant raw text를 cold save한다.
5. evidence/search/proof hardening을 docs + guard code로 강화했다.
   - `docs/operations/context/CONTEXT_LOAD_POLICY.md`, `docs/invest/OPERATIONS_SOP.md`, `docs/operations/skills/web-review.md`, `docs/operations/skills/web-review-templates.md`, `skills/web-review/SKILL.md`, `docs/invest/stage3/README.md`, `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`, `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`를 갱신했다.
   - hot layer 허용 경로를 `runtime/current-task.md`, `runtime/context-handoff.md`, `runtime/tasks/evidence/cards/*`, `runtime/tasks/evidence/proof-index.jsonl`로 명시했다.
   - `grep -R`로 raw/log/tmp를 뒤지지 말고 `python3 scripts/tasks/db.py evidence-search` canonical-only 기본을 쓰도록 정리했다.
   - 추가 guard로 `scripts/tasks/canonical_search_guard.py`를 넣어 recursive/raw search command를 거부하도록 했다.
6. closed-task proof는 기존 evidence-card 기반 구조를 유지하는 방향으로 문서 규칙을 재강조했다.
   - `proof` pointer는 canonical evidence card를 써야 한다는 점을 context/SOP 문서에 다시 고정했다.
   - one-task-one-final-card / proof-index(`canonical_summary=true`)를 hot layer 규칙과 묶어 재정렬했다.

## remaining
1. historical runtime runner(`runtime/tmp/stage3_external_chatgpt_batch_runner.py`)는 tracked source가 아니므로 이번 landed diff에 직접 연결하지 못했다.
   - 대신 tracked canonical helper(`scripts/stage3/external_primary_runtime.py`)와 compactor를 추가하고 관련 docs/skill을 그 경로 기준으로 재정렬했다.
   - 후속으로 실제 sender/batch runner를 tracked source로 승격하거나 helper import 경로로 통합하면 runtime policy enforcement가 더 강해진다.
2. 이미 dirty 상태인 Stage3 docs/README 계열 기존 수정분이 많아서, 이번 작업은 runtime/ops 규칙 추가분만 얹는 형태로 마무리했다. 별도 정리 티켓에서 doc drift sweep이 있으면 좋다.

## proof
- changed files:
  - `.gitignore`
  - `scripts/stage3/external_primary_runtime.py`
  - `scripts/stage3/compact_runtime_outputs.py`
  - `scripts/tasks/canonical_search_guard.py`
  - `skills/web-review/scripts/watch_chatgpt_response.py`
  - `skills/web-review/SKILL.md`
  - `docs/operations/context/CONTEXT_LOAD_POLICY.md`
  - `docs/invest/OPERATIONS_SOP.md`
  - `docs/operations/skills/web-review.md`
  - `docs/operations/skills/web-review-templates.md`
  - `docs/invest/stage3/README.md`
  - `docs/invest/stage3/STAGE3_EXTERNAL_PRIMARY_OPERATIONS.md`
  - `docs/invest/stage3/STAGE3_EXTERNAL_WEB_PACKAGE_SPEC.md`
- validation:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile scripts/stage3/external_primary_runtime.py scripts/stage3/compact_runtime_outputs.py skills/web-review/scripts/watch_chatgpt_response.py scripts/tasks/canonical_search_guard.py` → pass
  - partition helper sanity check: `41 -> [21,20]`, `61 -> [31,30]`, `100 -> [34,33,33]`
  - fixture dry-run: `python3 scripts/stage3/compact_runtime_outputs.py --dry-run <tmp-run-dir>` → keep=`batch_manifest.json,result.json,summary.json,card.json,proof-index.jsonl`, archive candidates=`prompt/full_prompt.txt,result/results_template.json`
  - guard dry-run: `python3 scripts/tasks/canonical_search_guard.py -- grep -R foo runtime/tmp` → `recursive_grep_forbidden`, `cold_raw_target_forbidden:runtime/tmp`
