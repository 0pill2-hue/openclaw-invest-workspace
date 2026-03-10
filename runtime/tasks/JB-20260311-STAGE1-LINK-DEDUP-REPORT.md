# JB-20260311-STAGE1-LINK-DEDUP-REPORT

- status: DONE
- completed_at: 2026-03-11 07:56 KST
- orchestrated_at: 2026-03-11 06:50 KST
- run_id: 20260311064927
- child_session: agent:main:subagent:f9e6f0ac-b733-4301-9b6c-752fd7c82cd8
- child_run_id: 8cda977e-99ad-4d59-bc3e-1be84c0870a7

## What
- Stage1 link sidecar collector ownership을 실제 raw output + raw DB archive까지 연결했다.
- Stage1 orchestrator(`stage01_daily_update.py`)에 `stage01_collect_link_sidecars.py` + `stage01_sync_raw_to_db.py`를 profile별로 연결했다.
- Stage2 refine(`stage02_onepass_refine_full.py`)가 Stage1 raw DB mirror를 우선 사용하고, sidecar canonical URL/blocks를 먼저 소비한 뒤에만 opt-in live fetch fallback을 쓰도록 바꿨다.
- `text/blog` ↔ `text/telegram` 교차 corpus dedup에 sidecar canonical URL 신호를 포함시켰고, bootstrap clean registry도 같은 규칙으로 맞췄다.
- Stage1/Stage2 문서를 raw DB + link sidecar + dedup 계약 기준으로 갱신했다.

## Why
- 외부 링크 fetch 책임을 Stage2 런타임에서 Stage1 sidecar/raw-db 경로로 옮겨야 Stage2가 deterministic DB snapshot만 읽도록 고정할 수 있다.
- 텔레그램/블로그 본문이 본문 길이보다 외부 링크 의존도가 높은 경우, clean 파일만으로는 교차 corpus dedup이 누락될 수 있어 sidecar canonical URL을 dedup SSOT에 포함해야 했다.
- 운영 기준으로는 DB row count / output count / mirror count가 모두 맞아야 handoff가 완료된 것으로 볼 수 있다.

## Verification
- `python3 -m py_compile invest/stages/common/stage_raw_db.py invest/stages/stage1/scripts/stage01_daily_update.py invest/stages/stage1/scripts/stage01_collect_link_sidecars.py invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- synthetic 검증 통과:
  - Stage2 `sanitize_text()`가 Stage1 sidecar block을 live fetch보다 먼저 소비
  - clean blog bootstrap + 신규 telegram candidate가 sidecar canonical URL로 duplicate 판정
- 실데이터 실행:
  - `python3 invest/stages/stage1/scripts/stage01_collect_link_sidecars.py`
  - `python3 invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
  - `prepare_stage2_raw_input_root(...)`로 Stage2 DB mirror materialize 확인

## Proof
- 증빙 JSON: `runtime/tasks/proofs/JB-20260311-STAGE1-LINK-DEDUP-REPORT.proof.json`
- 증빙 MD: `runtime/tasks/proofs/JB-20260311-STAGE1-LINK-DEDUP-REPORT.proof.md`
- 핵심 수치:
  - Stage1 sidecars written: 41,980
  - Stage1 sidecar blocks_written_files: 904
  - Stage1 canonical_urls_total: 291,843
  - raw DB sync id: `20260310T224733Z`
  - DB/archive/mirror 일치:
    - `qualitative/text/blog`: 40,939 / 40,939 / 40,939
    - `qualitative/text/telegram`: 73 / 73 / 73
    - `qualitative/link_enrichment/text/blog`: 40,939 / 40,939 / 40,939
    - `qualitative/link_enrichment/text/telegram`: 69 / 69 / 69
- Git scoped status / suggested commit도 동일 proof 파일에 정리했다.

## Scoped touched files
- `invest/stages/common/stage_raw_db.py`
- `invest/stages/stage1/scripts/stage01_daily_update.py`
- `invest/stages/stage1/scripts/stage01_collect_link_sidecars.py`
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- `docs/invest/stage1/README.md`
- `docs/invest/stage1/RUNBOOK.md`
- `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage1/stage01_data_collection.md`
- `docs/invest/stage2/README.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `runtime/tasks/JB-20260311-STAGE1-LINK-DEDUP-REPORT.md`
- `runtime/tasks/proofs/JB-20260311-STAGE1-LINK-DEDUP-REPORT.proof.json`
- `runtime/tasks/proofs/JB-20260311-STAGE1-LINK-DEDUP-REPORT.proof.md`

DONE
