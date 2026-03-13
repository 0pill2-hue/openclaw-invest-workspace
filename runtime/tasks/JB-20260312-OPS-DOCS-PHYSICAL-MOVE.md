# JB-20260312-OPS-DOCS-PHYSICAL-MOVE

- ticket: JB-20260312-OPS-DOCS-PHYSICAL-MOVE
- status: IN_PROGRESS
- title: operations 문서 실제 폴더 이동 및 링크 정합성 수정
- created_by: auto task event bridge
- created_at: 2026-03-12 23:11:53 KST

## Auto updates

### 2026-03-12 23:11:53 KST | documentation
- summary: operations docs physically moved into category folders and all remaining old-path references were reduced to zero in tracked docs/runtime/memory/scripts scope
- phase: main_review
- detail: moved context/governance/runtime/skills canonical files out of flat docs/operations root and kept only root indexes plus category folders
- detail: verified remaining old docs/operations flat-path references count = 0 in docs, AGENTS.md, TASKS.md, scripts, runtime/tasks, memory
- proof:
  - `docs/operations/context/CONTEXT_LOAD_POLICY.md`
  - `docs/operations/governance/DOCUMENT_STANDARD.md`
  - `docs/operations/runtime/PROGRAMS.md`
  - `docs/operations/skills/README.md`
  - `docs/index.html`
