# JB-20260313-DOCS-CANONICAL-LEAN-REFACTOR

- ticket: JB-20260313-DOCS-CANONICAL-LEAN-REFACTOR
- status: DONE
- checked_at: 2026-03-13 14:08 KST

## Goal
operations/invest 문서 체계를 인덱스 삭제/축소, canonical 단일화, volatile 내용 분리 원칙으로 재정리한다.

## Outcome summary
- `docs/operations/*/README.md` category index 문서를 제거하고 `docs/operations/OPERATIONS_BOOK.md`를 단일 operations index로 축소했다.
- `docs/invest/README.md`를 경량 entry doc로 정리했다.
- 결과 등급/승격/보관 경로 정책을 `docs/invest/RESULT_GOVERNANCE.md` 단일 SSOT로 고정하고 `OPERATIONS_SOP.md`에서는 중복 본문을 제거했다.
- `docs/invest/KPI_MASTER.md`를 threshold-only로 줄이고 변동성 높은 Stage6 현재값/UI 계약을 `docs/invest/stage6/STAGE6_KPI_RUNTIME_SPEC.md`로 분리했다.
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`는 contract/repro 중심으로 줄이고 구현 상세/current 값은 `docs/invest/stage2/STAGE2_IMPLEMENTATION_CURRENT_SPEC.md`로 분리했다.
- Stage1은 `STAGE1_RULEBOOK_AND_REPRO.md`=contract, `RUNBOOK.md`=operations로 역할을 분리하고 `stage1/README.md`를 맞춰 정리했다.
- 경로 드리프트 확인용 `scripts/check_docs_canonical_drift.py`를 추가했다.

## Proof
### Files deleted
- `docs/operations/README.md`
- `docs/operations/context/README.md`
- `docs/operations/governance/README.md`
- `docs/operations/runtime/README.md`
- `docs/operations/orchestration/README.md`
- `docs/operations/skills/README.md`

### Files created
- `docs/invest/stage2/STAGE2_IMPLEMENTATION_CURRENT_SPEC.md`
- `docs/invest/stage6/STAGE6_KPI_RUNTIME_SPEC.md`
- `scripts/check_docs_canonical_drift.py`

### Key files updated
- `docs/operations/OPERATIONS_BOOK.md`
- `docs/operations/context/CONTEXT_LOAD_POLICY.md`
- `docs/operations/runtime/MAIN_BRAIN_GUARD.md`
- `docs/operations/runtime/PROGRAMS.md`
- `docs/operations/orchestration/NONIDLE_ORCHESTRATION_GUIDE.md`
- `docs/operations/orchestration/diagrams/NONIDLE_ORCHESTRATION_FLOW.md`
- `docs/operations/skills/web-review.md`
- `docs/invest/README.md`
- `docs/invest/RESULT_GOVERNANCE.md`
- `docs/invest/OPERATIONS_SOP.md`
- `docs/invest/KPI_MASTER.md`
- `docs/invest/STAGE_EXECUTION_SPEC.md`
- `docs/invest/index.html`
- `docs/invest/stage1/README.md`
- `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage1/RUNBOOK.md`
- `docs/invest/stage2/README.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage6/README.md`

### Validation
- `python3 scripts/check_docs_canonical_drift.py`
  - result: `OK: docs canonical drift checks passed`

### Completion event attempt
- attempted: `openclaw system event --text "Done: docs canonical lean refactor applied" --mode now`
- result: failed in this session because local gateway returned `1006 abnormal closure`
