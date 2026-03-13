# JB-20260312-DOC-SLIM-AND-CLEANUP-PLAN

- ticket: JB-20260312-DOC-SLIM-AND-CLEANUP-PLAN
- status: IN_PROGRESS
- title: 운영 문서 슬림화 및 cleanup 후보 정리
- created_by: auto task event bridge
- created_at: 2026-03-12 23:34:26 KST

## Auto updates

### 2026-03-12 23:34:26 KST | documentation
- summary: Slimmed high-frequency docs and produced tmp/log/proof cleanup candidate report without deleting anything.
- phase: main_review
- detail: trimmed OPERATIONS_BOOK, CONTEXT_LOAD_POLICY, scripts/README, TASKS.md, MAIN_BRAIN_GUARD for lower context cost
- detail: identified runtime/tmp ~3.0G and runtime/tasks/proofs ~999M as main cleanup pressure; delete/archive remains approval-gated
- proof:
  - `docs/operations/OPERATIONS_BOOK.md`
  - `docs/operations/context/CONTEXT_LOAD_POLICY.md`
  - `scripts/README.md`
  - `TASKS.md`
  - `docs/operations/runtime/MAIN_BRAIN_GUARD.md`
  - `runtime/tasks/proofs/JB-20260312-DOC-SLIM-CLEANUP-CANDIDATES.md`
