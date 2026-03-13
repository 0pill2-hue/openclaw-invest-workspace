# JB-20260310-RAW-DB-PIPELINE

- run_id: 20260310034225
- status: TODO
- updated_at: 2026-03-13 07:19 KST
- backlog_reconcile: prior DONE_CANDIDATE superseded; Stage2 handoff proof is stale against 2026-03-11 deep audit and broader directive scope remains open

## current understanding/scope
- 목표: Stage1 raw 파일 경로를 Stage2의 직접 입력 SSOT로 두지 않고, Stage1 DB archive를 기준으로 Stage2 refine/QC가 동작하도록 전환한다.
- 실무적 최소 이관안으로 구현했다.
  - Stage1 collector는 기존 raw tree를 그대로 쓴다. (행동 보존)
  - Stage1 종료 시 `stage01_sync_raw_to_db.py`가 Stage2 필요 아티팩트를 SQLite DB archive로 동기화한다.
  - Stage2 refine/QC는 DB archive를 stage-local runtime mirror로 materialize해서 기존 파일 기반 정제 로직을 그대로 재사용한다.
  - DB archive가 없으면 기존 `inputs/upstream_stage1/raw`로 fallback 한다.
- 비범위로 유지한 것
  - collector 내부 저장 로직의 전면 DB write 전환
  - trading/strategy/algorithm 변경
  - deploy/delete/external-send/live-trade

## minimal safe migration plan
1. Stage1 종료 시 raw→DB archive sync를 추가해 Stage2 입력 SSOT를 만든다.
2. Stage2는 DB snapshot mirror를 stable path(`.../upstream_stage1_db_mirror/current/raw`)로 사용해 incremental signature를 유지한다.
3. 기존 raw tree는 collector 호환 미러로만 남기고 Stage2 문서/계약은 DB archive 기준으로 바꾼다.
4. 후속 Phase에서 collector 직접 DB write로 넘어가면 raw tree 자체를 물리적으로 줄이거나 제거할 수 있다.

## files changed
- `invest/stages/common/stage_raw_db.py`
  - Stage1 raw archive SQLite schema / sync / Stage2 mirror materialization helper 추가
- `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
  - Stage1 raw→DB archive sync 엔트리포인트 추가
- `invest/stages/stage1/scripts/stage01_daily_update.py`
  - 각 profile 종료 후 DB sync가 실행되도록 orchestration 연결
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
  - Stage1 DB archive 기반 raw mirror 사용, input provenance 노출
- `invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`
  - Stage1 DB archive 기반 raw mirror 사용, input provenance 노출
- `docs/invest/stage1/README.md`
- `docs/invest/stage1/stage01_data_collection.md`
- `docs/invest/stage2/README.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`

## key implementation notes
- DB path: `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- runtime sync status: `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`
- Stage2 mirror root default: `invest/stages/stage2/outputs/runtime/upstream_stage1_db_mirror/current/raw`
- incremental 안전성
  - materialized file의 원본 `mtime_ns`를 유지
  - Stage2는 stable symlink path(`current/raw`)를 사용
  - 따라서 path churn 없이 기존 processed-index 시그니처를 최대한 보존
- sync 범위 최적화
  - Stage2 필요 prefix만 archive 대상으로 제한
  - Telegram attachment는 `meta.json`, `extracted.txt`, 그리고 `extracted.txt`가 없는 PDF만 포함
  - mp4/기타 대용량 attachment는 Stage2 범위 밖으로 제외

## verification commands + results
1. 문법 검증
   - command:
     - `python3 -m py_compile invest/stages/common/stage_raw_db.py invest/stages/stage1/scripts/stage01_sync_raw_to_db.py invest/stages/stage1/scripts/stage01_daily_update.py invest/stages/stage2/scripts/stage02_onepass_refine_full.py invest/stages/stage2/scripts/stage02_qc_cleaning_full.py`
   - result:
     - PASS (무출력 종료)

