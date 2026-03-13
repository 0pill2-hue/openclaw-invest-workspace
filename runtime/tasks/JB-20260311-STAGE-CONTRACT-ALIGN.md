# JB-20260311-STAGE-CONTRACT-ALIGN

## 2026-03-11 진행 로그 (남은 태스크 재개)

### what changed
1) `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- stale runtime/lock cleanup 경로 추가 (`_recover_stale_runtime_state`)
- 락 타임아웃 에러에 lock holder pid 정보 포함
- `--status-only` 실행 시 stale RUNNING/lock 잔재를 우선 정리 후 sync_meta 기반 상태로 복구

2) `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
- selected_articles summary 검증 함수를 강화해서 live jsonl 집합과 핵심 필드 불일치 시 mismatch로 판정
- news scope에 `selected_articles_summary_status`, `selected_articles_summary_issues` 추가
- summary가 stale/invalid면 `selected_articles_summary_file`를 비워 fail-close 유도

3) `invest/stages/stage1/scripts/selected_articles_live_summary.py`
- validator를 expected full-summary 비교 방식으로 강화 (file list뿐 아니라 counts/domains/kinds/date/latest_mtime 포함)

4) docs sync
- `docs/invest/stage1/stage01_data_collection.md`
  - selected_articles canonical/derived summary 계약 및 fail-close 규칙 반영
  - raw_db_sync status lifecycle/stale-cleanup 상태모드 반영
  - news_backfill/10y backfill이 generic selected_articles를 live dir에 직접 쓰지 않는다는 계약 추가

### validation
- `python3 -m py_compile invest/stages/stage1/scripts/stage01_sync_raw_to_db.py invest/stages/stage1/scripts/stage01_update_coverage_manifest.py invest/stages/stage1/scripts/selected_articles_live_summary.py`
  - 결과: PASS

- stale lock cleanup harness (temp runtime/db/raw)
  - `stage01_sync_raw_to_db.py --status-only` 실행으로 stale RUNNING/lock 정리 확인
  - 기대 검증:
    - status=`PASS`
    - status_mode=`status_only_from_sync_meta_after_stale_cleanup`
    - `stale_cleanup` 필드 존재
    - lock 파일 truncate(빈 문자열)
  - 결과: PASS

- selected_articles validator harness
  - 정상 summary는 issues=`[]`
  - stale 변조(`output_file` 오염) 시 `output_file_mismatch` 검출
  - 결과: PASS

### current state
- 티켓은 계속 IN_PROGRESS (남은 stage contract 정렬 작업 진행 중)
- raw_db_sync 실운영 장기 실행(pid 55700 → 이후 62492 교체)은 별도로 살아 있으므로, 본 턴 검증은 격리 harness 기반으로 수행함
- 14:45 KST 기준 메인은 DB writer와 안 부딪히는 contract/doc sync를 계속 진행 중이며, selected_articles live 갱신은 writer 종료 후 narrow rerun으로 이어갈 예정

### proof paths
- `invest/stages/stage1/scripts/stage01_sync_raw_to_db.py`
- `invest/stages/stage1/scripts/stage01_update_coverage_manifest.py`
- `invest/stages/stage1/scripts/selected_articles_live_summary.py`
- `docs/invest/stage1/stage01_data_collection.md`
- `runtime/tasks/JB-20260311-STAGE-CONTRACT-ALIGN.md`

## 2026-03-11 16:00 KST follow-up

### what changed
- `invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py`
  - live `selected_articles` 갱신은 기본적으로 **explicit `--input-index`가 있을 때만** 허용하도록 fail-close 계약을 추가했다.
  - `--allow-nonverifiable-live-write` / `NEWS_SELECTED_ALLOW_NONVERIFIABLE_LIVE_WRITE=1`가 없으면, generic collector의 auto-discover/merge-all 경로는 live write를 거부한다.
  - `NEWS_SELECTED_MERGE_ALL_INDEXES` 기본값을 `1 -> 0`으로 바꿔, 실수로 전체 url_index를 합쳐 live corpus를 다시 오염시키는 기본 동작을 제거했다.

### why
- 15:55 KST 시점 live `selected_articles_merged_summary.json` / `news_selected_articles_status.json`를 재확인한 결과, canonical summary 계약 자체는 정리됐지만 live corpus는 다시 mixed-source 상태였다.
- 실제 live 파일셋은 `selected_articles_20260311-025510.jsonl`, `selected_articles_20260311-055104.jsonl`가 추가되어 총 4개였고, source kind/domain에 `guardian_open_platform`, `rss`, `sitemap`, `sec.gov`, `theguardian.com` 등이 포함됐다.
- 이는 `selected_articles`를 verifiable lane(Naver-only 등)으로 분리하겠다는 주인님 지시와 문서 계약에 어긋난다. 따라서 현재 가장 작은 안전 수정은 **generic collector가 기본 live writer가 되지 못하게 막는 것**이다.

### validation
- `python3 -m py_compile invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py`
  - 결과: PASS

### current state
- active writer는 현재 `stage01_sync_raw_to_db.py` pid `68462`로 살아 있어, live selected_articles 정리/재실행은 writer 종료 후 bounded clean rerun으로 이어가야 한다.
- 따라서 `JB-20260311-STAGE-CONTRACT-ALIGN`는 재개하고, `JB-20260311-SELECTED-ARTICLES-ALT-PATH`는 **현재 live mixed-source contamination 정리 + clean rerun 대기**로 유지한다.

### added proof paths
- `invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py`
- `invest/stages/stage1/outputs/runtime/news_selected_articles_status.json`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_merged_summary.json`
- `invest/stages/stage1/outputs/runtime/raw_db_sync_status.json`

## 2026-03-13 backlog resume decision

### why this is the next startable P1
- `JB-20260311-WEB-REVIEW-STAGE12-IMPROVE`는 로컬 증빙 기준 close recommendation이 DONE이고 추가 적용사항이 미확인이라 선행 착수 대상으로 보기 어렵다.
- `JB-20260311-STAGE2-PDF-CONTRACT-ALIGN-FIX`는 recoverable web-review APPLY 증빙이 약하고, 현재 즉시 처리 가능한 concrete mismatch는 `JB-20260310-RAW-DB-PIPELINE_stage2_handoff.md` vs `JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT.md` 계약 불일치다.
- 따라서 실제 다음 착수 가능 P1은 `JB-20260311-STAGE-CONTRACT-ALIGN`이다.

### next action
1. `runtime/tasks/JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT.md`의 73건 placeholder-page divergence를 기준으로 `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_stage2_handoff.md`와 관련 Stage1/Stage2 contract docs를 최신 구현에 맞게 정렬한다.
2. 그 결과에 따라 `JB-20260310-RAW-DB-PIPELINE` closure judgment와 `JB-20260311-STAGE2-PDF-CONTRACT-ALIGN-FIX` 필요 여부를 재판정한다.

### refreshed proof paths
- `runtime/tasks/JB-20260311-STAGE-CONTRACT-ALIGN.md`
- `runtime/tasks/JB-20260311-STAGE1-RAW-DB-DEEP-AUDIT.md`
- `runtime/tasks/JB-20260310-RAW-DB-PIPELINE_stage2_handoff.md`
- `runtime/tasks/JB-20260310-RAW-DB-PIPELINE.md`
- `runtime/tasks/JB-20260311-WEB-REVIEW-STAGE12-IMPROVE.md`