2. Stage1 raw→DB sync + Stage2 mirror smoke test (샘플 5개)
   - command:
     - 임시 raw tree에 샘플 5개(`signal/kr/ohlcv`, `qualitative/kr/dart`, `qualitative/market/rss`, `qualitative/text/telegram`, `qualitative/attachments/telegram/meta.json`)를 복사 후 `sync_raw_tree_to_db(...)`, `prepare_stage2_raw_input_root(...)` 실행
   - result:
     - PASS
     - `scanned_files=5`, `inserted_files=5`, `materialized_count=5`
     - materialized rel_path가 원본 logical path와 일치함 확인

3. Stage2 script import/runtime path smoke test
   - command:
     - 샘플 DB를 `STAGE1_RAW_DB_PATH`, `STAGE2_DB_MIRROR_ROOT`로 주입한 뒤
       `stage02_onepass_refine_full.py`, `stage02_qc_cleaning_full.py`를 import하여 `STAGE2_INPUT_SOURCE`, `RAW_BASE` 확인
   - result:
     - PASS
     - 두 스크립트 모두 `input_source=stage1_raw_db_mirror`
     - mirror raw base를 동일 stable path로 해석함 확인

4. live corpus 규모 확인
   - command:
     - raw corpus file/size 집계
   - result:
     - 전체 raw: `114356 files / 26.65 GB`
     - Stage2 archive 대상(필터 적용 후): `113650 files / 3.11 GB`

5. live corpus full sync 시도
   - command:
     - `python3 invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
   - result:
     - 120초 제한 내 완료 미확인 (tool timeout/SIGTERM)
     - 기능 오류로 단정할 수는 없고, 초기 대용량 archive 구축 시간 리스크로 기록

## remaining risks / follow-ups
- 초기 full archive 구축 시간
  - 현 raw corpus 기준 archive 대상이 약 3.11GB라 첫 sync가 오래 걸릴 수 있다.
  - launchd/운영 프로파일에서 최초 1회 warm-up 또는 장시간 실행 allowance가 필요할 수 있다.
- collector 직접 DB write는 아직 미구현
  - 현재는 raw tree → DB archive sync 방식이다.
  - 따라서 “raw 저장 완전 폐기”는 후속 phase에서 collector 저장부까지 바꿔야 한다.
- Stage1 gate/coverage는 아직 raw 기준 보조지표를 그대로 사용한다.
  - 본 티켓에서는 Stage2 input SSOT 전환을 우선 처리했다.
  - 후속으로 gate/coverage도 DB summary 기반으로 전환 가능.
- workspace에는 본 작업 이전부터 다른 수정 파일들이 존재한다.
  - 특히 일부 Stage1/Stage2 스크립트는 이미 dirty 상태였고, 본 작업은 DB archive 경로/문서 범위만 제한적으로 추가했다.

## 2026-03-13 backlog reconciliation
- prior `DONE_CANDIDATE` 판단은 최소 이관안 구현/초기 smoke 기준으로는 맞았지만, 이후 증빙이 추가되면서 현재 backlog SSOT와 충돌한다.
- `runtime/tasks/JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT.md` 기준으로 `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_stage2_handoff.md`의 page-count/page-row 계약은 stale이며, placeholder `pdf_pages` row 73건 divergence가 문서 정렬 없이 남아 있다.
- directive `JB-20260310-RAW-DB-PIPELINE`도 여전히 IN_PROGRESS이고, 현재 task DB는 `TODO/main_resume`이므로 본 티켓은 닫지 않고 contract/doc 정렬 후 재판정이 맞다.
- next action:
  1. `JB-20260311-STAGE-CONTRACT-ALIGN`에서 Stage1 deep audit 결과를 기준으로 handoff contract 문서와 운영 규칙을 다시 맞춘다.
  2. 그 다음 이 티켓을 `DONE`으로 닫을지, 문서 정렬 후속을 추가로 남길지 재판정한다.

## current closure judgment
- NOT_DONE
- 최신 backlog 기준 상태: `TODO / main_resume`
